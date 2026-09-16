"""Deterministic actual-day linear schedules and ledger postings."""

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.asset_schemas import AssetInput, ComponentInput, DepreciationPostInput
from app.api.ledger_schemas import EntryInput, LineInput
from app.core.money import from_cents, to_cents
from app.models import (
    Account,
    AccountingEntry,
    Asset,
    AssetComponent,
    DepreciationPeriod,
    DepreciationSchedule,
    Property,
)
from app.services.ledger import create_draft, fail, get_year, money, post_entry


def add_months(value: date, months: int) -> date:
    index = value.month - 1 + months
    year, month = value.year + index // 12, index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def account(session: Session, number: str, prefix: str) -> None:
    row = session.get(Account, number)
    if row is None or not row.active or not number.startswith(prefix):
        fail(
            "ASSET_ACCOUNT_INVALID",
            f"Le compte {number} doit être un compte actif de classe {prefix}.",
            422,
        )


def create_asset(session: Session, data: AssetInput) -> Asset:
    if session.get(Property, data.property_id) is None:
        fail("PROPERTY_NOT_FOUND", "Bien introuvable.", 404)
    account(session, data.asset_account, "2")
    if data.category == "LAND":
        if not data.asset_account.startswith("211"):
            fail("LAND_ACCOUNT_INVALID", "Le terrain doit utiliser un compte 211.", 422)
    else:
        if data.depreciation_account is None:
            fail(
                "DEPRECIATION_ACCOUNT_REQUIRED",
                "Le compte d’amortissement est obligatoire.",
                422,
            )
        account(session, data.depreciation_account, "28")
        if data.asset_account.startswith("28"):
            fail(
                "ASSET_ACCOUNT_INVALID",
                "Le compte d’actif ne peut pas être un compte d’amortissement.",
                422,
            )
    row = Asset(**data.model_dump())
    session.add(row)
    session.flush()
    return row


def create_component(session: Session, asset_id: int, data: ComponentInput) -> AssetComponent:
    asset = session.get(Asset, asset_id)
    if asset is None:
        fail("ASSET_NOT_FOUND", "Immobilisation introuvable.", 404)
    if asset.category != "BUILDING":
        fail("COMPONENT_PARENT_INVALID", "Seule une construction peut être décomposée.", 422)
    if data.service_start_date < asset.service_start_date:
        fail(
            "COMPONENT_DATE_INVALID",
            "La mise en service du composant précède celle de la construction.",
            422,
        )
    account(session, data.asset_account, "2")
    account(session, data.depreciation_account, "28")
    used = sum(
        to_cents(row.value)
        for row in session.scalars(
            select(AssetComponent).where(AssetComponent.asset_id == asset.id)
        )
    )
    if used + to_cents(data.value) > to_cents(asset.depreciable_value) - to_cents(
        asset.residual_value
    ):
        fail("COMPONENT_TOTAL_EXCEEDS_BASE", "Les composants dépassent la base amortissable.", 422)
    row = AssetComponent(asset_id=asset.id, **data.model_dump())
    session.add(row)
    session.flush()
    return row


def ensure_schedules(session: Session) -> list[DepreciationSchedule]:
    schedules: list[DepreciationSchedule] = []
    for asset in session.scalars(select(Asset).order_by(Asset.id)):
        if asset.category == "LAND":
            continue
        components = list(
            session.scalars(
                select(AssetComponent)
                .where(AssetComponent.asset_id == asset.id)
                .order_by(AssetComponent.id)
            )
        )
        targets: list[tuple[int | None, int | None, Decimal, int, date, str, str]]
        if components:
            total = sum(to_cents(component.value) for component in components)
            expected = to_cents(asset.depreciable_value) - to_cents(asset.residual_value)
            if total != expected:
                fail(
                    "DECOMPOSITION_INCOMPLETE",
                    f"Les composants de « {asset.label} » doivent totaliser {money(expected)} €.",
                    422,
                )
            targets = [
                (
                    None,
                    component.id,
                    component.value,
                    component.useful_life_months,
                    component.service_start_date,
                    component.asset_account,
                    component.depreciation_account,
                )
                for component in components
            ]
        else:
            if asset.useful_life_months is None or asset.depreciation_account is None:
                fail("ASSET_PLAN_INVALID", f"Le plan de « {asset.label} » est incomplet.", 422)
            targets = [
                (
                    asset.id,
                    None,
                    from_cents(to_cents(asset.depreciable_value) - to_cents(asset.residual_value)),
                    asset.useful_life_months,
                    asset.service_start_date,
                    asset.asset_account,
                    asset.depreciation_account,
                )
            ]
        for (
            asset_id,
            component_id,
            base,
            life,
            start,
            asset_account,
            depreciation_account,
        ) in targets:
            query = select(DepreciationSchedule).where(
                DepreciationSchedule.component_id == component_id
                if component_id is not None
                else DepreciationSchedule.asset_id == asset_id
            )
            schedule = session.scalar(query)
            if schedule is None:
                schedule = DepreciationSchedule(
                    asset_id=asset_id,
                    component_id=component_id,
                    base=base,
                    method="LINEAR",
                    useful_life_months=life,
                    service_start_date=start,
                    end_date=add_months(start, life) - timedelta(days=1),
                    asset_account=asset_account,
                    depreciation_account=depreciation_account,
                )
                session.add(schedule)
                session.flush()
            schedules.append(schedule)
    return schedules


def calculate_year(session: Session, year_id: int) -> list[DepreciationPeriod]:
    year = get_year(session, year_id, writable=True)
    schedules = ensure_schedules(session)
    output: list[DepreciationPeriod] = []
    for schedule in schedules:
        start = max(year.start_date, schedule.service_start_date)
        end = min(year.end_date, schedule.end_date)
        if schedule.asset_id is not None:
            asset = session.get(Asset, schedule.asset_id)
        else:
            component = session.get(AssetComponent, schedule.component_id)
            if component is None:
                fail("COMPONENT_NOT_FOUND", "Composant introuvable.", 500)
            asset = session.get(Asset, component.asset_id)
        if asset is None:
            fail("ASSET_NOT_FOUND", "Immobilisation introuvable.", 500)
        if asset.disposed_at is not None:
            end = min(end, asset.disposed_at)
        if start > end:
            continue
        existing = session.scalar(
            select(DepreciationPeriod).where(
                DepreciationPeriod.schedule_id == schedule.id,
                DepreciationPeriod.fiscal_year_id == year.id,
            )
        )
        if existing is not None:
            output.append(existing)
            continue
        total_days = (schedule.end_date - schedule.service_start_date).days + 1
        before_days = max(0, (start - schedule.service_start_date).days)
        end_days = min(total_days, (end - schedule.service_start_date).days + 1)
        base = Decimal(to_cents(schedule.base))
        cumulative_before = int(
            (base * Decimal(before_days) / Decimal(total_days)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        accumulated = int(
            (base * Decimal(end_days) / Decimal(total_days)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        amount = accumulated - cumulative_before
        period = DepreciationPeriod(
            schedule_id=schedule.id,
            fiscal_year_id=year.id,
            period_start=start,
            period_end=end,
            days=(end - start).days + 1,
            amount=from_cents(amount),
            accumulated=from_cents(accumulated),
            net_book_value=from_cents(to_cents(schedule.base) - accumulated),
            status="CALCULATED",
        )
        session.add(period)
        session.flush()
        output.append(period)
    return output


def post_period(session: Session, period_id: int, data: DepreciationPostInput) -> AccountingEntry:
    period = session.get(DepreciationPeriod, period_id)
    if period is None:
        fail("PERIOD_NOT_FOUND", "Période d’amortissement introuvable.", 404)
    if period.status == "POSTED":
        if period.accounting_entry_id is None:
            fail("PERIOD_POSTING_INVALID", "La dotation comptabilisée est incohérente.", 500)
        entry = session.get(AccountingEntry, period.accounting_entry_id)
        if entry is None:
            fail("ENTRY_NOT_FOUND", "Écriture de dotation introuvable.", 500)
        return entry
    get_year(session, period.fiscal_year_id, writable=True)
    if to_cents(period.amount) <= 0:
        fail("ZERO_DEPRECIATION", "Une dotation nulle ne peut pas être comptabilisée.", 422)
    schedule = session.get(DepreciationSchedule, period.schedule_id)
    if schedule is None:
        fail("SCHEDULE_NOT_FOUND", "Plan d’amortissement introuvable.", 500)
    label = "Dotation aux amortissements"
    entry_input = EntryInput(
        fiscal_year_id=period.fiscal_year_id,
        journal_code="OD",
        accounting_date=period.period_end,
        piece_reference=data.piece_reference,
        piece_date=period.period_end,
        label=label,
        lines=[
            LineInput(
                account_number="681100", label=label, debit=str(period.amount), credit="0.00"
            ),
            LineInput(
                account_number=schedule.depreciation_account,
                label=label,
                debit="0.00",
                credit=str(period.amount),
            ),
        ],
    )
    entry = create_draft(session, entry_input)
    entry.source_type = "DEPRECIATION"
    entry.source_id = data.request_id
    post_entry(session, entry, entry.version)
    period.accounting_entry_id = entry.id
    period.status = "POSTED"
    session.flush()
    return entry


def row_json(
    row: Asset | AssetComponent | DepreciationSchedule | DepreciationPeriod,
) -> dict[str, Any]:
    from app.api.operations import record

    return record(row)
