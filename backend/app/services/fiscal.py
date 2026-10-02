"""Fiscal preview from the ledger. Accounting entries are never rewritten."""

import hashlib
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import FiscalInput
from app.core.money import to_cents
from app.domain.fiscal.loader import load_vintage
from app.models import Account, AccountingEntry, AccountingEntryLine
from app.models.assets import Asset
from app.models.fiscal import DepreciationCarryForward, FiscalComputation, TaxLossCarryForward
from app.services.ledger import fail, get_year, money
from app.services.statements import statements


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
    _land_invariant(session)
    other = expenses - depreciation
    additions, addition_accounts = _additions(expense_balances, data)
    capacity = max(0, income - (other - additions))
    deductible = min(depreciation, capacity)
    unused = depreciation - deductible
    fiscal_result = income - other - deductible + additions
    tax_loss = max(0, -fiscal_result)
    accounting = income - expenses
    details = {
        "applied_rules": [rule["id"] for rule in vintage["executable"]],
        "blocked_rules": vintage["blocked"],
        "prior_carry_forward_use": "disabled",
        "imputed_on_global_income": "0.00",
        "additions": adjustments,
        "addition_accounts": addition_accounts,
        "accounting_depreciation": money(depreciation),
        "capacity": money(capacity),
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
                    "Consommation des reports antérieurs désactivée."
                ),
            )
        )
    else:
        loss.computation_id = row.id
        loss.amount = tax_loss
    session.flush()
    return _json(row, replayed=False)


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
