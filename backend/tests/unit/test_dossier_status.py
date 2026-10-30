"""Dossier status is closing plus fiscal and export posture, never déclarable."""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.dossier import DOSSIER_LABELS, classify_dossier, public_dossier

_PROVISOIRE = {"posture": "provisoire", "label": "Provisoire", "download": True}
_BLOQUEE = {"posture": "bloquee", "label": "Bloquée", "download": False}
_FINALE = {"posture": "finale", "label": "Finale", "download": True}


def _exports(*, liasse: dict[str, Any], fec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {"liasse": liasse, "pdf": liasse, "fec": fec, "archive": fec}


def _view(
    *,
    year_status: str | None,
    output_status: str | None,
    exports: dict[str, Any] | None,
    produced: bool,
    fiscal_year_id: int | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    payload = public_dossier(
        year_status=year_status,
        output_status=output_status,
        exports=exports,
        produced=produced,
        fiscal_year_id=fiscal_year_id,
        year=year,
    )
    assert payload["vintage_status"] == "research_only"
    assert payload["label"] == DOSSIER_LABELS[str(payload["status"])]
    assert "declarable" not in payload
    assert "Déclarable" not in str(payload["label"])
    return payload


def test_missing_year_is_incomplete() -> None:
    shown = _view(year_status=None, output_status=None, exports=None, produced=False)
    assert shown["status"] == "incomplet"
    assert shown["label"] == "Incomplet"
    assert shown["fiscal_year_id"] is None


@pytest.mark.parametrize("output_status", ["recherche", "provisoire", "declarable"])
def test_open_year_without_a_calculation_stays_incomplete(output_status: str) -> None:
    shown = _view(
        year_status="OPEN",
        output_status=output_status,
        exports=_exports(liasse=_BLOQUEE, fec=_BLOQUEE),
        produced=False,
        fiscal_year_id=1,
        year=2026,
    )
    assert shown["status"] == "incomplet"
    assert shown["year_status"] == "OPEN"


def test_blocked_liasse_blocks_the_dossier_even_when_the_trust_is_declarable() -> None:
    shown = _view(
        year_status="OPEN",
        output_status="declarable",
        exports=_exports(liasse=_BLOQUEE, fec=_BLOQUEE),
        produced=True,
        fiscal_year_id=1,
        year=2026,
    )
    assert shown["status"] == "bloque"
    assert shown["label"] == "Bloqué"
    assert (
        classify_dossier(
            year_status="READY_TO_CLOSE",
            output_status="declarable",
            exports=_exports(liasse=_BLOQUEE, fec=_BLOQUEE),
            produced=True,
        )
        == "bloque"
    )


def test_open_research_sheet_is_ready_to_review_while_fec_stays_blocked() -> None:
    shown = _view(
        year_status="OPEN",
        output_status="recherche",
        exports=_exports(liasse=_PROVISOIRE, fec=_BLOQUEE),
        produced=True,
        fiscal_year_id=4,
        year=2026,
    )
    assert shown["status"] == "pret_a_verifier"
    assert shown["label"] == "Prêt à vérifier"


def test_declarable_trust_is_ready_to_review_not_a_dossier_label() -> None:
    shown = _view(
        year_status="READY_TO_CLOSE",
        output_status="declarable",
        exports=_exports(liasse=_PROVISOIRE, fec=_BLOQUEE),
        produced=True,
        fiscal_year_id=4,
        year=2026,
    )
    assert shown["status"] == "pret_a_verifier"
    assert shown["vintage_status"] == "research_only"


def test_unknown_fiscal_trust_stays_incomplete() -> None:
    assert (
        classify_dossier(
            year_status="OPEN",
            output_status="pret",
            exports=_exports(liasse=_PROVISOIRE, fec=_BLOQUEE),
            produced=True,
        )
        == "incomplet"
    )


def test_closed_research_year_with_a_final_fec_is_closed() -> None:
    shown = _view(
        year_status="CLOSED",
        output_status="recherche",
        exports=_exports(liasse=_PROVISOIRE, fec=_FINALE),
        produced=True,
        fiscal_year_id=1,
        year=2025,
    )
    assert shown["status"] == "cloture"
    assert shown["label"] == "Clôturé"


def test_closed_year_with_a_blocked_export_stays_blocked() -> None:
    assert (
        classify_dossier(
            year_status="CLOSED",
            output_status="declarable",
            exports=_exports(liasse=_FINALE, fec=_BLOQUEE),
            produced=True,
        )
        == "bloque"
    )
    assert (
        classify_dossier(
            year_status="CLOSED",
            output_status="recherche",
            exports=_exports(liasse=_BLOQUEE, fec=_FINALE),
            produced=True,
        )
        == "bloque"
    )


def test_missing_or_unknown_export_posture_blocks_a_produced_sheet() -> None:
    assert (
        classify_dossier(
            year_status="OPEN",
            output_status="recherche",
            exports=None,
            produced=True,
        )
        == "bloque"
    )
    assert (
        classify_dossier(
            year_status="CLOSED",
            output_status="recherche",
            exports={"liasse": {"posture": "inconnu"}, "fec": _FINALE},
            produced=True,
        )
        == "bloque"
    )


def test_closed_declarable_sheet_is_closed_not_declarable() -> None:
    shown = _view(
        year_status="CLOSED",
        output_status="declarable",
        exports=_exports(liasse=_FINALE, fec=_FINALE),
        produced=True,
        fiscal_year_id=1,
        year=2026,
    )
    assert shown["status"] == "cloture"
    assert shown["label"] == "Clôturé"
