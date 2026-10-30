"""Consistent local backup and checked restore. Archives never contain environment secrets.

Restore replaces the live database only after a new pre-restore backup. It does
not update validated entries in place: the whole file is swapped for the
archive contents.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import Settings
from app.core.database import SCHEMA_REVISION, Database
from app.core.version import APPLICATION_VERSION
from app.domain.filing.backup_catalog import (
    backup_timestamp,
    backup_view,
    fingerprint,
    integrity_view,
    population,
)
from app.domain.fiscal.loader import available_vintages, load_vintage
from app.models.base import utc_now
from app.services.ledger import fail

MAX_ARCHIVE = 200 * 1024 * 1024
MAX_MEMBER = 100 * 1024 * 1024
_CHECKS = "integrity.json"


def create_backup(settings: Settings) -> dict[str, str]:
    backups = settings.database_path.parent / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    filename = _fresh_name(backups)
    destination = backups / filename
    temporary = destination.with_suffix(".zip.partial")
    handle, temporary_name = tempfile.mkstemp(suffix=".sqlite3")
    os.close(handle)
    database_copy = Path(temporary_name)
    try:
        _copy_database(settings.database_path, database_copy)
        manifest_files = [_file_record(database_copy, "database.sqlite3")]
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(database_copy, "database.sqlite3")
            documents = settings.documents_dir
            if documents.is_dir():
                for path in sorted(documents.iterdir()):
                    if path.is_file() and not path.is_symlink():
                        name = f"documents/{path.name}"
                        archive.write(path, name)
                        manifest_files.append(_file_record(path, name))
            manifest = {
                "created_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "application_version": APPLICATION_VERSION,
                "schema_revision": SCHEMA_REVISION,
                "fiscal_vintages": [
                    {"vintage": vintage, "rules_sha256": load_vintage(vintage)["sha256"]}
                    for vintage in available_vintages()
                ],
                "files": manifest_files,
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, sort_keys=True, ensure_ascii=False),
            )
        os.replace(temporary, destination)
    finally:
        database_copy.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
    return {
        "filename": destination.name,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def list_backups(settings: Settings) -> dict[str, Any]:
    root = _backup_root(settings)
    if not root.is_dir():
        return {"backups": []}
    checks = _read_checks(root)
    rows: list[dict[str, Any]] = []
    paths = [
        path for path in root.glob("sololmnp-*.zip") if path.is_file() and not path.is_symlink()
    ]
    for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
        rows.append(_describe(path, checks.get(path.name)))
    return {"backups": rows}


def verify_backup(settings: Settings, filename: str) -> dict[str, Any]:
    path = _archive_path(settings, filename)
    try:
        _validate_archive(path)
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "database.sqlite3"
            with zipfile.ZipFile(path) as archive:
                archive.extract("database.sqlite3", folder)
            _check_database(database)
    except HTTPException as exc:
        _record_check(path, ok=False, message=_error_message(exc))
        raise
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError, ValueError):
        _record_check(path, ok=False, message="Archive illisible.")
        fail("BACKUP_REJECTED", "Archive illisible.", 422)
    _record_check(path, ok=True, message="Contrôle d’intégrité réussi.")
    return _describe(path, _read_checks(path.parent).get(path.name))


def preview_restore(settings: Settings, filename: str) -> dict[str, Any]:
    path = _archive_path(settings, filename)
    manifest, backup_counts = _inspect(path)
    return {
        "filename": path.name,
        "backup_date": backup_timestamp(path, manifest),
        "current": _live_population(settings),
        "backup": backup_counts,
    }


def restore_backup(
    settings: Settings, database: Database, filename: str, confirmation: str
) -> dict[str, Any]:
    if confirmation != "RESTAURER":
        fail(
            "RESTORE_CONFIRMATION",
            "Confirmez la restauration en saisissant RESTAURER.",
            422,
            field="confirmation",
        )
    path = _archive_path(settings, filename)
    manifest, backup_counts = _inspect(path)
    safety = create_backup(settings)
    documents = _archive_documents(path)
    try:
        _replace_live_database(settings, database, path)
        _replace_documents(settings.documents_dir, documents)
    except Exception:
        safety_path = _backup_root(settings) / safety["filename"]
        try:
            _replace_live_database(settings, database, safety_path)
        except Exception:
            database.reopen()
        raise
    return {
        "restored_from": path.name,
        "pre_restore_backup": safety["filename"],
        "backup_date": backup_timestamp(path, manifest),
        "entries": backup_counts["entries"],
        "years": backup_counts["years"],
    }


def _fresh_name(backups: Path) -> str:
    filename = f"sololmnp-{time.time_ns()}.zip"
    while (backups / filename).exists():
        filename = f"sololmnp-{time.time_ns()}.zip"
    return filename


def _backup_root(settings: Settings) -> Path:
    return settings.database_path.parent / "backups"


def _describe(path: Path, stored: dict[str, Any] | None) -> dict[str, Any]:
    digest = fingerprint(path)
    manifest = _manifest_or_none(path)
    version = _text(manifest, "application_version")
    revision = _text(manifest, "schema_revision")
    return backup_view(
        filename=path.name,
        created_at=backup_timestamp(path, manifest),
        size=path.stat().st_size,
        application_version=version,
        schema_revision=revision,
        sha256=digest,
        integrity=integrity_view(stored, digest),
    )


def _manifest_or_none(path: Path) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(path) as archive:
            if "manifest.json" not in archive.namelist():
                return None
            loaded = json.loads(archive.read("manifest.json"))
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _text(manifest: dict[str, Any] | None, key: str) -> str | None:
    if manifest is None:
        return None
    value = manifest.get(key)
    return value if isinstance(value, str) and value else None


def _inspect(path: Path) -> tuple[dict[str, Any], dict[str, int]]:
    _validate_archive(path)
    with tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / "database.sqlite3"
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            archive.extract("database.sqlite3", folder)
        _check_database(database)
        try:
            counts = population(database)
        except ValueError:
            fail("BACKUP_REJECTED", "Base restaurée illisible.", 422)
    if not isinstance(manifest, dict):
        fail("BACKUP_REJECTED", "Manifeste d’archive illisible.", 422)
    return manifest, counts


def _live_population(settings: Settings) -> dict[str, int]:
    try:
        return population(settings.database_path)
    except ValueError:
        fail("BACKUP_REJECTED", "La base en service est illisible.", 422)


def _archive_path(settings: Settings, filename: str) -> Path:
    if filename != Path(filename).name or ".." in filename or filename.startswith("."):
        fail("BACKUP_PATH", "Nom d’archive refusé.", 422)
    path = (_backup_root(settings) / filename).resolve()
    root = _backup_root(settings).resolve()
    if path.parent != root or not path.is_file() or path.is_symlink():
        fail("BACKUP_NOT_FOUND", "Archive introuvable.", 404)
    return path


def _copy_database(source: Path, target: Path) -> None:
    origin = sqlite3.connect(source)
    copy = sqlite3.connect(target)
    try:
        origin.backup(copy)
    finally:
        copy.close()
        origin.close()


def _replace_live_database(settings: Settings, database: Database, archive_path: Path) -> None:
    destination = settings.database_path
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        extracted = Path(folder) / "database.sqlite3"
        with zipfile.ZipFile(archive_path) as archive:
            archive.extract("database.sqlite3", folder)
        _check_database(extracted)
        incoming = destination.with_name(f"{destination.name}.incoming")
        try:
            _copy_database(extracted, incoming)
            _quiesce(destination)
            database.engine.dispose()
            for suffix in ("-wal", "-shm"):
                Path(f"{destination}{suffix}").unlink(missing_ok=True)
            os.replace(incoming, destination)
        finally:
            incoming.unlink(missing_ok=True)
        database.reopen()


def _quiesce(path: Path) -> None:
    if not path.exists():
        return
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()


def _archive_documents(path: Path) -> list[tuple[str, bytes]]:
    documents: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            member = info.filename
            if not member.startswith("documents/") or member.endswith("/"):
                continue
            name = member.removeprefix("documents/")
            if not _single_segment(name):
                fail("BACKUP_REJECTED", "Chemin de document refusé.", 422)
            documents.append((name, archive.read(info)))
    return documents


def _replace_documents(root: Path, files: list[tuple[str, bytes]]) -> None:
    staging = root.parent / f".documents-restore-{uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        for name, content in files:
            if not _single_segment(name):
                fail("BACKUP_REJECTED", "Chemin de document refusé.", 422)
            (staging / name).write_bytes(content)
        if root.exists():
            previous = root.parent / f".documents-previous-{uuid4().hex}"
            os.replace(root, previous)
            try:
                os.replace(staging, root)
            except OSError:
                os.replace(previous, root)
                raise
            shutil.rmtree(previous, ignore_errors=True)
        else:
            os.replace(staging, root)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _single_segment(name: str) -> bool:
    return bool(name) and name == Path(name).name and ".." not in name and not name.startswith(".")


def _file_record(path: Path, name: str) -> dict[str, object]:
    content = path.read_bytes()
    return {"name": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _validate_archive(path: Path) -> None:
    if path.stat().st_size > MAX_ARCHIVE or path.is_symlink():
        fail("BACKUP_REJECTED", "Archive trop volumineuse ou lien refusé.", 422)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or "manifest.json" not in names:
            fail("BACKUP_REJECTED", "Manifeste manquant ou membre dupliqué.", 422)
        if "database.sqlite3" not in names:
            fail("BACKUP_REJECTED", "Base absente de l’archive.", 422)
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
            fail("BACKUP_REJECTED", "Manifeste d’archive illisible.", 422)
        listed = {
            item["name"]: item
            for item in manifest["files"]
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        for info in archive.infolist():
            member = info.filename
            if member.endswith("/") or member.startswith("/") or ".." in member.split("/"):
                fail("BACKUP_REJECTED", "Chemin d’archive refusé.", 422)
            if info.file_size > MAX_MEMBER:
                fail("BACKUP_REJECTED", "Membre d’archive trop volumineux.", 422)
            if member == "manifest.json":
                continue
            record = listed.get(member)
            content = archive.read(member)
            digest = hashlib.sha256(content).hexdigest()
            if (
                not isinstance(record, dict)
                or record.get("sha256") != digest
                or record.get("size") != len(content)
            ):
                fail("BACKUP_REJECTED", "Empreinte d’archive invalide.", 422)


def _check_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.Error:
        fail("BACKUP_REJECTED", "Base restaurée illisible.", 422)
    finally:
        connection.close()
    if (
        integrity is None
        or integrity[0] != "ok"
        or revision is None
        or revision[0] != SCHEMA_REVISION
    ):
        fail("BACKUP_REJECTED", "La base restaurée ne correspond pas au schéma attendu.", 422)


def _checks_path(root: Path) -> Path:
    return root / _CHECKS


def _read_checks(root: Path) -> dict[str, Any]:
    path = _checks_path(root)
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _record_check(path: Path, *, ok: bool, message: str) -> None:
    root = path.parent
    checks = _read_checks(root)
    checks[path.name] = {
        "sha256": fingerprint(path),
        "checked_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": ok,
        "message": message,
    }
    destination = _checks_path(root)
    temporary = destination.with_suffix(".json.partial")
    temporary.write_text(json.dumps(checks, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, destination)


def _error_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return str(detail["message"])
    return "Contrôle d’intégrité refusé."
