"""Verify archived official fiscal sources for vintage 2025."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCES = ROOT / "fiscal" / "2025" / "sources"
FORMS = ROOT / "fiscal" / "2025" / "forms"


def test_manifest_documents_match_archived_pdfs() -> None:
    manifest = json.loads((SOURCES / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["vintage"] == "2025"
    assert manifest["consulted_at"] == "2026-10-02"
    assert len(manifest["documents"]) >= 3
    for document in manifest["documents"]:
        path = SOURCES / document["local_path"]
        assert path.is_file(), f"PDF manquant : {path}"
        raw = path.read_bytes()
        assert len(raw) == document["bytes"]
        assert hashlib.sha256(raw).hexdigest() == document["sha256"]
        assert document["pdf_url"].startswith("https://www.impots.gouv.fr/")
        assert document["cerfa"]


def test_cases_registry_refuses_unverified_declarable_path() -> None:
    registry = json.loads((FORMS / "cases.yaml").read_text(encoding="utf-8"))
    assert registry["vintage"] == "2025"
    assert registry["status"] == "mvp_ready"
    assert registry["declarable"] is True
    verified = {
        "verified",
        "verified_by_cross_reference",
    }
    for case in registry["cases"]:
        if case["form"] == "2042-C-PRO":
            assert case["official_case"] in {"5NA", "5NY", "5GA-5GJ"}
            assert case["verification"] == "verified"
            assert case["source_document"] == "2042-C-PRO-2026"
            assert case["consulted_at"] == "2026-10-30"
            continue
        if case["form"].startswith("2033"):
            assert case["official_case"] is not None
            assert case["verification"] == "verified"
            assert case["source_document"] == "2033-SD-LIASSE-2025"
            continue
        if case["form"] in {"2031-SD", "2031-BIS-SD"}:
            assert case["verification"] == "verified_by_cross_reference"
            assert case["maps_from"] in {"370", "372"}
            assert case["source_document"] == "2031-SD-2025"
            continue
        raise AssertionError(f"Formulaire inattendu dans le registre MVP : {case['form']}")
    assert verified == {"verified", "verified_by_cross_reference"}
    annexes = {row["form"]: row for row in registry["annex_applicability"]}
    assert annexes["2033-F-SD"]["applicable"] is False
    assert annexes["2033-G-SD"]["applicable"] is False
    assert annexes["2042-C-PRO"]["applicable"] == "separate_product"
    assert annexes["2033-D-SD"]["applicable"] is False
    assert not any(case.get("work_code") == "DEFICITS_EXERCICE" for case in registry["cases"])
    terrains = next(
        case for case in registry["cases"] if case["work_code"] == "TERRAINS_BRUT_DEBUT"
    )
    assert terrains["official_case"] == "420"
    constructions = next(
        case for case in registry["cases"] if case["work_code"] == "CONSTRUCTIONS_BRUT_DEBUT"
    )
    assert constructions["official_case"] == "430"
    assert all(case.get("official_case") != "410" for case in registry["cases"])
    blocked = {
        (item["form"], item.get("official_case"))
        for item in registry["blocked_cases"]
        if item.get("official_case")
    }
    assert ("2042-C-PRO", "5NK") in blocked
    assert ("2042-C-PRO", "5NZ") in blocked


def test_work_mapping_carries_verified_official_cases() -> None:
    document = json.loads((FORMS / "2033.json").read_text(encoding="utf-8"))
    assert document["status"] == "research_only"
    assert document["source_manifest"] == "../sources/manifest.json"
    by_code = {field["code"]: field for field in document["fields"]}
    assert by_code["PRODUITS"]["official_case"] == "232"
    assert by_code["CHARGES"]["official_case"] == "264"
    assert by_code["RESULTAT_FISCAL"]["official_case"] == "370"
    assert by_code["RESULTAT_FISCAL"]["official_case_deficit"] == "372"
    assert all(field["verification"] == "verified" for field in document["fields"])
    assert all(field["official_case"] is not None for field in document["fields"])
