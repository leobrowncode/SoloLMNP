"""Load versioned fiscal rule files. Executable rules need a source and an interpretation."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.services.ledger import fail

EXECUTABLE_FIELDS = (
    "id",
    "status",
    "effect_start",
    "source",
    "source_url",
    "consulted_at",
    "interpretation",
)
BLOCKED_FIELDS = ("id", "status", "source", "source_url", "consulted_at", "blocking_reason")
SCOPE_FIELDS = ("id", "status", "source", "source_url", "consulted_at", "interpretation")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def rules_path(vintage: str) -> Path:
    if not vintage.isdigit() or len(vintage) != 4:
        fail("UNKNOWN_VINTAGE", "Millésime fiscal inconnu.", 404)
    path = PROJECT_ROOT / "fiscal" / vintage / "rules.yaml"
    if not path.is_file():
        fail("UNKNOWN_VINTAGE", "Millésime fiscal inconnu.", 404)
    return path


def load_vintage(vintage: str) -> dict[str, Any]:
    path = rules_path(vintage)
    raw = path.read_bytes()
    document = json.loads(raw)
    if document.get("vintage") != vintage or document.get("status") != "research_only":
        fail("VINTAGE_NOT_USABLE", "Ce millésime n’est pas utilisable en l’état.")
    if document.get("declarable") is True:
        fail("VINTAGE_NOT_USABLE", "Aucun millésime n’est déclarable.")
    executable = []
    blocked = []
    scope = []
    for rule in document.get("rules", []):
        status = rule.get("status")
        if status == "executable":
            _require(rule, EXECUTABLE_FIELDS)
            if rule.get("id", "").startswith("RULE-BLOCKED"):
                fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} incomplète.")
            _require_source(rule)
            _require_date(rule, "effect_start")
            executable.append(rule)
        elif status == "scope":
            _require(rule, SCOPE_FIELDS)
            _require_source(rule)
            scope.append(rule)
        elif status == "blocked":
            _require(rule, BLOCKED_FIELDS)
            _require_source(rule)
            blocked.append(rule)
        else:
            fail("RULE_INCOMPLETE", f"Statut de règle inconnu pour {rule.get('id')}.")
    return {
        "vintage": vintage,
        "version": document.get("version"),
        "status": "research_only",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "executable": executable,
        "blocked": blocked,
        "scope": [rule["id"] for rule in scope],
        "scope_rules": scope,
    }


def public_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Fields the API may show. The interpretation stays in the rule file and the docs."""
    return {
        "id": rule.get("id"),
        "status": rule.get("status"),
        "effect_start": rule.get("effect_start"),
        "effect_end": rule.get("effect_end"),
        "source": rule.get("source"),
        "source_url": rule.get("source_url"),
        "consulted_at": rule.get("consulted_at"),
        "blocking_reason": rule.get("blocking_reason"),
    }


def available_vintages() -> list[str]:
    root = PROJECT_ROOT / "fiscal"
    return sorted(path.name for path in root.iterdir() if (path / "rules.yaml").is_file())


def _require(rule: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not rule.get(field)]
    if missing:
        fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} incomplète.")


def _require_source(rule: dict[str, Any]) -> None:
    url = rule.get("source_url")
    if not isinstance(url, str) or not url.startswith("https://"):
        fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} sans source https.")
    consulted = rule.get("consulted_at")
    if not isinstance(consulted, str) or _DATE.fullmatch(consulted) is None:
        fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} sans date de consultation.")
    try:
        date.fromisoformat(consulted)
    except ValueError:
        fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} sans date de consultation.")


def _require_date(rule: dict[str, Any], field: str) -> None:
    value = rule.get(field)
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} incomplète.")
    try:
        date.fromisoformat(value)
    except ValueError:
        fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} incomplète.")
