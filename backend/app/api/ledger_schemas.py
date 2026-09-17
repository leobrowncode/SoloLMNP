"""Money crosses JSON boundaries as decimal strings only."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.core.money import to_cents

Label = Annotated[str, Field(min_length=1, max_length=200)]
AccountNumber = Annotated[str, Field(pattern=r"^[1-7][0-9]{2,9}$")]
JournalCode = Annotated[str, Field(pattern=r"^[A-Z0-9]{2,10}$")]


def parse_money(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Les montants JSON doivent être des chaînes décimales.")
    try:
        amount = Decimal(value)
        to_cents(amount)
    except (ArithmeticError, ValueError) as exc:
        raise ValueError("Montant fini au centime exact requis.") from exc
    if amount < 0:
        raise ValueError("Un débit ou crédit ne peut pas être négatif.")
    return amount


MoneyInput = Annotated[Decimal, BeforeValidator(parse_money)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ActivityInput(Input):
    activity_name: Label
    activity_start_date: date


class YearInput(Input):
    year: int = Field(ge=1900, le=9999)
    start_date: date
    end_date: date
    fiscal_vintage: Annotated[str, Field(pattern=r"^[0-9]{4}$")]

    @model_validator(mode="after")
    def dates(self) -> "YearInput":
        if self.start_date > self.end_date or self.end_date.year != self.year:
            raise ValueError("Dates d’exercice incohérentes avec l’année de clôture.")
        return self


class AccountInput(Input):
    number: AccountNumber
    label: Label
    account_type: Literal["ASSET", "LIABILITY", "EQUITY", "EXPENSE", "INCOME"]


class JournalInput(Input):
    code: JournalCode
    label: Label
    journal_type: Literal["GENERAL", "BANK", "SALES", "PURCHASE", "OPENING"]


class ActiveInput(Input):
    active: bool = Field(strict=True)


class LineInput(Input):
    account_number: AccountNumber
    label: Annotated[str, Field(min_length=1, max_length=300)]
    debit: MoneyInput = Decimal("0.00")
    credit: MoneyInput = Decimal("0.00")

    @model_validator(mode="after")
    def one_side(self) -> "LineInput":
        if (self.debit == 0) == (self.credit == 0):
            raise ValueError("Chaque ligne doit avoir exactement un côté positif.")
        return self


class EntryInput(Input):
    fiscal_year_id: int = Field(gt=0)
    journal_code: JournalCode
    accounting_date: date
    piece_reference: Label
    piece_date: date
    label: Annotated[str, Field(min_length=1, max_length=300)]
    lines: list[LineInput] = Field(min_length=2, max_length=100)


class EditInput(EntryInput):
    expected_version: int = Field(ge=1)


class VersionInput(Input):
    expected_version: int = Field(ge=1)


class ReversalInput(Input):
    accounting_date: date
    piece_reference: Label
    reason: Annotated[str, Field(min_length=5, max_length=300)]


class OpeningInput(Input):
    preview_token: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    journal_code: JournalCode
    piece_reference: Label
    result_account: AccountNumber | None = None
