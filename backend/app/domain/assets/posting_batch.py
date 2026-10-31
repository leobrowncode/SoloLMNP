"""Pure description of a depreciation posting batch.

The service commits each successful item, then stores this description under the
Idempotency-Key. A retry replays the description and does not post again.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint(items: list[tuple[int, str, str]]) -> str:
    """Stable hash of the lot the client asked to post."""
    payload = [
        {"period_id": period_id, "request_id": request_id, "piece_reference": piece}
        for period_id, request_id, piece in items
    ]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def posted_item(period_id: int, entry_id: int, *, replayed: bool) -> dict[str, Any]:
    return {
        "period_id": period_id,
        "status": "posted",
        "entry_id": entry_id,
        "replayed": replayed,
    }


def error_item(
    period_id: int,
    code: str,
    message: str,
    action: dict[str, str] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "period_id": period_id,
        "status": "error",
        "code": code,
        "message": message,
    }
    if action is not None:
        item["action"] = action
    return item


def skipped_item(period_id: int) -> dict[str, Any]:
    return {
        "period_id": period_id,
        "status": "skipped",
        "code": "BATCH_INTERRUPTED",
        "message": "Non traitée : une dotation précédente du lot a échoué.",
    }


def summarize(key: str, items: list[dict[str, Any]], *, replayed: bool) -> dict[str, Any]:
    return {
        "idempotency_key": key,
        "replayed": replayed,
        "posted_count": sum(1 for item in items if item["status"] == "posted"),
        "failed_count": sum(1 for item in items if item["status"] == "error"),
        "skipped_count": sum(1 for item in items if item["status"] == "skipped"),
        "items": items,
    }
