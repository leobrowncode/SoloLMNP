import json
from pathlib import Path

from lmnp_core.build import build_path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "golden"
CASES = ("premier-exercice", "plafond-39c", "deficit-imputation")


def test_golden_cases_match_the_hand_calculation() -> None:
    for name in CASES:
        result = build_path(GOLDEN / name / "input")
        expected = json.loads((GOLDEN / name / "expected.json").read_text(encoding="utf-8"))
        for year, payload in expected["annees"].items():
            got = result.annee(int(year)).public()
            for key, value in payload.items():
                if key == "cases":
                    for case, amount in value.items():
                        assert got["cases"].get(case) == amount, f"{name} {year} {case}"
                else:
                    assert got[key] == value, f"{name} {year} {key}"
        for item in result.annees:
            assert item.actif_net == item.passif
            assert item.fec_valide
            assert item.deficit_cree <= max(0, item.autres_charges - item.produits)
