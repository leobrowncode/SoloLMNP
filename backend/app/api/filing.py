"""Closing, FEC, liasse worksheet, documents and backups."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.filing_schemas import (
    BackupNameInput,
    CloseInput,
    CompleteUploadInput,
    DocumentInput,
    EntryLinkInput,
    ReadyInput,
    ReopenInput,
    RestoreInput,
    UploadGrantInput,
)
from app.api.sessions import dependencies
from app.core.config import Settings
from app.core.database import Database
from app.domain.filing.declaration import archival_csv, archival_json
from app.domain.filing.fec import export_fec
from app.domain.filing.mappings import compile_package
from app.services.archive import control_archive
from app.services.backup import (
    create_backup,
    list_backups,
    preview_restore,
    restore_backup,
    verify_backup,
)
from app.services.closing import close_year, mark_ready, precheck, reopen_year
from app.services.documents import (
    complete_upload,
    delete_document,
    link_document,
    list_documents,
    published_document,
    read_document_content,
    search_entries,
    storage_policy,
    store_document,
    upload_grant,
)
from app.services.dossier_export import (
    create_dossier_export,
    list_dossier_exports,
    preview_dossier_export,
    restore_dossier,
    verify_dossier_export,
)
from app.services.efi import efi_worksheet, worksheet_pdf
from app.services.export_gate import export_status, require_export
from app.services.spreadsheet import year_workbook


def build_filing_router(database: Database, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/filing", tags=["filing"])
    read_session, write_session = dependencies(database)
    Read = Annotated[Session, Depends(read_session)]
    Write = Annotated[Session, Depends(write_session, scope="function")]

    @router.get("/years/{year_id}/precheck")
    def read_precheck(year_id: int, session: Read) -> dict[str, Any]:
        return precheck(session, year_id)

    @router.post("/years/{year_id}/ready")
    def ready(year_id: int, data: ReadyInput, session: Write) -> dict[str, Any]:
        return mark_ready(session, year_id, data.acknowledged)

    @router.post("/years/{year_id}/close")
    def close(year_id: int, data: CloseInput, session: Write) -> dict[str, Any]:
        return close_year(session, year_id, data.confirmation)

    @router.post("/years/{year_id}/reopen")
    def reopen(year_id: int, data: ReopenInput, session: Write) -> dict[str, Any]:
        return reopen_year(session, year_id, data.confirmation, data.reason)

    @router.get("/years/{year_id}/exports")
    def exports(year_id: int, session: Read) -> dict[str, Any]:
        return export_status(session, year_id)

    @router.get("/years/{year_id}/fec")
    def fec(year_id: int, session: Read) -> Response:
        status = require_export(session, year_id, "fec")
        rendered = export_fec(session, year_id)
        return _download(
            rendered["content"],
            "text/plain; charset=utf-8",
            rendered["filename"],
            _posture(status, "fec"),
            sha256=rendered["sha256"],
        )

    @router.get("/years/{year_id}/package")
    def package(year_id: int, session: Read) -> dict[str, Any]:
        return compile_package(session, year_id)

    @router.get("/years/{year_id}/efi")
    def efi(year_id: int, session: Read) -> dict[str, Any]:
        return efi_worksheet(session, year_id)

    @router.get("/years/{year_id}/efi.pdf")
    def efi_pdf(year_id: int, session: Read) -> Response:
        status = require_export(session, year_id, "pdf")
        worksheet = efi_worksheet(session, year_id)
        return _download(
            worksheet_pdf(worksheet),
            "application/pdf",
            f"liasse-{worksheet['year']}.pdf",
            _posture(status, "pdf"),
        )

    @router.get("/years/{year_id}/efi.json")
    def efi_json(year_id: int, session: Read) -> Response:
        status = require_export(session, year_id, "pdf")
        worksheet = efi_worksheet(session, year_id)
        content, digest = archival_json(worksheet)
        return _download(
            content,
            "application/json",
            f"efi-{worksheet['year']}.json",
            _posture(status, "pdf"),
            sha256=digest,
        )

    @router.get("/years/{year_id}/efi.csv")
    def efi_csv(year_id: int, session: Read) -> Response:
        status = require_export(session, year_id, "pdf")
        worksheet = efi_worksheet(session, year_id)
        content, digest = archival_csv(worksheet)
        return _download(
            content,
            "text/csv; charset=utf-8",
            f"efi-{worksheet['year']}.csv",
            _posture(status, "pdf"),
            sha256=digest,
        )

    @router.get("/years/{year_id}/export.xlsx")
    def export_workbook(year_id: int, session: Read) -> Response:
        bundle = year_workbook(session, year_id)
        return Response(
            content=bundle["content"],
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{bundle["filename"]}"'},
        )

    @router.get("/years/{year_id}/archive")
    def archive(year_id: int, session: Read) -> Response:
        status = require_export(session, year_id, "archive")
        bundle = control_archive(session, year_id)
        return _download(
            bundle["content"],
            "application/zip",
            bundle["filename"],
            _posture(status, "archive"),
            sha256=bundle["sha256"],
        )

    @router.get("/storage")
    def storage() -> dict[str, object]:
        return storage_policy(settings)

    @router.get("/documents")
    def document_list(session: Read) -> dict[str, Any]:
        return {"documents": list_documents(session)}

    @router.get("/entries")
    def entry_picker(
        session: Read,
        number: str | None = None,
        entry_date: date | None = None,
        piece: str | None = None,
    ) -> dict[str, Any]:
        return {
            "entries": search_entries(session, number=number, entry_date=entry_date, piece=piece)
        }

    @router.post("/documents", status_code=201)
    def documents(data: DocumentInput, session: Write) -> dict[str, Any]:
        row = store_document(session, settings, data)
        return published_document(session, row)

    @router.post("/documents/upload-grant")
    def document_grant(data: UploadGrantInput) -> dict[str, object]:
        return upload_grant(settings, data)

    @router.post("/documents/complete", status_code=201)
    def document_complete(data: CompleteUploadInput, session: Write) -> dict[str, Any]:
        row = complete_upload(session, settings, data)
        return published_document(session, row)

    @router.get("/documents/{document_id}/content")
    def document_content(document_id: int, session: Read) -> Response:
        document, content = read_document_content(session, settings, document_id)
        return Response(
            content=content,
            media_type=document.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{document.original_name}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Content-SHA256": document.sha256,
            },
        )

    @router.delete("/documents/{document_id}")
    def document_delete(document_id: int, session: Write) -> dict[str, object]:
        return delete_document(session, settings, document_id)

    @router.post("/documents/{document_id}/link")
    def link(document_id: int, data: EntryLinkInput, session: Write) -> dict[str, Any]:
        return link_document(session, document_id, data)

    @router.post("/backup", status_code=201)
    def backup() -> dict[str, str]:
        return create_backup(settings)

    @router.get("/backups")
    def backups() -> dict[str, Any]:
        return list_backups(settings)

    @router.post("/backups/verify")
    def backup_verify(data: BackupNameInput) -> dict[str, Any]:
        return verify_backup(settings, data.filename)

    @router.get("/backups/preview")
    def backup_preview(filename: str) -> dict[str, Any]:
        return preview_restore(settings, filename)

    @router.post("/backup/restore")
    def restore(data: RestoreInput) -> dict[str, Any]:
        return restore_backup(settings, database, data.filename, data.confirmation)

    @router.post("/dossier/export", status_code=201)
    def dossier_export() -> dict[str, str]:
        return create_dossier_export(settings, database)

    @router.get("/dossier/exports")
    def dossier_exports() -> dict[str, Any]:
        return list_dossier_exports(settings)

    @router.post("/dossier/exports/verify")
    def dossier_verify(data: BackupNameInput) -> dict[str, Any]:
        return verify_dossier_export(settings, data.filename)

    @router.get("/dossier/exports/preview")
    def dossier_preview(filename: str) -> dict[str, Any]:
        return preview_dossier_export(settings, database, filename)

    @router.post("/dossier/restore")
    def dossier_restore(data: RestoreInput) -> dict[str, Any]:
        return restore_dossier(settings, database, data.filename, data.confirmation)

    return router


def _posture(status: dict[str, Any], kind: str) -> str:
    slot = status["exports"].get(kind)
    if isinstance(slot, dict) and isinstance(slot.get("posture"), str):
        return str(slot["posture"])
    return "bloquee"


def _download(
    content: bytes,
    media_type: str,
    filename: str,
    posture: str,
    *,
    sha256: str | None = None,
) -> Response:
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Export-Posture": posture,
    }
    if sha256 is not None:
        headers["X-Content-SHA256"] = sha256
    return Response(content=content, media_type=media_type, headers=headers)
