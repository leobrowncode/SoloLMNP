"""Load versioned fiscal rule files. Executable rules need a source and an interpretation."""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.services.ledger import fail

REQUIRED = ("id", "status", "effect_start", "source", "interpretation")


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
    executable = []
    blocked = []
    scope = []
    for rule in document.get("rules", []):
        status = rule.get("status")
        if status == "executable":
            missing = [field for field in REQUIRED if not rule.get(field)]
            if missing or rule.get("id", "").startswith("RULE-BLOCKED"):
                fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} incomplète.")
            executable.append(rule)
        elif status == "scope":
            if not rule.get("id") or not rule.get("interpretation"):
                fail("RULE_INCOMPLETE", f"Règle {rule.get('id')} incomplète.")
            scope.append(rule.get("id"))
        else:
            blocked.append(rule.get("id"))
    return {
        "vintage": vintage,
        "version": document.get("version"),
        "status": "research_only",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "executable": executable,
        "blocked": [item for item in blocked if item],
        "scope": [item for item in scope if item],
    }


def available_vintages() -> list[str]:
    root = PROJECT_ROOT / "fiscal"
    return sorted(path.name for path in root.iterdir() if (path / "rules.yaml").is_file())
