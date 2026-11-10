"""Cases 2025 à partir du ledger. Le mapping YAML/JSON n'est pas modifié."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.domain.filing.liasse import (
    _AMORT,
    _GROSS,
    _amort_key,
    _bilan,
    _field,
    _gross_key,
    _result_2031,
    _valeur_ajoutee,
)
from app.domain.filing.mappings import _eval, _named
from app.domain.fiscal.engine import Movement, Stock, apply_lmnp

from lmnp_core.depreciation import Plan, dotation
from lmnp_core.dossier import Dossier
from lmnp_core.money import cents_to_text, text_to_cents
from lmnp_core.posting import Ecriture, soldes

_PRIOR = {
    "2015": "5GA",
    "2016": "5GB",
    "2017": "5GC",
    "2018": "5GD",
    "2019": "5GE",
    "2020": "5GF",
    "2021": "5GG",
    "2022": "5GH",
    "2023": "5GI",
    "2024": "5GJ",
}


def registre_charge(millesime: str) -> bool:
    path = PROJECT_ROOT / "fiscal" / millesime / "forms" / "cases.yaml"
    document = _json_or_yaml(path)
    return isinstance(document, dict) and document.get("vintage") == millesime


def calculer_fiscal(
    *,
    annee: int,
    produits: int,
    autres_charges: int,
    dotation_annee: int,
    amortissements: list[Stock],
    deficits: list[Stock],
) -> tuple[Any, list[Stock], list[Stock]]:
    split = apply_lmnp(
        year=annee,
        income=produits,
        other_charges=autres_charges,
        depreciation=dotation_annee,
        additions=0,
        depreciation_stocks=amortissements,
        tax_loss_stocks=deficits,
    )
    return (
        split,
        _apres(amortissements, split.depreciation_uses, split.unused_depreciation, annee),
        _apres_deficit(deficits, split, annee),
    )


def cases_de(
    dossier: Dossier,
    exercice_index: int,
    entries: list[Ecriture],
    *,
    produits: int,
    charges: dict[str, int],
    dotation_annee: int,
    split: Any,
    plans: tuple[Plan, ...],
    dotations_anterieures: dict[str, int],
    deficits: list[Stock],
) -> dict[str, int]:
    exercice = dossier.exercices[exercice_index]
    if str(exercice.fin.year) != dossier.millesime:
        return {}
    nets = soldes(entries)
    fields = _bilan_cases(nets, split.accounting_result)
    fields.update(_cr_cases(entries, charges, produits, split))
    fields.update(
        _immo_cases(
            plans,
            exercice.debut,
            exercice.fin,
            premier=exercice_index == 0,
            dotations_anterieures=dotations_anterieures,
            terrain=dossier.terrain,
            terrain_date=plans[0].mise_en_service,
        )
    )
    fields.update(_va_cases(charges, produits))
    fields.update(_f2031(split))
    fields.update(_f2042(dossier, split, exercice.fin.year, deficits))
    _ = dotation_annee
    return fields


def _bilan_cases(nets: dict[str, int], resultat: int) -> dict[str, int]:
    assets: list[dict[str, str]] = []
    equity: list[dict[str, str]] = []
    liabilities: list[dict[str, str]] = []
    income: list[dict[str, str]] = []
    expenses: list[dict[str, str]] = []
    for compte, net in sorted(nets.items()):
        if compte[0] == "6":
            expenses.append({"account_number": compte, "amount": cents_to_text(net)})
        elif compte[0] == "7":
            income.append({"account_number": compte, "amount": cents_to_text(-net)})
        elif compte.startswith("16"):
            liabilities.append({"account_number": compte, "amount": cents_to_text(-net)})
        elif compte.startswith("1"):
            equity.append({"account_number": compte, "amount": cents_to_text(-net)})
        elif compte.startswith(("2", "3", "5")):
            assets.append({"account_number": compte, "amount": cents_to_text(net)})
    report = {
        "balance_sheet": {
            "assets": assets,
            "equity": equity,
            "liabilities": liabilities,
            "current_result": cents_to_text(resultat),
        },
        "income_statement": {"income": income, "expenses": expenses},
    }
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    built = _bilan(report, errors, warnings, resultat)
    if any(item["code"] == "BILAN_2033A" for item in errors):
        raise RuntimeError("Le 2033-A construit par le noyau ne s'équilibre pas.")
    return _index(built)


def _cr_cases(
    entries: list[Ecriture],
    charges: dict[str, int],
    produits: int,
    split: Any,
) -> dict[str, int]:
    produits_map = {"706000": produits}
    entry_ids = _entry_ids(entries)
    fiscal = {
        "accounting_result": cents_to_text(split.accounting_result),
        "fiscal_result": cents_to_text(split.fiscal_result),
        "unused_depreciation": cents_to_text(split.unused_depreciation),
        "non_deductible": cents_to_text(0),
        "details": {
            "fiscal_result_before_prior_losses": cents_to_text(split.fiscal_before_losses),
            "prior_depreciation_used": cents_to_text(split.prior_depreciation_used),
        },
    }
    named = _named(charges, produits_map, entry_ids, fiscal)
    context = {
        "balances": {**charges, **produits_map},
        "entries": entry_ids,
        "tax_result": split.fiscal_result,
        "named": named,
    }
    path = PROJECT_ROOT / "fiscal" / "2025" / "forms" / "2033.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    errors: list[dict[str, str]] = []
    out: dict[str, int] = {}
    for field in document["fields"]:
        value, _accounts, _ids = _eval(field["formula"], context, errors, field["code"])
        form = str(field.get("form_ref") or "2033-B-SD")
        case = field.get("official_case") or field["code"]
        out[f"{form}/{case}"] = value
    if errors:
        raise RuntimeError("Le mapping 2033-B a refusé une formule.")
    return out


def _immo_cases(
    plans: tuple[Plan, ...],
    debut: date,
    fin: date,
    *,
    premier: bool,
    dotations_anterieures: dict[str, int],
    terrain: int = 0,
    terrain_date: date | None = None,
) -> dict[str, int]:
    gross = {key: [0, 0, 0] for key in _GROSS}
    amort = {key: [0, 0, 0] for key in _AMORT}
    if terrain and terrain_date is not None and terrain_date <= fin:
        slot = 0 if terrain_date < debut and not premier else 1
        gross["terrains"][slot] += terrain
    for plan in plans:
        if plan.mise_en_service > fin:
            continue
        slot = 0 if plan.mise_en_service < debut and not premier else 1
        gross[_gross_key(plan.compte)][slot] += plan.base
        key = _amort_key(plan.compte_amortissement)
        amort[key][0] += dotations_anterieures.get(plan.cle, 0)
        amort[key][1] += dotation(plan, debut, fin)
    fields: list[dict[str, Any]] = []
    totals = [0, 0, 0]
    names = {
        "terrains": ("TERRAINS_BRUT_DEBUT", "TERRAINS_BRUT_AUGMENTATION", "TERRAINS_BRUT_FIN"),
        "constructions": (
            "CONSTRUCTIONS_BRUT_DEBUT",
            "CONSTRUCTIONS_BRUT_AUGMENTATION",
            "CONSTRUCTIONS_BRUT_FIN",
        ),
        "agencements": (
            "AGENCEMENTS_BRUT_DEBUT",
            "AGENCEMENTS_BRUT_AUGMENTATION",
            "AGENCEMENTS_BRUT_FIN",
        ),
        "autres": (
            "AUTRES_CORP_BRUT_DEBUT",
            "AUTRES_CORP_BRUT_AUGMENTATION",
            "AUTRES_CORP_BRUT_FIN",
        ),
    }
    for key, (start, increase, _down, end, label) in _GROSS.items():
        opening, added, removed = gross[key]
        closing = opening + added - removed
        totals[0] += opening
        totals[1] += added
        totals[2] += closing
        keep = key in {"terrains", "constructions", "autres"}
        for code, case, amount in (
            (names[key][0], start, opening),
            (names[key][1], increase, added),
            (names[key][2], end, closing),
        ):
            if amount or keep:
                fields.append(
                    _field(
                        code=code,
                        form_ref="2033-C-SD",
                        official_case=case,
                        label=label,
                        value=amount,
                    )
                )
    fields.extend(
        [
            _field(
                code="IMMO_BRUT_DEBUT",
                form_ref="2033-C-SD",
                official_case="490",
                label="Total brut début",
                value=totals[0],
            ),
            _field(
                code="IMMO_BRUT_AUGMENTATION",
                form_ref="2033-C-SD",
                official_case="492",
                label="Total augmentations",
                value=totals[1],
            ),
            _field(
                code="IMMO_BRUT_FIN",
                form_ref="2033-C-SD",
                official_case="496",
                label="Total brut fin",
                value=totals[2],
            ),
        ]
    )
    amort_names = {
        "constructions": (
            "CONSTRUCTIONS_AMORT_DEBUT",
            "CONSTRUCTIONS_AMORT_DOTATION",
            "CONSTRUCTIONS_AMORT_FIN",
        ),
        "agencements": (
            "AGENCEMENTS_AMORT_DEBUT",
            "AGENCEMENTS_AMORT_DOTATION",
            "AGENCEMENTS_AMORT_FIN",
        ),
        "autres": (
            "AUTRES_CORP_AMORT_DEBUT",
            "AUTRES_CORP_AMORT_DOTATION",
            "AUTRES_CORP_AMORT_FIN",
        ),
    }
    amort_totals = [0, 0, 0]
    for key, (start, dotation_case, _down, end, label) in _AMORT.items():
        opening, current, removed = amort[key]
        closing = opening + current - removed
        amort_totals[0] += opening
        amort_totals[1] += current
        amort_totals[2] += closing
        if key == "terrains":
            continue
        keep = key in {"constructions", "autres"}
        for code, case, amount in (
            (amort_names[key][0], start, opening),
            (amort_names[key][1], dotation_case, current),
            (amort_names[key][2], end, closing),
        ):
            if amount or keep:
                fields.append(
                    _field(
                        code=code,
                        form_ref="2033-C-SD",
                        official_case=case,
                        label=label,
                        value=amount,
                    )
                )
    fields.extend(
        [
            _field(
                code="IMMO_AMORT_DEBUT",
                form_ref="2033-C-SD",
                official_case="570",
                label="Total amortissements début",
                value=amort_totals[0],
            ),
            _field(
                code="IMMO_AMORT_DOTATION",
                form_ref="2033-C-SD",
                official_case="572",
                label="Total dotations",
                value=amort_totals[1],
            ),
            _field(
                code="IMMO_AMORT_FIN",
                form_ref="2033-C-SD",
                official_case="576",
                label="Total amortissements fin",
                value=amort_totals[2],
            ),
        ]
    )
    return _index(fields)


def _va_cases(charges: dict[str, int], produits: int) -> dict[str, int]:
    activity = {
        "income": [{"account_number": "706000", "amount": cents_to_text(produits)}],
        "expenses": [
            {"account_number": compte, "amount": cents_to_text(montant)}
            for compte, montant in sorted(charges.items())
        ],
    }
    warnings: list[dict[str, str]] = []
    return _index(_valeur_ajoutee(activity, warnings))


def _f2031(split: Any) -> dict[str, int]:
    fiscal = {
        "fiscal_result": cents_to_text(split.fiscal_result),
        "details": {
            "fiscal_result_before_prior_losses": cents_to_text(split.fiscal_before_losses)
        },
    }
    return _index(_result_2031(fiscal))


def _f2042(
    dossier: Dossier, split: Any, annee: int, deficits: list[Stock]
) -> dict[str, int]:
    if str(annee) != dossier.millesime:
        return {}
    benefit = max(0, split.fiscal_before_losses)
    deficit = max(0, -split.fiscal_before_losses)
    out = {"2042-C-PRO/5NA": benefit if benefit or not deficit else 0, "2042-C-PRO/5NY": deficit}
    if benefit == 0 and deficit == 0:
        out["2042-C-PRO/5NA"] = 0
    for stock in deficits:
        case = _PRIOR.get(str(stock.origin_year))
        opening = stock.remaining_before()
        if case and opening:
            out[f"2042-C-PRO/{case}"] = opening
    return out


def _entry_ids(entries: list[Ecriture]) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for entry in entries:
        if entry.journal == "AN":
            continue
        for line in entry.lignes:
            found.setdefault(line.compte, [])
            if entry.numero not in found[line.compte]:
                found[line.compte].append(entry.numero)
    return found


def _index(fields: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for field in fields:
        form = str(field.get("form_ref") or "")
        official = field.get("official_case")
        code = official if isinstance(official, str) and official else str(field.get("code"))
        out[f"{form}/{code}"] = text_to_cents(str(field["value"]))
    return out


def _apres(
    stocks: list[Stock], uses: tuple[Movement, ...], created: int, annee: int
) -> list[Stock]:
    used = {move.origin_year: move.amount for move in uses}
    suivant: list[Stock] = []
    for stock in stocks:
        take = used.get(stock.origin_year, 0)
        left = stock.remaining_before() - take
        if left > 0:
            suivant.append(
                Stock(stock.origin_year, stock.origin_year, left, 0, 0)
            )
    if created:
        suivant.append(Stock(annee, annee, created, 0, 0))
    return suivant


def _apres_deficit(stocks: list[Stock], split: Any, annee: int) -> list[Stock]:
    used = {move.origin_year: move.amount for move in split.tax_loss_uses}
    expired = {move.origin_year for move in split.tax_loss_expiries}
    suivant: list[Stock] = []
    for stock in stocks:
        if stock.origin_year in expired:
            continue
        left = stock.remaining_before() - used.get(stock.origin_year, 0)
        if left > 0:
            suivant.append(Stock(stock.origin_year, stock.origin_year, left, 0, 0))
    if split.tax_loss:
        suivant.append(Stock(annee, annee, split.tax_loss, 0, 0))
    return suivant


def _json_or_yaml(path: Path) -> object:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("{"):
        return json.loads(text)
    from lmnp_core.yamlio import loads

    return loads(text)
