"""Fiscal preview from the ledger. Accounting entries are never rewritten."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import FiscalInput
from app.core.money import to_cents
from app.domain.fiscal.loader import load_vintage
from app.models import Account, AccountingEntry, AccountingEntryLine, BusinessOperation, FiscalYear
from app.models.assets import Asset
from app.models.base import utc_now
from app.models.fiscal import DepreciationCarryForward, FiscalComputation, TaxLossCarryForward
from app.services.ledger import fail, get_year, money
from app.services.statements import statements

TAX_LOSS_HORIZON_YEARS = 10
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


def compute_fiscal(session: Session, year_id: int, data: FiscalInput) -> dict[str, Any]:
    year = get_year(session, year_id)
    vintage = load_vintage(year.fiscal_vintage)
    statements(session, year.id)
    income, expenses, depreciation, expense_balances, _income_balances = _operating(
        session, year.id
    )
    fingerprint = ledger_fingerprint(session, year.id)
    adjustments = [item.model_dump(mode="json") for item in data.adjustments]
    for item in adjustments:
        item["amount"] = money(to_cents(Decimal(item["amount"])))
    adjustments_hash = hashlib.sha256(json.dumps(adjustments, sort_keys=True).encode()).hexdigest()
    current = _current(session, year.id)
    if (
        current is not None
        and current.ledger_sha256 == fingerprint
        and current.adjustments_sha256 == adjustments_hash
        and current.rules_sha256 == vintage["sha256"]
        and current.invalidated_at is None
    ):
        return _json(current, replayed=True)
    if year.status != "OPEN":
        fail("YEAR_LOCKED", "Un exercice qui n’est pas ouvert ne peut pas être recalculé.")
    if current is not None:
        current.invalidated_at = utc_now()
        session.flush()
    _land_invariant(session)
    other = expenses - depreciation
    additions, addition_accounts = _additions(expense_balances, data)
    capacity = max(0, income - (other - additions))
    current_deductible = min(depreciation, capacity)
    capacity_left = capacity - current_deductible
    unused = depreciation - current_deductible
    dep_stocks = _prior_remaining(session, year, "depreciation")
    dep_uses, prior_dep_used = _consume_fifo(dep_stocks, capacity_left)
    deductible = current_deductible + prior_dep_used
    fiscal_before_losses = income - other - deductible + additions
    loss_stocks = _prior_remaining(
        session,
        year,
        "tax_loss",
        min_origin_year=year.year - TAX_LOSS_HORIZON_YEARS,
    )
    loss_budget = max(0, fiscal_before_losses)
    loss_uses, prior_loss_used = _consume_fifo(loss_stocks, loss_budget)
    fiscal_result = fiscal_before_losses - prior_loss_used
    tax_loss = max(0, -fiscal_result)
    accounting = income - expenses
    details = {
        "applied_rules": [rule["id"] for rule in vintage["executable"]],
        "blocked_rules": vintage["blocked"],
        "scope_rules": vintage["scope"],
        "prior_carry_forward_use": {
            "status": "enabled",
            "order": PRIOR_USE_ORDER,
            "tax_loss_horizon_years": TAX_LOSS_HORIZON_YEARS,
            "depreciation": dep_uses,
            "tax_loss": loss_uses,
            "notes": (
                "Registres d’origine inchangés. La consommation est tracée ici ; "
                "les soldes restants des exercices clôturés sont dérivés. "
                "Cession, TVA, plus-values et ventilation automatique du terrain restent hors MVP."
            ),
        },
        "fiscal_result_before_prior_losses": money(fiscal_before_losses),
        "prior_depreciation_used": money(prior_dep_used),
        "prior_tax_loss_used": money(prior_loss_used),
        "imputed_on_global_income": "0.00",
        "additions": adjustments,
        "addition_accounts": addition_accounts,
        "operating_income": money(income),
        "other_charges": money(other),
        "accounting_depreciation": money(depreciation),
        "capacity": money(capacity),
        "current_deductible_depreciation": money(current_deductible),
        "goal_hint": _goal_hint(fiscal_result, unused, prior_dep_used, prior_loss_used),
    }
    row = FiscalComputation(
        fiscal_year_id=year.id,
        vintage=year.fiscal_vintage,
        rules_sha256=vintage["sha256"],
        ledger_sha256=fingerprint,
        adjustments_sha256=adjustments_hash,
        accounting_result=accounting,
        fiscal_result=fiscal_result,
        deductible_depreciation=deductible,
        unused_depreciation=unused,
        tax_loss=tax_loss,
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
        unused,
        "RULE-LMNP-DEPRECIATION-LIMIT-001",
    )
    loss = session.scalar(
        select(TaxLossCarryForward).where(TaxLossCarryForward.fiscal_year_id == year.id)
    )
    if loss is None:
        session.add(
            TaxLossCarryForward(
                fiscal_year_id=year.id,
                computation_id=row.id,
                amount=tax_loss,
                rule_id="RULE-LMNP-LOSS-001",
                note=(
                    "Non imputé sur le revenu global. "
                    "Consommation FIFO des reports antérieurs (horizon 10 ans) activée pour le MVP."
                ),
            )
        )
    else:
        loss.computation_id = row.id
        loss.amount = tax_loss
        loss.note = (
            "Non imputé sur le revenu global. "
            "Consommation FIFO des reports antérieurs (horizon 10 ans) activée pour le MVP."
        )
    session.flush()
    return _json(row, replayed=False)


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
    get_year(session, year_id)
    current = _current(session, year_id)
    if current is None:
        fail("FISCAL_NOT_COMPUTED", "Aucun calcul fiscal n’est enregistré pour cet exercice.", 404)
    assert current is not None  # noqa: S101
    return _json(current, replayed=True)


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


def _prior_remaining(
    session: Session,
    year: FiscalYear,
    kind: str,
    *,
    min_origin_year: int | None = None,
) -> list[dict[str, int]]:
    """Remaining stocks from CLOSED prior years; registers are not mutated."""
    model = DepreciationCarryForward if kind == "depreciation" else TaxLossCarryForward
    query = (
        select(FiscalYear, model)
        .join(model, model.fiscal_year_id == FiscalYear.id)
        .where(
            FiscalYear.rental_activity_id == year.rental_activity_id,
            FiscalYear.status == "CLOSED",
            FiscalYear.year < year.year,
            model.amount > 0,
        )
        .order_by(FiscalYear.year.asc(), FiscalYear.id.asc())
    )
    if min_origin_year is not None:
        query = query.where(FiscalYear.year >= min_origin_year)
    stocks: list[dict[str, int]] = []
    for origin, register in session.execute(query):
        remaining = register.amount - _already_consumed(session, year, kind, origin.id, origin.year)
        if remaining > 0:
            stocks.append(
                {
                    "origin_year_id": origin.id,
                    "origin_year": origin.year,
                    "remaining": remaining,
                }
            )
    return stocks


def _already_consumed(
    session: Session,
    current: FiscalYear,
    kind: str,
    origin_year_id: int,
    origin_year: int,
) -> int:
    rows = session.execute(
        select(FiscalComputation.details)
        .join(FiscalYear, FiscalYear.id == FiscalComputation.fiscal_year_id)
        .where(
            FiscalYear.rental_activity_id == current.rental_activity_id,
            FiscalYear.year > origin_year,
            FiscalYear.id != current.id,
            FiscalComputation.invalidated_at.is_(None),
        )
    )
    total = 0
    key = "depreciation" if kind == "depreciation" else "tax_loss"
    for (details,) in rows:
        uses = (details or {}).get("prior_carry_forward_use") or {}
        if uses.get("status") != "enabled":
            continue
        for item in uses.get(key, []):
            if int(item["origin_year_id"]) == origin_year_id:
                total += _cents(str(item["used"]))
    return total


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


def _consume_fifo(
    stocks: list[dict[str, int]], budget: int
) -> tuple[list[dict[str, str | int]], int]:
    remaining_budget = budget
    uses: list[dict[str, str | int]] = []
    used_total = 0
    for stock in stocks:
        if remaining_budget <= 0:
            break
        take = min(stock["remaining"], remaining_budget)
        if take <= 0:
            continue
        remaining_budget -= take
        used_total += take
        uses.append(
            {
                "origin_year_id": stock["origin_year_id"],
                "origin_year": stock["origin_year"],
                "used": money(take),
                "remaining_after": money(stock["remaining"] - take),
            }
        )
    return uses, used_total


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
    return {
        "id": row.id,
        "fiscal_year_id": row.fiscal_year_id,
        "status": "research_only",
        "declarable": False,
        "replayed": replayed,
        "vintage": row.vintage,
        "rules_sha256": row.rules_sha256,
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
