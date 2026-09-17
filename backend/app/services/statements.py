"""Provisional account-level statements; no fiscal mapping or closing entries."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.models import Account, AccountingEntry, AccountingEntryLine
from app.services.ledger import fail, get_year, money


def statements(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    rows = session.execute(
        select(AccountingEntryLine, Account)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .join(Account, Account.number == AccountingEntryLine.account_number)
        .where(AccountingEntry.fiscal_year_id == year_id, AccountingEntry.status == "VALIDATED")
        .order_by(Account.number, AccountingEntry.sequence, AccountingEntryLine.position)
    )
    balances: dict[str, int] = {}
    accounts: dict[str, Account] = {}
    for line, account in rows:
        balances[account.number] = balances.get(account.number, 0) + (
            to_cents(line.debit) - to_cents(line.credit)
        )
        accounts[account.number] = account
    if sum(balances.values()) != 0:
        fail("UNBALANCED_STATEMENTS", "Le ledger validé est déséquilibré : états bloqués.")

    groups: dict[str, list[dict[str, str]]] = {
        kind: [] for kind in ("ASSET", "LIABILITY", "EQUITY", "EXPENSE", "INCOME")
    }
    totals = dict.fromkeys(groups, 0)
    for number, net in balances.items():
        account = accounts[number]
        kind = account.account_type
        # A configurable account must not move a class 6/7 balance into the balance sheet.
        expected = {"6": "EXPENSE", "7": "INCOME"}.get(number[0])
        if (expected and kind != expected) or (expected is None and kind in {"EXPENSE", "INCOME"}):
            fail("INVALID_STATEMENT_ACCOUNT", f"Classement du compte {number} incohérent.")
        value = net if kind in {"ASSET", "EXPENSE"} else -net
        totals[kind] += value
        groups[kind].append(
            {"account_number": number, "label": account.label, "amount": money(value)}
        )

    result = totals["INCOME"] - totals["EXPENSE"]
    liabilities_equity = totals["LIABILITY"] + totals["EQUITY"] + result
    if totals["ASSET"] != liabilities_equity:
        fail("UNBALANCED_STATEMENTS", "Le bilan est déséquilibré : états bloqués.")
    drafts = session.scalar(
        select(func.count())
        .select_from(AccountingEntry)
        .where(AccountingEntry.fiscal_year_id == year_id, AccountingEntry.status == "DRAFT")
    )
    return {
        "fiscal_year_id": year_id,
        "start_date": year.start_date.isoformat(),
        "end_date": year.end_date.isoformat(),
        "status": "PROVISIONAL",
        "validated_only": True,
        "excluded_draft_count": drafts,
        "income_statement": {
            "income": groups["INCOME"],
            "expenses": groups["EXPENSE"],
            "total_income": money(totals["INCOME"]),
            "total_expenses": money(totals["EXPENSE"]),
            "result": money(result),
        },
        "balance_sheet": {
            "assets": groups["ASSET"],
            "liabilities": groups["LIABILITY"],
            "equity": groups["EQUITY"],
            "total_assets": money(totals["ASSET"]),
            "total_liabilities": money(totals["LIABILITY"]),
            "total_equity": money(totals["EQUITY"]),
            "current_result": money(result),
            "total_liabilities_and_equity": money(liabilities_equity),
            "balanced": True,
        },
    }
