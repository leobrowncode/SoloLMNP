"""Operations, banking and loans; all writes share ledger transactions."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import ReversalInput
from app.api.operation_schemas import (
    BankCorrectionInput,
    BankInput,
    CsvAssistInput,
    CSVInput,
    CsvInspectInput,
    FundingInput,
    LoanCorrectionInput,
    LoanInput,
    LoanPaymentInput,
    LoanPaymentsCSVInput,
    MatchInput,
    OperationInput,
    OperationsCSVInput,
    PropertyCorrectionInput,
    PropertyInput,
    ReasonInput,
    RentScheduleInput,
    SettlementInput,
    TenantCorrectionInput,
    TenantInput,
)
from app.api.sessions import dependencies
from app.core.database import Database
from app.core.money import to_cents
from app.domain.csv_assistant import (
    PROFILES,
    TEMPLATE_NAMES,
    CsvReadError,
    Profile,
    inspect_content,
    is_profile,
    template_csv,
)
from app.models import AccountingEntryLine, Property, RentalActivity
from app.models.operations import (
    BankAccount,
    BankMatch,
    BankTransaction,
    BusinessOperation,
    Loan,
    Tenant,
)
from app.services import csv_assistant as assistant
from app.services import operations as service
from app.services import structuring
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
        return [
            structuring.present_property(session, row)
            for row in session.scalars(select(Property).order_by(Property.id))
        ]

    @router.post("/properties", status_code=201)
    def property_create(data: PropertyInput, session: Write) -> dict[str, Any]:
        if session.get(RentalActivity, 1) is None:
            fail("ACTIVITY_REQUIRED", "Initialisez d’abord l’activité dans Comptabilité.", 422)
        row = Property(rental_activity_id=1, **data.model_dump())
        session.add(row)
        event(session, "PROPERTY_CREATED", None, data.model_dump(mode="json"))
        return record(row)

    @router.patch("/properties/{property_id}")
    def property_correct(
        property_id: int, data: PropertyCorrectionInput, session: Write
    ) -> dict[str, Any]:
        return structuring.correct_property(session, property_id, data)

    @router.get("/properties/{property_id}/tenants")
    def tenants(property_id: int, session: Read) -> list[dict[str, Any]]:
        return [
            structuring.present_tenant(session, row)
            for row in session.scalars(
                select(Tenant).where(Tenant.property_id == property_id).order_by(Tenant.id)
            )
        ]

    @router.post("/properties/{property_id}/tenants", status_code=201)
    def tenant_create(property_id: int, data: TenantInput, session: Write) -> dict[str, Any]:
        return record(service.add_tenant(session, property_id, data))

    @router.patch("/properties/{property_id}/tenants/{tenant_id}")
    def tenant_correct(
        property_id: int, tenant_id: int, data: TenantCorrectionInput, session: Write
    ) -> dict[str, Any]:
        return structuring.correct_tenant(session, property_id, tenant_id, data)

    @router.post("/properties/{property_id}/rents", status_code=201)
    def rents(property_id: int, data: RentScheduleInput, session: Write) -> dict[str, int]:
        return service.schedule_rents(session, property_id, data)

    @router.get("/banks")
    def banks(session: Read) -> list[dict[str, Any]]:
        return [
            structuring.present_bank(session, row)
            for row in session.scalars(select(BankAccount).order_by(BankAccount.id))
        ]

    @router.post("/banks", status_code=201)
    def bank_create(data: BankInput, session: Write) -> dict[str, Any]:
        service.account(session, data.account_number, "512")
        row = BankAccount(**data.model_dump())
        session.add(row)
        event(session, "BANK_CREATED", None, data.model_dump())
        return record(row)

    @router.patch("/banks/{bank_id}")
    def bank_correct(bank_id: int, data: BankCorrectionInput, session: Write) -> dict[str, Any]:
        return structuring.correct_bank(session, bank_id, data)

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
            structuring.present_loan(session, row)
            for row in session.scalars(select(Loan).order_by(Loan.id))
        ]

    @router.post("/loans", status_code=201)
    def loan_create(data: LoanInput, session: Write) -> dict[str, Any]:
        service.property_exists(session, data.property_id)
        principal_account = service.allocate_principal_account(session, data.principal_account)
        payload = data.model_dump(exclude={"interest_rate", "principal_account"})
        row = Loan(
            **payload,
            principal_account=principal_account,
            interest_rate_basis_points=to_cents(data.interest_rate),
        )
        balance = service.principal_balance(session, row)
        if not 0 <= balance <= to_cents(data.initial_principal):
            fail("LOAN_OPENING_BALANCE", "Solde comptable incompatible avec le capital initial.")
        session.add(row)
        event(
            session,
            "LOAN_CREATED",
            None,
            {**data.model_dump(mode="json"), "principal_account": principal_account},
        )
        presented = structuring.present_loan(session, row)
        if presented["remaining_principal"] != money(balance):
            fail("LOAN_OPENING_BALANCE", "Solde comptable incompatible avec le capital initial.")
        return presented

    @router.patch("/loans/{loan_id}")
    def loan_correct(loan_id: int, data: LoanCorrectionInput, session: Write) -> dict[str, Any]:
        return structuring.correct_loan(session, loan_id, data)

    @router.post("/loans/{loan_id}/fund", status_code=201)
    def fund(loan_id: int, data: FundingInput, session: Write) -> dict[str, Any]:
        return service.operation_json(session, service.loan_post(session, loan_id, data, True))

    @router.post("/loans/{loan_id}/payments", status_code=201)
    def payment(loan_id: int, data: LoanPaymentInput, session: Write) -> dict[str, Any]:
        return service.operation_json(session, service.loan_post(session, loan_id, data, False))

    @router.post("/loans/{loan_id}/payments/import/preview")
    def loan_payments_preview(
        loan_id: int, data: LoanPaymentsCSVInput, session: Read
    ) -> dict[str, Any]:
        return service.import_loan_payments_csv(
            session,
            loan_id,
            data.fiscal_year_id,
            data.bank_account_id,
            data.content,
            False,
            data.preview_token,
            data.confirmed_loan_reference,
        )

    @router.post("/loans/{loan_id}/payments/import")
    def loan_payments_import(
        loan_id: int, data: LoanPaymentsCSVInput, session: Write
    ) -> dict[str, Any]:
        return service.import_loan_payments_csv(
            session,
            loan_id,
            data.fiscal_year_id,
            data.bank_account_id,
            data.content,
            True,
            data.preview_token,
            data.confirmed_loan_reference,
        )

    @router.post("/import/preview")
    def operations_preview(data: OperationsCSVInput, session: Read) -> dict[str, Any]:
        return service.import_operations_csv(
            session,
            data.property_id,
            data.fiscal_year_id,
            data.content,
            False,
            data.bank_account_id,
        )

    @router.post("/import")
    def operations_import(data: OperationsCSVInput, session: Write) -> dict[str, Any]:
        return service.import_operations_csv(
            session,
            data.property_id,
            data.fiscal_year_id,
            data.content,
            True,
            data.bank_account_id,
        )

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

    @router.get("/imports/{profile}/template")
    def csv_template(profile: str) -> Response:
        if not is_profile(profile):
            fail("CSV_PROFILE", "Import inconnu.", 404)
        name = TEMPLATE_NAMES[cast(Profile, profile)]
        return Response(
            content=template_csv(profile).encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @router.post("/imports/inspect")
    def csv_inspect(data: CsvInspectInput) -> dict[str, Any]:
        try:
            return inspect_content(data.content)
        except CsvReadError as exc:
            fail(exc.code, exc.message, 422, issues=exc.issues)

    def _assist(profile: str, data: CsvAssistInput) -> tuple[str, dict[str, str] | None]:
        if profile not in PROFILES:
            fail("CSV_PROFILE", "Import inconnu.", 404)
        return profile, data.mapping or None

    @router.post("/imports/{profile}/preview")
    def csv_preview(profile: str, data: CsvAssistInput, session: Read) -> dict[str, Any]:
        chosen, mapping = _assist(profile, data)
        return assistant.preview_import(
            session,
            chosen,
            data.content,
            mapping,
            bank_account_id=data.bank_account_id,
            property_id=data.property_id,
            fiscal_year_id=data.fiscal_year_id,
            loan_id=data.loan_id,
        )

    @router.post("/imports/{profile}/commit")
    def csv_commit(
        profile: str,
        data: CsvAssistInput,
        session: Write,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        chosen, mapping = _assist(profile, data)
        return assistant.commit_import(
            session,
            chosen,
            data.content,
            mapping,
            bank_account_id=data.bank_account_id,
            property_id=data.property_id,
            fiscal_year_id=data.fiscal_year_id,
            loan_id=data.loan_id,
            confirmed_loan_reference=data.confirmed_loan_reference,
            import_valid_only=data.import_valid_only,
            idempotency_key=idempotency_key,
        )

    return router
