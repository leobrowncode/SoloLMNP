"""Supporting documents. The stored name is generated, never taken from the user.

Bytes live in the object store (local disk, or private Blob). The API returns
the file itself. It never returns a storage URL.
"""

import base64
import hashlib
import re
import time
from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.filing_schemas import (
    CompleteUploadInput,
    DocumentInput,
    EntryLinkInput,
    UploadGrantInput,
)
from app.core.config import Settings
from app.domain.documents.catalog import document_view, entry_choice
from app.domain.documents.files import (
    VERCEL_FUNCTION_BODY_BYTES,
    extension_for,
    inline_budget,
    matches_signature,
    needs_direct_upload,
)
from app.domain.documents.keys import UnsafeObjectKey, document_key
from app.models import AccountingEntry, FiscalYear
from app.models.filing import SupportingDocument
from app.services.blob_api import BlobApiError, issue_client_token, put_url
from app.services.ledger import fail
from app.services.object_store import ObjectMissing, ObjectStore, ObjectStoreError, open_store

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_STORED_NAME = re.compile(r"^[0-9a-f]{32}\.(pdf|jpg|png)$")
_GRANT_SECONDS = 15 * 60


def storage_policy(settings: Settings) -> dict[str, object]:
    budget = inline_budget(settings.max_upload_bytes, blob=settings.uses_blob)
    return {
        "backend": "blob" if settings.uses_blob else "local",
        "max_upload_bytes": settings.max_upload_bytes,
        "inline_upload_bytes": budget,
        "direct_upload": settings.uses_blob,
        "function_body_bytes": VERCEL_FUNCTION_BODY_BYTES,
    }


def store_document(session: Session, settings: Settings, data: DocumentInput) -> SupportingDocument:
    try:
        content = base64_bytes(data.content_base64)
    except ValueError:
        fail("INVALID_DOCUMENT", "Le contenu du justificatif est illisible.", 422)
    _require_content(settings, content, data.media_type)
    if needs_direct_upload(len(content), settings.max_upload_bytes, blob=settings.uses_blob):
        fail(
            "DOCUMENT_BODY_LIMIT",
            "Ce justificatif dépasse le corps de requête d’une fonction. Utilisez l’envoi direct.",
            413,
        )
    entry_id = _linked_entry_id(session, data)
    return _insert_document(
        session,
        settings,
        content=content,
        filename=data.filename,
        media_type=data.media_type,
        entry_id=entry_id,
        stored_name=None,
    )


def upload_grant(settings: Settings, data: UploadGrantInput) -> dict[str, object]:
    if data.size > settings.max_upload_bytes:
        fail("DOCUMENT_SIZE", "La taille du justificatif est refusée.", 422)
    policy = storage_policy(settings)
    if not needs_direct_upload(data.size, settings.max_upload_bytes, blob=settings.uses_blob):
        return {"mode": "inline", **policy}
    stored = f"{uuid4().hex}.{extension_for(data.media_type)}"
    key = document_key(stored)
    try:
        token = issue_client_token(
            settings.blob_read_write_token,
            pathname=key,
            content_type=data.media_type,
            maximum_size=data.size,
            valid_until_ms=int(time.time() * 1000) + _GRANT_SECONDS * 1000,
        )
    except BlobApiError as exc:
        fail("DOCUMENT_STORE", str(exc), 502)
    return {
        "mode": "direct",
        "stored_name": stored,
        "method": "PUT",
        "upload_url": put_url(key),
        "headers": {
            "authorization": f"Bearer {token}",
            "x-api-version": "13",
            "x-vercel-blob-access": "private",
            "x-content-type": data.media_type,
            "x-add-random-suffix": "0",
        },
        **policy,
    }


def complete_upload(
    session: Session, settings: Settings, data: CompleteUploadInput
) -> SupportingDocument:
    if not settings.uses_blob:
        fail("DOCUMENT_STORE", "L’envoi direct exige le stockage objet.", 409)
    if not _STORED_NAME.fullmatch(data.stored_name):
        fail("DOCUMENT_PATH", "Chemin de stockage refusé.", 422)
    if extension_for(data.media_type) != data.stored_name.rsplit(".", 1)[-1]:
        fail(
            "DOCUMENT_SIGNATURE",
            "La signature du fichier ne correspond pas au type annoncé.",
            422,
        )
    store = open_store(settings)
    try:
        content = store.get(document_key(data.stored_name))
    except ObjectMissing:
        fail("UPLOAD_INCOMPLETE", "L’envoi direct n’est pas arrivé dans le stockage.", 409)
    except ObjectStoreError as exc:
        fail("DOCUMENT_STORE", str(exc), 502)
    try:
        _require_content(settings, content, data.media_type)
    except Exception:
        _discard(store, data.stored_name)
        raise
    digest = hashlib.sha256(content).hexdigest()
    if digest != data.sha256 or len(content) != data.size:
        _discard(store, data.stored_name)
        fail("DOCUMENT_SIGNATURE", "L’empreinte du fichier reçu ne correspond pas.", 422)
    entry_id = _linked_entry_id(session, data)
    return _insert_document(
        session,
        settings,
        content=content,
        filename=data.filename,
        media_type=data.media_type,
        entry_id=entry_id,
        stored_name=data.stored_name,
        already_stored=True,
    )


def read_document_content(
    session: Session, settings: Settings, document_id: int
) -> tuple[SupportingDocument, bytes]:
    document = _existing(session, document_id)
    try:
        content = open_store(settings).get(document_key(document.stored_name))
    except ObjectMissing:
        fail("DOCUMENT_STORE", "Le justificatif est introuvable dans le stockage.", 404)
    except (ObjectStoreError, UnsafeObjectKey) as exc:
        fail("DOCUMENT_STORE", str(exc), 502)
    if hashlib.sha256(content).hexdigest() != document.sha256 or len(content) != document.size:
        fail("DOCUMENT_STORE", "Le justificatif stocké ne correspond plus à son empreinte.", 409)
    return document, content


def delete_document(session: Session, settings: Settings, document_id: int) -> dict[str, object]:
    document = _existing(session, document_id)
    stored_name = document.stored_name
    session.delete(document)
    session.flush()
    try:
        open_store(settings).delete(document_key(stored_name))
    except ObjectStoreError as exc:
        fail("DOCUMENT_STORE", str(exc), 502)
    return {"id": document_id, "deleted": True}


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
    document = _existing(session, document_id)
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


def base64_bytes(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def _require_content(settings: Settings, content: bytes, media_type: str) -> None:
    if not content or len(content) > settings.max_upload_bytes:
        fail("DOCUMENT_SIZE", "La taille du justificatif est refusée.", 422)
    if not matches_signature(media_type, content):
        fail(
            "DOCUMENT_SIGNATURE",
            "La signature du fichier ne correspond pas au type annoncé.",
            422,
        )


def _insert_document(
    session: Session,
    settings: Settings,
    *,
    content: bytes,
    filename: str,
    media_type: str,
    entry_id: int | None,
    stored_name: str | None,
    already_stored: bool = False,
) -> SupportingDocument:
    stored = stored_name or f"{uuid4().hex}.{extension_for(media_type)}"
    if not _STORED_NAME.fullmatch(stored):
        fail("DOCUMENT_PATH", "Chemin de stockage refusé.", 422)
    store = open_store(settings)
    if not already_stored:
        try:
            store.put(document_key(stored), content, media_type)
        except (ObjectStoreError, UnsafeObjectKey) as exc:
            fail("DOCUMENT_STORE", str(exc), 502)
    original = SAFE_NAME.sub("_", filename).strip("._") or "piece"
    row = SupportingDocument(
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
        media_type=media_type,
        stored_name=stored,
        original_name=original[:200],
        entry_id=entry_id,
    )
    session.add(row)
    try:
        session.flush()
    except Exception:
        if not already_stored:
            _discard(store, stored)
        raise
    return row


def _discard(store: ObjectStore, stored_name: str) -> None:
    try:
        store.delete(document_key(stored_name))
    except (ObjectStoreError, UnsafeObjectKey, OSError):
        return


def _existing(session: Session, document_id: int) -> SupportingDocument:
    document = session.get(SupportingDocument, document_id)
    if document is None:
        fail("DOCUMENT_NOT_FOUND", "Justificatif introuvable.", 404)
    assert document is not None  # noqa: S101
    return document


def _linked_entry_id(session: Session, data: DocumentInput | CompleteUploadInput) -> int | None:
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
