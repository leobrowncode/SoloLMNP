"""Immutable ledger value contracts; persistence and posting belong to Phase 2."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, localcontext
from enum import StrEnum

ZERO = Decimal("0.00")


def _check_amount(amount: Decimal) -> None:
    if not isinstance(amount, Decimal):
        raise TypeError("Accounting amounts must be Decimal values")
    if not amount.is_finite():
        raise ValueError("Accounting amounts must be finite")
    if amount < ZERO:
        raise ValueError("Debit and credit must be non-negative")
    # Inspect digits instead of rounding: this works independently of Decimal context.
    decimal_tuple = amount.as_tuple()
    exponent = decimal_tuple.exponent
    if isinstance(exponent, int) and exponent < -2 and any(decimal_tuple.digits[exponent + 2 :]):
        raise ValueError("Accounting amounts must be exact cents")


class EntryStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"


@dataclass(frozen=True, slots=True)
class AccountingEntryLine:
    account_number: str
    label: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO

    def __post_init__(self) -> None:
        _check_amount(self.debit)
        _check_amount(self.credit)
        if (self.debit == ZERO) == (self.credit == ZERO):
            raise ValueError("Exactly one of debit or credit must be positive")


@dataclass(frozen=True, slots=True)
class AccountingEntry:
    fiscal_year_id: int
    journal_code: str
    entry_number: str
    accounting_date: date
    piece_reference: str
    piece_date: date
    label: str
    lines: tuple[AccountingEntryLine, ...] = field(default_factory=tuple)
    status: EntryStatus = field(default=EntryStatus.DRAFT, init=False)

    def __post_init__(self) -> None:
        # Copy iterables so retaining an input list cannot mutate this value later.
        immutable_lines = tuple(self.lines)
        if not all(isinstance(line, AccountingEntryLine) for line in immutable_lines):
            raise TypeError("Entry lines must be AccountingEntryLine values")
        object.__setattr__(self, "lines", immutable_lines)

    def validate(self) -> AccountingEntry:
        """Return a validated value without mutating the draft or its source lines.

        This checks the local value contract only. Account existence, fiscal-year
        locks and atomic persistence require the future posting service.
        """
        if len(self.lines) < 2:
            raise ValueError("An entry needs at least two lines")
        amounts = tuple(amount for line in self.lines for amount in (line.debit, line.credit))
        # Enough precision for every integer digit, cents and a possible sum carry.
        # A caller's low Decimal precision must never hide an imbalance.
        with localcontext() as context:
            context.prec = max(
                28,
                max(amount.adjusted() + 1 for amount in amounts) + 2 + len(str(len(self.lines))),
            )
            debit = sum((line.debit for line in self.lines), ZERO)
            credit = sum((line.credit for line in self.lines), ZERO)
        if debit != credit:
            raise ValueError(f"Unbalanced entry: debit={debit} credit={credit}")
        if self.status is EntryStatus.VALIDATED:
            return self
        validated_entry = replace(self)
        object.__setattr__(validated_entry, "status", EntryStatus.VALIDATED)
        return validated_entry
