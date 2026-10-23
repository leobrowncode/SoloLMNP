"""Minimal audited close. No result allocation and no new accounts."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccountingEntry, FiscalYear
from app.models.base import utc_now
from app.services.ledger import event, fail, get_year
from app.services.statements import statements


def year_state(year: FiscalYear) -> dict[str, Any]:
    return {
        "id": year.id,
        "year": year.year,
        "start_date": year.start_date.isoformat(),
        "end_date": year.end_date.isoformat(),
        "fiscal_vintage": year.fiscal_vintage,
        "status": year.status,
        "closed_at": year.closed_at.isoformat() + "Z" if year.closed_at else None,
        "reopened_at": year.reopened_at.isoformat() + "Z" if year.reopened_at else None,
        "reopening_reason": year.reopening_reason,
    }


def close_year(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    if year.status == "CLOSED":
        fail("YEAR_ALREADY_CLOSED", "Cet exercice est déjà clôturé.")
    if year.status != "OPEN":
        fail("YEAR_NOT_OPEN", "Seul un exercice ouvert peut être clôturé.")
    drafts = session.scalar(
        select(func.count())
        .select_from(AccountingEntry)
        .where(AccountingEntry.fiscal_year_id == year.id, AccountingEntry.status == "DRAFT")
    )
    if drafts:
        fail(
            "YEAR_HAS_DRAFTS",
            "Validez ou supprimez les brouillons avant de clôturer cet exercice.",
        )
    # The provisional statements refuse an unbalanced or misclassified ledger.
    # This close posts nothing and does not create accounts 120 or 129.
    report = statements(session, year.id)
    closed_at = utc_now()
    year.status = "CLOSED"
    year.closed_at = closed_at
    event(
        session,
        "YEAR_CLOSED",
        None,
        {
            "fiscal_year_id": year.id,
            "year": year.year,
            "previous_status": "OPEN",
            "closed_at": closed_at.isoformat() + "Z",
            "result": report["income_statement"]["result"],
            "allocates_result": False,
        },
    )
    return year_state(year)


def reopen_year(session: Session, year_id: int, reason: str) -> dict[str, Any]:
    year = get_year(session, year_id)
    if year.status != "CLOSED":
        fail("YEAR_NOT_CLOSED", "Seul un exercice clôturé peut être rouvert.")
    motive = reason.strip()
    if len(motive) < 5:
        fail("REOPEN_REASON_REQUIRED", "Indiquez un motif d’au moins 5 caractères.", 422)
    previous_closed_at = year.closed_at.isoformat() + "Z" if year.closed_at else None
    reopened_at = utc_now()
    year.status = "OPEN"
    year.closed_at = None
    year.reopened_at = reopened_at
    year.reopening_reason = motive
    event(
        session,
        "YEAR_REOPENED",
        None,
        {
            "fiscal_year_id": year.id,
            "year": year.year,
            "previous_status": "CLOSED",
            "previous_closed_at": previous_closed_at,
            "reopened_at": reopened_at.isoformat() + "Z",
            "reason": motive,
        },
    )
    return year_state(year)
