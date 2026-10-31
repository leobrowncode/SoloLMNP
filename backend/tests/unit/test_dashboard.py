"""Dossier board states: empty, partial, blocked, ready to close. Never déclarable."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest

from app.domain.dashboard import (
    STEP_IDS,
    DashboardFacts,
    EventFact,
    PrerequisiteFact,
    build_dashboard,
)

_PROVISOIRE = {"posture": "provisoire", "label": "Provisoire", "download": True}
_BLOQUEE = {"posture": "bloquee", "label": "Bloquée", "download": False}
_FINALE = {"posture": "finale", "label": "Finale", "download": True}
_WHEN = datetime(2026, 3, 2, 9, 30, 0)


def _dossier(
    status: str = "incomplet",
    label: str = "Incomplet",
    year_status: str | None = None,
    year: int | None = None,
    fiscal_year_id: int | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "label": label,
        "fiscal_year_id": fiscal_year_id,
        "year": year,
        "year_status": year_status,
        "vintage_status": "research_only",
    }


def _exports(*, liasse: dict[str, Any], fec: dict[str, Any]) -> dict[str, Any]:
    return {"liasse": liasse, "pdf": liasse, "fec": fec, "archive": fec}


def _facts(**overrides: Any) -> DashboardFacts:
    base: dict[str, Any] = {
        "activity_present": False,
        "siren_present": False,
        "year_id": None,
        "year": None,
        "year_status": None,
        "property_count": 0,
        "bank_count": 0,
        "operation_count": 0,
        "operation_amount_cents": 0,
        "draft_count": 0,
        "asset_count": 0,
        "depreciable_asset_count": 0,
        "calculated_period_count": 0,
        "posted_period_count": 0,
        "posted_depreciation_cents": 0,
        "asset_booking": "ok",
        "has_previous_year": False,
        "previous_year_closed": False,
        "opening_posted": False,
        "opening_amount_cents": 0,
        "target_has_entries": False,
        "fiscal_produced": False,
        "fiscal_stale": False,
        "fiscal_result_cents": None,
        "close_errors": (),
        "exports": {},
        "export_prerequisites": (),
        "events": (),
        "dossier": _dossier(),
    }
    base.update(overrides)
    return DashboardFacts(**base)


def _board(facts: DashboardFacts) -> dict[str, Any]:
    payload = build_dashboard(facts)
    encoded = json.dumps(payload, ensure_ascii=False).lower()
    assert "declarable" not in encoded
    assert "déclarable" not in encoded
    assert payload["dossier"]["vintage_status"] == "research_only"
    assert [step["id"] for step in payload["steps"]] == list(STEP_IDS)
    assert payload["continue"]["label"] == "Continuer"
    progress = payload["progression"]
    done = sum(1 for step in payload["steps"] if step["status"] == "fait")
    assert progress["done"] == done
    assert progress["total"] == len(payload["steps"])
    assert progress["label"] == f"{done}/{progress['total']}"
    assert progress["current_step"] == payload["continue"]["step"]
    current = next(step for step in payload["steps"] if step["id"] == progress["current_step"])
    assert progress["summary"] == current["summary"]
    assert progress["current_status_label"] == current["status_label"]
    for step in payload["steps"]:
        amount = step["amount_cents"]
        assert amount is None or type(amount) is int
        assert step["summary"]
        assert step["status_label"] in {"À faire", "En cours", "Bloqué", "Prête", "Terminé"}
        if step["status"] == "bloque":
            assert step["prerequisites"][0]["action"]["href"].startswith("/")
    return payload


def _step(payload: dict[str, Any], step_id: str) -> dict[str, Any]:
    return next(step for step in payload["steps"] if step["id"] == step_id)


def test_empty_dossier_points_at_creating_the_activity() -> None:
    payload = _board(_facts())
    assert payload["dossier"]["status"] == "incomplet"
    assert payload["continue"]["href"] == "/comptabilite/brouillons#creer-activite"
    assert payload["continue"]["step"] == "structure"
    for step in payload["steps"]:
        assert step["status"] == "a_faire"
        assert step["status_label"] == "À faire"
        assert step["last_event"] is None
        assert step["amount_cents"] is None
    assert _step(payload, "structure")["prerequisites"][0]["code"] == "NO_ACTIVITY"
    assert _step(payload, "operations")["prerequisites"][0]["action"]["href"].startswith(
        "/comptabilite"
    )


def test_partial_dossier_names_the_missing_siren_and_the_bank() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            year_id=4,
            year=2026,
            year_status="OPEN",
            property_count=1,
            bank_count=0,
            operation_count=0,
            operation_amount_cents=0,
            close_errors=(("FISCAL_NOT_COMPUTED", "Aucun calcul fiscal n’est enregistré."),),
            export_prerequisites=(
                PrerequisiteFact(
                    "FISCAL_NOT_COMPUTED",
                    "Calculez le résultat fiscal avant de télécharger la liasse ou le PDF.",
                    "liasse",
                    "Calculer la fiscalité",
                    "/fiscalite#calcul-fiscal",
                ),
            ),
            events=(EventFact("operations", _WHEN, "Bien enregistré"),),
            dossier=_dossier(year_status="OPEN", year=2026, fiscal_year_id=4),
        )
    )
    structure = _step(payload, "structure")
    assert structure["status"] == "en_cours"
    assert structure["prerequisites"][0]["code"] == "SIREN_REQUIRED"
    assert structure["prerequisites"][0]["action"] == {
        "label": "Renseigner le SIREN",
        "href": "/comptabilite/brouillons#identite-liasse",
    }
    operations = _step(payload, "operations")
    assert operations["status"] == "en_cours"
    assert operations["amount_cents"] is None
    assert operations["prerequisites"][0]["code"] == "NO_BANK"
    assert operations["prerequisites"][0]["action"]["href"] == "/operations/banque#ajouter-banque"
    assert operations["last_event"] == {
        "occurred_at": "2026-03-02T09:30:00Z",
        "label": "Bien enregistré",
    }
    assert _step(payload, "opening")["status"] == "fait"
    assert _step(payload, "opening")["summary"].startswith("Premier exercice")
    assert _step(payload, "closing")["status"] == "en_cours"
    assert _step(payload, "filing")["status"] == "en_cours"
    assert payload["continue"]["href"] == "/comptabilite/brouillons#identite-liasse"
    assert payload["dossier"]["status"] == "incomplet"


def test_blocked_dossier_reuses_the_export_prerequisite_link() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            siren_present=False,
            year_id=1,
            year=2026,
            year_status="OPEN",
            property_count=1,
            bank_count=1,
            operation_count=2,
            operation_amount_cents=5000,
            fiscal_produced=True,
            fiscal_result_cents=0,
            exports=_exports(liasse=_BLOQUEE, fec=_BLOQUEE),
            export_prerequisites=(
                PrerequisiteFact(
                    "SIREN_MANQUANT",
                    "Indiquez le SIREN de l’activité (Comptabilité → Identité).",
                    "liasse",
                    "Renseigner le SIREN",
                    "/comptabilite/brouillons#identite-liasse",
                ),
                PrerequisiteFact(
                    "YEAR_NOT_CLOSED",
                    "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
                    "fec",
                    "Clôturer l’exercice",
                    "/fiscalite#close-title",
                ),
            ),
            dossier=_dossier("bloque", "Bloqué", year_status="OPEN", year=2026, fiscal_year_id=1),
        )
    )
    assert payload["dossier"]["status"] == "bloque"
    assert _step(payload, "operations")["amount_cents"] == 5000
    assert _step(payload, "structure")["status"] == "bloque"
    filing = _step(payload, "filing")
    assert filing["status"] == "bloque"
    assert filing["status_label"] == "Bloqué"
    assert filing["amount_cents"] == 0
    assert filing["prerequisites"][0]["code"] == "SIREN_MANQUANT"
    assert filing["prerequisites"][0]["action"]["href"] == (
        "/comptabilite/brouillons#identite-liasse"
    )
    assert "YEAR_NOT_CLOSED" not in {item["code"] for item in filing["prerequisites"]}
    assert "Bloquée" in filing["summary"]
    assert "recherche" in filing["summary"].lower()
    assert payload["continue"]["step"] == "structure"
    assert payload["continue"]["href"].endswith("#identite-liasse")


def test_ready_to_close_continues_toward_closing_not_a_declaration() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=1,
            year=2026,
            year_status="READY_TO_CLOSE",
            property_count=1,
            bank_count=1,
            operation_count=1,
            operation_amount_cents=10000,
            asset_count=1,
            depreciable_asset_count=1,
            posted_period_count=1,
            posted_depreciation_cents=2500,
            fiscal_produced=True,
            fiscal_result_cents=0,
            exports=_exports(liasse=_PROVISOIRE, fec=_BLOQUEE),
            export_prerequisites=(
                PrerequisiteFact(
                    "YEAR_NOT_CLOSED",
                    "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
                    "fec",
                    "Clôturer l’exercice",
                    "/fiscalite#close-title",
                ),
            ),
            events=(EventFact("closing", _WHEN, "Exercice passé en prêt à clôturer"),),
            dossier=_dossier(
                "pret_a_verifier",
                "Prêt à vérifier",
                year_status="READY_TO_CLOSE",
                year=2026,
                fiscal_year_id=1,
            ),
        )
    )
    assert payload["dossier"]["label"] == "Prêt à vérifier"
    assert _step(payload, "structure")["status"] == "fait"
    assert _step(payload, "operations")["status"] == "fait"
    assert _step(payload, "assets")["amount_cents"] == 2500
    assert _step(payload, "assets")["status"] == "fait"
    closing = _step(payload, "closing")
    assert closing["status"] == "pret"
    assert closing["status_label"] == "Prête"
    assert closing["summary"] == "Exercice prêt à clôturer."
    assert closing["last_event"]["label"] == "Exercice passé en prêt à clôturer"
    filing = _step(payload, "filing")
    assert filing["status"] == "pret"
    assert filing["prerequisites"][0]["code"] == "YEAR_NOT_CLOSED"
    assert "Provisoire" in filing["summary"]
    assert payload["continue"] == {
        "label": "Continuer",
        "href": "/fiscalite#close-title",
        "detail": "Prochaine action : confirmer la clôture.",
        "step": "closing",
    }


def test_opening_blocked_when_the_previous_year_is_open() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=2,
            year=2026,
            year_status="OPEN",
            has_previous_year=True,
            previous_year_closed=False,
            dossier=_dossier(year_status="OPEN", year=2026, fiscal_year_id=2),
        )
    )
    opening = _step(payload, "opening")
    assert opening["status"] == "bloque"
    assert opening["prerequisites"][0]["code"] == "SOURCE_NOT_CLOSED"
    assert opening["prerequisites"][0]["action"]["href"] == "/fiscalite#close-title"
    assert payload["continue"]["step"] == "opening"


def test_opening_amount_stays_in_cents_once_posted() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=2,
            year=2026,
            year_status="OPEN",
            has_previous_year=True,
            previous_year_closed=True,
            opening_posted=True,
            opening_amount_cents=320000,
            close_errors=(("FISCAL_NOT_COMPUTED", "Aucun calcul fiscal n’est enregistré."),),
            dossier=_dossier(year_status="OPEN", year=2026, fiscal_year_id=2),
        )
    )
    opening = _step(payload, "opening")
    assert opening["status"] == "fait"
    assert opening["amount_cents"] == 320000


def test_unposted_depreciation_blocks_the_asset_step() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=1,
            year=2026,
            year_status="OPEN",
            property_count=1,
            asset_count=2,
            depreciable_asset_count=1,
            calculated_period_count=3,
            close_errors=(
                ("DEPRECIATION_UNPOSTED", "Des dotations calculées ne sont pas comptabilisées."),
            ),
            dossier=_dossier(year_status="OPEN", year=2026, fiscal_year_id=1),
        )
    )
    assets = _step(payload, "assets")
    assert assets["status"] == "bloque"
    assert assets["prerequisites"][0]["action"]["href"] == "/immobilisations#dotations"
    assert payload["continue"]["href"] == "/immobilisations#dotations"


def test_posted_dotations_without_the_asset_on_the_ledger_are_not_done() -> None:
    common: dict[str, Any] = {
        "activity_present": True,
        "siren_present": True,
        "year_id": 1,
        "year": 2026,
        "year_status": "OPEN",
        "property_count": 1,
        "asset_count": 1,
        "depreciable_asset_count": 1,
        "posted_period_count": 1,
        "posted_depreciation_cents": 12092,
        "dossier": _dossier(year_status="OPEN", year=2026, fiscal_year_id=1),
    }
    missing = _board(_facts(**common, asset_booking="entry"))
    assets = _step(missing, "assets")
    assert assets["status_label"] != "Terminé"
    assert assets["status"] == "en_cours"
    assert assets["prerequisites"][0]["code"] == "ASSET_NOT_BOOKED"
    assert assets["prerequisites"][0]["action"]["href"] == "/immobilisations#entree-bien"
    purchase = _step(_board(_facts(**common, asset_booking="journal")), "assets")
    assert purchase["status_label"] != "Terminé"
    journal = "/comptabilite/brouillons#nouvelle-ecriture"
    assert purchase["prerequisites"][0]["action"]["href"] == journal
    blocked = _board(
        _facts(
            **common,
            asset_booking="entry",
            close_errors=(
                (
                    "IMMOBILISATIONS_ECART",
                    "Le registre des immobilisations ne retrouve pas les comptes 21, 28 et 681.",
                ),
            ),
        )
    )
    assert _step(blocked, "assets")["status"] == "bloque"
    done = _step(_board(_facts(**common, asset_booking="ok")), "assets")
    assert done["status"] == "fait"
    assert done["status_label"] == "Terminé"


def test_negative_net_assets_keep_the_step_blocked_after_booking() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=1,
            year=2026,
            year_status="OPEN",
            property_count=1,
            asset_count=1,
            depreciable_asset_count=1,
            posted_period_count=1,
            posted_depreciation_cents=10000,
            asset_booking="ok",
            close_errors=(
                (
                    "IMMOBILISATIONS_NETTES_NEGATIVES",
                    "La case 030 du 2033-A (immobilisations corporelles nettes) est négative.",
                ),
            ),
            dossier=_dossier(year_status="OPEN", year=2026, fiscal_year_id=1),
        )
    )
    assets = _step(payload, "assets")
    assert assets["status"] == "bloque"
    assert assets["status_label"] != "Terminé"
    assert assets["prerequisites"][0]["code"] == "IMMOBILISATIONS_NETTES_NEGATIVES"
    assert assets["prerequisites"][0]["action"]["href"] == "/immobilisations#entree-bien"


def test_closed_research_year_with_a_final_fec_is_done() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=1,
            year=2025,
            year_status="CLOSED",
            property_count=1,
            bank_count=1,
            operation_count=1,
            operation_amount_cents=100,
            fiscal_produced=True,
            fiscal_result_cents=-4000,
            exports=_exports(liasse=_PROVISOIRE, fec=_FINALE),
            dossier=_dossier(
                "cloture", "Clôturé", year_status="CLOSED", year=2025, fiscal_year_id=1
            ),
        )
    )
    assert _step(payload, "closing")["status"] == "fait"
    assert _step(payload, "filing")["status"] == "fait"
    assert _step(payload, "filing")["amount_cents"] == -4000
    assert "Finale" in _step(payload, "filing")["summary"]
    assert payload["continue"]["href"] == "/fiscalite#sorties-figees"


def test_first_year_transitions_follow_prerequisites_until_close() -> None:
    empty = _board(_facts())
    assert empty["progression"]["label"] == "0/6"
    assert empty["continue"]["href"] == "/comptabilite/brouillons#creer-activite"
    assert all(step["status_label"] == "À faire" for step in empty["steps"])

    activity = _board(_facts(activity_present=True))
    assert _step(activity, "structure")["status_label"] == "En cours"
    assert activity["continue"]["href"] == "/comptabilite/brouillons#ajouter-exercice"
    assert activity["progression"]["done"] == 0

    year = _board(
        _facts(
            activity_present=True,
            year_id=1,
            year=2026,
            year_status="OPEN",
            close_errors=(("FISCAL_NOT_COMPUTED", "Aucun calcul fiscal n’est enregistré."),),
            dossier=_dossier(year_status="OPEN", year=2026, fiscal_year_id=1),
        )
    )
    assert _step(year, "opening")["status_label"] == "Terminé"
    assert "Premier exercice" in _step(year, "opening")["summary"]
    assert year["continue"]["href"] == "/comptabilite/brouillons#identite-liasse"
    assert year["progression"]["done"] == 1

    common: dict[str, Any] = {
        "activity_present": True,
        "siren_present": True,
        "year_id": 1,
        "year": 2026,
        "year_status": "OPEN",
        "property_count": 1,
        "bank_count": 1,
        "dossier": _dossier(year_status="OPEN", year=2026, fiscal_year_id=1),
    }
    missing_fiscal = (("FISCAL_NOT_COMPUTED", "Aucun calcul fiscal n’est enregistré."),)
    ready_to_record = _board(_facts(**common, close_errors=missing_fiscal))
    assert _step(ready_to_record, "structure")["status_label"] == "Terminé"
    assert _step(ready_to_record, "operations")["status_label"] == "En cours"
    assert ready_to_record["continue"]["href"] == "/operations/biens"
    assert ready_to_record["progression"]["done"] == 2

    with_operations = _board(_facts(**common, operation_count=2, operation_amount_cents=15000))
    assert _step(with_operations, "operations")["status_label"] == "Terminé"
    assert _step(with_operations, "operations")["amount_cents"] == 15000
    assert with_operations["continue"]["href"] == "/immobilisations#nouvelle-immobilisation"
    assert with_operations["progression"]["done"] == 3

    blocked_assets = _board(
        _facts(
            **common,
            operation_count=1,
            operation_amount_cents=100,
            asset_count=2,
            depreciable_asset_count=1,
            calculated_period_count=1,
            close_errors=(
                ("DEPRECIATION_UNPOSTED", "Des dotations calculées ne sont pas comptabilisées."),
            ),
        )
    )
    assert _step(blocked_assets, "assets")["status_label"] == "Bloqué"
    assert blocked_assets["continue"]["href"] == "/immobilisations#dotations"
    assert blocked_assets["progression"]["done"] == 3

    ready = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=1,
            year=2026,
            year_status="READY_TO_CLOSE",
            property_count=1,
            bank_count=1,
            operation_count=1,
            operation_amount_cents=10000,
            asset_count=1,
            depreciable_asset_count=1,
            posted_period_count=1,
            posted_depreciation_cents=2500,
            fiscal_produced=True,
            fiscal_result_cents=0,
            exports=_exports(liasse=_PROVISOIRE, fec=_BLOQUEE),
            dossier=_dossier(
                "pret_a_verifier",
                "Prêt à vérifier",
                year_status="READY_TO_CLOSE",
                year=2026,
                fiscal_year_id=1,
            ),
        )
    )
    assert _step(ready, "closing")["status_label"] == "Prête"
    assert ready["continue"]["href"] == "/fiscalite#close-title"
    assert ready["continue"]["detail"] == "Prochaine action : confirmer la clôture."
    assert ready["progression"]["done"] == 4

    closed = _board(
        _facts(
            activity_present=True,
            siren_present=True,
            year_id=1,
            year=2026,
            year_status="CLOSED",
            property_count=1,
            bank_count=1,
            operation_count=1,
            operation_amount_cents=10000,
            asset_count=1,
            depreciable_asset_count=1,
            posted_period_count=1,
            posted_depreciation_cents=2500,
            fiscal_produced=True,
            fiscal_result_cents=0,
            exports=_exports(liasse=_PROVISOIRE, fec=_FINALE),
            dossier=_dossier(
                "cloture", "Clôturé", year_status="CLOSED", year=2026, fiscal_year_id=1
            ),
        )
    )
    assert _step(closed, "closing")["status_label"] == "Terminé"
    assert _step(closed, "filing")["status_label"] == "Terminé"
    assert closed["progression"]["label"] == "6/6"
    assert closed["continue"]["href"] == "/fiscalite#sorties-figees"
    assert "recherche" in _step(closed, "filing")["summary"].lower()
    dones = [
        board["progression"]["done"]
        for board in (
            empty,
            activity,
            year,
            ready_to_record,
            with_operations,
            blocked_assets,
            ready,
            closed,
        )
    ]
    assert dones == sorted(dones)


def test_following_year_opening_transitions_before_the_precheck() -> None:
    base: dict[str, Any] = {
        "activity_present": True,
        "siren_present": True,
        "year_id": 2,
        "year": 2026,
        "year_status": "OPEN",
        "property_count": 1,
        "bank_count": 1,
        "operation_count": 1,
        "operation_amount_cents": 5000,
        "asset_count": 1,
        "depreciable_asset_count": 1,
        "posted_period_count": 1,
        "posted_depreciation_cents": 1000,
        "has_previous_year": True,
        "previous_year_closed": False,
        "dossier": _dossier(year_status="OPEN", year=2026, fiscal_year_id=2),
    }
    blocked = _board(_facts(**base))
    opening = _step(blocked, "opening")
    assert opening["status_label"] == "Bloqué"
    assert opening["prerequisites"][0]["code"] == "SOURCE_NOT_CLOSED"
    assert opening["prerequisites"][0]["action"] == {
        "label": "Clôturer l’exercice précédent",
        "href": "/fiscalite#close-title",
    }
    assert blocked["continue"]["href"] == "/fiscalite#close-title"
    assert blocked["continue"]["step"] == "opening"
    assert blocked["progression"]["current_status_label"] == "Bloqué"

    waiting = _board(_facts(**{**base, "previous_year_closed": True}))
    opening = _step(waiting, "opening")
    assert opening["status_label"] == "En cours"
    assert opening["prerequisites"][0]["code"] == "OPENING_MISSING"
    assert opening["prerequisites"][0]["action"]["href"] == "/etats-comptables#opening-title"
    assert _step(waiting, "closing")["status"] == "pret"
    assert waiting["continue"]["step"] == "opening"
    assert waiting["continue"]["href"] == "/etats-comptables#opening-title"
    assert waiting["progression"]["done"] == blocked["progression"]["done"]

    conflict = _board(_facts(**{**base, "previous_year_closed": True, "target_has_entries": True}))
    assert _step(conflict, "opening")["status_label"] == "Bloqué"
    assert conflict["continue"]["href"] == "/comptabilite/journal"
    assert conflict["progression"]["current_step"] == "opening"

    posted = _board(
        _facts(
            **{
                **base,
                "previous_year_closed": True,
                "opening_posted": True,
                "opening_amount_cents": 250050,
                "close_errors": (("FISCAL_NOT_COMPUTED", "Aucun calcul fiscal n’est enregistré."),),
            }
        )
    )
    opening = _step(posted, "opening")
    assert opening["status_label"] == "Terminé"
    assert opening["amount_cents"] == 250050
    assert "comptabilisés" in opening["summary"]
    assert posted["progression"]["done"] == waiting["progression"]["done"] + 1
    assert posted["continue"]["href"] == "/fiscalite#calcul-fiscal"
    assert posted["continue"]["step"] == "closing"
    assert posted["dossier"]["vintage_status"] == "research_only"


def test_a_declarable_label_is_refused() -> None:
    facts = _facts(dossier={**_dossier(), "label": "Déclarable", "vintage_status": "research_only"})
    with pytest.raises(ValueError, match="déclarable"):
        build_dashboard(facts)


def test_latest_event_wins_for_the_step() -> None:
    payload = _board(
        _facts(
            activity_present=True,
            events=(
                EventFact("structure", datetime(2026, 1, 1, 8, 0, 0), "Activité créée"),
                EventFact("structure", datetime(2026, 1, 2, 8, 0, 0), "Exercice 2026 créé"),
            ),
            dossier=_dossier(),
        )
    )
    assert _step(payload, "structure")["last_event"]["label"] == "Exercice 2026 créé"
