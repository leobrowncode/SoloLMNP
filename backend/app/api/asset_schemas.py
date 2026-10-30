"""Validated fixed-asset inputs; durations and bases require explanations."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.api.ledger_schemas import AccountNumber, Input, Label, MoneyInput, OptionalMoney
from app.core.money import to_cents

Reason = Annotated[str, Field(min_length=5, max_length=2000)]


class AssetInput(Input):
    property_id: int = Field(gt=0)
    category: Literal["LAND", "BUILDING", "FURNITURE", "EQUIPMENT", "IMPROVEMENT", "OTHER"]
    label: Label
    acquisition_date: date
    service_start_date: date
    acquisition_value: MoneyInput
    depreciable_value: MoneyInput
    non_depreciable_value: MoneyInput
    residual_value: MoneyInput = Decimal("0.00")
    method: Literal["NONE", "LINEAR"]
    useful_life_months: int | None = Field(default=None, ge=1, le=2400)
    asset_account: AccountNumber
    depreciation_account: AccountNumber | None = None
    basis_reason: Reason
    duration_reason: Annotated[str, Field(max_length=2000)] = ""
    disposed_at: date | None = None
    notes: Annotated[str, Field(max_length=2000)] = ""

    @model_validator(mode="after")
    def plan(self) -> "AssetInput":
        acquisition = to_cents(self.acquisition_value)
        depreciable = to_cents(self.depreciable_value)
        non_depreciable = to_cents(self.non_depreciable_value)
        residual = to_cents(self.residual_value)
        if acquisition <= 0 or depreciable + non_depreciable != acquisition:
            raise ValueError(
                "La base amortissable et la part non amortissable doivent totaliser "
                "la valeur d’acquisition."
            )
        if self.service_start_date < self.acquisition_date:
            raise ValueError("La mise en service ne peut pas précéder l’acquisition.")
        if self.disposed_at is not None and self.disposed_at < self.service_start_date:
            raise ValueError("La sortie ne peut pas précéder la mise en service.")
        if self.category == "LAND":
            if self.depreciation_account is not None:
                raise ValueError("Un terrain n’a pas de compte d’amortissement.")
            if any(
                (
                    self.method != "NONE",
                    depreciable != 0,
                    non_depreciable != acquisition,
                    residual != 0,
                    self.useful_life_months is not None,
                )
            ):
                raise ValueError("Le terrain doit être intégralement non amortissable.")
        elif any(
            (
                self.method != "LINEAR",
                depreciable <= residual,
                non_depreciable != 0,
                self.useful_life_months is None,
                self.depreciation_account is None,
                len(self.duration_reason.strip()) < 5,
            )
        ):
            raise ValueError(
                "Un actif amortissable exige une base, une durée documentée "
                "et un compte d’amortissement."
            )
        return self


class ComponentInput(Input):
    category: Annotated[str, Field(min_length=1, max_length=40)]
    label: Label
    value: MoneyInput
    useful_life_months: int = Field(ge=1, le=2400)
    service_start_date: date
    asset_account: AccountNumber
    depreciation_account: AccountNumber
    basis_reason: Reason
    duration_reason: Reason

    @model_validator(mode="after")
    def positive(self) -> "ComponentInput":
        if to_cents(self.value) <= 0:
            raise ValueError("La valeur du composant doit être positive.")
        return self


class AssetCorrectionInput(Input):
    """Partial audited correction. Omitted fields stay; null is not a silent wipe."""

    reason: Reason
    label: Label | None = None
    acquisition_date: date | None = None
    service_start_date: date | None = None
    acquisition_value: OptionalMoney = None
    depreciable_value: OptionalMoney = None
    non_depreciable_value: OptionalMoney = None
    residual_value: OptionalMoney = None
    useful_life_months: int | None = Field(default=None, ge=1, le=2400)
    asset_account: AccountNumber | None = None
    depreciation_account: AccountNumber | None = None
    basis_reason: Reason | None = None
    duration_reason: Annotated[str, Field(max_length=2000)] | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None


class ComponentCorrectionInput(Input):
    reason: Reason
    label: Label | None = None
    value: OptionalMoney = None
    useful_life_months: int | None = Field(default=None, ge=1, le=2400)
    service_start_date: date | None = None
    asset_account: AccountNumber | None = None
    depreciation_account: AccountNumber | None = None
    basis_reason: Reason | None = None
    duration_reason: Reason | None = None


class LoanBalanceInput(Input):
    loan_id: int = Field(gt=0)
    outstanding: MoneyInput


class PriorChargeInput(Input):
    account_number: AccountNumber
    amount: MoneyInput
    label: Label

    @model_validator(mode="after")
    def expense(self) -> "PriorChargeInput":
        if not self.account_number.startswith("6") or self.account_number.startswith("68"):
            raise ValueError("Une charge antérieure utilise un compte 6, hors dotations 68.")
        if to_cents(self.amount) <= 0:
            raise ValueError("Le montant de la charge doit être positif.")
        return self


class PropertyEntryInput(Input):
    """Brings a property bought before the exercise into the books, in one balanced entry."""

    fiscal_year_id: int = Field(gt=0)
    loans: list[LoanBalanceInput] = Field(default_factory=list, max_length=20)
    bank_account_id: int | None = Field(default=None, gt=0)
    bank_amount: MoneyInput = Decimal("0.00")
    prior_charges: list[PriorChargeInput] = Field(default_factory=list, max_length=20)
    piece_reference: Label
    confirm: bool = False

    @model_validator(mode="after")
    def bank(self) -> "PropertyEntryInput":
        if to_cents(self.bank_amount) < 0:
            raise ValueError("Le solde bancaire repris ne peut pas être négatif.")
        if to_cents(self.bank_amount) > 0 and self.bank_account_id is None:
            raise ValueError("Choisissez le compte bancaire qui reçoit le solde.")
        if len({item.loan_id for item in self.loans}) != len(self.loans):
            raise ValueError("Un emprunt ne peut être repris qu’une fois.")
        return self


class DepreciationPostInput(Input):
    request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
    piece_reference: Label


class DepreciationBatchItem(Input):
    """One calculated period inside a posting batch."""

    period_id: int = Field(gt=0)
    request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
    piece_reference: Label


class DepreciationBatchInput(Input):
    """Posts several depreciation periods and reports each one."""

    items: list[DepreciationBatchItem] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_periods(self) -> "DepreciationBatchInput":
        ids = [item.period_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Une période ne peut figurer qu’une fois dans le lot.")
        return self


class DwellingPlanConfirm(Input):
    """Creates exactly one previously previewed dwelling split."""

    confirm: Literal[True]
    preview_token: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
