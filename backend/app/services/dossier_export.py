"""Dossier export and reimport for SQLite and Postgres.

The zip is the rows (``data.json``) plus the justificatifs registered in
``supporting_document``. It is not a raw database file. Validated entries are
not edited one by one: user triggers are suspended for the replacement, then
turned back on before commit, as in the SQLite file swap and the Postgres copy.
A failed install puts the previous rows and files back.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import stat
import time
import zipfile
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.sql.schema import Table

from app.core.config import Settings
from app.core.database import SCHEMA_REVISION, Database
from app.core.version import APPLICATION_VERSION
from app.domain.documents.files import matches_signature
from app.domain.documents.keys import document_key, export_key, safe_segment
from app.domain.filing.backup_catalog import backup_view, integrity_view
from app.domain.filing.dossier_archive import (
    DATA_NAME,
    KIND,
    MANIFEST_NAME,
    DossierPayloadError,
    UnsafeDossierPath,
    classify_dossier_member,
    decode_value,
    document_filename,
    encode_value,
    population,
)
from app.domain.fiscal.loader import available_vintages, load_vintage
from app.models import Base
from app.models.account import DossierArchive
from app.models.base import utc_now
from app.services.ledger import fail
from app.services.object_store import ObjectMissing, ObjectStore, ObjectStoreError, open_store

MAX_ARCHIVE = 200 * 1024 * 1024
MAX_MEMBER = 100 * 1024 * 1024
_NAME = re.compile(r"^dossier-[0-9]{1,20}\.zip$")
_SKIP_WRITE = frozenset({"app_account", "dossier_archive"})
_SHARED = frozenset({"account", "accounting_journal"})
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CHECKS = "integrity.json"
_WRITE_LOCK = 119_001
logger = logging.getLogger(__name__)

Payload = dict[str, list[dict[str, object]]]
Files = dict[str, tuple[bytes, str]]


def create_dossier_export(settings: Settings, database: Database, owner_id: int) -> dict[str, str]:
    store = open_store(settings)
    with database.engine.connect() as connection:
        payload = _read_payload(connection, owner_id)
    documents = _documents_for_payload(store, payload)
    raw = _build_zip(payload, documents)
    _validate_zip(raw)
    filename = _fresh_name(store)
    store.put(export_key(filename), raw, "application/zip")
    _remember_archive(database, owner_id, filename)
    return {"filename": filename, "sha256": hashlib.sha256(raw).hexdigest()}


def list_dossier_exports(settings: Settings, database: Database, owner_id: int) -> dict[str, Any]:
    store = open_store(settings)
    checks = _read_checks(store, owner_id)
    rows: list[dict[str, Any]] = []
    for name in _owned_names(database, owner_id):
        try:
            raw = store.get(export_key(name))
        except ObjectMissing:
            continue
        rows.append(_describe(name, raw, checks.get(name)))
    return {"backups": rows}


def verify_dossier_export(
    settings: Settings, database: Database, filename: str, owner_id: int
) -> dict[str, Any]:
    store = open_store(settings)
    path_name = _require_owned_name(database, owner_id, filename)
    try:
        raw = store.get(export_key(path_name))
    except ObjectMissing:
        fail("DOSSIER_NOT_FOUND", "Archive de dossier introuvable.", 404)
    try:
        _validate_zip(raw)
    except HTTPException as exc:
        _record_check(store, owner_id, path_name, raw, ok=False, message=_error_message(exc))
        raise
    _record_check(store, owner_id, path_name, raw, ok=True, message="Contrôle d’intégrité réussi.")
    return _describe(path_name, raw, _read_checks(store, owner_id).get(path_name))


def preview_dossier_export(
    settings: Settings, database: Database, filename: str, owner_id: int
) -> dict[str, Any]:
    manifest, payload, _documents = _load_checked(settings, database, filename, owner_id)
    return {
        "filename": filename,
        "backup_date": _created_at(manifest),
        "current": _live_population(database, owner_id),
        "backup": {
            "entries": population(payload)["entries"],
            "years": population(payload)["years"],
        },
    }


def restore_dossier(
    settings: Settings,
    database: Database,
    filename: str,
    confirmation: str,
    owner_id: int,
) -> dict[str, Any]:
    if confirmation != "RESTAURER":
        fail(
            "RESTORE_CONFIRMATION",
            "Confirmez la restauration en saisissant RESTAURER.",
            422,
            field="confirmation",
        )
    manifest, payload, documents = _load_checked(settings, database, filename, owner_id)
    store = open_store(settings)
    safety = create_dossier_export(settings, database, owner_id)
    with database.engine.connect() as connection:
        snapshot = _read_payload(connection, owner_id)
    protected = _other_document_names(database, owner_id)
    replaced = False
    try:
        replace_rows(database, payload, owner_id)
        replaced = True
        sync_documents(store, documents, protected)
    except Exception as original:
        if not replaced:
            raise
        try:
            replace_rows(database, snapshot, owner_id)
        except Exception as rollback_error:
            logger.exception(
                "Échec du retour arrière de la restauration. L’archive préalable est %s.",
                safety["filename"],
            )
            raise rollback_error from original
        raise
    counts = population(payload)
    return {
        "restored_from": filename,
        "pre_restore_backup": safety["filename"],
        "backup_date": _created_at(manifest),
        "entries": counts["entries"],
        "years": counts["years"],
    }


def replace_rows(database: Database, payload: Payload, owner_id: int) -> None:
    """Replace one account's rows. Triggers are off only inside this transaction."""
    tables = list(Base.metadata.sorted_tables)
    _require_tables(payload, tables)
    _force_owner(payload, owner_id)
    with database.engine.connect().execution_options(sqlite_write=True) as connection:
        with connection.begin():
            if connection.dialect.name == "postgresql":
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"),
                    {"key": _WRITE_LOCK},
                )
            _suspend(connection, tables)
            _clear_self_references(connection, tables, owner_id)
            for table in reversed(tables):
                if "owner_id" not in table.c or table.name in _SKIP_WRITE:
                    continue
                connection.execute(table.delete().where(table.c.owner_id == owner_id))
            _insert_payload(connection, tables, payload, owner_id)
            if connection.dialect.name == "postgresql":
                _reset_identities(connection, tables)
            _resume(connection)


def sync_documents(store: ObjectStore, files: Files, managed: set[str] | None = None) -> None:
    """Install ``files``. ``managed`` names belong to other accounts and stay."""
    before = _snapshot_documents(store)
    try:
        _apply_documents(store, files, managed)
    except Exception as original:
        try:
            _apply_documents(store, before, None)
        except Exception as rollback_error:
            logger.exception("Échec du retour arrière des justificatifs.")
            raise rollback_error from original
        raise


def _read_payload(connection: Connection, owner_id: int) -> Payload:
    payload: Payload = {}
    for table in Base.metadata.sorted_tables:
        statement = table.select()
        if table.name == "app_account":
            statement = statement.where(table.c.id == owner_id)
        elif "owner_id" in table.c:
            statement = statement.where(table.c.owner_id == owner_id)
        rows: list[dict[str, object]] = []
        for mapping in connection.execute(statement).mappings():
            try:
                encoded = {
                    column.name: encode_value(column, mapping[column.name])
                    for column in table.columns
                }
                rows.append(encoded)
            except DossierPayloadError:
                raise
        primary = [column.name for column in table.primary_key.columns]
        rows.sort(key=lambda row: tuple(_sort_token(row[name]) for name in primary))
        payload[table.name] = rows
    return payload


def _sort_token(value: object) -> tuple[int, str]:
    if type(value) is int:
        return (0, f"{value:030d}")
    return (1, str(value))


def _documents_for_payload(store: ObjectStore, payload: Payload) -> Files:
    files: Files = {}
    for row in payload["supporting_document"]:
        name = row.get("stored_name")
        media = row.get("media_type")
        digest = row.get("sha256")
        size = row.get("size")
        if not isinstance(name, str) or not safe_segment(name):
            fail("DOSSIER_REJECTED", "Nom de justificatif refusé.", 422)
        if not isinstance(media, str) or not isinstance(digest, str) or type(size) is not int:
            fail("DOSSIER_REJECTED", "Justificatif illisible.", 422)
        try:
            content = store.get(document_key(name))
        except ObjectMissing:
            fail("DOSSIER_REJECTED", "Un justificatif enregistré est absent du stockage.", 409)
        except ObjectStoreError as exc:
            fail("DOCUMENT_STORE", str(exc), 502)
        if hashlib.sha256(content).hexdigest() != digest or len(content) != size:
            fail(
                "DOSSIER_REJECTED",
                "Un justificatif ne correspond plus à son empreinte.",
                409,
            )
        if not matches_signature(media, content):
            fail("DOSSIER_REJECTED", "La signature d’un justificatif est refusée.", 422)
        files[name] = (content, media)
    return files


def _build_zip(payload: Payload, documents: Files) -> bytes:
    data = json.dumps(
        {"tables": payload},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    records = [_file_record(DATA_NAME, data)]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(DATA_NAME, data)
        for name in sorted(documents):
            content, _media = documents[name]
            member = f"documents/{name}"
            archive.writestr(member, content)
            records.append(_file_record(member, content))
        manifest = {
            "kind": KIND,
            "created_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "application_version": APPLICATION_VERSION,
            "schema_revision": SCHEMA_REVISION,
            "counts": population(payload),
            "fiscal_vintages": [
                {"vintage": vintage, "rules_sha256": load_vintage(vintage)["sha256"]}
                for vintage in available_vintages()
            ],
            "files": records,
        }
        archive.writestr(
            MANIFEST_NAME,
            json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode(),
        )
    raw = buffer.getvalue()
    if len(raw) > MAX_ARCHIVE:
        fail("DOSSIER_REJECTED", "Archive trop volumineuse.", 422)
    return raw


def _validate_zip(raw: bytes) -> tuple[dict[str, Any], Payload, Files]:
    if len(raw) > MAX_ARCHIVE:
        fail("DOSSIER_REJECTED", "Archive trop volumineuse.", 422)
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        fail("DOSSIER_REJECTED", "Archive illisible.", 422)
    with archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or MANIFEST_NAME not in names or DATA_NAME not in names:
            fail("DOSSIER_REJECTED", "Manifeste manquant ou membre dupliqué.", 422)
        try:
            manifest = json.loads(archive.read(MANIFEST_NAME))
        except (json.JSONDecodeError, zipfile.BadZipFile):
            fail("DOSSIER_REJECTED", "Manifeste d’archive illisible.", 422)
        if (
            not isinstance(manifest, dict)
            or manifest.get("kind") != KIND
            or not isinstance(manifest.get("files"), list)
            or manifest.get("schema_revision") != SCHEMA_REVISION
        ):
            fail("DOSSIER_REJECTED", "La révision de schéma de l’archive est refusée.", 422)
        listed = {
            item["name"]: item
            for item in manifest["files"]
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        total = 0
        documents: Files = {}
        for info in archive.infolist():
            member = info.filename
            if _unsafe_member(member) or _is_symlink(info):
                fail("DOSSIER_REJECTED", "Chemin d’archive refusé.", 422)
            try:
                kind = classify_dossier_member(member)
            except UnsafeDossierPath:
                fail("DOSSIER_REJECTED", "Chemin de document refusé.", 422)
            if info.file_size > MAX_MEMBER:
                fail("DOSSIER_REJECTED", "Membre d’archive trop volumineux.", 422)
            total += info.file_size
            if total > MAX_ARCHIVE:
                fail("DOSSIER_REJECTED", "Archive trop volumineuse.", 422)
            if kind == "manifest":
                continue
            content = archive.read(info)
            digest = hashlib.sha256(content).hexdigest()
            record = listed.get(member)
            if (
                not isinstance(record, dict)
                or record.get("sha256") != digest
                or record.get("size") != len(content)
            ):
                fail("DOSSIER_REJECTED", "Empreinte d’archive invalide.", 422)
            if kind == "document":
                documents[document_filename(member)] = (content, "application/octet-stream")
        if set(listed) != {name for name in names if name != MANIFEST_NAME}:
            fail("DOSSIER_REJECTED", "Le manifeste ne correspond pas aux membres.", 422)
        try:
            loaded = json.loads(archive.read(DATA_NAME))
        except json.JSONDecodeError:
            fail("DOSSIER_REJECTED", "Données d’archive illisibles.", 422)
    if not isinstance(loaded, dict) or not isinstance(loaded.get("tables"), dict):
        fail("DOSSIER_REJECTED", "Données d’archive illisibles.", 422)
    raw_tables = loaded["tables"]
    expected = {table.name for table in Base.metadata.sorted_tables}
    if set(raw_tables) != expected:
        fail("DOSSIER_REJECTED", "Les tables de l’archive ne correspondent pas au schéma.", 422)
    payload: Payload = {}
    for table in Base.metadata.sorted_tables:
        rows = raw_tables[table.name]
        if not isinstance(rows, list):
            fail("DOSSIER_REJECTED", "Les tables de l’archive ne correspondent pas au schéma.", 422)
        columns = {column.name for column in table.columns}
        normalized: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != columns:
                fail("DOSSIER_REJECTED", "Une ligne de l’archive est illisible.", 422)
            try:
                decode_row = {
                    column.name: decode_value(column, row[column.name]) for column in table.columns
                }
            except DossierPayloadError:
                fail("DOSSIER_REJECTED", "Une ligne de l’archive est illisible.", 422)
            del decode_row
            normalized.append(row)
        payload[table.name] = normalized
    _bind_documents(payload, documents)
    counts = manifest.get("counts")
    if counts != population(payload):
        fail("DOSSIER_REJECTED", "Les compteurs de l’archive sont faux.", 422)
    return manifest, payload, documents


def _bind_documents(payload: Payload, documents: Files) -> None:
    seen: dict[str, dict[str, object]] = {}
    for row in payload["supporting_document"]:
        name = row.get("stored_name")
        if not isinstance(name, str) or not safe_segment(name) or name in seen:
            fail("DOSSIER_REJECTED", "Nom de justificatif refusé.", 422)
        seen[name] = row
    if set(seen) != set(documents):
        fail("DOSSIER_REJECTED", "Les justificatifs ne correspondent pas à la base.", 422)
    bound: Files = {}
    for name, row in seen.items():
        content, _media = documents[name]
        media = row.get("media_type")
        digest = row.get("sha256")
        size = row.get("size")
        if (
            not isinstance(media, str)
            or digest != hashlib.sha256(content).hexdigest()
            or size != len(content)
            or not matches_signature(media, content)
        ):
            fail("DOSSIER_REJECTED", "Un justificatif ne correspond plus à son empreinte.", 422)
        bound[name] = (content, media)
    documents.clear()
    documents.update(bound)


def _require_tables(payload: Payload, tables: list[Table]) -> None:
    expected = {table.name for table in tables}
    if set(payload) != expected:
        fail("DOSSIER_REJECTED", "Les tables de l’archive ne correspondent pas au schéma.", 422)


def _force_owner(payload: Payload, owner_id: int) -> None:
    for table in Base.metadata.sorted_tables:
        if "owner_id" not in table.c or table.name in _SKIP_WRITE:
            continue
        for row in payload[table.name]:
            row["owner_id"] = owner_id


def _other_document_names(database: Database, owner_id: int) -> set[str]:
    """Files that belong to someone else and must survive this restore."""
    table = Base.metadata.tables["supporting_document"]
    with database.engine.connect() as connection:
        rows = connection.execute(select(table.c.stored_name).where(table.c.owner_id != owner_id))
    return {str(name) for (name,) in rows if isinstance(name, str)}


def _insert_payload(
    connection: Connection, tables: list[Table], payload: Payload, owner_id: int
) -> None:
    del owner_id
    pending: list[tuple[Table, list[dict[str, object]]]] = []
    for table in tables:
        if table.name in _SKIP_WRITE:
            continue
        if table.name in _SHARED:
            _insert_missing(connection, table, payload[table.name])
            continue
        self_refs = _self_fk_names(table)
        decoded_rows: list[dict[str, object]] = []
        updates: list[dict[str, object]] = []
        columns = {column.name for column in table.columns}
        for raw in payload[table.name]:
            if set(raw) != columns:
                fail("DOSSIER_REJECTED", "Une ligne de l’archive est illisible.", 422)
            try:
                decoded = {
                    column.name: decode_value(column, raw[column.name]) for column in table.columns
                }
            except DossierPayloadError:
                fail("DOSSIER_REJECTED", "Une ligne de l’archive est illisible.", 422)
            if any(decoded[name] is not None for name in self_refs):
                update_row = {
                    column.name: decoded[column.name] for column in table.primary_key.columns
                }
                for name in self_refs:
                    update_row[name] = decoded[name]
                    decoded[name] = None
                updates.append(update_row)
            decoded_rows.append(decoded)
        if decoded_rows:
            connection.execute(table.insert(), decoded_rows)
        if updates:
            pending.append((table, updates))
    for table, updates in pending:
        names = _self_fk_names(table)
        for row in updates:
            where = [column == row[column.name] for column in table.primary_key.columns]
            values = {name: row[name] for name in names}
            connection.execute(update(table).where(*where).values(values))


def _self_fk_names(table: Table) -> list[str]:
    names: list[str] = []
    for constraint in table.foreign_key_constraints:
        for element in constraint.elements:
            if element.column.table.name == table.name:
                names.append(element.parent.name)
    return names


def _insert_missing(connection: Connection, table: Table, rows: list[dict[str, object]]) -> None:
    primary = list(table.primary_key.columns)
    for raw in rows:
        if set(raw) != {column.name for column in table.columns}:
            fail("DOSSIER_REJECTED", "Une ligne de l’archive est illisible.", 422)
        try:
            decoded = {
                column.name: decode_value(column, raw[column.name]) for column in table.columns
            }
        except DossierPayloadError:
            fail("DOSSIER_REJECTED", "Une ligne de l’archive est illisible.", 422)
        where = [column == decoded[column.name] for column in primary]
        found = connection.execute(select(table.c[primary[0].name]).where(*where)).first()
        if found is None:
            connection.execute(table.insert(), [decoded])


def _clear_self_references(connection: Connection, tables: list[Table], owner_id: int) -> None:
    for table in tables:
        names = _self_fk_names(table)
        if not names or "owner_id" not in table.c or table.name in _SKIP_WRITE:
            continue
        present = connection.execute(
            select(func.count()).select_from(table).where(table.c.owner_id == owner_id)
        ).scalar_one()
        if int(present) == 0:
            continue
        connection.execute(
            update(table).where(table.c.owner_id == owner_id).values({name: None for name in names})
        )


def _suspend(connection: Connection, tables: list[Table]) -> None:
    if connection.dialect.name == "postgresql":
        for table in tables:
            connection.execute(text(f"ALTER TABLE {_quote(table.name)} DISABLE TRIGGER USER"))  # noqa: S608
        return
    if connection.dialect.name != "sqlite":
        raise RuntimeError("Moteur inconnu.")
    rows = connection.exec_driver_sql(
        "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND sql IS NOT NULL"
    ).fetchall()
    saved: list[str] = []
    for name, sql in rows:
        if not isinstance(name, str) or not isinstance(sql, str):
            raise RuntimeError("Trigger illisible.")
        connection.exec_driver_sql(f"DROP TRIGGER {_quote(name)}")
        saved.append(sql)
    connection.info["sololmnp_triggers"] = saved


def _resume(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        for table in Base.metadata.sorted_tables:
            connection.execute(text(f"ALTER TABLE {_quote(table.name)} ENABLE TRIGGER USER"))  # noqa: S608
        return
    for sql in connection.info.get("sololmnp_triggers", []):
        connection.exec_driver_sql(sql)


def _reset_identities(connection: Connection, tables: list[Table]) -> None:
    for table in tables:
        if len(table.primary_key.columns) != 1:
            continue
        column = table.primary_key.columns[0]
        sequence = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table.name, "column_name": column.name},
        ).scalar()
        if not sequence:
            continue
        highest = connection.scalar(select(func.max(column)))
        if highest is None:
            connection.execute(text("SELECT setval(:sequence, 1, false)"), {"sequence": sequence})
        else:
            connection.execute(
                text("SELECT setval(:sequence, :highest, true)"),
                {"sequence": sequence, "highest": int(highest)},
            )


def _quote(identifier: str) -> str:
    if _IDENT.fullmatch(identifier) is None:
        raise RuntimeError(f"Identifiant SQL inattendu : {identifier}")
    return f'"{identifier}"'


def _snapshot_documents(store: ObjectStore) -> Files:
    files: Files = {}
    for name in store.list_names("documents"):
        files[name] = (store.get(document_key(name)), _content_type(name))
    return files


def _apply_documents(store: ObjectStore, files: Files, managed: set[str] | None) -> None:
    for name, (content, media) in files.items():
        if not safe_segment(name):
            fail("DOSSIER_REJECTED", "Nom de justificatif refusé.", 422)
        store.put(document_key(name), content, media, overwrite=True)
    protected = set() if managed is None else managed
    for name in store.list_names("documents"):
        if name not in files and name not in protected and safe_segment(name):
            store.delete(document_key(name))


def _content_type(name: str) -> str:
    extension = name.rsplit(".", 1)[-1] if "." in name else ""
    return {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "png": "image/png",
    }.get(extension, "application/octet-stream")


def _fresh_name(store: ObjectStore) -> str:
    existing = set(store.list_names("dossier-exports"))
    filename = f"dossier-{time.time_ns()}.zip"
    while filename in existing or not _NAME.fullmatch(filename):
        filename = f"dossier-{time.time_ns()}.zip"
    return filename


def _name_stamp(name: str) -> int:
    return int(name.removeprefix("dossier-").removesuffix(".zip"))


def _checked_name(filename: str) -> str:
    if not _NAME.fullmatch(filename):
        fail("DOSSIER_NOT_FOUND", "Archive de dossier introuvable.", 404)
    return filename


def _load_checked(
    settings: Settings, database: Database, filename: str, owner_id: int
) -> tuple[dict[str, Any], Payload, Files]:
    store = open_store(settings)
    path_name = _require_owned_name(database, owner_id, filename)
    try:
        raw = store.get(export_key(path_name))
    except ObjectMissing:
        fail("DOSSIER_NOT_FOUND", "Archive de dossier introuvable.", 404)
    except ObjectStoreError as exc:
        fail("DOCUMENT_STORE", str(exc), 502)
    return _validate_zip(raw)


def _live_population(database: Database, owner_id: int) -> dict[str, int]:
    with database.engine.connect() as connection:
        entries = connection.execute(
            text("SELECT COUNT(*) FROM accounting_entry WHERE owner_id = :owner"),
            {"owner": owner_id},
        ).scalar_one()
        years = connection.execute(
            text("SELECT COUNT(*) FROM fiscal_year WHERE owner_id = :owner"),
            {"owner": owner_id},
        ).scalar_one()
    return {"entries": int(entries), "years": int(years)}


def _remember_archive(database: Database, owner_id: int, filename: str) -> None:
    with database.engine.connect().execution_options(sqlite_write=True) as connection:
        with connection.begin():
            connection.execute(
                insert(DossierArchive),
                {"owner_id": owner_id, "filename": filename, "created_at": utc_now()},
            )


def _owned_names(database: Database, owner_id: int) -> list[str]:
    with database.engine.connect() as connection:
        rows = connection.execute(
            select(DossierArchive.filename)
            .where(DossierArchive.owner_id == owner_id)
            .order_by(DossierArchive.id.desc())
        ).scalars()
        return [name for name in rows if _NAME.fullmatch(name)]


def _require_owned_name(database: Database, owner_id: int, filename: str) -> str:
    path_name = _checked_name(filename)
    if path_name not in set(_owned_names(database, owner_id)):
        fail("DOSSIER_NOT_FOUND", "Archive de dossier introuvable.", 404)
    return path_name


def _describe(filename: str, raw: bytes, stored: dict[str, Any] | None) -> dict[str, Any]:
    digest = hashlib.sha256(raw).hexdigest()
    manifest = _manifest_or_none(raw)
    version = manifest.get("application_version") if isinstance(manifest, dict) else None
    revision = manifest.get("schema_revision") if isinstance(manifest, dict) else None
    return backup_view(
        filename=filename,
        created_at=_created_at(manifest) if isinstance(manifest, dict) else "",
        size=len(raw),
        application_version=version if isinstance(version, str) and version else None,
        schema_revision=revision if isinstance(revision, str) and revision else None,
        sha256=digest,
        integrity=integrity_view(stored, digest),
    )


def _manifest_or_none(raw: bytes) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if MANIFEST_NAME not in archive.namelist():
                return None
            loaded = json.loads(archive.read(MANIFEST_NAME))
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _created_at(manifest: dict[str, Any] | None) -> str:
    if manifest is not None and isinstance(manifest.get("created_at"), str):
        return str(manifest["created_at"])
    return ""


def _file_record(name: str, content: bytes) -> dict[str, object]:
    return {"name": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _unsafe_member(member: str) -> bool:
    if (
        not member
        or member.endswith("/")
        or "\\" in member
        or "\x00" in member
        or member.startswith("/")
        or (len(member) >= 2 and member[1] == ":")
    ):
        return True
    return any(part in {"", ".", ".."} for part in member.split("/"))


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def _checks_key() -> str:
    return export_key(_CHECKS)


def _read_checks(store: ObjectStore, owner_id: int) -> dict[str, Any]:
    book = _read_check_book(store)
    section = book.get(str(owner_id))
    return section if isinstance(section, dict) else {}


def _read_check_book(store: ObjectStore) -> dict[str, Any]:
    try:
        raw = store.get(_checks_key())
    except ObjectMissing:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _record_check(
    store: ObjectStore, owner_id: int, filename: str, raw: bytes, *, ok: bool, message: str
) -> None:
    book = _read_check_book(store)
    section = book.get(str(owner_id))
    if not isinstance(section, dict):
        section = {}
    section[filename] = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "checked_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": ok,
        "message": message,
    }
    book[str(owner_id)] = section
    store.put(
        _checks_key(),
        json.dumps(book, sort_keys=True, ensure_ascii=False).encode(),
        "application/json",
        overwrite=True,
    )


def _error_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return str(detail["message"])
    return "Contrôle d’intégrité refusé."
