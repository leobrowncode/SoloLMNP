"""Register gross against the ledger, in integer cents, without a fiscal guess."""

from datetime import date

import pytest

from app.domain.accounting.centralization import STALE_CODE, stale_error
from app.domain.assets.registration import (
    ECART_CODE,
    ENTRY_CODE,
    JOURNAL_CODE,
    NET_CODE,
    RegisterPiece,
    gap_error,
    negative_net_error,
    posting_refusal,
    registration_gap,
)

YEAR_START = date(2025, 1, 1)
YEAR_END = date(2025, 12, 31)


def test_a_shortfall_from_before_the_exercise_points_to_the_property_entry() -> None:
    short, fix = registration_gap(
        [RegisterPiece("213000", 8_000_000, YEAR_START)],
        {},
        as_of=YEAR_END,
        year_start=YEAR_START,
    )
    assert short == {"213000": 8_000_000}
    assert fix == "entry"
    refusal = posting_refusal(fix)
    assert refusal["code"] == ENTRY_CODE
    assert "entrer" in str(refusal["message"])
    action = refusal["action"]
    assert isinstance(action, dict)
    assert action["href"] == "/immobilisations#entree-bien"
    assert action["label"] == "Faire entrer le bien en comptabilité"


def test_an_in_year_purchase_points_to_a_journal_entry() -> None:
    short, fix = registration_gap(
        [RegisterPiece("218400", 120_000, date(2025, 7, 1))],
        {"218400": 0},
        as_of=YEAR_END,
        year_start=YEAR_START,
    )
    assert short == {"218400": 120_000}
    assert fix == "journal"
    refusal = posting_refusal(fix)
    assert refusal["code"] == JOURNAL_CODE
    action = refusal["action"]
    assert isinstance(action, dict)
    assert action["href"] == "/comptabilite/brouillons#nouvelle-ecriture"


def test_a_shared_account_uses_the_whole_register_and_a_covered_gross_is_ok() -> None:
    pieces = [
        RegisterPiece("218400", 120_000, date(2025, 7, 1)),
        RegisterPiece("218400", 80_000, date(2025, 8, 1)),
    ]
    short, fix = registration_gap(
        pieces, {"218400": 120_000}, as_of=YEAR_END, year_start=YEAR_START
    )
    assert short == {"218400": 80_000}
    assert fix == "journal"
    covered, ok = registration_gap(
        pieces, {"218400": 200_000}, as_of=YEAR_END, year_start=YEAR_START
    )
    assert covered == {}
    assert ok == "ok"
    scoped, scoped_fix = registration_gap(
        pieces,
        {"218400": 200_000},
        as_of=YEAR_END,
        year_start=YEAR_START,
        accounts={"213000"},
    )
    assert scoped == {}
    assert scoped_fix == "ok"


def test_register_gap_and_negative_box_030_block_without_acknowledgement() -> None:
    assert gap_error((1, 2, 3), (1, 2, 3)) is None
    gap = gap_error((8_000_000, 0, 0), (0, 10_000, 10_000))
    assert gap is not None
    assert gap["code"] == ECART_CODE
    assert "ne peut pas être accusé" in gap["message"]
    assert negative_net_error(0) is None
    assert negative_net_error(1) is None
    negative = negative_net_error(-420_151)
    assert negative is not None
    assert negative["code"] == NET_CODE
    assert "030" in negative["message"]
    stale = stale_error()
    assert stale["code"] == STALE_CODE
    assert "recentralis" in stale["message"]


def test_amounts_stay_integer_cents() -> None:
    with pytest.raises(TypeError):
        registration_gap(
            [RegisterPiece("213000", 1.5, YEAR_START)],  # type: ignore[arg-type]
            {},
            as_of=YEAR_END,
            year_start=YEAR_START,
        )
    with pytest.raises(ValueError):
        posting_refusal("ok")
