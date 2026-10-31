"""Fiscal preview from the ledger. Accounting entries are never rewritten."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import FiscalInput
from app.core.money import to_cents
from app.domain.fiscal.blocks import triggered_rule_ids
from app.domain.fiscal.engine import (
    DEPRECIATION_RULE_ID,
    TAX_LOSS_HORIZON_YEARS,
    TAX_LOSS_RULE_ID,
    Movement,
    Stock,
    apply_lmnp,
)
from app.domain.fiscal.loader import load_vintage
from app.domain.fiscal.output_status import calculation_status
from app.models import (
    Account,
    AccountingEntry,
    AccountingEntryLine,
    BusinessOperation,
    FiscalYear,
    Loan,
    Property,
)
from app.models.assets import Asset, AssetComponent
from app.models.base import utc_now
from app.models.fiscal import (
    CarryForwardEvent,
    DepreciationCarryForward,
    FiscalComputation,
    TaxLossCarryForward,
)
from app.services.ledger import fail, get_year, money
from app.services.statements import statements

PRIOR_USE_ORDER = "FIFO_oldest_origin_year_first"


def _cents(amount: str) -> int:
    return to_cents(Decimal(amount))


def ledger_fingerprint(session: Session, year_id: int) -> str:
    rows = session.execute(
        select(
            AccountingEntry.sequence,
            AccountingEntryLine.position,
            AccountingEntryLine.account_number,
            AccountingEntryLine.debit,
            AccountingEntryLine.credit,
        )
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .where(AccountingEntry.fiscal_year_id == year_id, AccountingEntry.status == "VALIDATED")
        .order_by(AccountingEntry.sequence, AccountingEntryLine.position)
    )
    payload = [
        [sequence, position, account, to_cents(debit), to_cents(credit)]
        for sequence, position, account, debit, credit in rows
    ]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def structuring_fingerprint(session: Session, activity_id: int) -> str:
    """Hypothèses de calcul : bien, immobilisation, composant, emprunt.

    Colonnes, dans l’ordre : bien (id, prix, frais, terrain, bâtiment, date
    d’acquisition) ; immobilisation (id, valeur d’achat, base amortissable,
    valeur non amortissable, valeur résiduelle, durée en mois, mise en service,
    compte d’actif, compte d’amortissement) ; composant (id, valeur, durée,
    mise en service, comptes) ; emprunt (id, capital, date, taux en points de
    base, durée, mensualité, assurance). Libellés, justificatifs, locataires
    et banques restent dehors.
    """
    properties = list(
        session.scalars(
            select(Property).where(Property.rental_activity_id == activity_id).order_by(Property.id)
        )
    )
    property_ids = [row.id for row in properties]
    assets = (
        list(
            session.scalars(
                select(Asset).where(Asset.property_id.in_(property_ids)).order_by(Asset.id)
            )
        )
        if property_ids
        else []
    )
    asset_ids = [row.id for row in assets]
    components = (
        list(
            session.scalars(
                select(AssetComponent)
                .where(AssetComponent.asset_id.in_(asset_ids))
                .order_by(AssetComponent.id)
            )
        )
        if asset_ids
        else []
    )
    loans = (
        list(
            session.scalars(
                select(Loan).where(Loan.property_id.in_(property_ids)).order_by(Loan.id)
            )
        )
        if property_ids
        else []
    )
    payload = {
        "properties": [
            [
                row.id,
                to_cents(row.acquisition_price),
                to_cents(row.acquisition_costs),
                to_cents(row.land_value),
                to_cents(row.building_value),
                row.acquisition_date.isoformat(),
            ]
            for row in properties
        ],
        "assets": [
            [
                row.id,
                to_cents(row.acquisition_value),
                to_cents(row.depreciable_value),
                to_cents(row.non_depreciable_value),
                to_cents(row.residual_value),
                row.useful_life_months,
                row.service_start_date.isoformat(),
                row.asset_account,
                row.depreciation_account,
            ]
            for row in assets
        ],
        "components": [
            [
                row.id,
                to_cents(row.value),
                row.useful_life_months,
                row.service_start_date.isoformat(),
                row.asset_account,
                row.depreciation_account,
            ]
            for row in components
        ],
        "loans": [
            [
                row.id,
                to_cents(row.initial_principal),
                row.start_date.isoformat(),
                row.interest_rate_basis_points,
                row.duration_months,
                to_cents(row.monthly_payment),
                to_cents(row.monthly_insurance),
            ]
            for row in loans
        ],
    }
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def _stored_carry(row: FiscalComputation) -> str | None:
    details = row.details if isinstance(row.details, dict) else {}
    stored = details.get("carry_inputs_sha256")
    if isinstance(stored, str) and len(stored) == 64:
        return stored
    return None


def _carry_fingerprint(depreciation: list[Stock], tax_loss: list[Stock]) -> str:
    payload = {
        "depreciation": [
            [stock.origin_year_id, stock.created, stock.used_before, stock.expired_before]
            for stock in depreciation
        ],
        "tax_loss": [
            [stock.origin_year_id, stock.created, stock.used_before, stock.expired_before]
            for stock in tax_loss
        ],
    }
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def _stored_structuring(row: FiscalComputation) -> str | None:
    details = row.details if isinstance(row.details, dict) else {}
    stored = details.get("structuring_sha256")
    if isinstance(stored, str) and len(stored) == 64:
        return stored
    return None


def _with_freshness(
    session: Session, year: FiscalYear, row: FiscalComputation, payload: dict[str, Any]
) -> dict[str, Any]:
    """Empreintes courantes, à comparer à celles du calcul affiché.

    `ledger_fingerprint` reste l’empreinte du ledger utilisée par la clôture.
    L’empreinte structurante est séparée : une correction de calcul la change
    sans réécrire l’empreinte figée dans un snapshot. Un exercice clôturé garde
    son calcul comme preuve, donc cet écart n’y est pas signalé. `invalidated`
    reste vrai après invalidation, y compris sur un exercice réouvert.
    """
    payload["current_ledger_sha256"] = ledger_fingerprint(session, year.id)
    payload["invalidated"] = row.invalidated_at is not None
    stored = _stored_structuring(row)
    payload["structuring_sha256"] = stored
    if year.status == "CLOSED":
        payload["current_structuring_sha256"] = stored
    else:
        payload["current_structuring_sha256"] = structuring_fingerprint(
            session, year.rental_activity_id
        )
    payload["blocked_facts"] = _blocking_issues(session, year, load_vintage(year.fiscal_vintage))
    return payload


def _iso_utc(value: datetime) -> str:
    stamp = value.isoformat(timespec="seconds")
    if value.tzinfo is None:
        return stamp + "Z"
    return stamp


def compute_fiscal(session: Session, year_id: int, data: FiscalInput) -> dict[str, Any]:
    year = get_year(session, year_id)
    vintage = load_vintage(year.fiscal_vintage)
    statements(session, year.id)
    income, expenses, depreciation, expense_balances, _income_balances = _operating(
        session, year.id
    )
    fingerprint = ledger_fingerprint(session, year.id)
    structuring = structuring_fingerprint(session, year.rental_activity_id)
    adjustments = [item.model_dump(mode="json") for item in data.adjustments]
    for item in adjustments:
        item["amount"] = money(to_cents(Decimal(item["amount"])))
    adjustments_hash = hashlib.sha256(json.dumps(adjustments, sort_keys=True).encode()).hexdigest()
    blocked = _blocking_issues(session, year, vintage)
    if blocked:
        fail(
            "FISCAL_RULE_BLOCKED",
            "Calcul fiscal bloqué. "
            + " ".join(f"{item['code']} : {item['message']}" for item in blocked),
            409,
            issues=blocked,
        )
    dep_stocks = _stocks(session, year, "depreciation")
    loss_stocks = _stocks(session, year, "tax_loss")
    carry_hash = _carry_fingerprint(dep_stocks, loss_stocks)
    current = _current(session, year.id)
    if (
        current is not None
        and current.ledger_sha256 == fingerprint
        and current.adjustments_sha256 == adjustments_hash
        and current.rules_sha256 == vintage["sha256"]
        and current.invalidated_at is None
        and _stored_structuring(current) == structuring
        and _stored_carry(current) == carry_hash
    ):
        return _with_freshness(session, year, current, _json(current, replayed=True))
    if year.status != "OPEN":
        fail("YEAR_LOCKED", "Un exercice qui n’est pas ouvert ne peut pas être recalculé.")
    if current is not None:
        current.invalidated_at = utc_now()
        session.flush()
    _land_invariant(session)
    other = expenses - depreciation
    additions, addition_accounts = _additions(expense_balances, data)
    split = apply_lmnp(
        year=year.year,
        income=income,
        other_charges=other,
        depreciation=depreciation,
        additions=additions,
        depreciation_stocks=dep_stocks,
        tax_loss_stocks=loss_stocks,
    )
    dep_uses = _use_dicts(split.depreciation_uses)
    loss_uses = _use_dicts(split.tax_loss_uses)
    prior_loss_available = sum(
        stock.remaining_before()
        for stock in loss_stocks
        if stock.origin_year >= year.year - TAX_LOSS_HORIZON_YEARS
    )
    details = {
        "applied_rules": [rule["id"] for rule in vintage["executable"]],
        "blocked_rules": [
            {
                "id": rule["id"],
                "blocking_reason": rule["blocking_reason"],
                "source": rule["source"],
                "source_url": rule["source_url"],
                "consulted_at": rule["consulted_at"],
            }
            for rule in vintage["blocked"]
        ],
        "scope_rules": vintage["scope"],
        "prior_carry_forward_use": {
            "status": "enabled",
            "order": PRIOR_USE_ORDER,
            "tax_loss_horizon_years": TAX_LOSS_HORIZON_YEARS,
            "depreciation": dep_uses,
            "tax_loss": loss_uses,
            "tax_loss_expired": [
                {
                    "origin_year_id": move.origin_year_id,
                    "origin_year": move.origin_year,
                    "expired": money(move.amount),
                    "remaining_after": money(move.remaining_after),
                }
                for move in split.tax_loss_expiries
            ],
            "notes": (
                "Le montant créé reste sur le registre de l’exercice d’origine. "
                "Création, utilisation et expiration sont des lignes distinctes du calcul "
                "qui les constate. Un recalcul ou une réouverture invalide ces lignes. "
                "Cession, TVA, plus-values et ventilation automatique du terrain restent bloquées."
            ),
        },
        "carry_registers": {
            "depreciation": _register_view(
                dep_stocks,
                split.depreciation_uses,
                (),
                year,
                split.unused_depreciation,
                DEPRECIATION_RULE_ID,
                expires=False,
            ),
            "tax_loss": _register_view(
                loss_stocks,
                split.tax_loss_uses,
                split.tax_loss_expiries,
                year,
                split.tax_loss,
                TAX_LOSS_RULE_ID,
                expires=True,
            ),
        },
        "fiscal_result_before_prior_losses": money(split.fiscal_before_losses),
        "prior_depreciation_used": money(split.prior_depreciation_used),
        "prior_tax_loss_used": money(split.prior_tax_loss_used),
        "imputed_on_global_income": "0.00",
        "additions": adjustments,
        "addition_accounts": addition_accounts,
        "operating_income": money(income),
        "other_charges": money(other),
        "accounting_depreciation": money(depreciation),
        "capacity": money(split.capacity),
        "current_deductible_depreciation": money(split.current_deductible),
        "prior_depreciation_available": money(
            sum(stock.remaining_before() for stock in dep_stocks)
        ),
        "prior_tax_loss_available": money(prior_loss_available),
        "depreciation_reports": _report_rows(dep_stocks, dep_uses),
        "depreciation_categories": _category_caps(session),
        "goal_hint": _goal_hint(
            split.fiscal_result,
            split.unused_depreciation,
            split.prior_depreciation_used,
            split.prior_tax_loss_used,
        ),
        "structuring_sha256": structuring,
        "carry_inputs_sha256": carry_hash,
    }
    row = FiscalComputation(
        fiscal_year_id=year.id,
        vintage=year.fiscal_vintage,
        rules_sha256=vintage["sha256"],
        ledger_sha256=fingerprint,
        adjustments_sha256=adjustments_hash,
        accounting_result=split.accounting_result,
        fiscal_result=split.fiscal_result,
        deductible_depreciation=split.current_deductible + split.prior_depreciation_used,
        unused_depreciation=split.unused_depreciation,
        tax_loss=split.tax_loss,
        non_deductible=additions,
        status="research_only",
        details=details,
    )
    session.add(row)
    session.flush()
    _replace_register(
        session,
        DepreciationCarryForward,
        year.id,
        row.id,
        split.unused_depreciation,
        DEPRECIATION_RULE_ID,
    )
    _persist_events(session, row, year, split)
    loss = session.scalar(
        select(TaxLossCarryForward).where(TaxLossCarryForward.fiscal_year_id == year.id)
    )
    if loss is None:
        session.add(
            TaxLossCarryForward(
                fiscal_year_id=year.id,
                computation_id=row.id,
                amount=split.tax_loss,
                rule_id=TAX_LOSS_RULE_ID,
                note=(
                    "Non imputé sur le revenu global. "
                    "Consommation FIFO des reports antérieurs (horizon 10 ans) activée pour le MVP."
                ),
            )
        )
    else:
        loss.computation_id = row.id
        loss.amount = split.tax_loss
        loss.note = (
            "Non imputé sur le revenu global. "
            "Consommation FIFO des reports antérieurs (horizon 10 ans) activée pour le MVP."
        )
    session.flush()
    return _with_freshness(session, year, row, _json(row, replayed=False))


def reintegration_suggestions(session: Session, year_id: int) -> list[dict[str, str]]:
    """Quote-parts déjà saisies sur les dépenses, regroupées par compte."""
    get_year(session, year_id)
    grouped: dict[str, int] = {}
    rows = session.scalars(
        select(BusinessOperation).where(
            BusinessOperation.fiscal_year_id == year_id,
            BusinessOperation.kind == "EXPENSE",
            BusinessOperation.deductible_basis_points < 10000,
        )
    )
    for row in rows:
        entry = session.get(AccountingEntry, row.accounting_entry_id)
        if entry is None or entry.status != "VALIDATED":
            continue
        share = to_cents(row.amount) * (10000 - row.deductible_basis_points) // 10000
        if share <= 0:
            continue
        grouped[row.accounting_account] = grouped.get(row.accounting_account, 0) + share
    return [
        {
            "account_number": number,
            "amount": money(amount),
            "justification": "Quote-part non déductible saisie sur les dépenses.",
        }
        for number, amount in sorted(grouped.items())
    ]


def latest_fiscal(session: Session, year_id: int) -> dict[str, Any]:
    """Calcul encore valide. La liasse et le pré-contrôle s’arrêtent s’il n’y en a pas."""
    year = get_year(session, year_id)
    current = _current(session, year_id)
    if current is None:
        fail("FISCAL_NOT_COMPUTED", "Aucun calcul fiscal n’est enregistré pour cet exercice.", 404)
    assert current is not None  # noqa: S101
    return _with_freshness(session, year, current, _json(current, replayed=True))


def displayed_fiscal(session: Session, year_id: int) -> dict[str, Any]:
    """Dernier calcul pour l’écran, y compris lorsqu’il a été invalidé.

    Une ligne invalidée n’est pas un calcul en cours : l’écran la marque
    obsolète. `latest_fiscal` continue de l’ignorer.
    """
    year = get_year(session, year_id)
    row = session.scalar(
        select(FiscalComputation)
        .where(FiscalComputation.fiscal_year_id == year_id)
        .order_by(FiscalComputation.id.desc())
    )
    if row is None:
        return {
            "empty": True,
            "fiscal_year_id": year.id,
            "year": year.year,
            "status": "absent",
            "message": "Aucun calcul fiscal n’est enregistré pour cet exercice.",
        }
    assert row is not None  # noqa: S101
    return _with_freshness(session, year, row, _json(row, replayed=True))


def _current(session: Session, year_id: int) -> FiscalComputation | None:
    return session.scalar(
        select(FiscalComputation)
        .where(
            FiscalComputation.fiscal_year_id == year_id,
            FiscalComputation.invalidated_at.is_(None),
        )
        .order_by(FiscalComputation.id.desc())
    )


def _land_invariant(session: Session) -> None:
    land = session.scalar(
        select(Asset.id).where(Asset.category == "LAND", Asset.depreciable_value > Decimal("0"))
    )
    if land is not None:
        fail("LAND_DEPRECIATED", "Un terrain ne peut pas avoir de base amortissable.")


def _operating(
    session: Session, year_id: int
) -> tuple[int, int, int, dict[str, int], dict[str, int]]:
    rows = session.execute(
        select(AccountingEntryLine, Account)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .join(Account, Account.number == AccountingEntryLine.account_number)
        .where(
            AccountingEntry.fiscal_year_id == year_id,
            AccountingEntry.status == "VALIDATED",
            AccountingEntry.source_type.notin_(("CENTRALIZATION", "APPROPRIATION")),
        )
    )
    income = expenses = depreciation = 0
    charges: dict[str, int] = {}
    products: dict[str, int] = {}
    for line, account in rows:
        net = to_cents(line.debit) - to_cents(line.credit)
        if account.account_type == "INCOME":
            products[account.number] = products.get(account.number, 0) - net
            income += -net
        elif account.account_type == "EXPENSE":
            charges[account.number] = charges.get(account.number, 0) + net
            expenses += net
            if account.number.startswith("681"):
                depreciation += net
    return income, expenses, depreciation, charges, products


def _additions(balances: dict[str, int], data: FiscalInput) -> tuple[int, list[str]]:
    total = 0
    accounts: list[str] = []
    seen: set[str] = set()
    for item in data.adjustments:
        number = item.account_number
        if number in seen:
            fail("DUPLICATE_ADJUSTMENT", f"Le compte {number} est déjà réintégré.", 422)
        seen.add(number)
        if number.startswith("681"):
            fail(
                "DEPRECIATION_ADJUSTMENT",
                "La dotation suit la règle de plafonnement, pas une réintégration libre.",
                422,
            )
        amount = to_cents(item.amount)
        if amount > balances.get(number, 0):
            fail(
                "ADJUSTMENT_TOO_LARGE",
                f"La réintégration de {number} dépasse la charge comptabilisée.",
                422,
            )
        total += amount
        accounts.append(number)
    return total, accounts


def _blocking_issues(
    session: Session, year: FiscalYear, vintage: dict[str, Any]
) -> list[dict[str, str]]:
    numbers = session.scalars(
        select(AccountingEntryLine.account_number)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .where(
            AccountingEntry.fiscal_year_id == year.id,
            AccountingEntry.status == "VALIDATED",
        )
        .distinct()
    ).all()
    disposal = (
        session.scalar(
            select(Asset.id).where(
                Asset.disposed_at.is_not(None),
                Asset.disposed_at <= year.end_date,
            )
        )
        is not None
    )
    by_id = {rule["id"]: rule for rule in vintage["blocked"]}
    issues: list[dict[str, str]] = []
    for rule_id in triggered_rule_ids(numbers, disposal=disposal):
        rule = by_id.get(rule_id)
        if rule is None:
            fail("RULE_INCOMPLETE", f"Règle bloquante {rule_id} absente du millésime.")
        issues.append({"code": rule_id, "message": str(rule["blocking_reason"])})
    return issues


def _stocks(session: Session, year: FiscalYear, register: str) -> list[Stock]:
    """Closed prior stocks. Live events win; older computations without events still count."""
    model = DepreciationCarryForward if register == "depreciation" else TaxLossCarryForward
    live_ids, totals = _event_index(session, year.rental_activity_id, exclude_year_id=year.id)
    legacy = _legacy_used(
        session, year.rental_activity_id, register, live_ids, exclude_year_id=year.id
    )
    rows = session.execute(
        select(FiscalYear, model)
        .join(model, model.fiscal_year_id == FiscalYear.id)
        .where(
            FiscalYear.rental_activity_id == year.rental_activity_id,
            FiscalYear.status == "CLOSED",
            FiscalYear.year < year.year,
        )
        .order_by(FiscalYear.year.asc(), FiscalYear.id.asc())
    )
    stocks: list[Stock] = []
    for origin, register_row in rows:
        used = totals.get((register, "used", origin.id), 0) + legacy.get(origin.id, 0)
        expired = totals.get((register, "expired", origin.id), 0)
        if register_row.amount == 0 and used == 0 and expired == 0:
            continue
        stocks.append(
            Stock(
                origin_year_id=origin.id,
                origin_year=origin.year,
                created=register_row.amount,
                used_before=used,
                expired_before=expired,
            )
        )
    return stocks


def _event_index(
    session: Session, activity_id: int, *, exclude_year_id: int
) -> tuple[set[int], dict[tuple[str, str, int], int]]:
    rows = session.execute(
        select(
            CarryForwardEvent.computation_id,
            CarryForwardEvent.register,
            CarryForwardEvent.kind,
            CarryForwardEvent.origin_fiscal_year_id,
            CarryForwardEvent.amount,
        )
        .join(FiscalComputation, FiscalComputation.id == CarryForwardEvent.computation_id)
        .join(FiscalYear, FiscalYear.id == FiscalComputation.fiscal_year_id)
        .where(
            FiscalYear.rental_activity_id == activity_id,
            FiscalComputation.invalidated_at.is_(None),
            FiscalComputation.fiscal_year_id != exclude_year_id,
        )
    )
    live: set[int] = set()
    totals: dict[tuple[str, str, int], int] = {}
    for computation_id, register, kind, origin_id, amount in rows:
        live.add(computation_id)
        key = (str(register), str(kind), int(origin_id))
        totals[key] = totals.get(key, 0) + int(amount)
    return live, totals


def _legacy_used(
    session: Session,
    activity_id: int,
    register: str,
    live_computation_ids: set[int],
    *,
    exclude_year_id: int,
) -> dict[int, int]:
    """Uses stored only in computation JSON, before carry_forward_event existed."""
    key = "depreciation" if register == "depreciation" else "tax_loss"
    rows = session.execute(
        select(FiscalComputation.id, FiscalComputation.details)
        .join(FiscalYear, FiscalYear.id == FiscalComputation.fiscal_year_id)
        .where(
            FiscalYear.rental_activity_id == activity_id,
            FiscalComputation.invalidated_at.is_(None),
            FiscalComputation.fiscal_year_id != exclude_year_id,
        )
    )
    totals: dict[int, int] = {}
    for computation_id, details in rows:
        if computation_id in live_computation_ids:
            continue
        uses = (details or {}).get("prior_carry_forward_use") or {}
        if uses.get("status") != "enabled":
            continue
        for item in uses.get(key) or []:
            origin = int(item["origin_year_id"])
            totals[origin] = totals.get(origin, 0) + _cents(str(item["used"]))
    return totals


def _prior_remaining(
    session: Session,
    year: FiscalYear,
    kind: str,
    *,
    min_origin_year: int | None = None,
) -> list[dict[str, int]]:
    """Remaining stocks from closed prior years. Registers are not mutated."""
    rows: list[dict[str, int]] = []
    for stock in _stocks(session, year, kind):
        remaining = stock.remaining_before()
        if remaining <= 0:
            continue
        if min_origin_year is not None and stock.origin_year < min_origin_year:
            continue
        rows.append(
            {
                "origin_year_id": stock.origin_year_id,
                "origin_year": stock.origin_year,
                "remaining": remaining,
            }
        )
    return rows


def _use_dicts(moves: tuple[Movement, ...] | list[Movement]) -> list[dict[str, str | int]]:
    return [
        {
            "origin_year_id": move.origin_year_id,
            "origin_year": move.origin_year,
            "used": money(move.amount),
            "remaining_after": money(move.remaining_after),
        }
        for move in moves
    ]


def _report_rows(
    stocks: list[Stock], uses: list[dict[str, str | int]]
) -> list[dict[str, str | int]]:
    used_by_year = {int(item["origin_year"]): item for item in uses}
    rows: list[dict[str, str | int]] = []
    for stock in stocks:
        opening = stock.remaining_before()
        if opening <= 0:
            continue
        used = used_by_year.get(stock.origin_year)
        rows.append(
            {
                "origin_year": stock.origin_year,
                "opening": money(opening),
                "used": used["used"] if used else "0.00",
                "remaining_after": used["remaining_after"] if used else money(opening),
            }
        )
    return rows


def _register_row(
    origin_year: int, created: int, used: int, expired: int, remaining: int
) -> dict[str, str | int]:
    return {
        "origin_year": origin_year,
        "created": money(created),
        "used": money(used),
        "expired": money(expired),
        "remaining": money(remaining),
    }


def _register_view(
    stocks: list[Stock],
    uses: tuple[Movement, ...] | list[Movement],
    expiries: tuple[Movement, ...] | list[Movement],
    year: FiscalYear,
    created_now: int,
    rule_id: str,
    *,
    expires: bool,
) -> dict[str, Any]:
    used_now = {move.origin_year_id: move.amount for move in uses}
    expired_now = {move.origin_year_id: move.amount for move in expiries}
    rows = [
        _register_row(
            stock.origin_year,
            stock.created,
            stock.used_before + used_now.get(stock.origin_year_id, 0),
            stock.expired_before + expired_now.get(stock.origin_year_id, 0),
            stock.created
            - (stock.used_before + used_now.get(stock.origin_year_id, 0))
            - (stock.expired_before + expired_now.get(stock.origin_year_id, 0)),
        )
        for stock in stocks
    ]
    rows.append(_register_row(year.year, created_now, 0, 0, created_now))
    rows.sort(key=lambda row: int(row["origin_year"]))
    totals = {
        key: money(sum(_cents(str(row[key])) for row in rows))
        for key in ("created", "used", "expired", "remaining")
    }
    return {
        "rule_id": rule_id,
        "horizon_years": TAX_LOSS_HORIZON_YEARS if expires else None,
        "expires": expires,
        "rows": rows,
        "totals": totals,
    }


def _persist_events(session: Session, row: FiscalComputation, year: FiscalYear, split: Any) -> None:
    _add_event(
        session,
        computation_id=row.id,
        event_year_id=year.id,
        origin_year_id=year.id,
        register="depreciation",
        kind="created",
        amount=split.unused_depreciation,
        remaining_after=split.unused_depreciation,
        rule_id=DEPRECIATION_RULE_ID,
    )
    _add_event(
        session,
        computation_id=row.id,
        event_year_id=year.id,
        origin_year_id=year.id,
        register="tax_loss",
        kind="created",
        amount=split.tax_loss,
        remaining_after=split.tax_loss,
        rule_id=TAX_LOSS_RULE_ID,
    )
    for move in split.depreciation_uses:
        _add_event(
            session,
            computation_id=row.id,
            event_year_id=year.id,
            origin_year_id=move.origin_year_id,
            register="depreciation",
            kind=move.kind,
            amount=move.amount,
            remaining_after=move.remaining_after,
            rule_id=DEPRECIATION_RULE_ID,
        )
    for move in (*split.tax_loss_uses, *split.tax_loss_expiries):
        _add_event(
            session,
            computation_id=row.id,
            event_year_id=year.id,
            origin_year_id=move.origin_year_id,
            register="tax_loss",
            kind=move.kind,
            amount=move.amount,
            remaining_after=move.remaining_after,
            rule_id=TAX_LOSS_RULE_ID,
        )


def _add_event(
    session: Session,
    *,
    computation_id: int,
    event_year_id: int,
    origin_year_id: int,
    register: str,
    kind: str,
    amount: int,
    remaining_after: int,
    rule_id: str,
) -> None:
    session.add(
        CarryForwardEvent(
            computation_id=computation_id,
            event_fiscal_year_id=event_year_id,
            origin_fiscal_year_id=origin_year_id,
            register=register,
            kind=kind,
            amount=amount,
            remaining_after=remaining_after,
            rule_id=rule_id,
        )
    )


def _category_caps(session: Session) -> list[dict[str, str]]:
    """Full-year linear maximum for each depreciable category. Land stays at zero."""
    caps: list[dict[str, str]] = []
    for asset in session.scalars(select(Asset).order_by(Asset.id)):
        if asset.category == "LAND":
            caps.append(
                {
                    "label": asset.label,
                    "base": money(to_cents(asset.acquisition_value)),
                    "rate_percent": "0.00",
                    "annual_max": "0.00",
                }
            )
            continue
        components = list(
            session.scalars(
                select(AssetComponent)
                .where(AssetComponent.asset_id == asset.id)
                .order_by(AssetComponent.id)
            )
        )
        if components:
            pieces = [
                (item.label, to_cents(item.value), item.useful_life_months) for item in components
            ]
        elif asset.useful_life_months:
            base = to_cents(asset.depreciable_value) - to_cents(asset.residual_value)
            pieces = [(asset.label, base, asset.useful_life_months)]
        else:
            pieces = []
        for label, base, life in pieces:
            if base <= 0 or life <= 0:
                continue
            annual = (base * 12 + life // 2) // life
            rate = (Decimal(1200) / Decimal(life)).quantize(Decimal("0.01"))
            caps.append(
                {
                    "label": label,
                    "base": money(base),
                    "rate_percent": f"{rate:.2f}",
                    "annual_max": money(annual),
                }
            )
    return caps


def _goal_hint(fiscal_result: int, unused: int, prior_dep_used: int, prior_loss_used: int) -> str:
    if fiscal_result == 0:
        if unused > 0:
            return (
                "Résultat fiscal à 0 € : objectif LMNP atteint pour l’impôt BIC de l’activité. "
                f"La part d’amortissement non déduite ({money(unused)} €) est reportée "
                "pour les exercices suivants."
            )
        return (
            "Résultat fiscal à 0 € : aucun bénéfice BIC à reporter sur la déclaration "
            "personnelle pour cette activité."
        )
    if fiscal_result > 0:
        parts = [
            f"Bénéfice fiscal de {money(fiscal_result)} €. "
            "En LMNP au réel, l’amortissement ne peut pas créer de déficit : "
            "il est plafonné aux loyers moins les autres charges déductibles."
        ]
        if prior_dep_used > 0:
            parts.append(
                f"Des amortissements reportés ({money(prior_dep_used)} €) ont déjà été repris."
            )
        if prior_loss_used > 0:
            parts.append(f"Des déficits antérieurs ({money(prior_loss_used)} €) ont été imputés.")
        parts.append(
            "Pour tendre vers 0 : vérifier les charges déductibles comptabilisées, "
            "les dotations d’amortissement, et les reports encore disponibles."
        )
        return " ".join(parts)
    return (
        f"Déficit LMNP de {money(-fiscal_result)} €. "
        "Il n’est pas imputable sur votre revenu global : il se reporte sur les revenus "
        "LMNP des dix années suivantes. L’amortissement comptable, lui, reste inchangé au ledger."
    )


def _replace_register(
    session: Session,
    model: type[DepreciationCarryForward],
    year_id: int,
    computation_id: int,
    amount: int,
    rule_id: str,
) -> None:
    row = session.scalar(select(model).where(model.fiscal_year_id == year_id))
    if row is None:
        session.add(
            model(
                fiscal_year_id=year_id,
                computation_id=computation_id,
                amount=amount,
                rule_id=rule_id,
            )
        )
    else:
        row.computation_id = computation_id
        row.amount = amount
        row.rule_id = rule_id


def _json(row: FiscalComputation, *, replayed: bool) -> dict[str, Any]:
    presented = calculation_status(row.vintage)
    return {
        "id": row.id,
        "fiscal_year_id": row.fiscal_year_id,
        "status": "research_only",
        "declarable": presented["declarable"],
        "output_status": presented["output_status"],
        "output_label": presented["output_label"],
        "replayed": replayed,
        "vintage": row.vintage,
        "rules_sha256": row.rules_sha256,
        "computed_at": _iso_utc(row.created_at),
        "ledger_sha256": row.ledger_sha256,
        "accounting_result": money(row.accounting_result),
        "fiscal_result": money(row.fiscal_result),
        "deductible_depreciation": money(row.deductible_depreciation),
        "unused_depreciation": money(row.unused_depreciation),
        "tax_loss": money(row.tax_loss),
        "non_deductible": money(row.non_deductible),
        "imputed_on_global_income": "0.00",
        "details": row.details,
    }
