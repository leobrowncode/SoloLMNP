"""Pure rules for committing an operations CSV.

Rejected lines are not posted unless the caller explicitly accepts them.
Paid lines without a bank account block the whole file. The batch description
is what an Idempotency-Key retry replays; a validated entry is never rewritten.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint(
    *,
    content: str,
    mapping: dict[str, str] | None,
    property_id: int | None,
    fiscal_year_id: int | None,
    bank_account_id: int | None,
    import_valid_only: bool,
) -> str:
    payload = {
        "bank_account_id": bank_account_id,
        "content": content,
        "fiscal_year_id": fiscal_year_id,
        "import_valid_only": import_valid_only,
        "mapping": mapping or {},
        "property_id": property_id,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def paid_lines_need_bank(rows: list[dict[str, Any]], bank_account_id: int | None) -> bool:
    return bank_account_id is None and any(bool(row.get("paid")) for row in rows)


def guard_operations_commit(
    rows: list[dict[str, Any]],
    *,
    bank_account_id: int | None,
    import_valid_only: bool,
) -> dict[str, Any]:
    """Decide whether any line may be posted. ``ok`` false means nothing was posted."""
    issues = [issue for row in rows for issue in row.get("issues") or []]
    if paid_lines_need_bank(rows, bank_account_id):
        return {
            "ok": False,
            "code": "BANK_REQUIRED",
            "message": (
                "Choisissez le compte bancaire des lignes déjà payées. Rien n’a été comptabilisé."
            ),
            "status": 422,
            "issues": issues or None,
        }
    errors = [row for row in rows if row.get("status") == "error"]
    importable = [row for row in rows if row.get("importable")]
    if errors and not import_valid_only:
        count = len(errors)
        lead = "1 ligne est rejetée." if count == 1 else f"{count} lignes sont rejetées."
        if importable:
            tail = "Corrigez le fichier, ou confirmez l’import des seules lignes valides."
        else:
            tail = "Corrigez le fichier avant de comptabiliser."
        return {
            "ok": False,
            "code": "CSV_PARTIAL_REFUSED",
            "message": f"{lead} Rien n’a été comptabilisé. {tail}",
            "status": 422,
            "issues": issues or None,
        }
    if not importable:
        if issues:
            return {
                "ok": False,
                "code": str(issues[0]["code"]),
                "message": str(issues[0]["message"]),
                "status": 422,
                "issues": issues,
            }
        return {
            "ok": False,
            "code": "CSV_EMPTY",
            "message": "Aucune ligne importable.",
            "status": 422,
            "issues": None,
        }
    return {"ok": True, "importable": importable}


def batch_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        line = int(row["line"])
        if row.get("status") == "error":
            issue = (row.get("issues") or [{}])[0]
            items.append(
                {
                    "line": line,
                    "status": "rejected",
                    "code": str(issue.get("code") or "CSV_INVALID"),
                    "message": str(issue.get("message") or "Ligne rejetée."),
                }
            )
            continue
        if row.get("duplicate") or row.get("status") == "duplicate":
            items.append(
                {
                    "line": line,
                    "status": "skipped",
                    "code": "CSV_DUPLICATE",
                    "message": "Déjà comptabilisée. Aucune nouvelle écriture.",
                }
            )
            continue
        if row.get("importable"):
            reference = str((row.get("values") or {}).get("piece_reference") or "")
            items.append(
                {
                    "line": line,
                    "status": "posted",
                    "piece_reference": reference,
                    "replayed": False,
                }
            )
            continue
        warning = (row.get("warnings") or [{}])[0]
        items.append(
            {
                "line": line,
                "status": "skipped",
                "code": str(warning.get("code") or "CSV_SKIPPED"),
                "message": str(warning.get("message") or "Ligne non comptabilisée."),
            }
        )
    return items


def summarize_batch(key: str, items: list[dict[str, Any]], *, replayed: bool) -> dict[str, Any]:
    return {
        "idempotency_key": key,
        "replayed": replayed,
        "posted_count": sum(1 for item in items if item["status"] == "posted"),
        "rejected_count": sum(1 for item in items if item["status"] == "rejected"),
        "skipped_count": sum(1 for item in items if item["status"] == "skipped"),
        "items": items,
    }
