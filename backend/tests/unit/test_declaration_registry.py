"""2042-C-PRO boxes stay tied to the archived form. Unread numbers stay blocked."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.domain.filing.declaration import WORK_MARKER, load_personal_form, prior_case

ROOT = Path(__file__).resolve().parents[3]
PDF = ROOT / "fiscal" / "2025" / "sources" / "official" / "2042-c-pro_2026.pdf"
FORM = ROOT / "fiscal" / "2025" / "forms" / "2042-c-pro.json"


def test_archived_2042_matches_the_registry() -> None:
    document = json.loads(FORM.read_text(encoding="utf-8"))
    assert document["status"] == "research_only"
    assert document["declarable"] is False
    assert document["cerfa"] == "11222*28"
    assert document["verification"] == "verified"
    source = document["source"]
    raw = PDF.read_bytes()
    assert len(raw) == source["bytes"] == 1_020_894
    assert hashlib.sha256(raw).hexdigest() == source["sha256"]
    assert source["pdf_url"].startswith("https://www.impots.gouv.fr/")
    assert WORK_MARKER


def test_real_regime_boxes_and_blocked_guesses() -> None:
    form = load_personal_form("2025")
    by_role = {line["role"]: line for line in form["lines"]}
    assert by_role["benefit"]["case"] == "5NA"
    assert by_role["benefit"]["case_declarant_2"] == "5OA"
    assert by_role["benefit"]["case_dependant"] == "5PA"
    assert by_role["deficit"]["case"] == "5NY"
    assert by_role["deficit"]["case_declarant_2"] == "5OY"
    assert {item["case"] for item in form["blocked"]} == {"5NK", "5NZ"}
    assert prior_case(form, 2015) == "5GA"
    assert prior_case(form, 2024) == "5GJ"
    assert prior_case(form, 2025) is None
    assert prior_case(form, 2014) is None


def test_2026_form_publishes_no_case() -> None:
    form = load_personal_form("2026")
    assert form["verification"] == "case_not_verified"
    assert form["declarable"] is False
    assert form["lines"] == []
    assert prior_case(form, 2025) is None
    assert "2027" in form["block_reason"]
    blocked = {item["case"] for item in form["blocked"]}
    assert {"5NA", "5NY", "5NK", "5NZ", "5GA"} <= blocked
