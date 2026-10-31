"""Compare the immobilisation register with validated ledger balances."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.domain.assets.registration import (
    Fix,
    RegisterPiece,
    posting_refusal,
    registration_gap,
)
from app.models import AccountingEntry, AccountingEntryLine, Asset, DepreciationSchedule, FiscalYear
from app.services.assets import gross_pieces
from app.services.ledger import fail, get_year


@dataclass(frozen=True, slots=True)
class RegistrationSnapshot:
    pieces: tuple[RegisterPiece, ...]
    ledger: dict[str, int]
    year_start: date
    year_end: date

    def booking_of(self, account: str) -> tuple[bool, Fix]:
        _short, fix = registration_gap(
            list(self.pieces),
            self.ledger,
            as_of=self.year_end,
            year_start=self.year_start,
            accounts={account},
        )
        return fix == "ok", fix

    def year_fix(self) -> Fix:
        _short, fix = registration_gap(
            list(self.pieces),
            self.ledger,
            as_of=self.year_end,
            year_start=self.year_start,
        )
        return fix


def load_registration(session: Session, year_id: int) -> RegistrationSnapshot:
    year = get_year(session, year_id)
    return _snapshot(session, year)


def year_asset_booking(session: Session, year: FiscalYear) -> Fix:
    """``ok`` when every register gross acquired by the year-end is on the ledger."""
    if not session.scalar(select(Asset.id).where(Asset.disposed_at.is_(None)).limit(1)):
        return "ok"
    return _snapshot(session, year).year_fix()


def require_schedule_booked(
    session: Session, schedule: DepreciationSchedule, year: FiscalYear
) -> None:
    """Refuse a dotation while the gross of its account is missing from the journal."""
    booked, fix = _snapshot(session, year).booking_of(schedule.asset_account)
    if booked:
        return
    refusal = posting_refusal(fix)
    code = refusal["code"]
    message = refusal["message"]
    action = refusal["action"]
    if not isinstance(code, str) or not isinstance(message, str) or not isinstance(action, dict):
        fail("ASSET_NOT_BOOKED", "Le brut du registre n’est pas au journal.")
    fail(code, message, action=action)


def _snapshot(session: Session, year: FiscalYear) -> RegistrationSnapshot:
    pieces: list[RegisterPiece] = []
    for asset in session.scalars(select(Asset).where(Asset.disposed_at.is_(None))):
        for account, cents, acquired, _label in gross_pieces(session, asset):
            pieces.append(RegisterPiece(account, cents, acquired))
    accounts = {piece.account for piece in pieces}
    return RegistrationSnapshot(
        pieces=tuple(pieces),
        ledger=_ledger_gross(session, year.id, accounts),
        year_start=year.start_date,
        year_end=year.end_date,
    )


def _ledger_gross(session: Session, year_id: int, accounts: set[str]) -> dict[str, int]:
    if not accounts:
        return {}
    rows = session.scalars(
        select(AccountingEntryLine)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .where(
            AccountingEntry.fiscal_year_id == year_id,
            AccountingEntry.status == "VALIDATED",
            AccountingEntryLine.account_number.in_(accounts),
        )
    )
    totals: dict[str, int] = {}
    for line in rows:
        net = to_cents(line.debit) - to_cents(line.credit)
        totals[line.account_number] = totals.get(line.account_number, 0) + net
    return totals
