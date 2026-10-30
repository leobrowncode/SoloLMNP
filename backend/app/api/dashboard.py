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
    "bloque": "Bloqué",
    "pret": "Prête",
    "fait": "Terminé",
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
    status_label: Literal["À faire", "En cours", "Bloqué", "Prête", "Terminé"]
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


class DashboardProgression(BaseModel):
    done: int = Field(ge=0)
    total: int = Field(ge=0)
    label: str
    current_step: StepId
    current_label: str
    current_status: StepStatus
    current_status_label: Literal["À faire", "En cours", "Bloqué", "Prête", "Terminé"]
    summary: str

    @model_validator(mode="after")
    def label_matches_count(self) -> Self:
        if self.label != f"{self.done}/{self.total}":
            raise ValueError("Le libellé de progression ne correspond pas au décompte.")
        if self.current_status_label != _STATUS_LABELS[self.current_status]:
            raise ValueError("Le libellé de l’étape en cours ne correspond pas à son état.")
        if self.done > self.total:
            raise ValueError("La progression dépasse le nombre d’étapes.")
        return self


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
    progression: DashboardProgression

    @model_validator(mode="after")
    def progression_matches_steps(self) -> Self:
        done = sum(1 for step in self.steps if step.status == "fait")
        if self.progression.done != done or self.progression.total != len(self.steps):
            raise ValueError("La progression ne correspond pas aux étapes.")
        if self.steps and self.progression.current_step != self.continue_action.step:
            raise ValueError("La progression ne correspond pas à la prochaine action.")
        current = next(
            (step for step in self.steps if step.id == self.progression.current_step),
            None,
        )
        if current is None:
            if self.steps:
                raise ValueError("La progression ne correspond pas à une étape.")
            return self
        if (
            current.status != self.progression.current_status
            or current.status_label != self.progression.current_status_label
            or current.label != self.progression.current_label
            or current.summary != self.progression.summary
        ):
            raise ValueError("La progression ne correspond pas à l’étape en cours.")
        for step in self.steps:
            if step.status == "bloque" and not step.prerequisites:
                raise ValueError("Chaque blocage a un lien correctif.")
        return self

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
