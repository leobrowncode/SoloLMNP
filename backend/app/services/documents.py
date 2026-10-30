"""Local supporting documents. The stored name is generated, never taken from the user."""

import base64
import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.filing_schemas import DocumentInput, EntryLinkInput
from app.core.config import Settings
from app.domain.documents.catalog import document_view, entry_choice
from app.models import AccountingEntry, FiscalYear
from app.models.filing import SupportingDocument
from app.services.ledger import fail

EXTENSIONS = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}
SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def store_document(session: Session, settings: Settings, data: DocumentInput) -> SupportingDocument:
    try:
        content = base64.b64decode(data.content_base64, validate=True)
    except ValueError:
        fail("INVALID_DOCUMENT", "Le contenu du justificatif est illisible.", 422)
    if not content or len(content) > settings.max_upload_bytes:
        fail("DOCUMENT_SIZE", "La taille du justificatif est refusée.", 422)
    if not content.startswith(SIGNATURES[data.media_type]):
        fail(
            "DOCUMENT_SIGNATURE",
            "La signature du fichier ne correspond pas au type annoncé.",
            422,
        )
    entry_id = _linked_entry_id(session, data)
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid4().hex}.{EXTENSIONS[data.media_type]}"
    target = settings.documents_dir / stored
    if not _inside(target, settings.documents_dir):
        fail("DOCUMENT_PATH", "Chemin de stockage refusé.", 422)
    target.write_bytes(content)
    original = SAFE_NAME.sub("_", data.filename).strip("._") or "piece"
    row = SupportingDocument(
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
        media_type=data.media_type,
        stored_name=stored,
        original_name=original[:200],
        entry_id=entry_id,
    )
    session.add(row)
    session.flush()
    return row


def list_documents(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(SupportingDocument, AccountingEntry, FiscalYear.year)
        .outerjoin(AccountingEntry, AccountingEntry.id == SupportingDocument.entry_id)
        .outerjoin(FiscalYear, FiscalYear.id == AccountingEntry.fiscal_year_id)
        .order_by(SupportingDocument.created_at.desc(), SupportingDocument.id.desc())
    )
    return [
        document_view(
            document_id=document.id,
            original_name=document.original_name,
            created_at=document.created_at,
            media_type=document.media_type,
            size=document.size,
            sha256=document.sha256,
            entry=_entry_view(entry, year),
        )
        for document, entry, year in rows
    ]


def search_entries(
    session: Session,
    *,
    number: str | None,
    entry_date: date | None,
    piece: str | None,
) -> list[dict[str, Any]]:
    number = _blank(number)
    piece = _blank(piece)
    if number is None and entry_date is None and piece is None:
        fail(
            "ENTRY_SEARCH",
            "Indiquez un numéro, une date ou une pièce pour chercher une écriture.",
            422,
            field="number",
        )
    query = select(AccountingEntry, FiscalYear.year).join(
        FiscalYear, FiscalYear.id == AccountingEntry.fiscal_year_id
    )
    if number is not None:
        query = query.where(AccountingEntry.entry_number.contains(number, autoescape=True))
    if entry_date is not None:
        query = query.where(AccountingEntry.accounting_date == entry_date)
    if piece is not None:
        query = query.where(AccountingEntry.piece_reference.contains(piece, autoescape=True))
    rows = session.execute(
        query.order_by(AccountingEntry.accounting_date.desc(), AccountingEntry.id.desc()).limit(30)
    )
    found: list[dict[str, Any]] = []
    for entry, year in rows:
        view = _entry_view(entry, year)
        if view is not None:
            found.append(view)
    return found


def published_document(session: Session, document: SupportingDocument) -> dict[str, Any]:
    entry = (
        session.get(AccountingEntry, document.entry_id) if document.entry_id is not None else None
    )
    year = session.get(FiscalYear, entry.fiscal_year_id) if entry is not None else None
    return document_view(
        document_id=document.id,
        original_name=document.original_name,
        created_at=document.created_at,
        media_type=document.media_type,
        size=document.size,
        sha256=document.sha256,
        entry=_entry_view(entry, year.year if year is not None else None),
    )


def link_document(session: Session, document_id: int, data: EntryLinkInput) -> dict[str, Any]:
    """Attach a file to an entry. The entry row itself is never updated."""
    document = session.get(SupportingDocument, document_id)
    if document is None:
        fail("DOCUMENT_NOT_FOUND", "Justificatif introuvable.", 404)
    assert document is not None  # noqa: S101
    entry = resolve_entry(
        session,
        entry_number=data.entry_number,
        accounting_date=data.accounting_date,
        piece_reference=data.piece_reference,
    )
    document.entry_id = entry.id
    session.flush()
    return published_document(session, document)


def resolve_entry(
    session: Session,
    *,
    entry_number: str | None,
    accounting_date: date,
    piece_reference: str,
) -> AccountingEntry:
    conditions = [
        AccountingEntry.accounting_date == accounting_date,
        AccountingEntry.piece_reference == piece_reference,
    ]
    if entry_number is None:
        conditions.append(AccountingEntry.entry_number.is_(None))
    else:
        conditions.append(AccountingEntry.entry_number == entry_number)
    rows = list(session.scalars(select(AccountingEntry).where(*conditions)))
    if not rows:
        fail(
            "ENTRY_NOT_FOUND",
            "Aucune écriture ne correspond à ce numéro, cette date et cette pièce.",
            404,
        )
    if len(rows) > 1:
        fail(
            "ENTRY_AMBIGUOUS",
            "Plusieurs écritures correspondent. Précisez le numéro, la date et la pièce.",
            409,
        )
    return rows[0]


def _linked_entry_id(session: Session, data: DocumentInput) -> int | None:
    if data.accounting_date is not None and data.piece_reference is not None:
        return resolve_entry(
            session,
            entry_number=data.entry_number,
            accounting_date=data.accounting_date,
            piece_reference=data.piece_reference,
        ).id
    if data.entry_id is not None and session.get(AccountingEntry, data.entry_id) is None:
        fail("ENTRY_NOT_FOUND", "Écriture introuvable.", 404)
    return data.entry_id


def _entry_view(entry: AccountingEntry | None, year: int | None) -> dict[str, Any] | None:
    if entry is None or year is None:
        return None
    return entry_choice(
        entry_number=entry.entry_number,
        accounting_date=entry.accounting_date,
        piece_reference=entry.piece_reference,
        piece_date=entry.piece_date,
        label=entry.label,
        status=entry.status,
        year=year,
    )


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
