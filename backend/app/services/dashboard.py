"""Read the current dossier board. Rules stay in app.domain.dashboard."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.domain.dashboard import (
    DashboardFacts,
    EventFact,
    PrerequisiteFact,
    build_dashboard,
)
from app.models import (
    AccountingEntry,
    Asset,
    AuditEvent,
    BankAccount,
    BusinessOperation,
    DepreciationPeriod,
    FiscalComputation,
    FiscalYear,
    Property,
    RentalActivity,
    TaxReturnSnapshot,
)
from app.services.closing import precheck
from app.services.dossier import current_dossier
from app.services.export_gate import export_status
from app.services.fiscal import ledger_fingerprint
from app.services.result_closing import _live

_OPERATION_LABELS = {
    "REVENUE": "Recette enregistrée",
    "EXPENSE": "Dépense enregistrée",
    "SETTLEMENT": "Règlement enregistré",
    "LOAN_PAYMENT": "Échéance enregistrée",
    "LOAN_FUNDING": "Déblocage enregistré",
}
_AUDIT_LABELS = {
    "READY_TO_CLOSE": "Exercice passé en prêt à clôturer",
    "CLOSED": "Exercice clôturé",
    "REOPENED": "Exercice rouvert",
}


def current_dashboard(session: Session) -> dict[str, Any]:
    """Board for the same exercise as the dossier banner."""
    dossier = current_dossier(session)
    activity = session.get(RentalActivity, 1)
    year_id = dossier.get("fiscal_year_id")
    year = session.get(FiscalYear, year_id) if isinstance(year_id, int) else None
    facts = _facts(session, activity, year, dossier)
    return build_dashboard(facts)


def _facts(
    session: Session,
    activity: RentalActivity | None,
    year: FiscalYear | None,
    dossier: dict[str, Any],
) -> DashboardFacts:
    properties = _count(session, Property)
    banks = _count(session, BankAccount)
    assets = list(session.scalars(select(Asset)))
    events: list[EventFact] = []
    if activity is not None:
        events.append(EventFact("structure", activity.created_at, "Activité créée"))
        if activity.siren:
            events.append(EventFact("structure", activity.updated_at, "SIREN renseigné"))
    _property_event(session, events)
    operation_count = 0
    operation_amount = 0
    draft_count = 0
    calculated = 0
    posted = 0
    posted_cents = 0
    has_previous = False
    previous_closed = False
    opening_posted = False
    opening_amount = 0
    target_has_entries = False
    fiscal_produced = False
    fiscal_stale = False
    fiscal_result: int | None = None
    close_errors: tuple[tuple[str, str], ...] = ()
    exports: dict[str, Any] = {}
    export_prerequisites: tuple[PrerequisiteFact, ...] = ()
    if year is not None:
        events.append(EventFact("structure", year.created_at, f"Exercice {year.year} créé"))
        operation_count, operation_amount = _operations(session, year, events)
        draft_count = _drafts(session, year.id)
        calculated, posted, posted_cents = _periods(session, year, events)
        has_previous, previous_closed = _previous(session, year)
        opening_posted, opening_amount, target_has_entries = _opening(session, year, events)
        _centralization(session, year, events)
        _audits(session, year, events)
        fiscal_produced, fiscal_stale, fiscal_result = _fiscal(session, year, events)
        _snapshot(session, year, events)
        posture = export_status(session, year.id)
        raw_exports = posture.get("exports")
        exports = raw_exports if isinstance(raw_exports, dict) else {}
        export_prerequisites = _prerequisites(posture.get("prerequisites"))
        close_errors = _close_errors(precheck(session, year.id))
    _asset_event(session, events)
    return DashboardFacts(
        activity_present=activity is not None,
        siren_present=bool(activity is not None and activity.siren),
        year_id=year.id if year is not None else None,
        year=year.year if year is not None else None,
        year_status=year.status if year is not None else None,
        property_count=properties,
        bank_count=banks,
        operation_count=operation_count,
        operation_amount_cents=operation_amount,
        draft_count=draft_count,
        asset_count=len(assets),
        depreciable_asset_count=sum(1 for asset in assets if asset.category != "LAND"),
        calculated_period_count=calculated,
        posted_period_count=posted,
        posted_depreciation_cents=posted_cents,
        has_previous_year=has_previous,
        previous_year_closed=previous_closed,
        opening_posted=opening_posted,
        opening_amount_cents=opening_amount,
        target_has_entries=target_has_entries,
        fiscal_produced=fiscal_produced,
        fiscal_stale=fiscal_stale,
        fiscal_result_cents=fiscal_result,
        close_errors=close_errors,
        exports=exports,
        export_prerequisites=export_prerequisites,
        events=tuple(events),
        dossier=dossier,
    )


def _count(session: Session, model: type[Any]) -> int:
    value = session.scalar(select(func.count()).select_from(model))
    return int(value or 0)


def _operations(session: Session, year: FiscalYear, events: list[EventFact]) -> tuple[int, int]:
    rows = list(
        session.scalars(
            select(BusinessOperation)
            .where(BusinessOperation.fiscal_year_id == year.id)
            .order_by(BusinessOperation.created_at.desc(), BusinessOperation.id.desc())
        )
    )
    if rows:
        latest = rows[0]
        events.append(
            EventFact(
                "operations",
                latest.created_at,
                _OPERATION_LABELS.get(latest.kind, "Opération enregistrée"),
            )
        )
    amount = sum(to_cents(row.amount) for row in rows)
    return len(rows), amount


def _drafts(session: Session, year_id: int) -> int:
    value = session.scalar(
        select(func.count())
        .select_from(AccountingEntry)
        .where(
            AccountingEntry.fiscal_year_id == year_id,
            AccountingEntry.status == "DRAFT",
        )
    )
    return int(value or 0)


def _periods(session: Session, year: FiscalYear, events: list[EventFact]) -> tuple[int, int, int]:
    rows = list(
        session.scalars(
            select(DepreciationPeriod).where(DepreciationPeriod.fiscal_year_id == year.id)
        )
    )
    calculated = [row for row in rows if row.status == "CALCULATED"]
    posted = [row for row in rows if row.status == "POSTED"]
    if calculated:
        latest = max(calculated, key=lambda row: (row.created_at, row.id))
        events.append(EventFact("assets", latest.created_at, "Périodes d’amortissement calculées"))
    posted_entry = session.scalar(
        select(AccountingEntry)
        .where(
            AccountingEntry.fiscal_year_id == year.id,
            AccountingEntry.source_type == "DEPRECIATION",
            AccountingEntry.status == "VALIDATED",
        )
        .order_by(AccountingEntry.validated_at.desc(), AccountingEntry.id.desc())
    )
    if posted_entry is not None and posted_entry.validated_at is not None:
        events.append(EventFact("assets", posted_entry.validated_at, "Dotation comptabilisée"))
    cents = sum(to_cents(row.amount) for row in posted)
    return len(calculated), len(posted), cents


def _previous(session: Session, year: FiscalYear) -> tuple[bool, bool]:
    previous = session.scalar(
        select(FiscalYear).where(
            FiscalYear.rental_activity_id == year.rental_activity_id,
            FiscalYear.end_date == year.start_date - timedelta(days=1),
        )
    )
    if previous is None:
        return False, False
    return True, previous.status == "CLOSED"


def _opening(session: Session, year: FiscalYear, events: list[EventFact]) -> tuple[bool, int, bool]:
    opening = _live(session, year.id, "OPENING")
    entry_count = _count_entries(session, year.id)
    if opening is None:
        return False, 0, entry_count > 0
    amount = sum(to_cents(line.debit) for line in opening.lines)
    if opening.validated_at is not None:
        events.append(EventFact("opening", opening.validated_at, "À-nouveaux comptabilisés"))
    return True, amount, False


def _count_entries(session: Session, year_id: int) -> int:
    value = session.scalar(
        select(func.count())
        .select_from(AccountingEntry)
        .where(AccountingEntry.fiscal_year_id == year_id)
    )
    return int(value or 0)


def _centralization(session: Session, year: FiscalYear, events: list[EventFact]) -> None:
    central = _live(session, year.id, "CENTRALIZATION")
    if central is not None and central.validated_at is not None:
        events.append(EventFact("closing", central.validated_at, "Résultat centralisé"))


def _audits(session: Session, year: FiscalYear, events: list[EventFact]) -> None:
    rows = session.scalars(
        select(AuditEvent).where(
            AuditEvent.entity == "fiscal_year",
            AuditEvent.entity_id == str(year.id),
        )
    )
    for row in rows:
        label = _AUDIT_LABELS.get(row.action)
        if label is not None:
            events.append(EventFact("closing", row.timestamp, label))
    if year.closed_at is not None:
        events.append(EventFact("closing", year.closed_at, "Exercice clôturé"))


def _fiscal(
    session: Session, year: FiscalYear, events: list[EventFact]
) -> tuple[bool, bool, int | None]:
    row = session.scalar(
        select(FiscalComputation)
        .where(
            FiscalComputation.fiscal_year_id == year.id,
            FiscalComputation.invalidated_at.is_(None),
        )
        .order_by(FiscalComputation.id.desc())
    )
    if row is None:
        return False, False, None
    stale = year.status != "CLOSED" and row.ledger_sha256 != ledger_fingerprint(session, year.id)
    label = "Calcul fiscal à reprendre" if stale else "Résultat fiscal calculé"
    events.append(EventFact("filing", row.created_at, label))
    return True, stale, None if stale else int(row.fiscal_result)


def _snapshot(session: Session, year: FiscalYear, events: list[EventFact]) -> None:
    row = session.scalar(
        select(TaxReturnSnapshot).where(
            TaxReturnSnapshot.fiscal_year_id == year.id,
            TaxReturnSnapshot.status == "CURRENT",
        )
    )
    if row is not None:
        events.append(EventFact("filing", row.created_at, "Sorties figées"))


def _property_event(session: Session, events: list[EventFact]) -> None:
    row = session.scalar(select(Property).order_by(Property.updated_at.desc(), Property.id.desc()))
    if row is not None:
        events.append(EventFact("operations", row.updated_at, "Bien enregistré"))


def _asset_event(session: Session, events: list[EventFact]) -> None:
    row = session.scalar(select(Asset).order_by(Asset.created_at.desc(), Asset.id.desc()))
    if row is not None:
        events.append(EventFact("assets", row.created_at, "Immobilisation enregistrée"))


def _prerequisites(value: object) -> tuple[PrerequisiteFact, ...]:
    if not isinstance(value, list):
        return ()
    rows: list[PrerequisiteFact] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        message = item.get("message")
        export = item.get("export")
        action = item.get("action")
        if not isinstance(code, str) or not isinstance(message, str) or not isinstance(export, str):
            continue
        label, href = _action(action, export)
        rows.append(PrerequisiteFact(code, message, export, label, href))
    return tuple(rows)


def _action(value: object, export: str) -> tuple[str, str]:
    if isinstance(value, dict):
        label = value.get("label")
        href = value.get("href")
        if isinstance(label, str) and isinstance(href, str) and href.startswith("/"):
            return label, href
    if export in {"fec", "archive"}:
        return "Clôturer l’exercice", "/fiscalite#close-title"
    return "Voir la liasse", "/fiscalite#sorties-figees"


def _close_errors(report: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    raw = report.get("errors")
    if not isinstance(raw, list):
        return ()
    rows: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        message = item.get("message")
        if isinstance(code, str) and isinstance(message, str):
            rows.append((code, message))
    return tuple(rows)
