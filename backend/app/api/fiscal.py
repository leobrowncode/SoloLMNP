"""Fiscal preview API. The status is never declarable."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.ledger_schemas import FiscalInput
from app.api.sessions import dependencies
from app.core.database import Database
from app.domain.fiscal.loader import available_vintages, load_vintage, public_rule
from app.domain.fiscal.output_status import calculation_status
from app.services.fiscal import compute_fiscal, displayed_fiscal, reintegration_suggestions


def build_fiscal_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/api/fiscal", tags=["fiscal"])
    read_session, write_session = dependencies(database)
    Read = Annotated[Session, Depends(read_session)]
    Write = Annotated[Session, Depends(write_session, scope="function")]

    @router.get("/vintages")
    def vintages() -> dict[str, Any]:
        rows = []
        for vintage in available_vintages():
            loaded = load_vintage(vintage)
            presented = calculation_status(vintage)
            rows.append(
                {
                    "vintage": vintage,
                    "status": "research_only",
                    "output_status": presented["output_status"],
                    "output_label": presented["output_label"],
                    "declarable": presented["declarable"],
                    "sha256": loaded["sha256"],
                    "executable": [rule["id"] for rule in loaded["executable"]],
                    "blocked": [public_rule(rule) for rule in loaded["blocked"]],
                    "scope": loaded["scope"],
                    "rules": [
                        public_rule(rule)
                        for rule in (
                            *loaded["executable"],
                            *loaded["scope_rules"],
                            *loaded["blocked"],
                        )
                    ],
                }
            )
        return {
            "status": "research_only",
            "declarable": False,
            "output_status": "recherche",
            "output_label": "Recherche",
            "vintages": rows,
        }

    @router.get("/years/{year_id}")
    def read_year(year_id: int, session: Read) -> dict[str, Any]:
        return displayed_fiscal(session, year_id)

    @router.get("/years/{year_id}/reintegrations")
    def reintegrations(year_id: int, session: Read) -> list[dict[str, str]]:
        return reintegration_suggestions(session, year_id)

    @router.post("/years/{year_id}")
    def compute(year_id: int, data: FiscalInput, session: Write) -> dict[str, Any]:
        return compute_fiscal(session, year_id, data)

    return router
