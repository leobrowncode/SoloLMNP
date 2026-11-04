"""Portable dossier archive: rows, hashes and member names, with no I/O.

The archive is a zip of ``manifest.json``, ``data.json`` and the justificatifs
registered in ``supporting_document``. Money is a decimal string of whole cents.
Dates stay ISO. A member that is not a single safe file name is refused.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import JSON, Boolean, Date, DateTime, Integer

from app.core.money import from_cents, to_cents
from app.domain.documents.keys import safe_segment
from app.models.base import Cents, Money

MemberKind = Literal["manifest", "data", "document"]
DATA_NAME = "data.json"
MANIFEST_NAME = "manifest.json"
KIND = "sololmnp-dossier"


class UnsafeDossierPath(ValueError):
    """A zip member is not manifest, data, or one safe document name."""


class DossierPayloadError(ValueError):
    """Rows cannot be encoded or do not match the current columns."""


def classify_dossier_member(member: str) -> MemberKind:
    if member == MANIFEST_NAME:
        return "manifest"
    if member == DATA_NAME:
        return "data"
    if not member.startswith("documents/") or member.endswith("/"):
        raise UnsafeDossierPath("Chemin de document refusé.")
    name = member.removeprefix("documents/")
    if not safe_segment(name):
        raise UnsafeDossierPath("Chemin de document refusé.")
    return "document"


def column_kind(column_type: object) -> str:
    if isinstance(column_type, Money):
        return "money"
    if isinstance(column_type, Cents):
        return "cents"
    if isinstance(column_type, JSON):
        return "json"
    if isinstance(column_type, Boolean):
        return "bool"
    visit = getattr(column_type, "__visit_name__", "")
    if visit == "date" or (isinstance(column_type, Date) and not isinstance(column_type, DateTime)):
        return "date"
    if visit == "datetime" or isinstance(column_type, DateTime):
        return "datetime"
    if visit == "integer" or isinstance(column_type, Integer):
        return "int"
    return "text"


def encode_value(column: Column[object], value: object) -> object:
    if value is None:
        return None
    kind = column_kind(column.type)
    if kind == "money":
        if type(value) is int:
            value = from_cents(value)
        if not isinstance(value, Decimal):
            raise DossierPayloadError(f"Montant illisible dans {column.table.name}.{column.name}.")
        cents = to_cents(value)
        sign = "-" if cents < 0 else ""
        whole, fractional = divmod(abs(cents), 100)
        return f"{sign}{whole}.{fractional:02d}"
    if kind in {"cents", "int"}:
        if type(value) is bool:
            raise DossierPayloadError(f"Entier illisible dans {column.table.name}.{column.name}.")
        if type(value) is int:
            return value
        if isinstance(value, Decimal) and value == value.to_integral_value():
            return int(value)
        raise DossierPayloadError(f"Entier illisible dans {column.table.name}.{column.name}.")
    if kind == "bool":
        if type(value) is not bool:
            raise DossierPayloadError(f"Booléen illisible dans {column.table.name}.{column.name}.")
        return value
    if kind == "date":
        if not isinstance(value, date) or isinstance(value, datetime):
            raise DossierPayloadError(f"Date illisible dans {column.table.name}.{column.name}.")
        return value.isoformat()
    if kind == "datetime":
        if not isinstance(value, datetime) or value.tzinfo is not None:
            raise DossierPayloadError(
                f"Horodatage illisible dans {column.table.name}.{column.name}."
            )
        return value.isoformat()
    if kind == "json":
        return value
    if isinstance(value, str):
        return value
    raise DossierPayloadError(f"Valeur illisible dans {column.table.name}.{column.name}.")


def decode_value(column: Column[object], value: object) -> object:
    if value is None:
        return None
    kind = column_kind(column.type)
    if kind == "money":
        if not isinstance(value, str):
            raise DossierPayloadError(f"Montant illisible dans {column.table.name}.{column.name}.")
        try:
            amount = Decimal(value)
            to_cents(amount)
        except (ArithmeticError, ValueError, TypeError) as exc:
            raise DossierPayloadError(
                f"Montant illisible dans {column.table.name}.{column.name}."
            ) from exc
        return amount
    if kind in {"cents", "int"}:
        if type(value) is not int:
            raise DossierPayloadError(f"Entier illisible dans {column.table.name}.{column.name}.")
        return value
    if kind == "bool":
        if type(value) is not bool:
            raise DossierPayloadError(f"Booléen illisible dans {column.table.name}.{column.name}.")
        return value
    if kind == "date":
        if not isinstance(value, str):
            raise DossierPayloadError(f"Date illisible dans {column.table.name}.{column.name}.")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise DossierPayloadError(
                f"Date illisible dans {column.table.name}.{column.name}."
            ) from exc
        if parsed.isoformat() != value:
            raise DossierPayloadError(f"Date illisible dans {column.table.name}.{column.name}.")
        return parsed
    if kind == "datetime":
        if not isinstance(value, str):
            raise DossierPayloadError(
                f"Horodatage illisible dans {column.table.name}.{column.name}."
            )
        try:
            parsed_time = datetime.fromisoformat(value)
        except ValueError as exc:
            raise DossierPayloadError(
                f"Horodatage illisible dans {column.table.name}.{column.name}."
            ) from exc
        if parsed_time.tzinfo is not None:
            raise DossierPayloadError(
                f"Horodatage illisible dans {column.table.name}.{column.name}."
            )
        return parsed_time
    if kind == "json":
        if value is not None and not isinstance(value, (dict, list, str, int, float, bool)):
            raise DossierPayloadError(f"JSON illisible dans {column.table.name}.{column.name}.")
        return value
    if not isinstance(value, str):
        raise DossierPayloadError(f"Texte illisible dans {column.table.name}.{column.name}.")
    return value


def population(payload: dict[str, list[dict[str, object]]]) -> dict[str, int]:
    return {
        "entries": len(payload.get("accounting_entry", [])),
        "years": len(payload.get("fiscal_year", [])),
        "documents": len(payload.get("supporting_document", [])),
    }


def document_filename(member: str) -> str:
    if classify_dossier_member(member) != "document":
        raise UnsafeDossierPath("Chemin de document refusé.")
    return Path(member).name
