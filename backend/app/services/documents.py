"""Local supporting documents. The stored name is generated, never taken from the user."""

import base64
import hashlib
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.api.filing_schemas import DocumentInput
from app.core.config import Settings
from app.models import AccountingEntry
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
    if data.entry_id is not None and session.get(AccountingEntry, data.entry_id) is None:
        fail("ENTRY_NOT_FOUND", "Écriture introuvable.", 404)
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
        entry_id=data.entry_id,
    )
    session.add(row)
    session.flush()
    return row


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
