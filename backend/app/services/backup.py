"""Consistent local backup and checked restore. Archives never contain environment secrets."""

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from app.core.config import Settings
from app.core.database import SCHEMA_REVISION
from app.core.version import APPLICATION_VERSION
from app.domain.fiscal.loader import available_vintages, load_vintage
from app.services.ledger import fail

MAX_ARCHIVE = 200 * 1024 * 1024
MAX_MEMBER = 100 * 1024 * 1024


def create_backup(settings: Settings) -> dict[str, str]:
    backups = settings.database_path.parent / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = settings.database_path.stat().st_mtime_ns
    filename = f"sololmnp-{stamp}.zip"
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


def restore_backup(settings: Settings, filename: str, destination: Path) -> dict[str, str]:
    archive_path = _archive_path(settings, filename)
    _validate_archive(archive_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive, tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / "database.sqlite3"
        archive.extract("database.sqlite3", folder)
        _check_database(database)
        os.replace(database, destination)
    return {
        "restored_to": destination.name,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def _archive_path(settings: Settings, filename: str) -> Path:
    if filename != Path(filename).name or ".." in filename or filename.startswith("."):
        fail("BACKUP_PATH", "Nom d’archive refusé.", 422)
    path = (settings.database_path.parent / "backups" / filename).resolve()
    root = (settings.database_path.parent / "backups").resolve()
    if path.parent != root or not path.is_file():
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
        listed = {item["name"]: item for item in manifest["files"]}
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
            if record is None or record["sha256"] != digest or record["size"] != len(content):
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
