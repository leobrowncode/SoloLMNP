"""Local single-user ledger API; every write is a serialized transaction."""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import (
    AccountInput,
    ActiveInput,
    ActivityInput,
    EditInput,
    EntryInput,
    JournalInput,
    ReversalInput,
    VersionInput,
    YearInput,
)
from app.api.sessions import dependencies
from app.core.database import Database
from app.domain.accounting.chart import INITIAL_ACCOUNTS, INITIAL_JOURNALS
from app.models import (
    Account,
    AccountingEntry,
    AccountingEntryLine,
    AccountingJournal,
    FiscalYear,
    LedgerEvent,
    RentalActivity,
)
from app.services.ledger import (
    check_draft,
    create_draft,
    entry_json,
    event,
    fail,
    get_entry,
    get_year,
    post_entry,
    projection,
    replace_draft,
    reverse_entry,
)
from app.services.opening import opening_preview
from app.services.statements import statements


def build_ledger_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/api/ledger", tags=["ledger"])

    read_session, write_session = dependencies(database)

    Read = Annotated[Session, Depends(read_session)]
    Write = Annotated[Session, Depends(write_session, scope="function")]

    @router.get("/setup")
    def setup(session: Read) -> dict[str, Any]:
        activity = session.get(RentalActivity, 1)
        years = session.scalars(select(FiscalYear).order_by(FiscalYear.year.desc())).all()
        return {
            "activity": {
                "id": activity.id,
                "activity_name": activity.activity_name,
                "activity_start_date": activity.activity_start_date.isoformat(),
            }
            if activity
            else None,
            "years": [
                {
                    "id": year.id,
                    "year": year.year,
                    "start_date": year.start_date.isoformat(),
                    "end_date": year.end_date.isoformat(),
                    "fiscal_vintage": year.fiscal_vintage,
                    "status": year.status,
                }
                for year in years
            ],
        }

    @router.post("/activity", status_code=201)
    def create_activity(data: ActivityInput, session: Write) -> dict[str, Any]:
        if session.get(RentalActivity, 1):
            fail("ACTIVITY_EXISTS", "Cette instance possède déjà une activité.")
        activity = RentalActivity(**data.model_dump())
        session.add(activity)
        for number, label, kind in INITIAL_ACCOUNTS:
            if not session.get(Account, number):
                session.add(Account(number=number, label=label, account_type=kind))
        for code, label, kind in INITIAL_JOURNALS:
            if not session.get(AccountingJournal, code):
                session.add(AccountingJournal(code=code, label=label, journal_type=kind))
        event(session, "ACTIVITY_CREATED", None, data.model_dump(mode="json"))
        return setup(session)

    @router.post("/years", status_code=201)
    def create_year(data: YearInput, session: Write) -> dict[str, Any]:
        activity = session.get(RentalActivity, 1)
        if not activity:
            fail("ACTIVITY_REQUIRED", "Créez l’activité avant l’exercice.", 422)
        if data.start_date < activity.activity_start_date:
            fail(
                "YEAR_BEFORE_ACTIVITY",
                "L’exercice ne peut pas précéder le début de l’activité.",
                422,
            )
        year = FiscalYear(rental_activity_id=1, **data.model_dump())
        session.add(year)
        event(session, "YEAR_CREATED", None, data.model_dump(mode="json"))
        return setup(session)

    @router.get("/accounts")
    def accounts(session: Read) -> list[dict[str, Any]]:
        return [
            {
                "number": a.number,
                "label": a.label,
                "account_type": a.account_type,
                "active": a.active,
            }
            for a in session.scalars(select(Account).order_by(Account.number))
        ]

    @router.post("/accounts", status_code=201)
    def create_account(data: AccountInput, session: Write) -> dict[str, Any]:
        if session.get(Account, data.number):
            fail("ACCOUNT_EXISTS", "Ce numéro de compte existe déjà.")
        row = Account(**data.model_dump())
        session.add(row)
        event(session, "ACCOUNT_CREATED", None, data.model_dump())
        return {
            "number": row.number,
            "label": row.label,
            "account_type": row.account_type,
            "active": row.active,
        }

    @router.patch("/accounts/{number}/active")
    def account_active(number: str, data: ActiveInput, session: Write) -> dict[str, Any]:
        row = session.get(Account, number)
        if not row:
            fail("ACCOUNT_NOT_FOUND", "Compte introuvable.", 404)
        assert row is not None  # noqa: S101
        before = row.active
        row.active = data.active
        event(
            session,
            "ACCOUNT_ACTIVE_CHANGED",
            None,
            {"number": number, "before": before, "after": row.active},
        )
        return {"number": number, "active": row.active}

    @router.get("/journals")
    def journals(session: Read) -> list[dict[str, Any]]:
        return [
            {"code": j.code, "label": j.label, "journal_type": j.journal_type, "active": j.active}
            for j in session.scalars(select(AccountingJournal).order_by(AccountingJournal.code))
        ]

    @router.post("/journals", status_code=201)
    def create_journal(data: JournalInput, session: Write) -> dict[str, Any]:
        if session.get(AccountingJournal, data.code):
            fail("JOURNAL_EXISTS", "Ce code de journal existe déjà.")
        row = AccountingJournal(**data.model_dump())
        session.add(row)
        event(session, "JOURNAL_CREATED", None, data.model_dump())
        return {
            "code": row.code,
            "label": row.label,
            "journal_type": row.journal_type,
            "active": row.active,
        }

    @router.patch("/journals/{code}/active")
    def journal_active(code: str, data: ActiveInput, session: Write) -> dict[str, Any]:
        row = session.get(AccountingJournal, code)
        if not row:
            fail("JOURNAL_NOT_FOUND", "Journal introuvable.", 404)
        assert row is not None  # noqa: S101
        before = row.active
        row.active = data.active
        event(
            session,
            "JOURNAL_ACTIVE_CHANGED",
            None,
            {"code": code, "before": before, "after": row.active},
        )
        return {"code": code, "active": row.active}

    @router.get("/entries")
    def entries(
        session: Read,
        fiscal_year_id: int,
        status: Literal["DRAFT", "VALIDATED"] | None = None,
        journal_code: str | None = None,
        account_number: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        piece: str | None = None,
        source: Literal[
            "MANUAL", "REVERSAL", "REVENUE", "EXPENSE", "SETTLEMENT", "LOAN_PAYMENT", "LOAN_FUNDING"
        ]
        | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        get_year(session, fiscal_year_id)
        query = select(AccountingEntry).where(AccountingEntry.fiscal_year_id == fiscal_year_id)
        if date_from and date_to and date_from > date_to:
            fail("INVALID_DATE_RANGE", "La période de filtrage est inversée.", 422)
        if status:
            query = query.where(AccountingEntry.status == status)
        if journal_code:
            query = query.where(AccountingEntry.journal_code == journal_code)
        if account_number:
            query = query.where(
                AccountingEntry.lines.any(AccountingEntryLine.account_number == account_number)
            )
        if date_from:
            query = query.where(AccountingEntry.accounting_date >= date_from)
        if date_to:
            query = query.where(AccountingEntry.accounting_date <= date_to)
        if piece:
            query = query.where(AccountingEntry.piece_reference.contains(piece, autoescape=True))
        if source:
            query = query.where(AccountingEntry.source_type == source)
        count = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.scalars(
            query.order_by(
                AccountingEntry.accounting_date, AccountingEntry.sequence, AccountingEntry.id
            )
            .limit(limit)
            .offset(offset)
        )
        return {
            "entries": [entry_json(row) for row in rows],
            "count": count,
            "limit": limit,
            "offset": offset,
        }

    @router.get("/entries/{entry_id}")
    def entry(entry_id: int, session: Read) -> dict[str, Any]:
        return entry_json(get_entry(session, entry_id))

    @router.post("/entries", status_code=201)
    def create(data: EntryInput, session: Write) -> dict[str, Any]:
        return entry_json(create_draft(session, data))

    @router.put("/entries/{entry_id}")
    def edit(entry_id: int, data: EditInput, session: Write) -> dict[str, Any]:
        row = get_entry(session, entry_id)
        replace_draft(session, row, data, data.expected_version)
        return entry_json(row)

    @router.delete("/entries/{entry_id}")
    def delete(entry_id: int, data: VersionInput, session: Write) -> dict[str, bool]:
        row = get_entry(session, entry_id)
        check_draft(row, data.expected_version)
        get_year(session, row.fiscal_year_id, writable=True)
        event(session, "DRAFT_DELETED", row, {"before": entry_json(row)})
        session.delete(row)
        session.flush()
        return {"deleted": True}

    @router.post("/entries/{entry_id}/validate")
    def validate(entry_id: int, data: VersionInput, session: Write) -> dict[str, Any]:
        return entry_json(post_entry(session, get_entry(session, entry_id), data.expected_version))

    @router.post("/entries/{entry_id}/reverse", status_code=201)
    def reverse(entry_id: int, data: ReversalInput, session: Write) -> dict[str, Any]:
        return entry_json(reverse_entry(session, get_entry(session, entry_id), data))

    @router.get("/years/{year_id}/statements")
    def financial_statements(year_id: int, session: Read) -> dict[str, Any]:
        return statements(session, year_id)

    @router.get("/years/{year_id}/opening-preview")
    def preview_opening(year_id: int, session: Read) -> dict[str, Any]:
        return opening_preview(session, year_id)

    @router.get("/years/{year_id}/balance")
    def balance(year_id: int, session: Read) -> dict[str, Any]:
        result = projection(session, year_id)
        del result["ledger"]
        return result

    @router.get("/years/{year_id}/general-ledger")
    def general_ledger(year_id: int, session: Read, account_number: str) -> dict[str, Any]:
        if session.get(Account, account_number) is None:
            fail("ACCOUNT_NOT_FOUND", "Compte introuvable.", 404)
        result = projection(session, year_id, account_number)
        return {
            "fiscal_year_id": year_id,
            "account_number": account_number,
            "validated_only": True,
            "lines": result["ledger"],
        }

    @router.get("/entries/{entry_id}/events")
    def events(entry_id: int, session: Read) -> list[dict[str, Any]]:
        # Deleted draft IDs remain queryable through this append-only journal.
        return [
            {
                "id": e.id,
                "action": e.action,
                "timestamp": e.timestamp.isoformat() + "Z",
                "details": e.details,
            }
            for e in session.scalars(
                select(LedgerEvent).where(LedgerEvent.entry_id == entry_id).order_by(LedgerEvent.id)
            )
        ]

    return router
