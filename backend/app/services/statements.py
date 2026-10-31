"""Statements from validated entries, with PCG rubrics and no fiscal mapping.

The income statement ignores the centralization entry. After that entry zeroes
classes 6 and 7, the exercise result stays visible and matches account 120 or 129.
Those accounts are not listed under equity excluding the result. An open exercise
stays PROVISIONAL; a closed one is CLOSED.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.domain.accounting.result_accounts import is_result_account, still_held
from app.models import Account, AccountingEntry, AccountingEntryLine, FiscalYear
from app.services.ledger import fail, get_year, money

_PNL = frozenset({"INCOME", "EXPENSE"})
_KINDS = ("ASSET", "LIABILITY", "EQUITY", "EXPENSE", "INCOME")


@dataclass(frozen=True)
class _LedgerNets:
    year: FiscalYear
    accounts: dict[str, Account]
    full: dict[str, int]
    operating: dict[str, int]
    drafts: int


def statements(session: Session, year_id: int) -> dict[str, Any]:
    view = _load(session, year_id)
    _validate(view.full, view.accounts)
    _raw_groups, raw_totals = _classify(view.full, view.accounts, _PNL)
    raw_result = raw_totals["INCOME"] - raw_totals["EXPENSE"]
    presented = _presented_nets(view, raw_result)
    groups, totals = _classify(presented, view.accounts, _KINDS)
    result = totals["INCOME"] - totals["EXPENSE"]
    current = raw_result + _held_total(view, raw_result)
    liabilities_equity = totals["LIABILITY"] + totals["EQUITY"] + current
    if totals["ASSET"] != liabilities_equity:
        fail("UNBALANCED_STATEMENTS", "Le bilan est déséquilibré : états bloqués.")
    status = _status(view.year)
    drafts = view.drafts
    return {
        "fiscal_year_id": year_id,
        "start_date": view.year.start_date.isoformat(),
        "end_date": view.year.end_date.isoformat(),
        "status": status,
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
            "current_result": money(current),
            "total_liabilities_and_equity": money(liabilities_equity),
            "balanced": True,
        },
        "presentation": _presentation(presented, view.accounts, groups, status),
    }


def ledger_income(session: Session, year_id: int) -> dict[str, Any]:
    """Class 6/7 as stored, including centralization. This is the amount left to close."""
    view = _load(session, year_id)
    _validate(view.full, view.accounts)
    groups, totals = _classify(view.full, view.accounts, _PNL)
    return {
        "income": groups["INCOME"],
        "expenses": groups["EXPENSE"],
        "result": money(totals["INCOME"] - totals["EXPENSE"]),
        "excluded_draft_count": view.drafts,
    }


def classes_open(session: Session, year_id: int) -> bool:
    """True when centralization has not yet zeroed every class 6/7 balance."""
    income = ledger_income(session, year_id)
    rows = income["income"] + income["expenses"]
    return any(row["amount"] not in {"0.00", "-0.00"} for row in rows)


def unclosed_class_result(session: Session, year_id: int) -> int:
    """Credit-positive class 6/7 result still open in the ledger, in cents."""
    income = ledger_income(session, year_id)
    return to_cents(Decimal(income["result"]))


def equity_nets(session: Session, year_id: int) -> dict[str, int]:
    """Debit-positive nets of every equity account, including 120 and 129."""
    view = _load(session, year_id)
    return {
        number: net
        for number, net in view.full.items()
        if view.accounts[number].account_type == "EQUITY"
    }


def carryforward_view(session: Session, year_id: int) -> dict[str, Any]:
    """Balance sheet at ledger value, and only the class 6/7 result not yet centralized.

    Opening entries carry 120/129 when the result is already there. They must not
    also replay that result, or the next exercise would count it twice.
    """
    view = _load(session, year_id)
    _validate(view.full, view.accounts)
    groups, totals = _classify(view.full, view.accounts, _KINDS)
    return {
        "balance_sheet": {
            "assets": groups["ASSET"],
            "liabilities": groups["LIABILITY"],
            "equity": groups["EQUITY"],
        },
        "income_statement": {"result": money(totals["INCOME"] - totals["EXPENSE"])},
        "excluded_draft_count": view.drafts,
    }


def _load(session: Session, year_id: int) -> _LedgerNets:
    year = get_year(session, year_id)
    rows = session.execute(
        select(AccountingEntryLine, Account, AccountingEntry)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .join(Account, Account.number == AccountingEntryLine.account_number)
        .where(AccountingEntry.fiscal_year_id == year_id, AccountingEntry.status == "VALIDATED")
        .order_by(Account.number, AccountingEntry.sequence, AccountingEntryLine.position)
    )
    recorded: list[tuple[str, int, int]] = []
    full: dict[str, int] = {}
    entry_balances: dict[int, int] = {}
    accounts: dict[str, Account] = {}
    source_by_id: dict[int, str] = {}
    reversal_of: dict[int, int | None] = {}
    for line, account, entry in rows:
        net = to_cents(line.debit) - to_cents(line.credit)
        full[account.number] = full.get(account.number, 0) + net
        entry_balances[entry.id] = entry_balances.get(entry.id, 0) + net
        accounts[account.number] = account
        source_by_id[entry.id] = entry.source_type
        reversal_of[entry.id] = entry.reversal_of_id
        recorded.append((account.number, net, entry.id))
    # Opposite errors in separate entries must never cancel in annual totals.
    # Opening previews and posting share this same defensive source validation.
    if any(entry_balances.values()):
        fail("UNBALANCED_STATEMENTS", "Une écriture validée est déséquilibrée : états bloqués.")
    if sum(full.values()) != 0:
        fail("UNBALANCED_STATEMENTS", "Le ledger validé est déséquilibré : états bloqués.")
    centralization_ids = {
        entry_id for entry_id, source in source_by_id.items() if source == "CENTRALIZATION"
    }
    excluded = set(centralization_ids)
    for entry_id, original in reversal_of.items():
        if original in centralization_ids:
            excluded.add(entry_id)
    operating: dict[str, int] = {}
    for number, net, entry_id in recorded:
        if entry_id in excluded:
            continue
        operating[number] = operating.get(number, 0) + net
    drafts = session.scalar(
        select(func.count())
        .select_from(AccountingEntry)
        .where(AccountingEntry.fiscal_year_id == year_id, AccountingEntry.status == "DRAFT")
    )
    return _LedgerNets(
        year=year,
        accounts=accounts,
        full=full,
        operating=operating,
        drafts=int(drafts or 0),
    )


def _status(year: FiscalYear) -> str:
    if year.status == "CLOSED":
        return "CLOSED"
    return "PROVISIONAL"


def _validate(nets: dict[str, int], accounts: dict[str, Account]) -> None:
    for number in nets:
        kind = accounts[number].account_type
        # A configurable account must not move a class 6/7 balance into the balance sheet.
        expected = {"6": "EXPENSE", "7": "INCOME"}.get(number[0])
        if (expected and kind != expected) or (expected is None and kind in _PNL):
            fail("INVALID_STATEMENT_ACCOUNT", f"Classement du compte {number} incohérent.")


def _classify(
    nets: dict[str, int], accounts: dict[str, Account], kinds: frozenset[str] | tuple[str, ...]
) -> tuple[dict[str, list[dict[str, str]]], dict[str, int]]:
    groups: dict[str, list[dict[str, str]]] = {kind: [] for kind in kinds}
    totals: dict[str, int] = {kind: 0 for kind in kinds}
    for number, net in nets.items():
        account = accounts[number]
        kind = account.account_type
        if kind not in groups:
            continue
        value = net if kind in {"ASSET", "EXPENSE"} else -net
        totals[kind] += value
        groups[kind].append(
            {"account_number": number, "label": account.label, "amount": money(value)}
        )
    return groups, totals


def _held_total(view: _LedgerNets, raw_result: int) -> int:
    _groups, operating_totals = _classify(view.operating, view.accounts, _PNL)
    closed = (operating_totals["INCOME"] - operating_totals["EXPENSE"]) - raw_result
    return sum(_held(view, closed).values())


def _held(view: _LedgerNets, closed: int) -> dict[str, int]:
    sitting = {
        number: -net
        for number, net in view.full.items()
        if is_result_account(number) and view.accounts[number].account_type == "EQUITY"
    }
    return still_held(closed, sitting)


def _presented_nets(view: _LedgerNets, raw_result: int) -> dict[str, int]:
    """Operating class 6/7, and equity without the result still sitting on 120/129."""
    _groups, operating_totals = _classify(view.operating, view.accounts, _PNL)
    closed = (operating_totals["INCOME"] - operating_totals["EXPENSE"]) - raw_result
    held = _held(view, closed)
    presented: dict[str, int] = {}
    for number, net in view.full.items():
        account = view.accounts[number]
        if account.account_type in _PNL:
            if number in view.operating:
                presented[number] = view.operating[number]
            continue
        adjusted = net + held.get(number, 0)
        if is_result_account(number) and account.account_type == "EQUITY" and adjusted == 0:
            continue
        presented[number] = adjusted
    return presented


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
    status: str,
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
        "status": status,
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
