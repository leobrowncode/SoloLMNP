"""GET /api/dashboard — dossier board for the overview. Amounts are integer cents."""

import json
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.api.sessions import dependencies
from app.core.database import Database
from app.services.dashboard import current_dashboard

StepId = Literal["structure", "operations", "assets", "opening", "closing", "filing"]
StepStatus = Literal["a_faire", "en_cours", "bloque", "pret", "fait"]

_STATUS_LABELS: dict[str, str] = {
    "a_faire": "À faire",
    "en_cours": "En cours",
    "bloque": "Bloquée",
    "pret": "Prête",
    "fait": "Faite",
}
_DOSSIER_LABELS = {
    "incomplet": "Incomplet",
    "bloque": "Bloqué",
    "pret_a_verifier": "Prêt à vérifier",
    "cloture": "Clôturé",
}


class DashboardAction(BaseModel):
    label: str
    href: str


class DashboardPrerequisite(BaseModel):
    code: str
    message: str
    action: DashboardAction


class DashboardEvent(BaseModel):
    occurred_at: datetime
    label: str


class DashboardStep(BaseModel):
    id: StepId
    label: str
    status: StepStatus
    status_label: Literal["À faire", "En cours", "Bloquée", "Prête", "Faite"]
    summary: str
    prerequisites: list[DashboardPrerequisite]
    last_event: DashboardEvent | None
    amount_cents: int | None

    @model_validator(mode="after")
    def label_matches_status(self) -> Self:
        if self.status_label != _STATUS_LABELS[self.status]:
            raise ValueError("Le libellé de l’étape ne correspond pas à son état.")
        return self


class DashboardContinue(BaseModel):
    label: Literal["Continuer"]
    href: str
    detail: str
    step: StepId


class DossierView(BaseModel):
    status: Literal["incomplet", "bloque", "pret_a_verifier", "cloture"]
    label: Literal["Incomplet", "Bloqué", "Prêt à vérifier", "Clôturé"]
    fiscal_year_id: int | None
    year: int | None
    year_status: Literal["OPEN", "READY_TO_CLOSE", "CLOSED"] | None
    vintage_status: Literal["research_only"]

    @model_validator(mode="after")
    def label_matches_status(self) -> Self:
        if self.label != _DOSSIER_LABELS[self.status]:
            raise ValueError("Le libellé du dossier ne correspond pas à son statut.")
        return self


class DashboardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dossier: DossierView
    continue_action: DashboardContinue = Field(alias="continue")
    steps: list[DashboardStep]

    @model_validator(mode="after")
    def not_declarable(self) -> Self:
        encoded = json.dumps(
            self.model_dump(mode="json", by_alias=True), ensure_ascii=False
        ).lower()
        if "declarable" in encoded or "déclarable" in encoded:
            raise ValueError("Le tableau de bord ne présente pas un dossier déclarable.")
        return self


def build_dashboard_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["system"])
    read_session, _write_session = dependencies(database)
    read = Annotated[Session, Depends(read_session)]

    @router.get("/dashboard", response_model=DashboardResponse)
    def read_dashboard(session: read) -> Any:
        return current_dashboard(session)

    return router
