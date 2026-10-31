"""Audited corrections of structuring data.

Validated journal entries stay. A calculated depreciation period on an open
exercise may be dropped so the next calculation rebuilds it from the corrected
plan. Closed exercises and their fiscal computations stay as historical evidence.
The schedule row is updated in this service, after the asset or component: a
database trigger cannot do both without seeing a stale row.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.asset_schemas import (
    AssetCorrectionInput,
    AssetInput,
    ComponentCorrectionInput,
    ComponentInput,
)
from app.api.operation_schemas import (
    BankCorrectionInput,
    BankInput,
    LoanCorrectionInput,
    LoanInput,
    PropertyCorrectionInput,
    PropertyInput,
    TenantCorrectionInput,
    TenantInput,
)
from app.core.money import from_cents, to_cents
from app.domain.loans.posting import choose_posting_path
from app.models import (
    AccountingEntry,
    AccountingEntryLine,
    Asset,
    AssetComponent,
    BankAccount,
    BankTransaction,
    BusinessOperation,
    DepreciationSchedule,
    FiscalYear,
    Loan,
    Property,
    Tenant,
)
from app.services.asset_read_cache import (
    cached_asset_schedule,
    cached_component_schedule,
    cached_component_schedules,
    cached_components,
)
from app.services.assets import (
    _live_property_entry,
    add_months,
    asset_account_warning,
    component_account_warning,
    require_asset_accounts,
    require_component_accounts,
)
from app.services.corrections import (
    changed_attributes,
    closed_cap_blocks,
    count_periods,
    empty_invalidation,
    invalidate_open_dependencies,
    merge_invalidation,
    period_in_closed_year,
    reject_locked,
    release_calculated_periods,
    snapshot,
    validation_message,
    write_audit,
)
from app.services.ledger import fail, money
from app.services.operations import account as require_prefixed_account
from app.services.operations import principal_balance, principal_on_balance_sheet

ASSET_FIELDS = (
    "label",
    "acquisition_date",
    "service_start_date",
    "acquisition_value",
    "depreciable_value",
    "non_depreciable_value",
    "residual_value",
    "useful_life_months",
    "asset_account",
    "depreciation_account",
    "basis_reason",
    "duration_reason",
    "notes",
)
ASSET_GROUPS = {
    "acquisition_value": "value",
    "depreciable_value": "value",
    "non_depreciable_value": "value",
    "residual_value": "value",
    "useful_life_months": "life",
    "acquisition_date": "dates",
    "service_start_date": "dates",
    "asset_account": "account",
    "depreciation_account": "account",
    "basis_reason": "justification",
    "duration_reason": "justification",
    "label": "label",
    "notes": "notes",
}
ASSET_DRIVERS = {
    "depreciable_value",
    "residual_value",
    "useful_life_months",
    "service_start_date",
    "asset_account",
    "depreciation_account",
}
ASSET_CALC = ASSET_DRIVERS | {"acquisition_value", "non_depreciable_value"}
COMPONENT_FIELDS = (
    "label",
    "value",
    "useful_life_months",
    "service_start_date",
    "asset_account",
    "depreciation_account",
    "basis_reason",
    "duration_reason",
)
COMPONENT_GROUPS = {
    "value": "value",
    "useful_life_months": "life",
    "service_start_date": "dates",
    "asset_account": "account",
    "depreciation_account": "account",
    "basis_reason": "justification",
    "duration_reason": "justification",
    "label": "label",
}
COMPONENT_CALC = {
    "value",
    "useful_life_months",
    "service_start_date",
    "asset_account",
    "depreciation_account",
}
LOAN_COLUMNS = (
    "lender",
    "start_date",
    "initial_principal",
    "duration_months",
    "monthly_payment",
    "monthly_insurance",
    "notes",
)
LOAN_GROUPS = {
    "initial_principal": "identity",
    "start_date": "identity",
    "interest_rate": "terms",
    "duration_months": "terms",
    "monthly_payment": "terms",
    "monthly_insurance": "terms",
    "lender": "lender",
    "notes": "notes",
}
LOAN_CALC = {
    "initial_principal",
    "start_date",
    "interest_rate",
    "duration_months",
    "monthly_payment",
    "monthly_insurance",
}
PROPERTY_FIELDS = (
    "name",
    "address",
    "acquisition_date",
    "rental_start_date",
    "acquisition_price",
    "acquisition_costs",
    "land_value",
    "building_value",
    "notes",
)
PROPERTY_GROUPS = {
    "acquisition_price": "financial",
    "acquisition_costs": "financial",
    "land_value": "financial",
    "building_value": "financial",
    "acquisition_date": "financial",
    "name": "label",
    "address": "label",
    "rental_start_date": "label",
    "notes": "label",
}
PROPERTY_CALC = {
    "acquisition_price",
    "acquisition_costs",
    "land_value",
    "building_value",
    "acquisition_date",
}
TENANT_FIELDS = ("name", "monthly_rent", "entry_date", "exit_date")
TENANT_GROUPS = {
    "name": "identity",
    "monthly_rent": "identity",
    "entry_date": "identity",
    "exit_date": "exit",
}
BANK_FIELDS = ("name", "account_number")
BANK_GROUPS = {"account_number": "account_number", "name": "name"}
STRUCTURAL = ["value", "life", "dates", "account"]
VALUE_ACCOUNT = ["value", "account"]
VALUE_LIFE = ["value", "life"]
POSTED_OWN = (
    "Une dotation est déjà comptabilisée. La valeur, la durée, les dates et les comptes "
    "restent figés : une écriture validée n’est pas réécrite, et l’extourne d’une dotation "
    "n’est pas proposée ici. Seule la justification peut être précisée."
)
POSTED_BUILDING = (
    "Un composant a déjà une dotation comptabilisée. La valeur et les comptes de la "
    "construction restent figés. La durée propre de la construction et sa justification "
    "peuvent encore être précisées."
)
YEAR_LOCKED_MSG = (
    "Un exercice clôturé contient une période calculée de ce plan. "
    "Rouvrez-le avant de corriger la valeur, la durée, les dates ou les comptes. "
    "La période n’est pas supprimée."
)
CLOSED_CAP_MSG = (
    "Le calcul fiscal d’un exercice clôturé a conservé cette base ou cette durée. "
    "Rouvrez l’exercice avant de les modifier. "
    "L’instantané de clôture n’est pas modifié en silence."
)
MISMATCH_MSG = (
    "Les composants doivent totaliser exactement la base amortissable dès qu’un plan existe. "
    "Une correction ne modifie qu’un composant à la fois : réaffectez l’ensemble "
    "avant d’en changer la valeur."
)
EXCEEDS_MSG = "Les composants dépassent la base amortissable."
LOAN_ACCOUNT_MSG = (
    "Le compte 164 identifie l’emprunt et n’est pas modifiable. L’emprunt n’est pas supprimé."
)
LOAN_REFERENCED_MSG = (
    "Des mouvements existent déjà. Le capital initial et la date de départ restent figés. "
    "Le prêteur, le taux, la durée, l’échéance, l’assurance et les notes peuvent être corrigés. "
    "Les échéances validées ne sont pas réécrites."
)
TENANT_RENTS_MSG = (
    "Des quittances sont déjà comptabilisées. Le nom, le loyer et la date d’entrée "
    "ne sont pas réécrits. La date de sortie peut être corrigée. "
    "Pour modifier un loyer passé, contrepassez les quittances."
)
BANK_MOVEMENTS_MSG = (
    "Des mouvements existent déjà sur ce compte. Le numéro comptable reste figé. "
    "Le nom peut être corrigé. Les écritures validées ne sont pas réécrites."
)


def present_asset(session: Session, asset: Asset) -> dict[str, Any]:
    components = _components(session, asset.id)
    own = _schedule_for_asset(session, asset.id)
    own_ids = [own.id] if own is not None else []
    return {
        **snapshot(asset),
        "account_warning": asset_account_warning(asset),
        "correction": _view(
            _asset_locks(session, asset, components),
            count_periods(session, own_ids, "CALCULATED"),
        ),
        "components": [present_component(session, asset, row) for row in components],
    }


def present_component(session: Session, asset: Asset, component: AssetComponent) -> dict[str, Any]:
    schedule = _schedule_for_component(session, component.id)
    schedule_ids = [schedule.id] if schedule is not None else []
    return {
        **snapshot(component),
        "account_warning": component_account_warning(component),
        "correction": _view(
            _component_locks(session, asset, component),
            count_periods(session, schedule_ids, "CALCULATED"),
        ),
    }


def present_property(session: Session, prop: Property) -> dict[str, Any]:
    return {**snapshot(prop), "correction": _view(_property_locks(session, prop))}


def present_tenant(session: Session, tenant: Tenant) -> dict[str, Any]:
    return {**snapshot(tenant), "correction": _view(_tenant_locks(session, tenant))}


def present_bank(session: Session, bank: BankAccount) -> dict[str, Any]:
    return {**snapshot(bank), "correction": _view(_bank_locks(session, bank))}


def present_loan(session: Session, loan: Loan) -> dict[str, Any]:
    balance = principal_balance(session, loan)
    booked = principal_on_balance_sheet(session, loan)
    posting_path = None
    if not booked:
        exercise = session.scalar(
            select(FiscalYear)
            .where(FiscalYear.status == "OPEN")
            .order_by(FiscalYear.start_date, FiscalYear.id)
        )
        posting_path = choose_posting_path(
            start_date=loan.start_date,
            exercise_start=exercise.start_date if exercise is not None else None,
            property_booked=_live_property_entry(session, loan.property_id) is not None,
        )
    return {
        **snapshot(loan),
        "remaining_principal": money(balance),
        "on_balance_sheet": booked,
        "posting_path": posting_path,
        "interest_rate": money(loan.interest_rate_basis_points),
        "correction": _view(_loan_locks(session, loan)),
    }


def correct_asset(session: Session, asset_id: int, data: AssetCorrectionInput) -> dict[str, Any]:
    asset = session.get(Asset, asset_id)
    if asset is None:
        fail("ASSET_NOT_FOUND", "Immobilisation introuvable.", 404)
    components = _components(session, asset.id)
    changed = changed_attributes(asset, data, ASSET_FIELDS)
    _normalize_blanks(changed, asset, ("notes",))
    if not changed:
        fail("CORRECTION_EMPTY", "Aucune valeur n’a changé.", 422)
    reject_locked(changed, _asset_locks(session, asset, components), ASSET_GROUPS)
    merged = _parse(AssetInput, _asset_base(asset), data, "ASSET_CORRECTION_INVALID", ("notes",))
    if _hits(changed, {"asset_account", "depreciation_account"}):
        require_asset_accounts(
            session, asset.category, merged.asset_account, merged.depreciation_account
        )
    _check_asset_coverage(session, asset, components, merged)
    _check_component_dates(components, merged.service_start_date)
    before = snapshot(asset)
    own = _schedule_for_asset(session, asset.id)
    dropped: list[int] = []
    ready: list[int] = []
    if _hits(changed, ASSET_DRIVERS) and own is not None:
        if components:
            fail(
                "ASSET_SCHEDULE_CONFLICT",
                "Cette construction a déjà un plan propre et des composants. "
                "La durée, les dates et les comptes de ce plan ne peuvent pas être réalignés. "
                "La justification peut encore être précisée.",
                409,
            )
        dropped, ready = release_calculated_periods(
            session,
            own.id,
            reason=data.reason,
            source_entity="asset",
            source_id=str(asset.id),
        )
    _assign(asset, merged, changed)
    session.flush()
    if _hits(changed, ASSET_DRIVERS) and own is not None:
        _realign_asset_schedule(asset, own)
        session.flush()
    invalidation = _finish(
        session,
        entity="asset",
        row=asset,
        before=before,
        reason=data.reason,
        changed=changed,
        calc=ASSET_CALC,
        dropped=dropped,
        ready=ready,
    )
    return {**present_asset(session, asset), "invalidation": invalidation}


def correct_component(
    session: Session, asset_id: int, component_id: int, data: ComponentCorrectionInput
) -> dict[str, Any]:
    asset = session.get(Asset, asset_id)
    if asset is None:
        fail("ASSET_NOT_FOUND", "Immobilisation introuvable.", 404)
    component = session.get(AssetComponent, component_id)
    if component is None or component.asset_id != asset.id:
        fail("COMPONENT_NOT_FOUND", "Composant introuvable.", 404)
    changed = changed_attributes(component, data, COMPONENT_FIELDS)
    if not changed:
        fail("CORRECTION_EMPTY", "Aucune valeur n’a changé.", 422)
    reject_locked(changed, _component_locks(session, asset, component), COMPONENT_GROUPS)
    merged = _parse(
        ComponentInput,
        {"category": component.category, **_column_payload(component, COMPONENT_FIELDS)},
        data,
        "COMPONENT_CORRECTION_INVALID",
    )
    if merged.service_start_date < asset.service_start_date:
        fail(
            "COMPONENT_DATE_INVALID",
            "La mise en service du composant précède celle de la construction.",
            422,
        )
    if _hits(changed, {"asset_account", "depreciation_account"}):
        require_component_accounts(session, merged.asset_account, merged.depreciation_account)
    _check_component_total(session, asset, component, merged.value)
    before = snapshot(component)
    schedule = _schedule_for_component(session, component.id)
    dropped: list[int] = []
    ready: list[int] = []
    if _hits(changed, COMPONENT_CALC) and schedule is not None:
        dropped, ready = release_calculated_periods(
            session,
            schedule.id,
            reason=data.reason,
            source_entity="asset_component",
            source_id=str(component.id),
        )
    _assign(component, merged, changed)
    session.flush()
    if _hits(changed, COMPONENT_CALC) and schedule is not None:
        _realign_component_schedule(component, schedule)
        session.flush()
    invalidation = _finish(
        session,
        entity="asset_component",
        row=component,
        before=before,
        reason=data.reason,
        changed=changed,
        calc=COMPONENT_CALC,
        dropped=dropped,
        ready=ready,
    )
    return {**present_component(session, asset, component), "invalidation": invalidation}


def correct_loan(session: Session, loan_id: int, data: LoanCorrectionInput) -> dict[str, Any]:
    loan = session.get(Loan, loan_id)
    if loan is None:
        fail("LOAN_NOT_FOUND", "Emprunt introuvable.", 404)
    changed = _loan_changed(loan, data)
    _normalize_blanks(changed, loan, ("notes",))
    if not changed:
        fail("CORRECTION_EMPTY", "Aucune valeur n’a changé.", 422)
    reject_locked(changed, _loan_locks(session, loan), LOAN_GROUPS)
    merged = _parse(LoanInput, _loan_base(loan), data, "LOAN_CORRECTION_INVALID", ("notes",))
    before = snapshot(loan)
    for name in changed:
        if name == "interest_rate":
            loan.interest_rate_basis_points = to_cents(merged.interest_rate)
        else:
            setattr(loan, name, getattr(merged, name))
    session.flush()
    invalidation = _finish(
        session,
        entity="loan",
        row=loan,
        before=before,
        reason=data.reason,
        changed=changed,
        calc=LOAN_CALC,
        dropped=[],
        ready=[],
    )
    return {**present_loan(session, loan), "invalidation": invalidation}


def correct_property(
    session: Session, property_id: int, data: PropertyCorrectionInput
) -> dict[str, Any]:
    prop = session.get(Property, property_id)
    if prop is None:
        fail("PROPERTY_NOT_FOUND", "Bien introuvable.", 404)
    changed = changed_attributes(prop, data, PROPERTY_FIELDS)
    _normalize_blanks(changed, prop, ("notes",))
    if not changed:
        fail("CORRECTION_EMPTY", "Aucune valeur n’a changé.", 422)
    reject_locked(changed, _property_locks(session, prop), PROPERTY_GROUPS)
    merged = _parse(
        PropertyInput,
        _column_payload(prop, PROPERTY_FIELDS),
        data,
        "PROPERTY_CORRECTION_INVALID",
        ("notes",),
    )
    before = snapshot(prop)
    _assign(prop, merged, changed)
    session.flush()
    invalidation = _finish(
        session,
        entity="property",
        row=prop,
        before=before,
        reason=data.reason,
        changed=changed,
        calc=PROPERTY_CALC,
        dropped=[],
        ready=[],
    )
    return {**present_property(session, prop), "invalidation": invalidation}


def correct_tenant(
    session: Session, property_id: int, tenant_id: int, data: TenantCorrectionInput
) -> dict[str, Any]:
    if session.get(Property, property_id) is None:
        fail("PROPERTY_NOT_FOUND", "Bien introuvable.", 404)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None or tenant.property_id != property_id:
        fail("TENANT_NOT_FOUND", "Locataire introuvable.", 404)
    changed = changed_attributes(tenant, data, TENANT_FIELDS)
    if not changed:
        fail("CORRECTION_EMPTY", "Aucune valeur n’a changé.", 422)
    reject_locked(changed, _tenant_locks(session, tenant), TENANT_GROUPS)
    merged = _parse(
        TenantInput, _column_payload(tenant, TENANT_FIELDS), data, "TENANT_CORRECTION_INVALID"
    )
    if "name" in changed:
        taken = session.scalar(
            select(Tenant.id).where(
                Tenant.property_id == tenant.property_id,
                Tenant.name == merged.name,
                Tenant.id != tenant.id,
            )
        )
        if taken is not None:
            fail("TENANT_EXISTS", "Ce colocataire est déjà enregistré sur ce bien.", 422)
    before = snapshot(tenant)
    _assign(tenant, merged, changed)
    session.flush()
    invalidation = _finish(
        session,
        entity="tenant",
        row=tenant,
        before=before,
        reason=data.reason,
        changed=changed,
        calc=set(),
        dropped=[],
        ready=[],
    )
    return {**present_tenant(session, tenant), "invalidation": invalidation}


def correct_bank(session: Session, bank_id: int, data: BankCorrectionInput) -> dict[str, Any]:
    bank = session.get(BankAccount, bank_id)
    if bank is None:
        fail("BANK_NOT_FOUND", "Compte bancaire introuvable.", 404)
    changed = changed_attributes(bank, data, BANK_FIELDS)
    if not changed:
        fail("CORRECTION_EMPTY", "Aucune valeur n’a changé.", 422)
    reject_locked(changed, _bank_locks(session, bank), BANK_GROUPS)
    merged = _parse(BankInput, _column_payload(bank, BANK_FIELDS), data, "BANK_CORRECTION_INVALID")
    if "account_number" in changed:
        require_prefixed_account(session, merged.account_number, "512")
        taken = session.scalar(
            select(BankAccount.id).where(
                BankAccount.account_number == merged.account_number,
                BankAccount.id != bank.id,
            )
        )
        if taken is not None:
            fail("BANK_ACCOUNT_TAKEN", "Ce compte 512 est déjà lié à une autre banque.", 422)
    before = snapshot(bank)
    _assign(bank, merged, changed)
    session.flush()
    invalidation = _finish(
        session,
        entity="bank_account",
        row=bank,
        before=before,
        reason=data.reason,
        changed=changed,
        calc=set(),
        dropped=[],
        ready=[],
    )
    return {**present_bank(session, bank), "invalidation": invalidation}


def _asset_locks(
    session: Session, asset: Asset, components: list[AssetComponent]
) -> list[dict[str, Any]]:
    locks: list[dict[str, Any]] = []
    own = _schedule_for_asset(session, asset.id)
    own_ids = [own.id] if own is not None else []
    component_ids = [row.id for row in _component_schedules(session, asset.id)]
    if count_periods(session, own_ids, "POSTED"):
        locks.append(_lock("DEPRECIATION_POSTED", STRUCTURAL, POSTED_OWN))
    elif components and count_periods(session, component_ids, "POSTED"):
        locks.append(_lock("DEPRECIATION_POSTED", VALUE_ACCOUNT, POSTED_BUILDING))
    if period_in_closed_year(session, own_ids):
        locks.append(_lock("YEAR_LOCKED", STRUCTURAL, YEAR_LOCKED_MSG))
    entry = _live_property_entry(session, asset.property_id)
    if entry is not None:
        locks.append(_lock("PROPERTY_ALREADY_BOOKED", VALUE_ACCOUNT, _booked_message(entry, False)))
    if closed_cap_blocks(session, asset.label) and not _covered(locks, {"value", "life"}):
        locks.append(_lock("CLOSED_FISCAL_DEPENDENCY", VALUE_LIFE, CLOSED_CAP_MSG))
    return locks


def _component_locks(
    session: Session, asset: Asset, component: AssetComponent
) -> list[dict[str, Any]]:
    locks: list[dict[str, Any]] = []
    schedule = _schedule_for_component(session, component.id)
    schedule_ids = [schedule.id] if schedule is not None else []
    if count_periods(session, schedule_ids, "POSTED"):
        locks.append(_lock("DEPRECIATION_POSTED", STRUCTURAL, POSTED_OWN))
    if period_in_closed_year(session, schedule_ids):
        locks.append(_lock("YEAR_LOCKED", STRUCTURAL, YEAR_LOCKED_MSG))
    entry = _live_property_entry(session, asset.property_id)
    if entry is not None:
        locks.append(_lock("PROPERTY_ALREADY_BOOKED", VALUE_ACCOUNT, _booked_message(entry, True)))
    if closed_cap_blocks(session, component.label) and not _covered(locks, {"value", "life"}):
        locks.append(_lock("CLOSED_FISCAL_DEPENDENCY", VALUE_LIFE, CLOSED_CAP_MSG))
    return locks


def _loan_locks(session: Session, loan: Loan) -> list[dict[str, Any]]:
    locks = [_lock("LOAN_ACCOUNT_FIXED", ["principal_account"], LOAN_ACCOUNT_MSG)]
    if _loan_referenced(session, loan):
        locks.append(_lock("LOAN_REFERENCED", ["identity"], LOAN_REFERENCED_MSG))
    return locks


def _property_locks(session: Session, prop: Property) -> list[dict[str, Any]]:
    has_asset = (
        session.scalar(select(Asset.id).where(Asset.property_id == prop.id).limit(1)) is not None
    )
    entry = _live_property_entry(session, prop.id)
    if not has_asset and entry is None:
        return []
    return [_lock("PROPERTY_HAS_ASSETS", ["financial"], _property_message(has_asset, entry))]


def _tenant_locks(session: Session, tenant: Tenant) -> list[dict[str, Any]]:
    if not _tenant_has_rents(session, tenant):
        return []
    return [_lock("TENANT_HAS_RENTS", ["identity"], TENANT_RENTS_MSG)]


def _bank_locks(session: Session, bank: BankAccount) -> list[dict[str, Any]]:
    if not _bank_has_movements(session, bank):
        return []
    return [_lock("BANK_HAS_MOVEMENTS", ["account_number"], BANK_MOVEMENTS_MSG)]


def _booked_message(entry: AccountingEntry, component: bool) -> str:
    target = (
        "la valeur et les comptes de ce composant" if component else "cette valeur et ces comptes"
    )
    return (
        f"L’écriture d’acquisition {entry.entry_number} a déjà inscrit {target}. "
        "Contrepassez cette écriture depuis le journal avant de les corriger. "
        "La durée et la justification restent modifiables tant qu’aucune dotation "
        "n’est comptabilisée."
    )


def _property_message(has_asset: bool, entry: AccountingEntry | None) -> str:
    if has_asset:
        text = (
            "Des immobilisations existent déjà : le prix, les frais, le terrain, le bâtiment "
            "et la date d’acquisition ne pilotent plus le plan. Corrigez le registre des "
            "immobilisations. Le nom, l’adresse, la date de mise en location et les notes "
            "restent modifiables."
        )
    else:
        text = (
            "Une écriture d’acquisition a déjà repris ce bien. Le prix, les frais, le terrain, "
            "le bâtiment et la date d’acquisition restent ceux de l’écriture. Le nom, l’adresse, "
            "la date de mise en location et les notes restent modifiables."
        )
    if entry is not None:
        return f"{text} L’écriture {entry.entry_number} n’est pas réécrite."
    return text


def _check_asset_coverage(
    session: Session, asset: Asset, components: list[AssetComponent], merged: AssetInput
) -> None:
    if not components:
        return
    total = sum(to_cents(row.value) for row in components)
    base = to_cents(merged.depreciable_value) - to_cents(merged.residual_value)
    if total > base:
        fail("COMPONENT_TOTAL_EXCEEDS_BASE", EXCEEDS_MSG, 422)
    if _component_schedules(session, asset.id) and total != base:
        fail("COMPONENT_TOTAL_MISMATCH", MISMATCH_MSG, 422)


def _check_component_dates(components: list[AssetComponent], service_start: Any) -> None:
    for row in components:
        if row.service_start_date < service_start:
            fail(
                "COMPONENT_DATE_INVALID",
                "La mise en service de la construction ne peut pas être postérieure "
                "à celle d’un composant.",
                422,
            )


def _check_component_total(
    session: Session, asset: Asset, component: AssetComponent, new_value: Decimal
) -> None:
    others = sum(
        to_cents(row.value) for row in _components(session, asset.id) if row.id != component.id
    )
    total = others + to_cents(new_value)
    base = to_cents(asset.depreciable_value) - to_cents(asset.residual_value)
    if _component_schedules(session, asset.id):
        if total != base:
            fail("COMPONENT_TOTAL_MISMATCH", MISMATCH_MSG, 422)
        return
    if total > base:
        fail("COMPONENT_TOTAL_EXCEEDS_BASE", EXCEEDS_MSG, 422)


def _realign_asset_schedule(asset: Asset, schedule: DepreciationSchedule) -> None:
    life = asset.useful_life_months
    depreciation = asset.depreciation_account
    if life is None or depreciation is None:
        fail("ASSET_PLAN_INVALID", f"Le plan de « {asset.label} » est incomplet.", 422)
    schedule.base = from_cents(to_cents(asset.depreciable_value) - to_cents(asset.residual_value))
    schedule.useful_life_months = life
    schedule.service_start_date = asset.service_start_date
    schedule.asset_account = asset.asset_account
    schedule.depreciation_account = depreciation
    schedule.end_date = add_months(asset.service_start_date, life) - timedelta(days=1)


def _realign_component_schedule(component: AssetComponent, schedule: DepreciationSchedule) -> None:
    schedule.base = component.value
    schedule.useful_life_months = component.useful_life_months
    schedule.service_start_date = component.service_start_date
    schedule.asset_account = component.asset_account
    schedule.depreciation_account = component.depreciation_account
    schedule.end_date = add_months(
        component.service_start_date, component.useful_life_months
    ) - timedelta(days=1)


def _loan_changed(loan: Loan, data: LoanCorrectionInput) -> dict[str, object]:
    changed = changed_attributes(loan, data, LOAN_COLUMNS)
    if "interest_rate" not in data.model_fields_set:
        return changed
    rate = data.interest_rate
    if rate is None or to_cents(rate) != loan.interest_rate_basis_points:
        changed["interest_rate"] = rate
    return changed


def _loan_referenced(session: Session, loan: Loan) -> bool:
    operation = session.scalar(
        select(BusinessOperation.id).where(BusinessOperation.loan_id == loan.id).limit(1)
    )
    if operation is not None:
        return True
    line = session.scalar(
        select(AccountingEntryLine.id)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .where(
            AccountingEntryLine.account_number == loan.principal_account,
            AccountingEntry.status == "VALIDATED",
        )
        .limit(1)
    )
    return line is not None


def _tenant_has_rents(session: Session, tenant: Tenant) -> bool:
    prefix = f"rent-p{tenant.property_id}-t{tenant.id}-"
    found = session.scalar(
        select(BusinessOperation.id).where(BusinessOperation.request_id.startswith(prefix)).limit(1)
    )
    return found is not None


def _bank_has_movements(session: Session, bank: BankAccount) -> bool:
    if (
        session.scalar(
            select(BankTransaction.id).where(BankTransaction.bank_account_id == bank.id).limit(1)
        )
        is not None
    ):
        return True
    if (
        session.scalar(
            select(BusinessOperation.id)
            .where(BusinessOperation.bank_account_id == bank.id)
            .limit(1)
        )
        is not None
    ):
        return True
    line = session.scalar(
        select(AccountingEntryLine.id)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .where(
            AccountingEntryLine.account_number == bank.account_number,
            AccountingEntry.status == "VALIDATED",
        )
        .limit(1)
    )
    return line is not None


def _asset_base(asset: Asset) -> dict[str, Any]:
    return {
        "property_id": asset.property_id,
        "category": asset.category,
        "method": asset.method,
        **_column_payload(asset, ASSET_FIELDS),
    }


def _loan_base(loan: Loan) -> dict[str, Any]:
    return {
        "property_id": loan.property_id,
        "lender": loan.lender,
        "start_date": loan.start_date.isoformat(),
        "initial_principal": money(to_cents(loan.initial_principal)),
        "interest_rate": money(loan.interest_rate_basis_points),
        "duration_months": loan.duration_months,
        "monthly_payment": money(to_cents(loan.monthly_payment)),
        "monthly_insurance": money(to_cents(loan.monthly_insurance)),
        "notes": loan.notes,
    }


def _parse[ModelT: BaseModel](
    model: type[ModelT],
    base: dict[str, Any],
    data: BaseModel,
    code: str,
    blanks: tuple[str, ...] = (),
) -> ModelT:
    payload = dict(base)
    payload.update(_prepare_overlay(data, blanks))
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        fail(code, validation_message(exc), 422)


def _prepare_overlay(data: BaseModel, blanks: tuple[str, ...]) -> dict[str, Any]:
    overlay = data.model_dump(exclude_unset=True, exclude={"reason"}, mode="json")
    for name in blanks:
        if name in overlay and overlay[name] is None:
            overlay[name] = ""
    return overlay


def _column_payload(row: object, names: tuple[str, ...]) -> dict[str, Any]:
    from datetime import date

    payload: dict[str, Any] = {}
    for name in names:
        value = getattr(row, name)
        if isinstance(value, Decimal):
            payload[name] = money(to_cents(value))
        elif isinstance(value, date):
            payload[name] = value.isoformat()
        else:
            payload[name] = value
    return payload


def _normalize_blanks(changed: dict[str, object], row: object, names: tuple[str, ...]) -> None:
    for name in names:
        if name in changed and changed[name] is None:
            current = getattr(row, name)
            if current in ("", None):
                del changed[name]
            else:
                changed[name] = ""


def _assign(row: object, source: BaseModel, changed: dict[str, object]) -> None:
    for name in changed:
        setattr(row, name, getattr(source, name))


class _Identifiable(Protocol):
    id: int


def _finish(
    session: Session,
    *,
    entity: str,
    row: _Identifiable,
    before: dict[str, Any],
    reason: str,
    changed: dict[str, object],
    calc: set[str],
    dropped: list[int],
    ready: list[int],
) -> dict[str, Any]:
    entity_id = str(row.id)
    if _hits(changed, calc):
        stats = invalidate_open_dependencies(
            session,
            reason=reason,
            source_entity=entity,
            source_id=entity_id,
        )
        invalidation = merge_invalidation(dropped, ready, stats)
    else:
        invalidation = empty_invalidation()
        invalidation["dropped_period_ids"] = dropped
        invalidation["ready_years_reset"] = ready
    write_audit(
        session,
        entity=entity,
        entity_id=entity_id,
        action="CORRECTED",
        before=before,
        after=snapshot(row),
        reason=reason,
        metadata={"invalidation": invalidation},
    )
    return invalidation


def _hits(changed: dict[str, object], names: set[str]) -> bool:
    return any(name in names for name in changed)


def _lock(code: str, fields: list[str], message: str) -> dict[str, Any]:
    return {"code": code, "fields": fields, "message": message}


def _view(locks: list[dict[str, Any]], calculated: int = 0) -> dict[str, Any]:
    return {"locks": locks, "calculated_periods": calculated}


def _covered(locks: list[dict[str, Any]], groups: set[str]) -> bool:
    found = {str(field) for lock in locks for field in lock["fields"]}
    return groups <= found


def _components(session: Session, asset_id: int) -> list[AssetComponent]:
    cached = cached_components(session, asset_id)
    if cached is not None:
        return cached
    return list(
        session.scalars(
            select(AssetComponent)
            .where(AssetComponent.asset_id == asset_id)
            .order_by(AssetComponent.id)
        )
    )


def _schedule_for_asset(session: Session, asset_id: int) -> DepreciationSchedule | None:
    hit, schedule = cached_asset_schedule(session, asset_id)
    if hit:
        return schedule
    return session.scalar(
        select(DepreciationSchedule).where(DepreciationSchedule.asset_id == asset_id)
    )


def _schedule_for_component(session: Session, component_id: int) -> DepreciationSchedule | None:
    hit, schedule = cached_component_schedule(session, component_id)
    if hit:
        return schedule
    return session.scalar(
        select(DepreciationSchedule).where(DepreciationSchedule.component_id == component_id)
    )


def _component_schedules(session: Session, asset_id: int) -> list[DepreciationSchedule]:
    cached = cached_component_schedules(session, asset_id)
    if cached is not None:
        return cached
    component_ids = select(AssetComponent.id).where(AssetComponent.asset_id == asset_id)
    return list(
        session.scalars(
            select(DepreciationSchedule).where(DepreciationSchedule.component_id.in_(component_ids))
        )
    )
