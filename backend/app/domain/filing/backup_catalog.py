"""Pure descriptions of a backup archive: population, date, members and last check."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

DocumentMember = Literal["keep", "ignore"]


class UnsafeDocumentPath(ValueError):
    """A documents/ member is not a single safe file name."""


def classify_document_member(member: str) -> DocumentMember | None:
    """Decide what restore does with one zip member.

    ``None`` means the member is not under ``documents/``. A leading dot on a
    single file name (``.gitkeep``) is ignored: the application may have put it
    in an older archive, and it is not a stored justificatif. Nested paths,
    traversal, separators and empty names are refused.
    """
    if not member.startswith("documents/") or member.endswith("/"):
        return None
    name = member.removeprefix("documents/")
    if not _single_document_name(name):
        raise UnsafeDocumentPath("Chemin de document refusé.")
    if name.startswith("."):
        return "ignore"
    return "keep"


def archived_document_names(present: Iterable[str], registered: Iterable[str]) -> list[str]:
    """File names to archive: registered in the database, never hidden or unsafe."""
    allowed = {name for name in registered if name}
    chosen: list[str] = []
    for name in sorted(present):
        if name not in allowed:
            continue
        try:
            decision = classify_document_member(f"documents/{name}")
        except UnsafeDocumentPath:
            continue
        if decision == "keep":
            chosen.append(name)
    return chosen


def _single_document_name(name: str) -> bool:
    if (
        not name
        or name in {".", ".."}
        or "\x00" in name
        or ".." in name
        or "\\" in name
        or "/" in name
        or name != Path(name).name
    ):
        return False
    return True


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def population(path: Path) -> dict[str, int]:
    """Entry and fiscal-year counts stored in a SQLite file."""
    uri = path.resolve().as_posix()
    connection = sqlite3.connect(f"file:{uri}?mode=ro", uri=True)
    try:
        entries = connection.execute("SELECT COUNT(*) FROM accounting_entry").fetchone()
        years = connection.execute("SELECT COUNT(*) FROM fiscal_year").fetchone()
    except sqlite3.Error as exc:
        raise ValueError("Base illisible.") from exc
    finally:
        connection.close()
    if entries is None or years is None:
        raise ValueError("Base illisible.")
    return {"entries": int(entries[0]), "years": int(years[0])}


def backup_timestamp(path: Path, manifest: dict[str, Any] | None) -> str:
    if manifest is not None and isinstance(manifest.get("created_at"), str):
        return str(manifest["created_at"])
    stamp = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def integrity_view(stored: dict[str, Any] | None, sha256: str) -> dict[str, Any]:
    if stored is None or stored.get("sha256") != sha256:
        message = (
            "Le fichier a changé depuis le dernier contrôle."
            if stored is not None
            else "Aucun contrôle enregistré."
        )
        return {"status": "unchecked", "checked_at": None, "message": message}
    ok = stored.get("ok") is True
    checked_at = stored.get("checked_at")
    recorded = stored.get("message")
    if not isinstance(recorded, str) or not recorded:
        recorded = "Contrôle d’intégrité réussi." if ok else "Contrôle d’intégrité refusé."
    return {
        "status": "ok" if ok else "failed",
        "checked_at": checked_at if isinstance(checked_at, str) else None,
        "message": recorded,
    }


def backup_view(
    *,
    filename: str,
    created_at: str,
    size: int,
    application_version: str | None,
    schema_revision: str | None,
    sha256: str,
    integrity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "filename": filename,
        "created_at": created_at,
        "size": size,
        "application_version": application_version,
        "schema_revision": schema_revision,
        "sha256": sha256,
        "integrity": integrity,
    }
