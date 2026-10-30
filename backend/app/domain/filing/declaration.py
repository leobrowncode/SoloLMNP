"""Declaration worksheet: explained amounts, EFI rows, 2042-C-PRO.

Every vintage stays research_only. A box is published only when this vintage's
own official form was read. Uncertain numbers are blocked, not guessed.
Nothing here is sent to the tax authority.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.core.money import to_cents
from app.domain.fiscal.engine import DEPRECIATION_RULE_ID, TAX_LOSS_RULE_ID
from app.domain.fiscal.loader import load_vintage, public_rule
from app.models import AccountingEntry, FiscalYear
from app.services.fiscal import _prior_remaining
from app.services.ledger import money

WORK_MARKER = "document de travail, à vérifier"
_NAMED = {
    "services": "somme des comptes 706",
    "exploitation_income": "produits d’exploitation hors 76 et 77",
    "financial_income": "produits financiers (76)",
    "external": "charges externes (60, 61, 62)",
    "taxes": "impôts et taxes (63)",
    "depreciation": "dotations comptables (681)",
    "financial_expense": "charges financières (66, 67)",
    "exploitation_charges": "charges d’exploitation hors 66 et 67",
    "operating_result": "produits d’exploitation − charges d’exploitation",
    "accounting": "résultat comptable",
    "unused": "amortissement non déduit de l’exercice (art. 39 C II)",
    "additions": "réintégrations confirmées, hors 681",
    "prior_depreciation_used": "reprises d’amortissements non déduits des exercices clôturés",
    "fiscal_before": "résultat fiscal avant imputation des déficits LMNP antérieurs",
}
_EXPLANATIONS: tuple[dict[str, Any], ...] = (
    {
        "code": "accounting_result",
        "label": "Résultat comptable",
        "formula": "produits − autres charges − dotations comptables (681)",
        "key": "accounting_result",
        "rules": [],
        "prefixes": ("6", "7"),
    },
    {
        "code": "additions",
        "label": "Réintégrations",
        "formula": "quotes-parts non déductibles confirmées, hors comptes 681",
        "key": "non_deductible",
        "rules": ["RULE-PARTIAL-CHARGE-001"],
        "prefixes": (),
    },
    {
        "code": "accounting_depreciation",
        "label": "Dotation comptable",
        "formula": "somme des comptes 681 validés, hors centralisation",
        "key": "accounting_depreciation",
        "rules": [DEPRECIATION_RULE_ID],
        "prefixes": ("681",),
    },
    {
        "code": "capacity",
        "label": "Plafond d’amortissement déductible",
        "formula": "max(0, loyers − autres charges + réintégrations)",
        "key": "capacity",
        "rules": [DEPRECIATION_RULE_ID],
        "prefixes": ("6", "7"),
    },
    {
        "code": "current_deductible_depreciation",
        "label": "Dotation déductible de l’exercice",
        "formula": "min(dotation comptable, plafond)",
        "key": "current_deductible_depreciation",
        "rules": [DEPRECIATION_RULE_ID],
        "prefixes": ("681",),
    },
    {
        "code": "unused_depreciation",
        "label": "Amortissement non déduit, reporté",
        "formula": "dotation comptable − dotation déductible de l’exercice",
        "key": "unused_depreciation",
        "rules": [DEPRECIATION_RULE_ID],
        "prefixes": ("681",),
    },
    {
        "code": "prior_depreciation_used",
        "label": "Reprise d’amortissements antérieurs",
        "formula": (
            "consommation FIFO du registre d’amortissements non déduits, sur la capacité restante"
        ),
        "key": "prior_depreciation_used",
        "rules": [DEPRECIATION_RULE_ID],
        "prefixes": (),
    },
    {
        "code": "deductible_depreciation",
        "label": "Amortissement fiscalement déduit",
        "formula": "dotation déductible de l’exercice + reprises du registre",
        "key": "deductible_depreciation",
        "rules": [DEPRECIATION_RULE_ID],
        "prefixes": ("681",),
    },
    {
        "code": "fiscal_before_losses",
        "label": "Résultat fiscal avant déficits antérieurs",
        "formula": "produits − autres charges − amortissement déduit + réintégrations",
        "key": "fiscal_result_before_prior_losses",
        "rules": [DEPRECIATION_RULE_ID, "RULE-PARTIAL-CHARGE-001"],
        "prefixes": ("6", "7"),
    },
    {
        "code": "prior_tax_loss_used",
        "label": "Déficits LMNP antérieurs imputés (estimation)",
        "formula": "consommation FIFO du registre des déficits, horizon 10 ans, hors revenu global",
        "key": "prior_tax_loss_used",
        "rules": [TAX_LOSS_RULE_ID],
        "prefixes": (),
    },
    {
        "code": "fiscal_result",
        "label": "Résultat fiscal après imputation estimée",
        "formula": "résultat avant déficits antérieurs − déficits imputés",
        "key": "fiscal_result",
        "rules": [DEPRECIATION_RULE_ID, TAX_LOSS_RULE_ID],
        "prefixes": ("6", "7"),
    },
    {
        "code": "tax_loss",
        "label": "Déficit LMNP de l’exercice",
        "formula": "max(0, − résultat fiscal). Non imputé sur le revenu global.",
        "key": "tax_loss",
        "rules": [TAX_LOSS_RULE_ID],
        "prefixes": (),
    },
)


def personal_return(session: Session, year: FiscalYear, fiscal: dict[str, Any]) -> dict[str, Any]:
    """2042-C-PRO for this vintage. Unpublished forms keep the amount and drop the case."""
    form = load_personal_form(year.fiscal_vintage)
    result = _fiscal_before(fiscal)
    benefit = max(0, result)
    deficit = max(0, -result)
    verified = form.get("verification") == "verified" and form.get("declarable") is not True
    source = form.get("source") if isinstance(form.get("source"), dict) else None
    lines = _result_lines(form, benefit, deficit, result, verified=verified, source=source)
    prior, usage = _deficit_rows(session, year, fiscal, form, verified=verified)
    return {
        "form": "2042-C-PRO",
        "status": "verified" if verified else "case_not_verified",
        "separated_from_liasse": True,
        "research_only": True,
        "declarable": False,
        "project_vintage": year.fiscal_vintage,
        "form_millesime": form.get("form_millesime"),
        "income_year": form.get("income_year"),
        "cerfa": form.get("cerfa"),
        "source": _public_source(source),
        "lines": lines,
        "prior_deficits": prior,
        "deficit_usage": usage,
        "blocked_cases": list(form.get("blocked") or []),
        "unfilled_cases": list(form.get("unfilled") or []),
        "note": _personal_note(form, verified),
    }


def explanation_inputs(fiscal: dict[str, Any]) -> dict[str, Any]:
    """Amounts frozen with the package. Presentation is rebuilt at read time."""
    details = fiscal.get("details") or {}
    return {
        "vintage": fiscal.get("vintage"),
        "rules_sha256": fiscal.get("rules_sha256"),
        "accounting_result": fiscal.get("accounting_result"),
        "fiscal_result": fiscal.get("fiscal_result"),
        "deductible_depreciation": fiscal.get("deductible_depreciation"),
        "unused_depreciation": fiscal.get("unused_depreciation"),
        "tax_loss": fiscal.get("tax_loss"),
        "non_deductible": fiscal.get("non_deductible"),
        "operating_income": details.get("operating_income"),
        "other_charges": details.get("other_charges"),
        "accounting_depreciation": details.get("accounting_depreciation"),
        "capacity": details.get("capacity"),
        "current_deductible_depreciation": details.get("current_deductible_depreciation"),
        "prior_depreciation_used": details.get("prior_depreciation_used"),
        "prior_tax_loss_used": details.get("prior_tax_loss_used"),
        "fiscal_result_before_prior_losses": details.get("fiscal_result_before_prior_losses"),
        "addition_accounts": list(details.get("addition_accounts") or []),
    }


def build_declaration(
    session: Session, year: FiscalYear, package: dict[str, Any]
) -> dict[str, Any]:
    """Screen payload. declarable stays false even if the liasse trust is higher."""
    vintage = str(package.get("vintage") or year.fiscal_vintage)
    inputs = package.get("explanation_inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    rules = _rules(vintage, inputs.get("rules_sha256"))
    publication = _publication(vintage)
    sources = _manifest_sources(vintage if publication == "verified_from_archive" else "2025")
    rows = [
        _efi_row(field, publication=publication, sources=sources, rules=rules)
        for field in package.get("fields") or []
        if isinstance(field, dict)
    ]
    briefs = _briefs(session, _ids_in(rows))
    for row in rows:
        row["entries"] = [briefs[item] for item in row["entry_ids"] if item in briefs]
    explanations = _explanations(session, year.id, inputs, rules)
    personal_sha = _file_sha(PROJECT_ROOT / "fiscal" / vintage / "forms" / "2042-c-pro.json")
    return {
        "marker": WORK_MARKER,
        "manual_only": True,
        "transmission": False,
        "edi": False,
        "scraping": False,
        "status": "research_only",
        "declarable": False,
        "vintage": vintage,
        "rules_version": rules.get("version") if rules.get("matches_computation") else None,
        "rules_sha256": inputs.get("rules_sha256") or rules.get("sha256"),
        "rules_file_version": rules.get("version"),
        "rules_file_sha256": rules.get("sha256"),
        "rules_match_computation": bool(rules.get("matches_computation")),
        "forms_version": package.get("version"),
        "forms_sha256": package.get("source_sha256"),
        "case_publication": publication,
        "personal_form_sha256": personal_sha,
        "explanations": explanations,
        "efi_rows": rows,
    }


def archival_json(worksheet: dict[str, Any]) -> tuple[bytes, str]:
    raw = (
        json.dumps(_archival(worksheet), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    return raw, hashlib.sha256(raw).hexdigest()


def archival_csv(worksheet: dict[str, Any]) -> tuple[bytes, str]:
    document = _archival(worksheet)
    buffer = io.StringIO()
    buffer.write(f"# {WORK_MARKER}\n")
    buffer.write("# status=research_only\n")
    buffer.write("# declarable=false\n")
    buffer.write("# transmission=false\n")
    buffer.write("# manual_only=true\n")
    buffer.write("# edi=false\n")
    buffer.write("# scraping=false\n")
    buffer.write(f"# vintage={document['vintage']}\n")
    buffer.write(f"# rules_version={document['rules_version']}\n")
    buffer.write(f"# rules_sha256={document['rules_sha256']}\n")
    buffer.write(f"# forms_version={document['forms_version']}\n")
    buffer.write(f"# forms_sha256={document['forms_sha256']}\n")
    buffer.write(f"# personal_form_sha256={document['personal_form_sha256']}\n")
    buffer.write("# montants en euros, point décimal ; séparateur ;\n")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(["formulaire", "case", "statut_case", "libelle", "montant", "regle", "source"])
    for row in document["rows"]:
        writer.writerow(
            [
                row["form"],
                row["case"] or "",
                row["case_status"],
                row["label"],
                row["amount"],
                " ".join(row["rules"]),
                row["source_url"] or "",
            ]
        )
    raw = buffer.getvalue().encode()
    return raw, hashlib.sha256(raw).hexdigest()


def load_personal_form(vintage: str) -> dict[str, Any]:
    path = PROJECT_ROOT / "fiscal" / vintage / "forms" / "2042-c-pro.json"
    if not path.is_file():
        return {
            "form": "2042-C-PRO",
            "project_vintage": vintage,
            "verification": "case_not_verified",
            "declarable": False,
            "status": "research_only",
            "lines": [],
            "prior_deficit_cases": {},
            "blocked": [],
            "unfilled": [],
            "block_reason": "Aucun registre 2042-C-PRO pour ce millésime.",
            "source": None,
        }
    parsed = json.loads(path.read_text(encoding="utf-8"))
    document = cast(dict[str, Any], parsed if isinstance(parsed, dict) else {})
    if document.get("declarable") is True or document.get("status") != "research_only":
        return {
            **document,
            "verification": "case_not_verified",
            "lines": [],
            "prior_deficit_cases": {},
            "block_reason": "Registre 2042-C-PRO inutilisable : un millésime reste en recherche.",
        }
    if document.get("project_vintage") != vintage:
        document["verification"] = "case_not_verified"
        document["lines"] = []
        document["prior_deficit_cases"] = {}
    return document


def prior_case(form: dict[str, Any], origin_year: int) -> str | None:
    """Official prior-deficit box, or None when this vintage does not publish one."""
    if form.get("verification") != "verified":
        return None
    cases = form.get("prior_deficit_cases")
    if not isinstance(cases, dict):
        return None
    value = cases.get(str(origin_year))
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def describe_formula(formula: object) -> str:
    if not isinstance(formula, dict):
        return "Reprise du résultat fiscal et du ledger, hors centralisation."
    op = formula.get("op")
    if op == "named":
        key = str(formula.get("key") or "")
        return _NAMED.get(key, f"agrégat {key}")
    if op == "nonneg":
        return f"partie positive ({describe_formula(formula.get('term'))})"
    if op == "absneg":
        return f"partie négative, sans signe ({describe_formula(formula.get('term'))})"
    if op == "add":
        terms = formula.get("terms")
        if not isinstance(terms, list):
            return "somme"
        return " + ".join(describe_formula(term) for term in terms)
    if op == "subtract":
        return f"{describe_formula(formula.get('left'))} − {describe_formula(formula.get('right'))}"
    if op == "tax_result":
        return "résultat fiscal du moteur"
    return "Reprise du résultat fiscal et du ledger, hors centralisation."


def _result_lines(
    form: dict[str, Any],
    benefit: int,
    deficit: int,
    result: int,
    *,
    verified: bool,
    source: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not verified:
        reason = str(form.get("block_reason") or "Case non vérifiée pour ce millésime.")
        return [
            _blocked_line(
                "benefit", "Bénéfice ou résultat nul de l’exercice", benefit, result >= 0, reason
            ),
            _blocked_line(
                "deficit", "Déficit de l’exercice, sans signe", deficit, result < 0, reason
            ),
        ]
    lines = []
    for spec in form.get("lines") or []:
        if not isinstance(spec, dict):
            continue
        role = spec.get("role")
        if role == "benefit":
            amount, served = benefit, result >= 0
        elif role == "deficit":
            amount, served = deficit, result < 0
        else:
            continue
        case = spec.get("case") if spec.get("verification") == "verified" else None
        lines.append(
            {
                "code": spec.get("code") or role,
                "case": case if isinstance(case, str) else None,
                "case_declarant_2": spec.get("case_declarant_2"),
                "case_dependant": spec.get("case_dependant"),
                "case_status": "verified" if isinstance(case, str) else "blocked",
                "served": served,
                "label": spec.get("label") or "",
                "amount": money(amount),
                "source_url": (source or {}).get("pdf_url"),
                "source_label": (source or {}).get("title"),
                "block_reason": None,
            }
        )
    return lines


def _blocked_line(code: str, label: str, amount: int, served: bool, reason: str) -> dict[str, Any]:
    return {
        "code": code,
        "case": None,
        "case_declarant_2": None,
        "case_dependant": None,
        "case_status": "blocked",
        "served": served,
        "label": label,
        "amount": money(amount),
        "source_url": None,
        "source_label": None,
        "block_reason": reason,
    }


def _deficit_rows(
    session: Session,
    year: FiscalYear,
    fiscal: dict[str, Any],
    form: dict[str, Any],
    *,
    verified: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    uses = {
        int(item["origin_year"]): item
        for item in ((fiscal.get("details") or {}).get("prior_carry_forward_use") or {}).get(
            "tax_loss"
        )
        or []
        if isinstance(item, dict) and "origin_year" in item
    }
    prior: list[dict[str, Any]] = []
    usage: list[dict[str, Any]] = []
    for stock in _prior_remaining(session, year, "tax_loss"):
        origin = int(stock["origin_year"])
        case = prior_case(form, origin) if verified else None
        use = uses.get(origin)
        used = str(use["used"]) if use else "0.00"
        remaining_after = str(use["remaining_after"]) if use else money(int(stock["remaining"]))
        status = "verified" if case else "blocked"
        reason = None if case else _prior_block_reason(form, origin)
        prior.append(
            {
                "origin_year": origin,
                "case": case,
                "case_status": status,
                "amount": money(int(stock["remaining"])),
                "block_reason": reason,
            }
        )
        usage.append(
            {
                "origin_year": origin,
                "opening": money(int(stock["remaining"])),
                "used": used,
                "remaining_after": remaining_after,
                "case": case,
                "case_status": status,
                "register": "tax_loss",
            }
        )
    return prior, usage


def _prior_block_reason(form: dict[str, Any], origin_year: int) -> str:
    if form.get("verification") != "verified":
        return str(form.get("block_reason") or "Case de report non vérifiée pour ce millésime.")
    return (
        f"L’année {origin_year} n’a pas de case 5GA à 5GJ sur le formulaire archivé "
        f"({form.get('cerfa') or '2042-C-PRO'})."
    )


def _personal_note(form: dict[str, Any], verified: bool) -> str:
    if not verified:
        return str(form.get("block_reason") or "Cases 2042-C-PRO non vérifiées.")
    return (
        "Document de travail, à vérifier. Une seule ligne est servie : bénéfice ou 0 en 5NA, "
        "déficit en 5NY. Les colonnes du déclarant 2 et de la personne à charge ne sont pas "
        "remplies. Les cotisations sociales (5NM, 5WE) ne se cumulent pas avec 5NA ou 5NY. "
        "Les déficits antérieurs encore ouverts vont en 5GA (2015) à 5GJ (2024), d’après le "
        "registre, avant l’imputation estimée. Saisie manuelle uniquement."
    )


def _efi_row(
    field: dict[str, Any],
    *,
    publication: str,
    sources: dict[str, dict[str, Any]],
    rules: dict[str, Any],
) -> dict[str, Any]:
    form_ref = str(field.get("form_ref") or "")
    official = field.get("official_case")
    case = official if isinstance(official, str) and official else None
    if publication != "verified_from_archive":
        status = "blocked"
        published = None
        reason = (
            "Numéro non publié pour ce millésime. "
            "Les formulaires officiels correspondants ne sont pas archivés."
        )
    elif case is None:
        status = "unnumbered"
        published = None
        reason = None
    else:
        status = "verified"
        published = case
        reason = None
    source = _source_for_form(form_ref, sources) if status != "blocked" else None
    rule_ids = [item for item in field.get("rules") or [] if isinstance(item, str)]
    formula = field.get("expression")
    parsed: object = formula
    if isinstance(formula, str) and formula.startswith("{"):
        try:
            parsed = json.loads(formula)
        except json.JSONDecodeError:
            parsed = formula
    return {
        "code": field.get("code"),
        "form": form_ref,
        "case": published,
        "carryover_case": case if status == "blocked" else None,
        "case_status": status,
        "block_reason": reason,
        "label": field.get("label") or "",
        "amount": field.get("value"),
        "formula": describe_formula(parsed),
        "rules": [_rule_view(rules, rule_id) for rule_id in rule_ids],
        "source_label": None if source is None else source.get("title"),
        "source_url": None if source is None else source.get("pdf_url"),
        "entry_ids": [int(item) for item in field.get("entries") or [] if _is_int(item)],
        "accounts": [str(item) for item in field.get("accounts") or []],
    }


def _explanations(
    session: Session,
    year_id: int,
    inputs: dict[str, Any],
    rules: dict[str, Any],
) -> list[dict[str, Any]]:
    catalog = _entries_by_prefix(session, year_id)
    addition_accounts = {str(item) for item in inputs.get("addition_accounts") or []}
    rows = []
    for spec in _EXPLANATIONS:
        amount = inputs.get(spec["key"])
        if spec["code"] == "additions" and addition_accounts:
            entries = [
                brief
                for brief in catalog["all"]
                if addition_accounts.intersection(brief["accounts"])
            ]
        else:
            entries = _matching(catalog, spec["prefixes"])
        rows.append(
            {
                "code": spec["code"],
                "label": spec["label"],
                "amount": amount if isinstance(amount, str) else None,
                "formula": spec["formula"],
                "rules": [_rule_view(rules, rule_id) for rule_id in spec["rules"]],
                "entries": entries,
            }
        )
    return rows


def _matching(catalog: dict[str, Any], prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
    if not prefixes:
        return []
    seen: set[int] = set()
    rows: list[dict[str, Any]] = []
    for brief in catalog["all"]:
        if brief["id"] in seen:
            continue
        if any(account.startswith(prefixes) for account in brief["accounts"]):
            seen.add(brief["id"])
            rows.append(brief)
    return rows


def _entries_by_prefix(session: Session, year_id: int) -> dict[str, Any]:
    rows = session.scalars(
        select(AccountingEntry)
        .where(
            AccountingEntry.fiscal_year_id == year_id,
            AccountingEntry.status == "VALIDATED",
            AccountingEntry.source_type.notin_(("CENTRALIZATION", "APPROPRIATION")),
        )
        .order_by(AccountingEntry.id)
    )
    briefs = [_brief(entry) for entry in rows]
    return {"all": briefs}


def _briefs(session: Session, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    rows = session.scalars(select(AccountingEntry).where(AccountingEntry.id.in_(ids)))
    return {entry.id: _brief(entry) for entry in rows}


def _brief(entry: AccountingEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "accounting_date": entry.accounting_date.isoformat(),
        "journal_code": entry.journal_code,
        "piece_reference": entry.piece_reference,
        "label": entry.label,
        "accounts": sorted({line.account_number for line in entry.lines}),
    }


def _rules(vintage: str, stored_sha: object) -> dict[str, Any]:
    loaded = load_vintage(vintage)
    by_id = {
        str(rule["id"]): public_rule(rule)
        for rule in (*loaded["executable"], *loaded["scope_rules"], *loaded["blocked"])
    }
    digest = loaded.get("sha256")
    return {
        "version": loaded.get("version"),
        "sha256": digest,
        "by_id": by_id,
        "matches_computation": isinstance(stored_sha, str) and stored_sha == digest,
    }


def _rule_view(rules: dict[str, Any], rule_id: str) -> dict[str, Any]:
    found = rules.get("by_id", {}).get(rule_id)
    if isinstance(found, dict):
        return {
            "id": found.get("id"),
            "source": found.get("source"),
            "source_url": found.get("source_url"),
            "consulted_at": found.get("consulted_at"),
        }
    return {"id": rule_id, "source": None, "source_url": None, "consulted_at": None}


def _publication(vintage: str) -> str:
    path = PROJECT_ROOT / "fiscal" / vintage / "forms" / "2033.json"
    if not path.is_file():
        return "blocked"
    document = json.loads(path.read_text(encoding="utf-8"))
    value = document.get("case_publication")
    if value == "verified_from_archive":
        return "verified_from_archive"
    return "blocked"


def _manifest_sources(vintage: str) -> dict[str, dict[str, Any]]:
    path = PROJECT_ROOT / "fiscal" / vintage / "sources" / "manifest.json"
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item["id"]): item
        for item in document.get("documents") or []
        if isinstance(item, dict) and item.get("id")
    }


def _source_for_form(form_ref: str, sources: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if form_ref.startswith("2033"):
        return sources.get("2033-SD-LIASSE-2025")
    if form_ref.startswith("2031"):
        return sources.get("2031-SD-2025")
    return None


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _archival(worksheet: dict[str, Any]) -> dict[str, Any]:
    declaration = _mapping(worksheet.get("declaration"))
    personal = _mapping(worksheet.get("personal_return"))
    rows = []
    for row in declaration.get("efi_rows") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "form": row.get("form"),
                "case": row.get("case"),
                "case_status": row.get("case_status"),
                "label": row.get("label"),
                "amount": row.get("amount"),
                "formula": row.get("formula"),
                "rules": [
                    item.get("id") for item in row.get("rules") or [] if isinstance(item, dict)
                ],
                "source_url": row.get("source_url"),
                "entry_ids": row.get("entry_ids") or [],
            }
        )
    for line in personal.get("lines") or []:
        if isinstance(line, dict):
            rows.append(
                {
                    "form": "2042-C-PRO",
                    "case": line.get("case"),
                    "case_status": line.get("case_status"),
                    "label": line.get("label"),
                    "amount": line.get("amount"),
                    "formula": "résultat fiscal avant imputation des déficits antérieurs",
                    "rules": [TAX_LOSS_RULE_ID, DEPRECIATION_RULE_ID],
                    "source_url": line.get("source_url"),
                    "entry_ids": [],
                }
            )
    return {
        "marker": WORK_MARKER,
        "status": "research_only",
        "declarable": False,
        "transmission": False,
        "manual_only": True,
        "edi": False,
        "scraping": False,
        "vintage": declaration.get("vintage") or worksheet.get("liasse", {}).get("vintage"),
        "rules_version": declaration.get("rules_version"),
        "rules_sha256": declaration.get("rules_sha256"),
        "rules_file_version": declaration.get("rules_file_version"),
        "rules_file_sha256": declaration.get("rules_file_sha256"),
        "forms_version": declaration.get("forms_version"),
        "forms_sha256": declaration.get("forms_sha256"),
        "personal_form_sha256": declaration.get("personal_form_sha256"),
        "year": worksheet.get("year"),
        "fiscal_year_id": worksheet.get("fiscal_year_id"),
        "rows": rows,
        "prior_deficits": personal.get("prior_deficits") or [],
        "deficit_usage": personal.get("deficit_usage") or [],
        "blocked_cases": personal.get("blocked_cases") or [],
        "explanations": [
            {
                "code": item.get("code"),
                "label": item.get("label"),
                "amount": item.get("amount"),
                "formula": item.get("formula"),
                "rules": [
                    {"id": rule.get("id"), "source_url": rule.get("source_url")}
                    for rule in item.get("rules") or []
                    if isinstance(rule, dict)
                ],
                "entry_ids": [entry.get("id") for entry in item.get("entries") or []],
            }
            for item in declaration.get("explanations") or []
            if isinstance(item, dict)
        ],
    }


def _fiscal_before(fiscal: dict[str, Any]) -> int:
    details = fiscal.get("details") or {}
    raw = details.get("fiscal_result_before_prior_losses", fiscal.get("fiscal_result", "0"))
    return to_cents(Decimal(str(raw)))


def _public_source(source: dict[str, Any] | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "id": source.get("id"),
        "title": source.get("title"),
        "pdf_url": source.get("pdf_url"),
        "page_url": source.get("page_url"),
        "notice_url": source.get("notice_url"),
        "cerfa": source.get("cerfa"),
        "sha256": source.get("sha256"),
        "consulted_at": source.get("consulted_at"),
    }


def _ids_in(rows: list[dict[str, Any]]) -> list[int]:
    found: list[int] = []
    for row in rows:
        found.extend(row["entry_ids"])
    return list(dict.fromkeys(found))


def _file_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
