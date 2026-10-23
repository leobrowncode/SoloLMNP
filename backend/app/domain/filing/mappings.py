"""Whitelist compiler for tax-form mappings. Expressions are data, never evaluated as code."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.core.money import to_cents
from app.domain.filing.liasse import extend_package
from app.models import AccountingEntry, AccountingEntryLine
from app.services.fiscal import _operating, latest_fiscal
from app.services.ledger import fail, get_year, money
from app.services.statements import statements

OPS = {"sum_accounts", "balance", "tax_result", "add", "subtract", "named", "nonneg", "absneg"}
BLOCKING_WARNINGS = frozenset(
    {
        "IMMOBILISATIONS_ECART",
        "EFFECTIFS",
        "RESULTAT_MIXTE",
        "CLASSEMENT_INCOMPLET",
        "SIREN_MANQUANT",
    }
)


def compile_package(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    path = PROJECT_ROOT / "fiscal" / year.fiscal_vintage / "forms" / "2033.json"
    if not path.is_file():
        fail("MAPPING_MISSING", "Aucun mapping n’est archivé pour ce millésime.")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("status") != "research_only" or document.get("vintage") != year.fiscal_vintage:
        fail("MAPPING_UNUSABLE", "Le mapping de ce millésime n’est pas utilisable.")
    report = statements(session, year.id)
    fiscal = latest_fiscal(session, year.id)
    context = _context(session, year.id, report, fiscal)
    fields = []
    errors: list[dict[str, str]] = []
    for field in document["fields"]:
        value, accounts, entries = _eval(field["formula"], context, errors, field["code"])
        fields.append(
            {
                "code": field["code"],
                "form_ref": field.get("form_ref", document["form"]),
                "official_case": field.get("official_case"),
                "official_case_deficit": field.get("official_case_deficit"),
                "label": field["label"],
                "required": field["required"],
                "expression": json.dumps(field["formula"], sort_keys=True),
                "rules": field.get("rules", []),
                "accounts": accounts,
                "entries": entries,
                "value": money(value),
                "status": "research_only",
            }
        )
        if field["required"] and value is None:
            errors.append({"code": "REQUIRED_FIELD", "message": f"Case {field['code']} absente."})
    by_code = {field["code"]: _cents(field["value"]) for field in fields}
    for check in document.get("checks", []):
        left = by_code.get(check["left"])
        right, _, _ = _eval(check["right"], context, errors, check["id"])
        if left != right:
            errors.append(
                {"code": "INTERFORM", "message": f"Contrôle {check['id']} non satisfait."}
            )
    package = {
        "status": "research_only",
        "declarable": False,
        "form": document["form"],
        "vintage": document["vintage"],
        "version": document["version"],
        "source": document["source"],
        "source_sha256": _file_hash(path),
        "ledger_sha256": fiscal["ledger_sha256"],
        "accounting_result": fiscal["accounting_result"],
        "fiscal_result": fiscal["fiscal_result"],
        "fields": fields,
        "errors": errors,
        "warnings": [
            {
                "code": "RESEARCH_ONLY",
                "message": (
                    "Feuille de recopie pour la déclaration. SoloLMNP n’envoie rien aux impôts."
                ),
            }
        ],
        "by_property": [],
        "copy": {
            "transmission": False,
            "portal": "https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi",
        },
    }
    extend_package(session, year, fiscal, package)
    _mark_copy_ready(year, package)
    return package


def _mark_copy_ready(year: Any, package: dict[str, Any]) -> None:
    """Copy sheet for the 2026 exercise. A failing gate stays research_only."""
    for field in package["fields"]:
        field["status"] = "research_only"
    package["status"] = "research_only"
    package["declarable"] = False
    if year.fiscal_vintage not in {"2026", "2025"} or package["errors"]:
        return
    registry = json.loads(
        (PROJECT_ROOT / "fiscal" / "2025" / "forms" / "cases.yaml").read_text(encoding="utf-8")
    )
    known = {
        case["work_code"]: case
        for case in registry["cases"]
        if case.get("work_code") and case["form"] != "2042-C-PRO"
    }
    for field in package["fields"]:
        case = known.get(field["code"])
        form = field.get("form_ref", "")
        if (
            case is None
            or case["form"] != form
            or (form.startswith("2033") and case.get("official_case") != field.get("official_case"))
            or (form.startswith("2033") and case.get("verification") != "verified")
            or (
                form.startswith("2031")
                and case.get("verification") != "verified_by_cross_reference"
            )
        ):
            package["errors"].append(
                {
                    "code": "CASE_NON_VERIFIEE",
                    "message": f"La case {field['code']} n’est pas au registre des cases lues.",
                }
            )
            return
        if form.startswith("2033") and not field.get("official_case"):
            package["errors"].append(
                {
                    "code": "CASE_NON_VERIFIEE",
                    "message": f"La case {field['code']} n’a pas de numéro officiel.",
                }
            )
            return
    if any(item["code"] in BLOCKING_WARNINGS for item in package["warnings"]):
        return
    package["status"] = "ready"
    package["declarable"] = True
    for field in package["fields"]:
        field["status"] = "ready"


def _context(
    session: Session, year_id: int, report: dict[str, Any], fiscal: dict[str, Any]
) -> dict[str, Any]:
    entry_ids = {
        number: _entry_ids(session, year_id, number)
        for number in {
            row["account_number"]
            for group in (
                report["income_statement"]["income"],
                report["income_statement"]["expenses"],
                report["balance_sheet"]["assets"],
                report["balance_sheet"]["liabilities"],
                report["balance_sheet"]["equity"],
            )
            for row in group
        }
    }
    balances = {
        row["account_number"]: _cents(row["amount"])
        for group in report["balance_sheet"].values()
        if isinstance(group, list)
        for row in group
    }
    _income, _expenses, _depreciation, charges, products = _operating(session, year_id)
    balances.update(charges)
    balances.update(products)
    for number in (*charges, *products):
        entry_ids.setdefault(number, _entry_ids(session, year_id, number))
    named = _named(charges, products, entry_ids, fiscal)
    return {
        "balances": balances,
        "entries": entry_ids,
        "tax_result": _cents(fiscal["fiscal_result"]),
        "named": named,
    }


def _named(
    charges: dict[str, int],
    products: dict[str, int],
    entry_ids: dict[str, list[int]],
    fiscal: dict[str, Any],
) -> dict[str, tuple[int, list[str], list[int]]]:
    def bucket(amounts: dict[str, int]) -> tuple[int, list[str], list[int]]:
        accounts = sorted(amounts)
        entries = [entry for number in accounts for entry in entry_ids.get(number, [])]
        return sum(amounts.values()), accounts, entries

    def pick(source: dict[str, int], prefixes: tuple[str, ...]) -> dict[str, int]:
        return {number: amount for number, amount in source.items() if number.startswith(prefixes)}

    exploitation_income = {
        number: amount for number, amount in products.items() if not number.startswith(("76", "77"))
    }
    exploitation_charges = {
        number: amount for number, amount in charges.items() if not number.startswith(("66", "67"))
    }
    income_total = sum(exploitation_income.values())
    charge_total = sum(exploitation_charges.values())
    income_accounts = sorted(exploitation_income)
    charge_accounts = sorted(exploitation_charges)
    details = fiscal.get("details") or {}
    before = details.get("fiscal_result_before_prior_losses", fiscal["fiscal_result"])
    return {
        "services": bucket(pick(products, ("706",))),
        "exploitation_income": bucket(exploitation_income),
        "financial_income": bucket(pick(products, ("76",))),
        "external": bucket(pick(charges, ("60", "61", "62"))),
        "taxes": bucket(pick(charges, ("63",))),
        "depreciation": bucket(pick(charges, ("681",))),
        "financial_expense": bucket(pick(charges, ("66", "67"))),
        "exploitation_charges": bucket(exploitation_charges),
        "operating_result": (
            income_total - charge_total,
            income_accounts + charge_accounts,
            [
                entry
                for number in income_accounts + charge_accounts
                for entry in entry_ids.get(number, [])
            ],
        ),
        "accounting": (_cents(fiscal["accounting_result"]), [], []),
        "unused": (_cents(fiscal["unused_depreciation"]), [], []),
        "additions": (_cents(fiscal["non_deductible"]), [], []),
        "prior_depreciation_used": (
            _cents(str(details.get("prior_depreciation_used", "0.00"))),
            [],
            [],
        ),
        "fiscal_before": (_cents(str(before)), [], []),
    }


def _eval(
    formula: dict[str, Any], context: dict[str, Any], errors: list[dict[str, str]], code: str
) -> tuple[int, list[str], list[int]]:
    op = formula.get("op")
    if op not in OPS:
        errors.append({"code": "DSL", "message": f"Opérateur refusé pour {code}."})
        return 0, [], []
    if op == "tax_result":
        return context["tax_result"], [], []
    if op == "named":
        named: dict[str, tuple[int, list[str], list[int]]] = context["named"]
        bucket = named.get(str(formula.get("key", "")))
        if bucket is None:
            errors.append({"code": "DSL", "message": f"Montant inconnu pour {code}."})
            return 0, [], []
        return bucket
    if op == "nonneg":
        value, accounts, entries = _eval(formula["term"], context, errors, code)
        return max(0, value), accounts, entries
    if op == "absneg":
        value, accounts, entries = _eval(formula["term"], context, errors, code)
        return max(0, -value), accounts, entries
    if op == "sum_accounts":
        prefixes = tuple(formula.get("prefixes", []))
        accounts = [number for number in context["balances"] if number.startswith(prefixes)]
        entries = [entry for number in accounts for entry in context["entries"].get(number, [])]
        return sum(context["balances"][number] for number in accounts), sorted(accounts), entries
    if op == "balance":
        number = str(formula.get("account", ""))
        return context["balances"].get(number, 0), [number], context["entries"].get(number, [])
    if op == "add":
        total = 0
        used_accounts: list[str] = []
        used_entries: list[int] = []
        for term in formula.get("terms", []):
            value, used, ids = _eval(term, context, errors, code)
            total += value
            used_accounts.extend(used)
            used_entries.extend(ids)
        return total, used_accounts, used_entries
    left, left_accounts, left_entries = _eval(formula["left"], context, errors, code)
    right, right_accounts, right_entries = _eval(formula["right"], context, errors, code)
    return left - right, left_accounts + right_accounts, left_entries + right_entries


def _entry_ids(session: Session, year_id: int, account: str) -> list[int]:
    rows = session.scalars(
        select(AccountingEntry.id)
        .join(AccountingEntryLine)
        .where(
            AccountingEntry.fiscal_year_id == year_id,
            AccountingEntry.status == "VALIDATED",
            AccountingEntryLine.account_number == account,
        )
        .order_by(AccountingEntry.id)
    )
    return list(dict.fromkeys(rows))


def _cents(amount: str) -> int:
    return to_cents(Decimal(amount))


def _file_hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
