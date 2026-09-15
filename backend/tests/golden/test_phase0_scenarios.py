import json
from pathlib import Path

ROOT = Path(__file__).parents[3]

def test_reference_scenarios_are_complete_and_fictional() -> None:
    data = json.loads((ROOT / "backend/tests/fixtures/scenarios.json").read_text())
    assert data["fictional_only"] is True
    assert [scenario["id"] for scenario in data["scenarios"]] == list("ABCDEFGHIJ")
    assert all(scenario["assertions"] for scenario in data["scenarios"])

def test_vintages_are_separate_and_research_only() -> None:
    rules_2025 = json.loads((ROOT / "fiscal/2025/rules.yaml").read_text())
    rules_2026 = json.loads((ROOT / "fiscal/2026/rules.yaml").read_text())
    assert rules_2025["vintage"] == "2025"
    assert rules_2026["vintage"] == "2026"
    assert rules_2025["status"] == rules_2026["status"] == "research_only"
    assert rules_2025 != rules_2026
