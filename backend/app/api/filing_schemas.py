"""Inputs for closing, documents and restore."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.api.ledger_schemas import Input


class ReadyInput(Input):
    acknowledged: list[str] = Field(max_length=40)


class CloseInput(Input):
    confirmation: Literal["CLOTURER"]


class ReopenInput(Input):
    confirmation: Literal["ROUVRIR"]
    reason: Annotated[str, Field(min_length=10, max_length=3000)]


class DocumentInput(Input):
    filename: Annotated[str, Field(min_length=1, max_length=200)]
    media_type: Literal["application/pdf", "image/jpeg", "image/png"]
    content_base64: Annotated[str, Field(min_length=4, max_length=20_000_000)]
    entry_id: int | None = Field(default=None, gt=0)
    entry_number: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    accounting_date: date | None = None
    piece_reference: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    @model_validator(mode="after")
    def link_is_complete(self) -> Self:
        has_date = self.accounting_date is not None
        has_piece = self.piece_reference is not None
        if has_date != has_piece:
            raise ValueError("La date et la pièce sont requises ensemble pour lier une écriture.")
        if self.entry_number is not None and not has_date:
            raise ValueError("Le numéro d’écriture se joint à la date et à la pièce.")
        return self


class EntryLinkInput(Input):
    entry_number: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    accounting_date: date
    piece_reference: Annotated[str, Field(min_length=1, max_length=200)]


class BackupNameInput(Input):
    filename: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,120}$")]


class RestoreInput(Input):
    filename: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,120}$")]
    confirmation: Literal["RESTAURER"]
