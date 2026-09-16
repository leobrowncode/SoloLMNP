from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal, localcontext
from typing import cast

import pytest

from app.domain.accounting.entities import AccountingEntry, AccountingEntryLine, EntryStatus


def make_entry(debit: str = "100.00", credit: str = "100.00") -> AccountingEntry:
    return AccountingEntry(
        fiscal_year_id=1,
        journal_code="BQ",
        entry_number="BQ-1",
        accounting_date=date(2025, 1, 1),
        piece_reference="P1",
        piece_date=date(2025, 1, 1),
        label="Loyer fictif",
        lines=(
            AccountingEntryLine("512000", "Banque", debit=Decimal(debit)),
            AccountingEntryLine("706000", "Loyer", credit=Decimal(credit)),
        ),
    )


def test_balanced_entry_validation_returns_immutable_value() -> None:
    draft = make_entry()
    validated = draft.validate()
    assert draft.status is EntryStatus.DRAFT
    assert validated.status is EntryStatus.VALIDATED
    assert validated.lines == draft.lines
    assert validated.validate() is validated


def test_unbalanced_entry_is_rejected() -> None:
    draft = make_entry("99.99", "100.00")
    with pytest.raises(ValueError, match="Unbalanced"):
        draft.validate()
    assert draft.status is EntryStatus.DRAFT


@pytest.mark.parametrize("amount", [100, 100.0, True, "100.00", None])
@pytest.mark.parametrize("side", ["debit", "credit"])
def test_non_decimal_amounts_are_rejected(amount: object, side: str) -> None:
    with pytest.raises(TypeError, match="must be Decimal"):
        if side == "debit":
            AccountingEntryLine("512000", "Banque", debit=cast(Decimal, amount))
        else:
            AccountingEntryLine("512000", "Banque", credit=cast(Decimal, amount))


@pytest.mark.parametrize("amount", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_nonfinite_amounts_are_rejected(amount: str) -> None:
    with pytest.raises(ValueError, match="finite"):
        AccountingEntryLine("512000", "Banque", debit=Decimal(amount))


@pytest.mark.parametrize("amount", ["0.001", "100.001", "100.01001", "1E-100"])
def test_subcent_amounts_are_rejected_without_rounding(amount: str) -> None:
    with pytest.raises(ValueError, match="exact cents"):
        AccountingEntryLine("512000", "Banque", debit=Decimal(amount))


@pytest.mark.parametrize("amount", ["0.01", "100.000", "100.01000", "1E+30"])
def test_exact_cent_amounts_accept_trailing_zeros(amount: str) -> None:
    line = AccountingEntryLine("512000", "Banque", debit=Decimal(amount))
    assert line.debit == Decimal(amount)


@pytest.mark.parametrize("debit,credit", [("-1", "0"), ("0", "-1"), ("0", "0"), ("1", "1")])
def test_line_requires_exactly_one_positive_side(debit: str, credit: str) -> None:
    with pytest.raises(ValueError):
        AccountingEntryLine("512000", "Banque", Decimal(debit), Decimal(credit))


@pytest.mark.parametrize("line_count", [0, 1])
def test_entry_requires_at_least_two_lines(line_count: int) -> None:
    draft = make_entry()
    incomplete = replace(draft, lines=draft.lines[:line_count])
    with pytest.raises(ValueError, match="at least two"):
        incomplete.validate()


def test_caller_list_cannot_mutate_entry() -> None:
    original = make_entry()
    caller_lines = list(original.lines)
    entry = replace(original, lines=cast(tuple[AccountingEntryLine, ...], caller_lines))
    validated = entry.validate()
    caller_lines.clear()
    assert len(entry.lines) == len(validated.lines) == 2


def test_invalid_line_objects_are_rejected() -> None:
    with pytest.raises(TypeError, match="AccountingEntryLine"):
        replace(make_entry(), lines=cast(tuple[AccountingEntryLine, ...], (object(),)))


def test_validated_values_reject_normal_mutation() -> None:
    validated = make_entry().validate()
    mutations = (
        (validated, "lines", ()),
        (validated, "accounting_date", date(2026, 1, 1)),
        (validated.lines[0], "debit", Decimal("1.00")),
        (validated, "status", EntryStatus.DRAFT),
    )
    for target, field_name, value in mutations:
        with pytest.raises(FrozenInstanceError):
            setattr(target, field_name, value)


def test_status_cannot_be_supplied_through_constructor_or_replace() -> None:
    with pytest.raises(TypeError, match="status"):
        AccountingEntry(status=EntryStatus.VALIDATED)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="init=False"):
        replace(make_entry(), status=EntryStatus.VALIDATED)
    altered = replace(make_entry().validate(), lines=())
    assert altered.status is EntryStatus.DRAFT
    with pytest.raises(ValueError, match="at least two"):
        altered.validate()


def test_decimal_context_cannot_hide_an_imbalance() -> None:
    with localcontext() as context:
        context.prec = 3
        with pytest.raises(ValueError, match="Unbalanced"):
            make_entry(
                "1000000000000000000000000000000.01",
                "1000000000000000000000000000000.02",
            ).validate()
