"""Explicit accounting dates, exact money and retry identities."""

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.api.ledger_schemas import AccountNumber, Input, Label, MoneyInput
from app.core.money import to_cents

PositiveMoney = Annotated[MoneyInput, Field(gt=0)]
Percentage = Annotated[MoneyInput, Field(le=100)]
RequestId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")]


class PropertyInput(Input):
    name: Label
    address: Annotated[str, Field(min_length=1, max_length=1000)]
    acquisition_date: Date
    rental_start_date: Date | None = None
    acquisition_price: MoneyInput
    acquisition_costs: MoneyInput = Decimal("0.00")
    land_value: MoneyInput
    building_value: MoneyInput
    notes: Annotated[str, Field(max_length=2000)] = ""

    @model_validator(mode="after")
    def split(self) -> "PropertyInput":
        if to_cents(self.land_value) + to_cents(self.building_value) != to_cents(
            self.acquisition_price
        ):
            raise ValueError("Le terrain et le bâtiment doivent totaliser le prix d’acquisition.")
        return self


class BankInput(Input):
    name: Label
    account_number: AccountNumber


class OperationInput(Input):
    request_id: RequestId
    kind: Literal["REVENUE", "EXPENSE"]
    property_id: int = Field(gt=0)
    fiscal_year_id: int = Field(gt=0)
    date: Date
    piece_date: Date
    piece_reference: Label
    amount: PositiveMoney
    description: Annotated[str, Field(min_length=1, max_length=300)]
    counterparty: Label
    accounting_account: AccountNumber
    bank_account_id: int | None = Field(default=None, gt=0)
    deductible_percentage: Percentage = Decimal("100.00")
    fiscal_treatment: Literal["REQUIRES_REVIEW", "DEDUCTIBLE", "PARTIAL", "NON_DEDUCTIBLE"] = (
        "REQUIRES_REVIEW"
    )
    bank_transaction_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def fiscal_metadata(self) -> "OperationInput":
        percentage = to_cents(self.deductible_percentage)
        expected = {
            "DEDUCTIBLE": percentage == 10000,
            "NON_DEDUCTIBLE": percentage == 0,
            "PARTIAL": 0 < percentage < 10000,
            "REQUIRES_REVIEW": True,
        }
        if not expected[self.fiscal_treatment]:
            raise ValueError("Le traitement fiscal et le pourcentage saisi sont incohérents.")
        return self


class SettlementInput(Input):
    request_id: RequestId
    fiscal_year_id: int = Field(gt=0)
    date: Date
    piece_reference: Label
    amount: PositiveMoney
    bank_account_id: int = Field(gt=0)
    bank_transaction_id: int | None = Field(default=None, gt=0)


class LoanInput(Input):
    property_id: int = Field(gt=0)
    lender: Label
    start_date: Date
    initial_principal: PositiveMoney
    interest_rate: Percentage
    duration_months: int = Field(ge=1, le=1200)
    monthly_payment: MoneyInput = Decimal("0.00")
    monthly_insurance: MoneyInput = Decimal("0.00")
    principal_account: AccountNumber
    notes: Annotated[str, Field(max_length=2000)] = ""


class FundingInput(SettlementInput):
    pass


class LoanPaymentInput(SettlementInput):
    principal: MoneyInput
    interest: MoneyInput
    insurance: MoneyInput
    other_costs: MoneyInput
    interest_account: AccountNumber = "661000"
    insurance_account: AccountNumber = "616000"
    other_costs_account: AccountNumber = "627000"

    @model_validator(mode="after")
    def split(self) -> "LoanPaymentInput":
        total = sum(
            to_cents(value)
            for value in (self.principal, self.interest, self.insurance, self.other_costs)
        )
        if total != to_cents(self.amount):
            raise ValueError("La ventilation doit égaler le montant total de l’échéance.")
        return self


class CSVInput(Input):
    bank_account_id: int = Field(gt=0)
    content: Annotated[str, Field(min_length=1, max_length=1_000_000)]


class MatchInput(Input):
    entry_line_id: int = Field(gt=0)


class ReasonInput(Input):
    reason: Annotated[str, Field(min_length=5, max_length=300)]
