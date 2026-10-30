"""Trust of a fiscal output: Recherche, Provisoire, Déclarable."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.domain.fiscal.output_status import (
    align_controlled_exports,
    allows_ready_phrase,
    artifact_posture,
    calculation_status,
    classify,
    contains_ready_phrase,
    download_refusal,
    export_slot,
    is_validated,
    load_validation,
    presentation,
    resolve_trust,
)

VALIDATED: dict[str, Any] = {
    "vintage": "2025",
    "version": "validation-1",
    "status": "validated",
    "declarable": True,
    "official_source": {
        "reference": "CERFA 2031-SD et liasse 2033-SD, millésime 2025",
        "url": "https://www.impots.gouv.fr/formulaire/2031-sd/impot-sur-le-revenu",
    },
    "validated_on": "2026-10-02",
    "scope": {
        "activity": "LMNP déclaré",
        "regime": "réel simplifié BIC",
        "excluded": ["cession", "TVA", "plus-values", "LMP"],
    },
    "rules_version": "research-1",
}


def test_shipped_vintages_stay_research() -> None:
    for vintage in ("2025", "2026"):
        record = load_validation(vintage)
        assert record["status"] == "research_only"
        assert record["declarable"] is False
        assert is_validated(record) is False
        shown = calculation_status(vintage)
        assert shown["output_status"] == "recherche"
        assert shown["output_label"] == "Recherche"
        assert shown["declarable"] is False
        assert shown["validation"]["effective"] is False
        assert not contains_ready_phrase(shown["output_headline"])
        assert not contains_ready_phrase(shown["disclaimer"])


def test_unreadable_or_missing_validation_fails_closed(tmp_path, monkeypatch) -> None:
    root = tmp_path / "fiscal" / "2025"
    root.mkdir(parents=True)
    (root / "validation.json").write_text("{", encoding="utf-8")
    (root / "rules.yaml").write_text(json.dumps({"version": "research-1"}), encoding="utf-8")
    monkeypatch.setattr("app.domain.fiscal.output_status.PROJECT_ROOT", tmp_path)
    broken = load_validation("2025")
    assert broken["defect"] == "VALIDATION_UNREADABLE"
    assert is_validated(broken) is False
    missing = load_validation("2024")
    assert missing["defect"] == "VALIDATION_MISSING"
    assert calculation_status("2025")["output_status"] == "recherche"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record.update({"status": "research_only", "declarable": False}),
        lambda record: record.update({"declarable": False}),
        lambda record: record.update({"official_source": None}),
        lambda record: record.__setitem__(
            "official_source",
            {"reference": "notice", "url": "http://www.impots.gouv.fr/formulaire"},
        ),
        lambda record: record.update({"validated_on": "2026-13-40"}),
        lambda record: record.update({"version": "  "}),
        lambda record: record.update({"rules_version": ""}),
        lambda record: record.update(
            {"scope": {"activity": "LMNP", "regime": "réel", "excluded": []}}
        ),
        lambda record: record.update({"vintage": "20"}),
    ],
)
def test_incomplete_attestation_is_not_validated(mutate) -> None:
    record = json.loads(json.dumps(VALIDATED))
    mutate(record)
    assert is_validated(record) is False
    shown = classify(
        validation=record,
        copy_complete=True,
        year_closed=True,
        produced=True,
    )
    assert shown["output_status"] == "recherche"
    assert shown["declarable"] is False
    assert not allows_ready_phrase(shown["output_status"])
    assert not contains_ready_phrase(shown["output_headline"])
    assert not contains_ready_phrase(shown["disclaimer"])


def test_validated_but_stale_rules_stay_provisional() -> None:
    record = {**VALIDATED, "rules_version": "research-0"}
    assert is_validated(record) is True
    shown = classify(
        validation=record,
        copy_complete=True,
        year_closed=True,
        produced=True,
    )
    assert shown["output_status"] == "provisoire"
    assert shown["output_label"] == "Provisoire"
    assert shown["declarable"] is False
    assert shown["validation"]["effective"] is False
    assert not contains_ready_phrase(shown["disclaimer"])
    assert shown["export_posture"] == "provisoire"
    assert shown["exports"]["fec"]["posture"] == "finale"


def test_validated_without_copy_gates_is_provisional() -> None:
    shown = classify(
        validation=VALIDATED,
        copy_complete=False,
        year_closed=False,
        produced=True,
    )
    assert shown["output_status"] == "provisoire"
    assert shown["declarable"] is False
    assert shown["exports"]["liasse"]["posture"] == "bloquee"
    assert shown["exports"]["pdf"]["label"] == "Bloquée"
    assert shown["exports"]["fec"]["posture"] == "bloquee"
    assert not contains_ready_phrase(presentation("provisoire", copy_complete=False)["disclaimer"])


def test_validated_aligned_and_complete_is_declarable() -> None:
    open_year = classify(
        validation=VALIDATED,
        copy_complete=True,
        year_closed=False,
        produced=True,
    )
    assert open_year["output_status"] == "declarable"
    assert open_year["output_label"] == "Déclarable"
    assert open_year["declarable"] is True
    assert allows_ready_phrase(open_year["output_status"])
    assert contains_ready_phrase(open_year["output_headline"])
    assert open_year["exports"]["liasse"]["posture"] == "provisoire"
    assert open_year["exports"]["fec"]["posture"] == "bloquee"
    closed = classify(
        validation=VALIDATED,
        copy_complete=True,
        year_closed=True,
        produced=True,
    )
    assert closed["exports"]["liasse"]["posture"] == "finale"
    assert closed["exports"]["liasse"]["download"] is True
    assert closed["exports"]["pdf"]["posture"] == "finale"
    assert closed["exports"]["archive"]["label"] == "Finale"
    assert closed["validation"]["effective"] is True
    assert closed["validation"]["official_source"]["reference"]
    assert closed["validation"]["validated_on"] == "2026-10-02"
    assert closed["validation"]["scope"]["excluded"]
    assert closed["validation"]["version"] == "validation-1"


def test_research_copy_is_never_final_and_never_ready_to_copy() -> None:
    record = load_validation("2025")
    closed = classify(
        validation=record,
        copy_complete=True,
        year_closed=True,
        produced=True,
    )
    assert closed["output_status"] == "recherche"
    assert closed["exports"]["liasse"]["posture"] == "provisoire"
    assert closed["exports"]["fec"]["posture"] == "finale"
    blocked = classify(
        validation=record,
        copy_complete=False,
        year_closed=False,
        produced=True,
    )
    assert blocked["exports"]["liasse"]["posture"] == "bloquee"
    assert blocked["exports"]["liasse"]["download"] is False
    assert resolve_trust(record_valid=False, rules_aligned=True, copy_complete=True) == "recherche"
    assert artifact_posture(produced=False, blocked=False, final=True) == "bloquee"


def test_only_the_declarable_headline_uses_the_ready_phrase() -> None:
    for trust in ("recherche", "provisoire"):
        shown = presentation(trust, copy_complete=True)
        assert shown["output_headline"] in {"Recherche", "Provisoire"}
        assert not contains_ready_phrase(shown["output_headline"])
        assert not contains_ready_phrase(shown["disclaimer"])
    ready = presentation("declarable", copy_complete=True)
    assert ready["output_headline"] == "Déclarable — Prête à recopier"
    assert contains_ready_phrase(ready["disclaimer"])


def test_download_follows_the_posture_without_recomputing_gates() -> None:
    assert export_slot("finale") == {"posture": "finale", "label": "Finale", "download": True}
    assert export_slot("provisoire")["download"] is True
    assert export_slot("inconnu") == {"posture": "bloquee", "label": "Bloquée", "download": False}
    aligned = align_controlled_exports(
        {
            "liasse": export_slot("provisoire"),
            "pdf": export_slot("provisoire"),
            "fec": export_slot("finale"),
            "archive": export_slot("finale"),
        },
        year_closed=True,
        fec_blocked=True,
    )
    assert aligned["pdf"]["download"] is True
    assert aligned["fec"]["download"] is False
    assert aligned["archive"]["label"] == "Bloquée"
    status = {
        "exports": aligned,
        "prerequisites": [
            {
                "code": "FEC_INVALID",
                "message": "En-tête FEC absent.",
                "export": "fec",
                "action": {"label": "Voir le pré-contrôle", "href": "/fiscalite#close-title"},
            }
        ],
    }
    refusal = download_refusal("archive", status)
    assert refusal is not None
    assert refusal["code"] == "FEC_INVALID"
    assert refusal["action"]["href"] == "/fiscalite#close-title"
    assert download_refusal("pdf", status) is None
    blocked = download_refusal(
        "pdf",
        {
            "exports": {"pdf": export_slot("bloquee")},
            "prerequisites": [
                {"code": "SIREN_MANQUANT", "message": "Indiquez le SIREN.", "export": "liasse"},
                {"code": "CASE_NON_VERIFIEE", "message": "Case absente.", "export": "liasse"},
            ],
        },
    )
    assert blocked is not None
    assert blocked["code"] == "EXPORT_BLOCKED"
    assert blocked["message"] == "La liasse indique des prérequis manquants."
    assert len(blocked["issues"]) == 2
