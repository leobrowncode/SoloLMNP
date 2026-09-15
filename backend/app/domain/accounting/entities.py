"""Framework-independent ledger contracts for Phase 2 implementation."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

ZERO = Decimal("0.00")

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
        if self.debit < ZERO or self.credit < ZERO:
            raise ValueError("Debit and credit must be non-negative")
        if (self.debit == ZERO) == (self.credit == ZERO):
            raise ValueError("Exactly one of debit or credit must be positive")

@dataclass(slots=True)
class AccountingEntry:
    fiscal_year_id: int
    journal_code: str
    entry_number: str
    accounting_date: date
    piece_reference: str
    piece_date: date
    label: str
    lines: list[AccountingEntryLine] = field(default_factory=list)
    status: EntryStatus = EntryStatus.DRAFT

    def validate(self) -> None:
        if len(self.lines) < 2:
            raise ValueError("An entry needs at least two lines")
        debit = sum((line.debit for line in self.lines), ZERO)
        credit = sum((line.credit for line in self.lines), ZERO)
        if debit != credit:
            raise ValueError(f"Unbalanced entry: debit={debit} credit={credit}")
        self.status = EntryStatus.VALIDATED
