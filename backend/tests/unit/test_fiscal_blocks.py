"""Blocked rules stay out of the computation unless a triggering fact is present."""

from app.domain.fiscal.blocks import triggered_rule_ids
from app.domain.fiscal.loader import load_vintage


def test_ordinary_accounts_trigger_nothing() -> None:
    assert triggered_rule_ids(["512000", "706000", "681100", "615000"], disposal=False) == []


def test_disposal_and_vat_accounts_are_named() -> None:
    assert triggered_rule_ids(["775000"], disposal=False) == [
        "RULE-BLOCKED-CESSION-001",
        "RULE-BLOCKED-PLUS-VALUE-001",
    ]
    assert triggered_rule_ids(["445710"], disposal=False) == ["RULE-BLOCKED-TVA-001"]
    assert triggered_rule_ids([], disposal=True) == [
        "RULE-BLOCKED-CESSION-001",
        "RULE-BLOCKED-PLUS-VALUE-001",
    ]


def test_shipped_vintages_keep_blocked_rules_sourced_and_research_only() -> None:
    for vintage in ("2025", "2026"):
        loaded = load_vintage(vintage)
        assert loaded["status"] == "research_only"
        assert loaded["version"] == "research-2"
        executable = {rule["id"] for rule in loaded["executable"]}
        assert "RULE-LMNP-DEPRECIATION-LIMIT-001" in executable
        assert "RULE-LMNP-LOSS-001" in executable
        blocked = {rule["id"]: rule for rule in loaded["blocked"]}
        assert "RULE-BLOCKED-ARD-39B-001" in blocked
        assert "RULE-BLOCKED-156-BIS-001" in blocked
        assert "RULE-BLOCKED-CESSION-001" in blocked
        for rule in loaded["blocked"]:
            assert rule["blocking_reason"]
            assert rule["source_url"].startswith("https://")
            assert rule["consulted_at"]
        for rule_id in triggered_rule_ids(["675000", "445000"], disposal=True):
            assert rule_id in blocked
