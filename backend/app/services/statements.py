"""Provisional statements from validated entries, with PCG rubrics and no fiscal mapping."""

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
    entry_balances: dict[int, int] = {}
    accounts: dict[str, Account] = {}
    for line, account in rows:
        net = to_cents(line.debit) - to_cents(line.credit)
        balances[account.number] = balances.get(account.number, 0) + net
        entry_id = line.accounting_entry_id
        entry_balances[entry_id] = entry_balances.get(entry_id, 0) + net
        accounts[account.number] = account
    # Opposite errors in separate entries must never cancel in annual totals.
    # Opening previews and posting share this same defensive source validation.
    if any(entry_balances.values()):
        fail("UNBALANCED_STATEMENTS", "Une écriture validée est déséquilibrée : états bloqués.")
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
    presentation = _presentation(balances, accounts, groups)
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
        "presentation": presentation,
    }


_EXPENSE = {
    "60": "ACHATS",
    "61": "SERVICES_EXTERIEURS",
    "62": "SERVICES_EXTERIEURS",
    "63": "IMPOTS",
    "64": "CHARGES_PERSONNEL",
    "65": "AUTRES_CHARGES",
    "66": "CHARGES_FINANCIERES",
    "67": "CHARGES_EXCEPTIONNELLES",
    "68": "DOTATIONS",
    "69": "IMPOTS_SUR_BENEFICES",
}
_INCOME = {
    "70": "PRODUITS_EXPLOITATION",
    "71": "PRODUITS_EXPLOITATION",
    "72": "PRODUITS_EXPLOITATION",
    "74": "PRODUITS_EXPLOITATION",
    "75": "PRODUITS_EXPLOITATION",
    "76": "PRODUITS_FINANCIERS",
    "77": "PRODUITS_EXCEPTIONNELS",
    "78": "REPRISES",
    "79": "TRANSFERTS",
}
_LABELS = {
    "IMMOBILISE": "Immobilisations",
    "CIRCULANT": "Actif circulant",
    "TRESORERIE": "Trésorerie",
    "CAPITAUX": "Capitaux propres",
    "DETTES": "Dettes",
    "ACHATS": "Achats",
    "SERVICES_EXTERIEURS": "Services extérieurs",
    "IMPOTS": "Impôts et taxes",
    "CHARGES_PERSONNEL": "Charges de personnel",
    "AUTRES_CHARGES": "Autres charges",
    "CHARGES_FINANCIERES": "Charges financières",
    "CHARGES_EXCEPTIONNELLES": "Charges exceptionnelles",
    "DOTATIONS": "Dotations",
    "IMPOTS_SUR_BENEFICES": "Impôts sur les bénéfices",
    "PRODUITS_EXPLOITATION": "Produits d’exploitation",
    "PRODUITS_FINANCIERS": "Produits financiers",
    "PRODUITS_EXCEPTIONNELS": "Produits exceptionnels",
    "REPRISES": "Reprises",
    "TRANSFERTS": "Transferts de charges",
    "AUTRES_PRODUITS": "Autres produits",
}
_BALANCE_ORDER = ("IMMOBILISE", "CIRCULANT", "TRESORERIE", "CAPITAUX", "DETTES")
_INCOME_ORDER = (
    "PRODUITS_EXPLOITATION",
    "PRODUITS_FINANCIERS",
    "PRODUITS_EXCEPTIONNELS",
    "REPRISES",
    "TRANSFERTS",
    "AUTRES_PRODUITS",
    "ACHATS",
    "SERVICES_EXTERIEURS",
    "IMPOTS",
    "CHARGES_PERSONNEL",
    "AUTRES_CHARGES",
    "CHARGES_FINANCIERES",
    "CHARGES_EXCEPTIONNELLES",
    "DOTATIONS",
    "IMPOTS_SUR_BENEFICES",
)


def _rubric(number: str, kind: str) -> str:
    prefix = number[:2]
    if kind == "ASSET":
        if prefix in {"20", "21", "22", "23", "26", "27", "28"}:
            return "IMMOBILISE"
        if prefix in {"50", "51", "52", "53", "54", "58"}:
            return "TRESORERIE"
        return "CIRCULANT"
    if kind == "EQUITY":
        return "CAPITAUX"
    if kind == "LIABILITY":
        return "DETTES"
    if kind == "EXPENSE":
        return _EXPENSE.get(prefix, "AUTRES_CHARGES")
    return _INCOME.get(prefix, "AUTRES_PRODUITS")


def _presentation(
    balances: dict[str, int],
    accounts: dict[str, Account],
    groups: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    indexed = {row["account_number"]: row for rows in groups.values() for row in rows}
    buckets: dict[str, list[dict[str, str]]] = {}
    totals: dict[str, int] = {}
    warnings: list[dict[str, str]] = []
    for number, net in balances.items():
        if net == 0:
            continue
        account = accounts[number]
        code = _rubric(number, account.account_type)
        row = indexed[number]
        buckets.setdefault(code, []).append(row)
        displayed = net if account.account_type in {"ASSET", "EXPENSE"} else -net
        totals[code] = totals.get(code, 0) + displayed
        warnings.extend(_unusual(number, account.account_type, displayed))
    return {
        "status": "PROVISIONAL",
        "model": "PCG_RUBRICS",
        "reclassifications_applied": False,
        "balance_rubrics": [_rubric_json(code, buckets, totals) for code in _BALANCE_ORDER],
        "income_rubrics": [
            _rubric_json(code, buckets, totals) for code in _INCOME_ORDER if code in buckets
        ],
        "warnings": warnings,
    }


def _rubric_json(
    code: str, buckets: dict[str, list[dict[str, str]]], totals: dict[str, int]
) -> dict[str, Any]:
    rows = buckets.get(code, [])
    return {
        "code": code,
        "label": _LABELS[code],
        "accounts": rows,
        "total": money(totals.get(code, 0)),
    }


def _unusual(number: str, kind: str, cents: int) -> list[dict[str, str]]:
    if cents >= 0:
        return []
    if kind == "ASSET" and number.startswith(("28", "29", "39", "49", "59")):
        return []
    if kind == "EQUITY" and number.startswith(("108", "129")):
        return []
    code = (
        "DECOUVERT" if kind == "ASSET" and number.startswith(("51", "53")) else "SOLDE_INHABITUEL"
    )
    message = (
        f"Le compte {number} présente un solde créditeur de trésorerie. "
        "Il reste dans sa rubrique, sans reclassement automatique."
        if code == "DECOUVERT"
        else (
            f"Le compte {number} a un solde de sens inhabituel. "
            "Aucune compensation n’est appliquée."
        )
    )
    return [{"code": code, "account_number": number, "message": message}]
