"""Pure descriptions of a backup archive: population, date and last check."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
