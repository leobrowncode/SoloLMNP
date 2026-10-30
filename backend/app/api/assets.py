"""Fixed-asset register, schedules and accounting depreciation API."""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.asset_schemas import (
    AssetCorrectionInput,
    AssetInput,
    ComponentCorrectionInput,
    ComponentInput,
    DepreciationBatchInput,
    DepreciationPostInput,
    DwellingPlanConfirm,
    PropertyEntryInput,
)
from app.api.sessions import dependencies
from app.core.database import Database
from app.models import Asset, AssetComponent, DepreciationPeriod, DepreciationSchedule
from app.services import assets as service
from app.services import structuring
from app.services.asset_read_cache import prime_asset_reads
from app.services.ledger import entry_json, fail

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def _idempotency_key(value: str | None) -> str:
    if value is None or _IDEMPOTENCY_KEY.fullmatch(value) is None:
        fail(
            "IDEMPOTENCY_KEY_REQUIRED",
            "L’en-tête Idempotency-Key est requis : 8 à 80 caractères (lettres, chiffres, _ ou -).",
            422,
            field="Idempotency-Key",
            location="header",
        )
    return value


def build_assets_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/api/assets", tags=["assets"])
    read, write = dependencies(database)
    Read = Annotated[Session, Depends(read)]
    Write = Annotated[Session, Depends(write, scope="function")]

    @router.get("")
    def assets(session: Read) -> list[dict[str, Any]]:
        rows = list(session.scalars(select(Asset).order_by(Asset.id)))
        prime_asset_reads(session, rows)
        return [structuring.present_asset(session, asset) for asset in rows]

    @router.get("/properties/{property_id}/plan")
    def preview_dwelling_plan(property_id: int, session: Read) -> dict[str, Any]:
        return service.preview_dwelling_plan(session, property_id)

    @router.post("/properties/{property_id}/plan")
    def dwelling_plan(
        property_id: int,
        data: DwellingPlanConfirm,
        session: Write,
        response: Response,
    ) -> dict[str, Any]:
        result = service.install_dwelling_plan(
            session,
            property_id,
            confirm=data.confirm,
            preview_token=data.preview_token,
        )
        response.status_code = 201 if result["created"] else 200
        return result

    @router.post("/properties/{property_id}/entry")
    def property_entry(
        property_id: int, data: PropertyEntryInput, session: Write
    ) -> dict[str, Any]:
        return service.property_entry(session, property_id, data)

    @router.post("", status_code=201)
    def create(data: AssetInput, session: Write) -> dict[str, Any]:
        return service.row_json(service.create_asset(session, data))

    @router.post("/{asset_id}/components", status_code=201)
    def component(asset_id: int, data: ComponentInput, session: Write) -> dict[str, Any]:
        return service.row_json(service.create_component(session, asset_id, data))

    @router.patch("/{asset_id}")
    def correct_asset(asset_id: int, data: AssetCorrectionInput, session: Write) -> dict[str, Any]:
        return structuring.correct_asset(session, asset_id, data)

    @router.patch("/{asset_id}/components/{component_id}")
    def correct_component(
        asset_id: int, component_id: int, data: ComponentCorrectionInput, session: Write
    ) -> dict[str, Any]:
        return structuring.correct_component(session, asset_id, component_id, data)

    @router.post("/years/{year_id}/calculate")
    def calculate(year_id: int, session: Write) -> list[dict[str, Any]]:
        return [period_json(session, row) for row in service.calculate_year(session, year_id)]

    @router.post("/years/{year_id}/post")
    def post_year(
        year_id: int,
        data: DepreciationBatchInput,
        session: Write,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        return service.post_period_batch(
            session, year_id, _idempotency_key(idempotency_key), data.items
        )

    @router.get("/years/{year_id}/periods")
    def periods(year_id: int, session: Read) -> list[dict[str, Any]]:
        rows = session.scalars(
            select(DepreciationPeriod)
            .where(DepreciationPeriod.fiscal_year_id == year_id)
            .order_by(DepreciationPeriod.id)
        )
        return [period_json(session, row) for row in rows]

    @router.post("/periods/{period_id}/post", status_code=201)
    def post(period_id: int, data: DepreciationPostInput, session: Write) -> dict[str, Any]:
        return entry_json(service.post_period(session, period_id, data))

    return router


def period_json(session: Session, period: DepreciationPeriod) -> dict[str, Any]:
    schedule = session.get(DepreciationSchedule, period.schedule_id)
    if schedule is None:
        fail("SCHEDULE_NOT_FOUND", "Plan d’amortissement introuvable.", 500)
    if schedule.asset_id is not None:
        asset = session.get(Asset, schedule.asset_id)
        target_id = asset.id if asset else None
        target_label = asset.label if asset else None
        target_type = "ASSET"
    else:
        component = session.get(AssetComponent, schedule.component_id)
        target_id = component.id if component else None
        target_label = component.label if component else None
        target_type = "COMPONENT"
    if target_id is None or target_label is None:
        fail("DEPRECIATION_TARGET_NOT_FOUND", "Cible d’amortissement introuvable.", 500)
    return {
        **service.row_json(period),
        "target_type": target_type,
        "target_id": target_id,
        "target_label": target_label,
        "base": service.row_json(schedule)["base"],
        "depreciation_account": schedule.depreciation_account,
    }
