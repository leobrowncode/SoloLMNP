"""One-shot preload for the asset list.

The correction view asks, for every asset, for its components, schedules,
period counts, property entry and closed-year cap. Priming those reads once
keeps the list from repeating the same queries. Callers that do not prime
keep the original per-row queries.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AccountingEntry,
    Asset,
    AssetComponent,
    DepreciationPeriod,
    DepreciationSchedule,
    FiscalComputation,
    FiscalYear,
)

CACHE_KEY = "sololmnp_asset_reads"


def prime_asset_reads(session: Session, assets: list[Asset]) -> None:
    if not assets:
        return
    asset_ids = [asset.id for asset in assets]
    components: dict[int, list[AssetComponent]] = {asset_id: [] for asset_id in asset_ids}
    for component in session.scalars(
        select(AssetComponent)
        .where(AssetComponent.asset_id.in_(asset_ids))
        .order_by(AssetComponent.id)
    ):
        components[component.asset_id].append(component)
    component_ids = [row.id for rows in components.values() for row in rows]
    schedules_by_asset: dict[int, DepreciationSchedule | None] = dict.fromkeys(asset_ids)
    schedules_by_component: dict[int, DepreciationSchedule | None] = dict.fromkeys(component_ids)
    component_schedules: dict[int, list[DepreciationSchedule]] = {
        asset_id: [] for asset_id in asset_ids
    }
    component_owner = {row.id: asset_id for asset_id, rows in components.items() for row in rows}
    filters = [DepreciationSchedule.asset_id.in_(asset_ids)]
    if component_ids:
        filters.append(DepreciationSchedule.component_id.in_(component_ids))
    for schedule in session.scalars(select(DepreciationSchedule).where(or_(*filters))):
        if schedule.asset_id is not None:
            schedules_by_asset[schedule.asset_id] = schedule
        if schedule.component_id is not None:
            schedules_by_component[schedule.component_id] = schedule
            owner = component_owner.get(schedule.component_id)
            if owner is not None:
                component_schedules[owner].append(schedule)
    known = {
        schedule.id
        for schedule in [*schedules_by_asset.values(), *schedules_by_component.values()]
        if schedule is not None
    }
    counts: dict[tuple[int, str], int] = {}
    closed_schedules: set[int] = set()
    if known:
        for schedule_id, status, total in session.execute(
            select(
                DepreciationPeriod.schedule_id,
                DepreciationPeriod.status,
                func.count(),
            )
            .where(DepreciationPeriod.schedule_id.in_(known))
            .group_by(DepreciationPeriod.schedule_id, DepreciationPeriod.status)
        ):
            counts[(int(schedule_id), str(status))] = int(total)
        closed_years = set(
            session.scalars(select(FiscalYear.id).where(FiscalYear.status == "CLOSED")).all()
        )
        if closed_years:
            closed_schedules = set(
                session.scalars(
                    select(DepreciationPeriod.schedule_id)
                    .where(
                        DepreciationPeriod.schedule_id.in_(known),
                        DepreciationPeriod.status == "CALCULATED",
                        DepreciationPeriod.fiscal_year_id.in_(closed_years),
                    )
                    .distinct()
                ).all()
            )
    property_ids = {asset.property_id for asset in assets}
    entries: dict[int, AccountingEntry | None] = dict.fromkeys(property_ids)
    source_ids = [f"property:{property_id}" for property_id in property_ids]
    found = list(
        session.scalars(
            select(AccountingEntry)
            .where(
                AccountingEntry.source_type == "ACQUISITION",
                AccountingEntry.source_id.in_(source_ids),
                AccountingEntry.status == "VALIDATED",
            )
            .order_by(AccountingEntry.id)
        )
    )
    reversed_ids: set[int] = set()
    if found:
        reversed_ids = {
            value
            for value in session.scalars(
                select(AccountingEntry.reversal_of_id).where(
                    AccountingEntry.reversal_of_id.in_([entry.id for entry in found])
                )
            ).all()
            if value is not None
        }
    for entry in found:
        if entry.id in reversed_ids:
            continue
        property_id = int(str(entry.source_id).removeprefix("property:"))
        if entries.get(property_id) is None:
            entries[property_id] = entry
    labels: set[str] = set()
    for details in session.scalars(
        select(FiscalComputation.details)
        .join(FiscalYear, FiscalYear.id == FiscalComputation.fiscal_year_id)
        .where(
            FiscalYear.status == "CLOSED",
            FiscalComputation.invalidated_at.is_(None),
        )
    ):
        if not isinstance(details, dict):
            continue
        categories = details.get("depreciation_categories")
        if not isinstance(categories, list):
            continue
        for item in categories:
            if isinstance(item, dict) and isinstance(item.get("label"), str):
                labels.add(item["label"])
    session.info[CACHE_KEY] = {
        "components": components,
        "schedules_by_asset": schedules_by_asset,
        "schedules_by_component": schedules_by_component,
        "component_schedules": component_schedules,
        "known_schedules": known,
        "counts": counts,
        "closed_schedules": closed_schedules,
        "entries": entries,
        "cap_labels": labels,
    }


def _cache(session: Session) -> dict[str, Any] | None:
    value = session.info.get(CACHE_KEY)
    return value if isinstance(value, dict) else None


def cached_components(session: Session, asset_id: int) -> list[AssetComponent] | None:
    cache = _cache(session)
    if cache is None:
        return None
    rows = cache["components"].get(asset_id)
    return None if rows is None else list(rows)


def cached_asset_schedule(
    session: Session, asset_id: int
) -> tuple[bool, DepreciationSchedule | None]:
    cache = _cache(session)
    if cache is None or asset_id not in cache["schedules_by_asset"]:
        return False, None
    return True, cache["schedules_by_asset"][asset_id]


def cached_component_schedule(
    session: Session, component_id: int
) -> tuple[bool, DepreciationSchedule | None]:
    cache = _cache(session)
    if cache is None or component_id not in cache["schedules_by_component"]:
        return False, None
    return True, cache["schedules_by_component"][component_id]


def cached_component_schedules(
    session: Session, asset_id: int
) -> list[DepreciationSchedule] | None:
    cache = _cache(session)
    if cache is None:
        return None
    rows = cache["component_schedules"].get(asset_id)
    return None if rows is None else list(rows)


def cached_period_count(session: Session, schedule_ids: list[int], status: str) -> int | None:
    cache = _cache(session)
    if cache is None or any(
        schedule_id not in cache["known_schedules"] for schedule_id in schedule_ids
    ):
        return None
    counts: dict[tuple[int, str], int] = cache["counts"]
    return sum(counts.get((schedule_id, status), 0) for schedule_id in schedule_ids)


def cached_closed_period(session: Session, schedule_ids: list[int]) -> bool | None:
    cache = _cache(session)
    if cache is None or any(
        schedule_id not in cache["known_schedules"] for schedule_id in schedule_ids
    ):
        return None
    closed: set[int] = cache["closed_schedules"]
    return any(schedule_id in closed for schedule_id in schedule_ids)


def cached_property_entry(
    session: Session, property_id: int
) -> tuple[bool, AccountingEntry | None]:
    cache = _cache(session)
    if cache is None or property_id not in cache["entries"]:
        return False, None
    return True, cache["entries"][property_id]


def cached_cap_label(session: Session, label: str) -> bool | None:
    cache = _cache(session)
    if cache is None:
        return None
    return label in cache["cap_labels"]
