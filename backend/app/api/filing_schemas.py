"""Inputs for closing, documents and restore."""

from typing import Annotated, Literal

from pydantic import Field

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


class RestoreInput(Input):
    filename: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,120}$")]
