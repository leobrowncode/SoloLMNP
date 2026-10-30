"""Public views of supporting documents and the entries they can cite.

The views expose the business key (numéro, date, pièce), never an internal id
of the accounting entry. Linking a document must not be read as a change to
that entry.
"""

from datetime import date, datetime

MEDIA_LABELS = {
    "application/pdf": "PDF",
    "image/jpeg": "JPEG",
    "image/png": "PNG",
}


def media_label(media_type: str) -> str:
    return MEDIA_LABELS.get(media_type, media_type)


def iso_z(value: datetime) -> str:
    return value.isoformat() + "Z"


def entry_choice(
    *,
    entry_number: str | None,
    accounting_date: date,
    piece_reference: str,
    piece_date: date,
    label: str,
    status: str,
    year: int,
) -> dict[str, object]:
    return {
        "entry_number": entry_number,
        "accounting_date": accounting_date.isoformat(),
        "piece_reference": piece_reference,
        "piece_date": piece_date.isoformat(),
        "label": label,
        "status": status,
        "year": year,
    }


def document_view(
    *,
    document_id: int,
    original_name: str,
    created_at: datetime,
    media_type: str,
    size: int,
    sha256: str,
    entry: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "id": document_id,
        "original_name": original_name,
        "created_at": iso_z(created_at),
        "media_type": media_type,
        "media_label": media_label(media_type),
        "size": size,
        "sha256": sha256,
        "entry": entry,
    }
