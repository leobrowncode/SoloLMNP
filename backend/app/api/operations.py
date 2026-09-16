"""Operations, banking and loans; all writes share ledger transactions."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import ReversalInput
from app.api.operation_schemas import (
    BankInput,
    CSVInput,
    FundingInput,
    LoanInput,
    LoanPaymentInput,
    MatchInput,
    OperationInput,
    PropertyInput,
    ReasonInput,
    SettlementInput,
)
from app.api.sessions import dependencies
from app.core.database import Database
from app.core.money import to_cents
from app.models import AccountingEntryLine, Property, RentalActivity
from app.models.operations import BankAccount, BankMatch, BankTransaction, BusinessOperation, Loan
from app.services import operations as service
from app.services.ledger import entry_json, event, fail, money


def record(row: Any) -> dict[str, Any]:
    return {
        column.key: money(to_cents(value))
        if isinstance(value := getattr(row, column.key), Decimal)
        else value.isoformat()
        if isinstance(value, date | datetime)
        else value
        for column in inspect(type(row)).columns
    }


def build_operations_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/api/operations", tags=["operations"])
    read, write = dependencies(database)
    Read = Annotated[Session, Depends(read)]
    Write = Annotated[Session, Depends(write, scope="function")]

    @router.get("/properties")
    def properties(session: Read) -> list[dict[str, Any]]:
        return [record(row) for row in session.scalars(select(Property).order_by(Property.id))]

    @router.post("/properties", status_code=201)
    def property_create(data: PropertyInput, session: Write) -> dict[str, Any]:
        if session.get(RentalActivity, 1) is None:
            fail("ACTIVITY_REQUIRED", "Initialisez d’abord l’activité dans Comptabilité.", 422)
        row = Property(rental_activity_id=1, **data.model_dump())
        session.add(row)
        event(session, "PROPERTY_CREATED", None, data.model_dump(mode="json"))
        return record(row)

    @router.get("/banks")
    def banks(session: Read) -> list[dict[str, Any]]:
        return [
            record(row) for row in session.scalars(select(BankAccount).order_by(BankAccount.id))
        ]

    @router.post("/banks", status_code=201)
    def bank_create(data: BankInput, session: Write) -> dict[str, Any]:
        service.account(session, data.account_number, "512")
        row = BankAccount(**data.model_dump())
        session.add(row)
        event(session, "BANK_CREATED", None, data.model_dump())
        return record(row)

    @router.get("")
    def operations(
        session: Read,
        fiscal_year_id: int | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[dict[str, Any]]:
        query = select(BusinessOperation)
        if fiscal_year_id is not None:
            query = query.where(BusinessOperation.fiscal_year_id == fiscal_year_id)
        return [
            service.operation_json(session, row)
            for row in session.scalars(
                query.order_by(BusinessOperation.id.desc()).limit(limit).offset(offset)
            )
        ]

    @router.post("", status_code=201)
    def create(data: OperationInput, session: Write) -> dict[str, Any]:
        return service.operation_json(session, service.create_operation(session, data))

    @router.post("/{operation_id}/settle", status_code=201)
    def settle(operation_id: int, data: SettlementInput, session: Write) -> dict[str, Any]:
        return service.operation_json(session, service.settle(session, operation_id, data))

    @router.post("/{operation_id}/reverse", status_code=201)
    def reverse(operation_id: int, data: ReversalInput, session: Write) -> dict[str, Any]:
        return entry_json(service.cancel(session, operation_id, data))

    @router.get("/loans")
    def loans(session: Read) -> list[dict[str, Any]]:
        return [
            {**record(row), "remaining_principal": money(service.principal_balance(session, row))}
            for row in session.scalars(select(Loan).order_by(Loan.id))
        ]

    @router.post("/loans", status_code=201)
    def loan_create(data: LoanInput, session: Write) -> dict[str, Any]:
        service.property_exists(session, data.property_id)
        service.account(session, data.principal_account, "164")
        row = Loan(
            **data.model_dump(exclude={"interest_rate"}),
            interest_rate_basis_points=to_cents(data.interest_rate),
        )
        balance = service.principal_balance(session, row)
        if not 0 <= balance <= to_cents(data.initial_principal):
            fail("LOAN_OPENING_BALANCE", "Solde comptable incompatible avec le capital initial.")
        session.add(row)
        event(session, "LOAN_CREATED", None, data.model_dump(mode="json"))
        return {**record(row), "remaining_principal": money(balance)}

    @router.post("/loans/{loan_id}/fund", status_code=201)
    def fund(loan_id: int, data: FundingInput, session: Write) -> dict[str, Any]:
        return service.operation_json(session, service.loan_post(session, loan_id, data, True))

    @router.post("/loans/{loan_id}/payments", status_code=201)
    def payment(loan_id: int, data: LoanPaymentInput, session: Write) -> dict[str, Any]:
        return service.operation_json(session, service.loan_post(session, loan_id, data, False))

    @router.post("/bank/preview")
    def preview(data: CSVInput, session: Read) -> dict[str, Any]:
        return service.import_csv(session, data.bank_account_id, data.content, False)

    @router.post("/bank/import")
    def bank_import(data: CSVInput, session: Write) -> dict[str, Any]:
        return service.import_csv(session, data.bank_account_id, data.content, True)

    @router.get("/bank/transactions")
    def transactions(
        session: Read,
        bank_account_id: int,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[dict[str, Any]]:
        service.bank(session, bank_account_id)
        rows = session.scalars(
            select(BankTransaction)
            .where(BankTransaction.bank_account_id == bank_account_id)
            .order_by(BankTransaction.date, BankTransaction.id)
            .limit(limit)
            .offset(offset)
        )
        output = []
        for row in rows:
            match = session.get(BankMatch, row.id)
            line = session.get(AccountingEntryLine, match.entry_line_id) if match else None
            output.append(
                {
                    **record(row),
                    "matched_line_id": line.id if line else None,
                    "matched_entry_id": line.accounting_entry_id if line else None,
                }
            )
        return output

    @router.post("/bank/transactions/{transaction_id}/match")
    def match(transaction_id: int, data: MatchInput, session: Write) -> dict[str, Any]:
        return record(service.match(session, transaction_id, data.entry_line_id))

    @router.post("/bank/transactions/{transaction_id}/unmatch")
    def unmatch(transaction_id: int, data: ReasonInput, session: Write) -> dict[str, bool]:
        service.unmatch(session, transaction_id, data.reason)
        return {"unmatched": True}

    return router
