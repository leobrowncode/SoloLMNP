"""Facts that must stop a fiscal computation instead of being folded into it.

Cession, TVA and plus-values have no executable reading in the vintage. A
validated movement on the matching accounts, or an asset already disposed, is
reported with the blocked rule id. The amounts are not reclassified as rent
or as a deductible charge.
"""

from __future__ import annotations

from collections.abc import Iterable

ACCOUNT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("445", ("RULE-BLOCKED-TVA-001",)),
    ("675", ("RULE-BLOCKED-CESSION-001", "RULE-BLOCKED-PLUS-VALUE-001")),
    ("775", ("RULE-BLOCKED-CESSION-001", "RULE-BLOCKED-PLUS-VALUE-001")),
)
DISPOSAL_RULES: tuple[str, ...] = (
    "RULE-BLOCKED-CESSION-001",
    "RULE-BLOCKED-PLUS-VALUE-001",
)


def triggered_rule_ids(account_numbers: Iterable[str], *, disposal: bool) -> list[str]:
    """Stable, de-duplicated rule ids. Empty when nothing out of scope is present."""
    found: list[str] = []
    for number in sorted(set(account_numbers)):
        for prefix, rule_ids in ACCOUNT_RULES:
            if not number.startswith(prefix):
                continue
            for rule_id in rule_ids:
                if rule_id not in found:
                    found.append(rule_id)
    if disposal:
        for rule_id in DISPOSAL_RULES:
            if rule_id not in found:
                found.append(rule_id)
    return found
