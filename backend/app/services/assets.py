"""Deterministic actual-day linear schedules and ledger postings."""

import calendar
import hashlib
import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.asset_schemas import (
    AssetInput,
    ComponentInput,
    DepreciationBatchItem,
    DepreciationPostInput,
    PropertyEntryInput,
)
from app.api.ledger_schemas import EntryInput, LineInput
from app.core.api_errors import HELP_IDS
from app.core.money import from_cents, to_cents
from app.domain.assets.accounts import (
    AssetAccountError,
    validate_asset_accounts,
    validate_component_accounts,
)
from app.domain.assets.posting_batch import (
    error_item,
    fingerprint,
    posted_item,
    skipped_item,
    summarize,
)
from app.models import (
    Account,
    AccountingEntry,
    AccountingEntryLine,
    Asset,
    AssetComponent,
    BankAccount,
    DepreciationPeriod,
    DepreciationSchedule,
    LedgerEvent,
    Loan,
    Property,
)
from app.services.ledger import create_draft, event, fail, get_year, money, post_entry

_BATCH_ACTION = "DEPRECIATION_BATCH"


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


def _active_account(session: Session, number: str) -> None:
    row = session.get(Account, number)
    if row is None or not row.active:
        fail("ASSET_ACCOUNT_INVALID", f"Le compte {number} est introuvable ou inactif.", 422)


def require_asset_accounts(
    session: Session, category: str, asset_account: str, depreciation_account: str | None
) -> None:
    try:
        validate_asset_accounts(category, asset_account, depreciation_account)
    except AssetAccountError as exc:
        fail("ASSET_ACCOUNT_PAIR_INVALID", str(exc), 422)
    _active_account(session, asset_account)
    if depreciation_account is not None:
        _active_account(session, depreciation_account)


def require_component_accounts(
    session: Session, asset_account: str, depreciation_account: str
) -> None:
    try:
        validate_component_accounts(asset_account, depreciation_account)
    except AssetAccountError as exc:
        fail("ASSET_ACCOUNT_PAIR_INVALID", str(exc), 422)
    _active_account(session, asset_account)
    _active_account(session, depreciation_account)


_KEPT = " Le registre et les écritures ne sont pas réécrits automatiquement."


def asset_account_warning(asset: Asset) -> str | None:
    """Describe a stored pair that new writes would reject. Does not update the row."""
    try:
        validate_asset_accounts(asset.category, asset.asset_account, asset.depreciation_account)
    except AssetAccountError as exc:
        return f"{exc}{_KEPT}"
    return None


def component_account_warning(component: AssetComponent) -> str | None:
    try:
        validate_component_accounts(component.asset_account, component.depreciation_account)
    except AssetAccountError as exc:
        return f"{exc}{_KEPT}"
    return None


def create_asset(session: Session, data: AssetInput) -> Asset:
    if session.get(Property, data.property_id) is None:
        fail("PROPERTY_NOT_FOUND", "Bien introuvable.", 404)
    require_asset_accounts(session, data.category, data.asset_account, data.depreciation_account)
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
    require_component_accounts(session, data.asset_account, data.depreciation_account)
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


def _annotate(item: dict[str, Any]) -> dict[str, Any]:
    code = item.get("code")
    if isinstance(code, str) and "help" not in item:
        help_id = HELP_IDS.get(code)
        if help_id:
            return {**item, "help": help_id}
    return item


def _stored_batch(session: Session, key: str) -> tuple[str, dict[str, Any]] | None:
    row = session.scalar(
        select(LedgerEvent)
        .where(
            LedgerEvent.action == _BATCH_ACTION,
            func.json_extract(LedgerEvent.details, "$.idempotency_key") == key,
        )
        .order_by(LedgerEvent.id.desc())
    )
    if row is None:
        return None
    stored_fingerprint = row.details.get("fingerprint")
    stored_result = row.details.get("result")
    if not isinstance(stored_fingerprint, str) or not isinstance(stored_result, dict):
        fail("IDEMPOTENCY_RECORD_INVALID", "Le lot enregistré est illisible.", 500)
    return stored_fingerprint, cast(dict[str, Any], stored_result)


def _post_one(session: Session, year_id: int, item: DepreciationBatchItem) -> dict[str, Any]:
    period = session.get(DepreciationPeriod, item.period_id)
    if period is None:
        return error_item(
            item.period_id, "PERIOD_NOT_FOUND", "Période d’amortissement introuvable."
        )
    if period.fiscal_year_id != year_id:
        return error_item(
            item.period_id,
            "PERIOD_YEAR_MISMATCH",
            "Cette période n’appartient pas à l’exercice du lot.",
        )
    already = period.status == "POSTED"
    payload = DepreciationPostInput(
        request_id=item.request_id,
        piece_reference=item.piece_reference,
    )
    try:
        with session.begin_nested():
            entry = post_period(session, item.period_id, payload)
            posted = posted_item(item.period_id, entry.id, replayed=already)
    except HTTPException as exc:
        session.expire_all()
        raw = exc.detail
        detail: dict[str, Any] = raw if isinstance(raw, dict) else {}
        code = detail.get("code")
        message = detail.get("message")
        return error_item(
            item.period_id,
            code if isinstance(code, str) else "POSTING_REJECTED",
            message if isinstance(message, str) else "Comptabilisation refusée.",
        )
    return posted


def post_period_batch(
    session: Session,
    year_id: int,
    idempotency_key: str,
    items: list[DepreciationBatchItem],
) -> dict[str, Any]:
    """Post each period. Stop at the first refusal and keep what already posted.

    The same Idempotency-Key with the same lot returns the stored result.
    A validated entry is never rewritten: an already posted period is replayed.
    """
    digest = fingerprint(
        [(item.period_id, item.request_id, item.piece_reference) for item in items]
    )
    stored = _stored_batch(session, idempotency_key)
    if stored is not None:
        stored_fingerprint, stored_result = stored
        if stored_fingerprint != digest:
            fail(
                "IDEMPOTENCY_CONFLICT",
                "Cette clé d’idempotence a déjà servi pour un autre lot de dotations.",
                409,
            )
        return {**stored_result, "replayed": True}

    get_year(session, year_id, writable=True)
    results: list[dict[str, Any]] = []
    stopped = False
    for item in items:
        if stopped:
            results.append(skipped_item(item.period_id))
            continue
        outcome = _post_one(session, year_id, item)
        results.append(outcome)
        if outcome["status"] == "error":
            stopped = True
    payload = summarize(idempotency_key, [_annotate(item) for item in results], replayed=False)
    event(
        session,
        _BATCH_ACTION,
        None,
        {
            "idempotency_key": idempotency_key,
            "fingerprint": digest,
            "year_id": year_id,
            "result": payload,
        },
    )
    return payload


def gross_pieces(session: Session, asset: Asset) -> list[tuple[str, int, date, str]]:
    """Gross value by balance-sheet account; components first, any remainder on the asset."""
    components = list(
        session.scalars(
            select(AssetComponent)
            .where(AssetComponent.asset_id == asset.id)
            .order_by(AssetComponent.id)
        )
    )
    pieces = [
        (item.asset_account, to_cents(item.value), asset.acquisition_date, item.label)
        for item in components
    ]
    remainder = to_cents(asset.acquisition_value) - sum(piece[1] for piece in pieces)
    if remainder:
        pieces.append((asset.asset_account, remainder, asset.acquisition_date, asset.label))
    return pieces


def _live_property_entry(session: Session, property_id: int) -> AccountingEntry | None:
    from app.services.asset_read_cache import cached_property_entry

    hit, cached = cached_property_entry(session, property_id)
    if hit:
        return cached
    rows = session.scalars(
        select(AccountingEntry).where(
            AccountingEntry.source_type == "ACQUISITION",
            AccountingEntry.source_id == f"property:{property_id}",
            AccountingEntry.status == "VALIDATED",
        )
    )
    for row in rows:
        reversed_by = session.scalar(
            select(AccountingEntry.id).where(AccountingEntry.reversal_of_id == row.id)
        )
        if reversed_by is None:
            return row
    return None


def property_entry(session: Session, property_id: int, data: PropertyEntryInput) -> dict[str, Any]:
    """Bring a property, its loans and pre-start costs into the books at the exercise start."""
    prop = session.get(Property, property_id)
    if prop is None:
        fail("PROPERTY_NOT_FOUND", "Bien introuvable.", 404)
    year = get_year(session, data.fiscal_year_id, writable=True)
    existing = _live_property_entry(session, prop.id)
    if existing is not None:
        fail(
            "PROPERTY_ALREADY_BOOKED",
            f"Le bien est déjà entré en comptabilité (écriture {existing.entry_number}). "
            "Extournez-la depuis le journal pour la refaire.",
        )
    day = year.start_date
    lines: list[LineInput] = []
    label = f"Entrée du bien {prop.name}"[:200]
    assets = session.scalars(
        select(Asset).where(Asset.property_id == prop.id).order_by(Asset.id)
    ).all()
    for asset in assets:
        if asset.acquisition_date > day:
            continue
        for number, cents, _acquired, piece_label in gross_pieces(session, asset):
            if cents > 0:
                lines.append(_line(number, cents, 0, piece_label[:200]))
    if not lines:
        fail(
            "NO_ASSET_TO_BOOK",
            "Aucune immobilisation de ce bien acquise avant le début de l’exercice. "
            "Créez d’abord les immobilisations du logement depuis l’aperçu.",
            422,
        )
    for item in data.loans:
        loan = session.get(Loan, item.loan_id)
        if loan is None or loan.property_id != prop.id:
            fail("LOAN_NOT_FOUND", "Emprunt introuvable pour ce bien.", 404)
        cents = to_cents(item.outstanding)
        if cents < 0 or cents > to_cents(loan.initial_principal):
            fail(
                "LOAN_OUTSTANDING_INVALID", "Le capital restant dû dépasse le capital initial.", 422
            )
        if session.scalar(
            select(AccountingEntryLine.id)
            .join(AccountingEntry)
            .where(
                AccountingEntry.status == "VALIDATED",
                AccountingEntryLine.account_number == loan.principal_account,
            )
            .limit(1)
        ):
            fail(
                "LOAN_ALREADY_BOOKED",
                f"L’emprunt {loan.lender} a déjà des mouvements comptables.",
            )
        account(session, loan.principal_account, "164")
        if cents:
            lines.append(
                _line(loan.principal_account, 0, cents, f"Capital restant dû — {loan.lender}"[:200])
            )
    if to_cents(data.bank_amount) > 0:
        bank = session.get(BankAccount, data.bank_account_id)
        if bank is None:
            fail("BANK_NOT_FOUND", "Compte bancaire introuvable.", 404)
        lines.append(
            _line(bank.account_number, to_cents(data.bank_amount), 0, "Solde bancaire repris")
        )
    for charge in data.prior_charges:
        account(session, charge.account_number, "6")
        lines.append(_line(charge.account_number, to_cents(charge.amount), 0, charge.label))
    debit = sum(to_cents(line.debit) for line in lines)
    credit = sum(to_cents(line.credit) for line in lines)
    if debit != credit:
        owner = "Apport de l’exploitant" if debit > credit else "Prélèvement de l’exploitant"
        lines.append(_line("108000", max(0, credit - debit), max(0, debit - credit), owner))
    preview = {
        "property_id": prop.id,
        "accounting_date": day.isoformat(),
        "piece_date": min(prop.acquisition_date, day).isoformat(),
        "lines": [line.model_dump(mode="json") for line in lines],
        "owner_contribution": money(debit - credit),
        "posted": False,
    }
    if not data.confirm:
        return preview
    account(session, "108000", "108")
    entry = create_draft(
        session,
        EntryInput(
            fiscal_year_id=year.id,
            journal_code="OD",
            accounting_date=day,
            piece_reference=data.piece_reference,
            piece_date=min(prop.acquisition_date, day),
            label=label,
            lines=lines,
        ),
    )
    entry.source_type = "ACQUISITION"
    entry.source_id = f"property:{prop.id}"
    post_entry(session, entry, entry.version)
    return {**preview, "posted": True, "entry_id": entry.id, "entry_number": entry.entry_number}


def _line(number: str, debit: int, credit: int, label: str) -> LineInput:
    return LineInput(account_number=number, label=label, debit=money(debit), credit=money(credit))


DWELLING_PARTS = (
    ("Gros œuvre", 4000, 480, "213000", "281300"),
    ("Toiture et étanchéité", 1000, 300, "213500", "281350"),
    ("Façade et menuiseries", 1000, 240, "213500", "281350"),
    ("Installations électriques", 1000, 240, "213500", "281350"),
    ("Plomberie et sanitaires", 1000, 240, "213500", "281350"),
    ("Agencements intérieurs", 2000, 180, "213500", "281350"),
)
DURATION_REASON = (
    "Durée d’usage proposée pour un logement en location longue durée, "
    "à confirmer selon l’état du bien et les travaux. Ce n’est pas un barème légal."
)


def _component_shares(base: int) -> list[int]:
    shares = [base * ratio // 10000 for _label, ratio, _life, _asset, _depr in DWELLING_PARTS]
    shares[-1] += base - sum(shares)
    for index, part in enumerate(shares):
        if part <= 0:
            shares[0] += part
            shares[index] = 0
    return shares


def _plan_property(session: Session, property_id: int) -> Property:
    prop = session.get(Property, property_id)
    if prop is None:
        fail("PROPERTY_NOT_FOUND", "Bien introuvable.", 404)
    return prop


def _dwelling_proposal(prop: Property) -> dict[str, Any]:
    """Describe the dwelling split. This function does not write."""
    base = to_cents(prop.building_value) + to_cents(prop.acquisition_costs)
    if base <= 0:
        fail(
            "BUILDING_REQUIRED",
            "Indiquez la valeur du bâtiment avant de prévisualiser l’amortissement.",
            422,
        )
    start = prop.rental_start_date or prop.acquisition_date
    items: list[dict[str, Any]] = []
    if to_cents(prop.land_value) > 0:
        land_amount = money(to_cents(prop.land_value))
        items.append(
            {
                "kind": "LAND",
                "label": f"Terrain — {prop.name}"[:200],
                "amount": land_amount,
                "asset_account": "211000",
                "depreciation_account": None,
                "useful_life_months": None,
                "service_start_date": start,
                "component_category": None,
            }
        )
    building_amount = money(base)
    items.append(
        {
            "kind": "BUILDING",
            "label": f"Construction — {prop.name}"[:200],
            "amount": building_amount,
            "asset_account": "213000",
            "depreciation_account": "281300",
            "useful_life_months": 480,
            "service_start_date": start,
            "component_category": None,
        }
    )
    for (label, _ratio, life, asset_account, depreciation_account), part in zip(
        DWELLING_PARTS, _component_shares(base), strict=True
    ):
        if part <= 0:
            continue
        items.append(
            {
                "kind": "COMPONENT",
                "label": label,
                "amount": money(part),
                "asset_account": asset_account,
                "depreciation_account": depreciation_account,
                "useful_life_months": life,
                "service_start_date": start,
                "component_category": (
                    "STRUCTURE" if asset_account == "213000" else "INSTALLATION"
                ),
            }
        )
    return {
        "property_id": prop.id,
        "depreciable_base": building_amount,
        "land": money(to_cents(prop.land_value)),
        "acquisition_costs_included": money(to_cents(prop.acquisition_costs)),
        "labels": [str(item["label"]) for item in items],
        "items": items,
    }


def _token_item(item: dict[str, Any]) -> dict[str, Any]:
    start = item["service_start_date"]
    return {
        "kind": item["kind"],
        "label": item["label"],
        "amount": item["amount"],
        "asset_account": item["asset_account"],
        "depreciation_account": item["depreciation_account"],
        "useful_life_months": item["useful_life_months"],
        "service_start_date": start.isoformat() if isinstance(start, date) else start,
        "component_category": item.get("component_category"),
    }


def _preview_token(proposal: dict[str, Any]) -> str:
    identity = {
        "property_id": proposal["property_id"],
        "items": [_token_item(item) for item in proposal["items"]],
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _public_item(item: dict[str, Any]) -> dict[str, Any]:
    shown = _token_item(item)
    shown.pop("component_category")
    return shown


def _public_plan(proposal: dict[str, Any], *, created: bool) -> dict[str, Any]:
    return {
        "property_id": proposal["property_id"],
        "depreciable_base": proposal["depreciable_base"],
        "land": proposal["land"],
        "acquisition_costs_included": proposal["acquisition_costs_included"],
        "labels": proposal["labels"],
        "items": [_public_item(item) for item in proposal["items"]],
        "preview_token": _preview_token(proposal),
        "created": created,
    }


def _plan_fingerprint(items: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            item["kind"],
            item["label"],
            item["amount"],
            item["asset_account"],
            item["depreciation_account"],
            item["useful_life_months"],
            item["service_start_date"],
            item.get("component_category"),
        )
        for item in items
    ]


def _recorded_plan_items(session: Session, property_id: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    assets = session.scalars(
        select(Asset).where(Asset.property_id == property_id).order_by(Asset.id)
    ).all()
    for asset in assets:
        if asset.category == "LAND":
            kind = "LAND"
        elif asset.category == "BUILDING":
            kind = "BUILDING"
        else:
            kind = asset.category
        items.append(
            {
                "kind": kind,
                "label": asset.label,
                "amount": money(to_cents(asset.acquisition_value)),
                "asset_account": asset.asset_account,
                "depreciation_account": asset.depreciation_account,
                "useful_life_months": asset.useful_life_months,
                "service_start_date": asset.service_start_date,
                "component_category": None,
            }
        )
        components = session.scalars(
            select(AssetComponent)
            .where(AssetComponent.asset_id == asset.id)
            .order_by(AssetComponent.id)
        ).all()
        for component in components:
            items.append(
                {
                    "kind": "COMPONENT",
                    "label": component.label,
                    "amount": money(to_cents(component.value)),
                    "asset_account": component.asset_account,
                    "depreciation_account": component.depreciation_account,
                    "useful_life_months": component.useful_life_months,
                    "service_start_date": component.service_start_date,
                    "component_category": component.category,
                }
            )
    return items


def preview_dwelling_plan(session: Session, property_id: int) -> dict[str, Any]:
    """Return the dwelling split without inserting assets, components or accounts."""
    return _public_plan(_dwelling_proposal(_plan_property(session, property_id)), created=False)


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    fail("PLAN_INVALID", "La date de mise en service du plan est invalide.", 500)


def _persist_dwelling_plan(session: Session, prop: Property, items: list[dict[str, Any]]) -> None:
    building_id: int | None = None
    for item in items:
        start = _as_date(item["service_start_date"])
        if item["kind"] == "LAND":
            create_asset(
                session,
                AssetInput(
                    property_id=prop.id,
                    category="LAND",
                    label=item["label"],
                    acquisition_date=prop.acquisition_date,
                    service_start_date=start,
                    acquisition_value=item["amount"],
                    depreciable_value="0.00",
                    non_depreciable_value=item["amount"],
                    method="NONE",
                    asset_account=item["asset_account"],
                    basis_reason=(
                        "Valeur de terrain saisie sur le bien. Le terrain n’est pas amortissable."
                    ),
                    duration_reason="Terrain non amortissable",
                ),
            )
        elif item["kind"] == "BUILDING":
            life = item["useful_life_months"]
            depreciation_account = item["depreciation_account"]
            if not isinstance(life, int) or not isinstance(depreciation_account, str):
                fail("PLAN_INVALID", "Le plan de la construction est incomplet.", 500)
            building = create_asset(
                session,
                AssetInput(
                    property_id=prop.id,
                    category="BUILDING",
                    label=item["label"],
                    acquisition_date=prop.acquisition_date,
                    service_start_date=start,
                    acquisition_value=item["amount"],
                    depreciable_value=item["amount"],
                    non_depreciable_value="0.00",
                    method="LINEAR",
                    useful_life_months=life,
                    asset_account=item["asset_account"],
                    depreciation_account=depreciation_account,
                    basis_reason=(
                        "Valeur du bâtiment augmentée des frais de notaire et d’agence. "
                        "Le terrain reste hors base amortissable."
                    ),
                    duration_reason=DURATION_REASON,
                ),
            )
            building_id = building.id
        else:
            if building_id is None:
                fail("PLAN_INVALID", "La construction manque dans le plan proposé.", 500)
            category = item["component_category"]
            life = item["useful_life_months"]
            depreciation_account = item["depreciation_account"]
            if (
                not isinstance(category, str)
                or not isinstance(life, int)
                or not isinstance(depreciation_account, str)
            ):
                fail("PLAN_INVALID", "Un composant du plan proposé est incomplet.", 500)
            create_component(
                session,
                building_id,
                ComponentInput(
                    category=category,
                    label=item["label"],
                    value=item["amount"],
                    useful_life_months=life,
                    service_start_date=start,
                    asset_account=item["asset_account"],
                    depreciation_account=depreciation_account,
                    basis_reason=(
                        "Quote-part proposée pour un logement en location longue durée. "
                        "À confirmer selon l’état réel du bien."
                    ),
                    duration_reason=DURATION_REASON,
                ),
            )


def install_dwelling_plan(
    session: Session, property_id: int, *, confirm: bool, preview_token: str
) -> dict[str, Any]:
    """Persist the previewed split once. A repeated confirmation of the same plan is a no-op."""
    if not confirm:
        fail(
            "PLAN_CONFIRMATION_REQUIRED",
            "La création exige une confirmation explicite de l’aperçu.",
            422,
        )
    prop = _plan_property(session, property_id)
    proposal = _dwelling_proposal(prop)
    if preview_token != _preview_token(proposal):
        fail(
            "PLAN_PREVIEW_STALE",
            "Les données du bien ont changé. Actualisez la prévisualisation.",
            409,
        )
    public = _public_plan(proposal, created=False)
    recorded = _recorded_plan_items(session, prop.id)
    if recorded:
        if _plan_fingerprint(recorded) == _plan_fingerprint(proposal["items"]):
            return public
        fail(
            "PLAN_EXISTS",
            "Ce bien a déjà des immobilisations. Complétez le registre à la main.",
            422,
        )
    _persist_dwelling_plan(session, prop, proposal["items"])
    return _public_plan(proposal, created=True)


def row_json(
    row: Asset | AssetComponent | DepreciationSchedule | DepreciationPeriod,
) -> dict[str, Any]:
    from app.api.operations import record

    return record(row)
