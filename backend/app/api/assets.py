"""Fixed-asset register, schedules and accounting depreciation API."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.asset_schemas import AssetInput, ComponentInput, DepreciationPostInput
from app.api.sessions import dependencies
from app.core.database import Database
from app.models import Asset, AssetComponent, DepreciationPeriod, DepreciationSchedule
from app.services import assets as service
from app.services.ledger import entry_json, fail


def build_assets_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/api/assets", tags=["assets"])
    read, write = dependencies(database)
    Read = Annotated[Session, Depends(read)]
    Write = Annotated[Session, Depends(write, scope="function")]

    @router.get("")
    def assets(session: Read) -> list[dict[str, Any]]:
        rows = []
        for asset in session.scalars(select(Asset).order_by(Asset.id)):
            components = session.scalars(
                select(AssetComponent)
                .where(AssetComponent.asset_id == asset.id)
                .order_by(AssetComponent.id)
            )
            rows.append(
                {
                    **service.row_json(asset),
                    "components": [service.row_json(row) for row in components],
                }
            )
        return rows

    @router.post("", status_code=201)
    def create(data: AssetInput, session: Write) -> dict[str, Any]:
        return service.row_json(service.create_asset(session, data))

    @router.post("/{asset_id}/components", status_code=201)
    def component(asset_id: int, data: ComponentInput, session: Write) -> dict[str, Any]:
        return service.row_json(service.create_component(session, asset_id, data))

    @router.post("/years/{year_id}/calculate")
    def calculate(year_id: int, session: Write) -> list[dict[str, Any]]:
        return [period_json(session, row) for row in service.calculate_year(session, year_id)]

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
