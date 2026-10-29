"""Audited corrections and explicit invalidation of dependent outputs.

Validated ledger rows stay. Calculated depreciation periods on an open exercise
may be dropped so the next calculation rebuilds them. Closed exercises are left
untouched.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.models import FiscalYear
from app.models.assets import DepreciationPeriod
from app.models.base import utc_now
from app.models.filing import AuditEvent, TaxReturnSnapshot
from app.models.fiscal import FiscalComputation
from app.services.ledger import fail


def same(left: object, right: object) -> bool:
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        if left is None or right is None:
            return left is right
        left_amount = left if isinstance(left, Decimal) else Decimal(str(left))
        right_amount = right if isinstance(right, Decimal) else Decimal(str(right))
        return to_cents(left_amount) == to_cents(right_amount)
    return left == right


def changed_attributes(row: object, data: BaseModel, names: tuple[str, ...]) -> dict[str, object]:
    changed: dict[str, object] = {}
    fields_set = data.model_fields_set
    for name in names:
        if name not in fields_set:
            continue
        new = getattr(data, name)
        old = getattr(row, name)
        if not same(old, new):
            changed[name] = new
    return changed


def reject_locked(
    changed: dict[str, object],
    locks: list[dict[str, Any]],
    groups: dict[str, str],
) -> None:
    by_group: dict[str, dict[str, Any]] = {}
    for lock in locks:
        for group in lock["fields"]:
            by_group.setdefault(str(group), lock)
    for name in changed:
        group = groups.get(name)
        if group is not None and group in by_group:
            lock = by_group[group]
            fail(str(lock["code"]), str(lock["message"]))


def validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    raw = str(errors[0]["msg"]) if errors else "Correction refusée."
    prefix = "Value error, "
    return raw[len(prefix) :] if raw.startswith(prefix) else raw


def snapshot(row: object) -> dict[str, Any]:
    from app.api.operations import record

    return record(row)


def write_audit(
    session: Session,
    *,
    entity: str,
    entity_id: str,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reason: str,
    metadata: dict[str, Any],
) -> None:
    session.add(
        AuditEvent(
            entity=entity,
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            reason=reason,
            metadata_json=metadata,
        )
    )
    session.flush()


def closed_cap_blocks(session: Session, label: str) -> bool:
    """True when a closed exercise stored this label in its depreciation cap."""
    details_rows = session.scalars(
        select(FiscalComputation.details)
        .join(FiscalYear, FiscalYear.id == FiscalComputation.fiscal_year_id)
        .where(
            FiscalYear.status == "CLOSED",
            FiscalComputation.invalidated_at.is_(None),
        )
    )
    for details in details_rows:
        if not isinstance(details, dict):
            continue
        categories = details.get("depreciation_categories")
        if not isinstance(categories, list):
            continue
        for item in categories:
            if isinstance(item, dict) and item.get("label") == label:
                return True
    return False


def calculated_periods(session: Session, schedule_id: int) -> list[DepreciationPeriod]:
    return list(
        session.scalars(
            select(DepreciationPeriod)
            .where(
                DepreciationPeriod.schedule_id == schedule_id,
                DepreciationPeriod.status == "CALCULATED",
            )
            .order_by(DepreciationPeriod.id)
        )
    )


def count_periods(session: Session, schedule_ids: list[int], status: str) -> int:
    if not schedule_ids:
        return 0
    return len(
        session.scalars(
            select(DepreciationPeriod.id).where(
                DepreciationPeriod.schedule_id.in_(schedule_ids),
                DepreciationPeriod.status == status,
            )
        ).all()
    )


def release_calculated_periods(
    session: Session,
    schedule_id: int,
    *,
    reason: str,
    source_entity: str,
    source_id: str,
) -> tuple[list[int], list[int]]:
    """Drop open calculated periods. A ready exercise is returned to OPEN first."""
    periods = calculated_periods(session, schedule_id)
    ready: list[int] = []
    seen: set[int] = set()
    for period in periods:
        year = session.get(FiscalYear, period.fiscal_year_id)
        if year is None:
            fail("YEAR_NOT_FOUND", "Exercice de la période introuvable.", 500)
        if year.status == "CLOSED":
            fail(
                "YEAR_LOCKED",
                "Un exercice clôturé contient une période calculée de ce plan. "
                "Rouvrez-le avant de corriger la valeur, la durée, les dates ou les comptes. "
                "La période n’est pas supprimée.",
            )
        if year.status == "READY_TO_CLOSE" and year.id not in seen:
            before = year.status
            year.status = "OPEN"
            seen.add(year.id)
            ready.append(year.id)
            write_audit(
                session,
                entity="fiscal_year",
                entity_id=str(year.id),
                action="DEPENDENCIES_INVALIDATED",
                before={"status": before},
                after={"status": "OPEN"},
                reason=reason,
                metadata={"source_entity": source_entity, "source_id": source_id},
            )
    session.flush()
    dropped = [period.id for period in periods]
    for period in periods:
        session.delete(period)
    session.flush()
    return dropped, ready


def invalidate_open_dependencies(
    session: Session,
    *,
    reason: str,
    source_entity: str,
    source_id: str,
) -> dict[str, Any]:
    """Invalidate fiscal output on exercises that are not closed."""
    fiscal_count = 0
    ready: list[int] = []
    snapshots = 0
    years = session.scalars(select(FiscalYear).order_by(FiscalYear.id)).all()
    for year in years:
        if year.status == "CLOSED":
            continue
        if year.status == "READY_TO_CLOSE":
            before = year.status
            year.status = "OPEN"
            ready.append(year.id)
            write_audit(
                session,
                entity="fiscal_year",
                entity_id=str(year.id),
                action="DEPENDENCIES_INVALIDATED",
                before={"status": before},
                after={"status": "OPEN"},
                reason=reason,
                metadata={"source_entity": source_entity, "source_id": source_id},
            )
        rows = session.scalars(
            select(FiscalComputation).where(
                FiscalComputation.fiscal_year_id == year.id,
                FiscalComputation.invalidated_at.is_(None),
            )
        ).all()
        for row in rows:
            row.invalidated_at = utc_now()
            fiscal_count += 1
        current = session.scalars(
            select(TaxReturnSnapshot).where(
                TaxReturnSnapshot.fiscal_year_id == year.id,
                TaxReturnSnapshot.status == "CURRENT",
            )
        ).all()
        for snap in current:
            snap.status = "SUPERSEDED"
            snapshots += 1
    session.flush()
    return {
        "fiscal_computations": fiscal_count,
        "ready_years_reset": ready,
        "snapshots_superseded": snapshots,
    }


def empty_invalidation() -> dict[str, Any]:
    return {
        "dropped_period_ids": [],
        "fiscal_computations": 0,
        "ready_years_reset": [],
        "snapshots_superseded": 0,
    }


def merge_invalidation(
    dropped: list[int], ready_from_periods: list[int], stats: dict[str, Any]
) -> dict[str, Any]:
    ready = list(dict.fromkeys([*ready_from_periods, *stats["ready_years_reset"]]))
    return {
        "dropped_period_ids": dropped,
        "fiscal_computations": stats["fiscal_computations"],
        "ready_years_reset": ready,
        "snapshots_superseded": stats["snapshots_superseded"],
    }


def touches(changed: dict[str, object], groups: dict[str, str], names: set[str]) -> bool:
    return any(groups.get(name) in names or name in names for name in changed)


def period_in_closed_year(session: Session, schedule_ids: list[int]) -> bool:
    if not schedule_ids:
        return False
    rows = session.execute(
        select(DepreciationPeriod.fiscal_year_id)
        .where(
            DepreciationPeriod.schedule_id.in_(schedule_ids),
            DepreciationPeriod.status == "CALCULATED",
        )
        .distinct()
    ).all()
    for (year_id,) in rows:
        year = session.get(FiscalYear, year_id)
        if year is not None and year.status == "CLOSED":
            return True
    return False


def iso_or_none(value: date | None) -> str | None:
    return None if value is None else value.isoformat()
