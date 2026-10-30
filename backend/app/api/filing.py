"""Closing, FEC, liasse worksheet, documents and backups."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.filing_schemas import CloseInput, DocumentInput, ReadyInput, ReopenInput, RestoreInput
from app.api.sessions import dependencies
from app.core.config import Settings
from app.core.database import Database
from app.domain.filing.fec import export_fec
from app.domain.filing.mappings import compile_package
from app.services.archive import control_archive
from app.services.backup import create_backup, restore_backup
from app.services.closing import close_year, mark_ready, precheck, reopen_year
from app.services.documents import store_document
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

    @router.post("/documents", status_code=201)
    def documents(data: DocumentInput, session: Write) -> dict[str, Any]:
        row = store_document(session, settings, data)
        return {
            "id": row.id,
            "sha256": row.sha256,
            "size": row.size,
            "media_type": row.media_type,
            "original_name": row.original_name,
            "entry_id": row.entry_id,
        }

    @router.post("/backup", status_code=201)
    def backup() -> dict[str, str]:
        return create_backup(settings)

    @router.post("/backup/restore")
    def restore(data: RestoreInput) -> dict[str, str]:
        destination = settings.database_path.parent / "restore-check.sqlite3"
        return restore_backup(settings, data.filename, destination)

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
