"""Annex lines of the LMNP copy liasse. Case numbers come from the verified 2025 registry."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.models import AccountingEntry, Asset, FiscalYear, Property
from app.models.assets import AssetComponent, DepreciationPeriod, DepreciationSchedule
from app.models.foundation import RentalActivity
from app.models.operations import BusinessOperation
from app.services.fiscal import _prior_remaining
from app.services.ledger import money
from app.services.statements import statements


def _amount(value: object) -> int:
    return to_cents(value if isinstance(value, Decimal) else Decimal(str(value)))


def extend_package(
    session: Session, year: FiscalYear, fiscal: dict[str, Any], package: dict[str, Any]
) -> None:
    fields, errors, warnings = _sheets(session, year, fiscal)
    package["fields"].extend(fields)
    package["errors"].extend(errors)
    package["warnings"].extend(warnings)
    package["by_property"] = _segments(session, year)
    activity = session.get(RentalActivity, 1)
    note = (
        "Exercice 2026 : il n’y a pas de liasse 2025. "
        "Les numéros sont ceux du dernier formulaire lu. "
        "Vérifiez-les sur la déclaration que vous déposerez en 2027."
        if year.fiscal_vintage == "2026"
        else "Cases lues sur les PDF 2031 et 2033 archivés."
    )
    package["copy"] = {
        "transmission": False,
        "portal": "https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi",
        "vintage_note": note,
        "declarant": {
            "name": activity.activity_name if activity else "",
            "siren": activity.siren if activity else None,
            "siret": activity.siret if activity else None,
        },
    }
    _detail_warning(package)


def _sheets(
    session: Session, year: FiscalYear, fiscal: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    report = statements(session, year.id)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    fields = [
        *_bilan(report, errors, warnings),
        *_immobilisations(session, year, report, errors, warnings),
        *_deficits(session, year, fiscal),
        *_valeur_ajoutee(report, warnings),
        *_result_2031(fiscal),
    ]
    return fields, errors, warnings


def _field(
    *,
    code: str,
    form_ref: str,
    official_case: str | None,
    label: str,
    value: int,
) -> dict[str, Any]:
    return {
        "code": code,
        "form_ref": form_ref,
        "official_case": official_case,
        "label": label,
        "required": True,
        "expression": "registre",
        "rules": [],
        "accounts": [],
        "entries": [],
        "value": money(value),
        "status": "research_only",
    }


_GROSS = {
    "terrains": ("420", "422", "424", "426", "Terrains"),
    "constructions": ("430", "432", "434", "436", "Constructions"),
    "agencements": ("450", "452", "454", "456", "Installations générales, agencements"),
    "autres": ("470", "472", "474", "476", "Autres immobilisations corporelles"),
}
_AMORT = {
    "terrains": ("510", "512", "514", "516", "Terrains"),
    "constructions": ("520", "522", "524", "526", "Constructions"),
    "agencements": ("540", "542", "544", "546", "Agencements"),
    "autres": ("560", "562", "564", "566", "Autres immobilisations corporelles"),
}
_CVAE_THRESHOLD = 15_250_000


def _gross_key(account: str) -> str:
    if account.startswith("211"):
        return "terrains"
    if account.startswith(("2135", "2181")):
        return "agencements"
    if account.startswith(("212", "213")):
        return "constructions"
    return "autres"


def _amort_key(account: str) -> str:
    if account.startswith("2811"):
        return "terrains"
    if account.startswith(("28135", "28181")):
        return "agencements"
    if account.startswith(("2812", "2813")):
        return "constructions"
    return "autres"


def _immobilisations(
    session: Session,
    year: FiscalYear,
    report: dict[str, Any],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    gross = {key: [0, 0, 0] for key in _GROSS}
    amort = {key: [0, 0, 0] for key in _AMORT}
    for asset in session.scalars(select(Asset)):
        if asset.disposed_at is not None:
            errors.append(
                {
                    "code": "CESSION_HORS_MVP",
                    "message": (
                        "Une immobilisation est sortie. Les plus-values restent hors liasse."
                    ),
                }
            )
            continue
        components = list(
            session.scalars(select(AssetComponent).where(AssetComponent.asset_id == asset.id))
        )
        pieces = (
            [(item.asset_account, item.value, item.service_start_date) for item in components]
            if components
            else [(asset.asset_account, asset.acquisition_value, asset.acquisition_date)]
        )
        for account, gross_value, acquired in pieces:
            slot = 0 if acquired < year.start_date else 1 if acquired <= year.end_date else None
            if slot is not None:
                gross[_gross_key(account)][slot] += to_cents(gross_value)
    for period in session.scalars(
        select(DepreciationPeriod).where(DepreciationPeriod.status == "POSTED")
    ):
        schedule = session.get(DepreciationSchedule, period.schedule_id)
        fiscal_year = session.get(FiscalYear, period.fiscal_year_id)
        if schedule is None or fiscal_year is None:
            continue
        key = _amort_key(schedule.depreciation_account)
        if fiscal_year.end_date < year.start_date:
            amort[key][0] += to_cents(period.amount)
        elif period.fiscal_year_id == year.id:
            amort[key][1] += to_cents(period.amount)
    fields: list[dict[str, Any]] = []
    totals = [0, 0, 0]
    for key, (start, increase, _decrease, end, label) in _GROSS.items():
        opening, added, removed = gross[key]
        closing = opening + added - removed
        totals[0] += opening
        totals[1] += added
        totals[2] += closing
        codes = {
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
        }[key]
        keep = key in {"terrains", "constructions", "autres"}
        for code, case, amount, when in (
            (codes[0], start, opening, "début"),
            (codes[1], increase, added, "augmentations"),
            (codes[2], end, closing, "fin"),
        ):
            if amount or keep:
                fields.append(
                    _field(
                        code=code,
                        form_ref="2033-C-SD",
                        official_case=case,
                        label=f"{label} — valeur brute, {when}",
                        value=amount,
                    )
                )
    fields.extend(
        [
            _field(
                code="IMMO_BRUT_DEBUT",
                form_ref="2033-C-SD",
                official_case="490",
                label="Total des valeurs brutes au début de l’exercice",
                value=totals[0],
            ),
            _field(
                code="IMMO_BRUT_AUGMENTATION",
                form_ref="2033-C-SD",
                official_case="492",
                label="Total des augmentations de valeurs brutes",
                value=totals[1],
            ),
            _field(
                code="IMMO_BRUT_FIN",
                form_ref="2033-C-SD",
                official_case="496",
                label="Total des valeurs brutes à la fin de l’exercice",
                value=totals[2],
            ),
        ]
    )
    amort_totals = [0, 0, 0]
    for key, (start, dotation_case, _down, end, label) in _AMORT.items():
        opening, dotation, removed = amort[key]
        closing = opening + dotation - removed
        amort_totals[0] += opening
        amort_totals[1] += dotation
        amort_totals[2] += closing
        if key == "terrains":
            continue
        names = {
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
        }[key]
        keep = key in {"constructions", "autres"}
        for code, case, amount, when in (
            (names[0], start, opening, "début"),
            (names[1], dotation_case, dotation, "dotations"),
            (names[2], end, closing, "fin"),
        ):
            if amount or keep:
                fields.append(
                    _field(
                        code=code,
                        form_ref="2033-C-SD",
                        official_case=case,
                        label=f"{label} — amortissements, {when}",
                        value=amount,
                    )
                )
    fields.extend(
        [
            _field(
                code="IMMO_AMORT_DEBUT",
                form_ref="2033-C-SD",
                official_case="570",
                label="Total des amortissements au début de l’exercice",
                value=amort_totals[0],
            ),
            _field(
                code="IMMO_AMORT_DOTATION",
                form_ref="2033-C-SD",
                official_case="572",
                label="Total des dotations aux amortissements de l’exercice",
                value=amort_totals[1],
            ),
            _field(
                code="IMMO_AMORT_FIN",
                form_ref="2033-C-SD",
                official_case="576",
                label="Total des amortissements à la fin de l’exercice",
                value=amort_totals[2],
            ),
        ]
    )
    ledger_gross, ledger_amort, ledger_dotation = _ledger_immobilisations(report)
    register_end = (totals[2], amort_totals[2], amort_totals[1])
    if (ledger_gross, ledger_amort, ledger_dotation) != register_end:
        warnings.append(
            {
                "code": "IMMOBILISATIONS_ECART",
                "message": (
                    "Le registre des immobilisations ne retrouve pas les comptes 21, 28 et 681. "
                    "La feuille 2033-C n’est pas recopiable tant que cet écart demeure."
                ),
            }
        )
    return fields


def _ledger_immobilisations(report: dict[str, Any]) -> tuple[int, int, int]:
    gross = amort = dotation = 0
    for row in report["balance_sheet"]["assets"]:
        number = row["account_number"]
        amount = _amount(row["amount"])
        if number.startswith(("20", "21", "22", "23", "26", "27")) and not number.startswith(
            ("28", "29")
        ):
            gross += amount
        elif number.startswith(("28", "29")):
            amort += -amount
    for row in report["income_statement"]["expenses"]:
        if row["account_number"].startswith("681"):
            dotation += _amount(row["amount"])
    return gross, amort, dotation


def _bilan(
    report: dict[str, Any],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    corp_brut = corp_amort = other_fixed = other_amort = 0
    clients = bank = other_current = 0
    for number, amount in _signed(report["balance_sheet"]["assets"]):
        if number.startswith(("675", "775", "445")):
            errors.append(_out_of_scope(number))
        elif number.startswith(("28", "29")) and number.startswith(("280", "290", "296", "297")):
            other_amort += -amount
        elif number.startswith(("28", "29")):
            corp_amort += -amount
        elif number.startswith(("21", "22", "23")):
            corp_brut += amount
        elif number.startswith(("20", "26", "27")):
            other_fixed += amount
        elif number.startswith("41"):
            clients += amount
        elif number.startswith(("51", "53", "54", "58")):
            bank += amount
        else:
            other_current += amount
    capital = retained = result_equity = other_equity = 0
    for number, amount in _signed(report["balance_sheet"]["equity"]):
        if number.startswith(("101", "108")):
            capital += amount
        elif number.startswith("11"):
            retained += amount
        elif number.startswith(("120", "129")):
            result_equity += amount
        else:
            other_equity += amount
    loans = suppliers = tax_debts = provisions = other_debts = 0
    for number, amount in _signed(report["balance_sheet"]["liabilities"]):
        if number.startswith(("675", "775", "445")):
            errors.append(_out_of_scope(number))
        elif number.startswith("16"):
            loans += amount
        elif number.startswith(("401", "403", "408")):
            suppliers += amount
        elif number.startswith(("42", "43", "44")):
            tax_debts += amount
        elif number.startswith("15"):
            provisions += amount
        else:
            other_debts += amount
    for number, amount in _signed(report["income_statement"]["income"]):
        if number.startswith(("675", "775", "445")) and amount:
            errors.append(_out_of_scope(number))
    for number, amount in _signed(report["income_statement"]["expenses"]):
        if number.startswith(("675", "775", "445")) and amount:
            errors.append(_out_of_scope(number))
    result = _amount(report["income_statement"]["result"])
    if result and result_equity:
        warnings.append(
            {
                "code": "RESULTAT_MIXTE",
                "message": (
                    "Le résultat de l’exercice figure à la fois dans les comptes 6/7 "
                    "et dans un compte 120 ou 129."
                ),
            }
        )
    if other_fixed or other_amort or other_current or other_equity:
        warnings.append(
            {
                "code": "CLASSEMENT_INCOMPLET",
                "message": (
                    "Des comptes de bilan ne sont pas détaillés sur les cases LMNP du 2033-A. "
                    "La liasse n’est pas recopiable tant qu’ils sont présents."
                ),
            }
        )
    current = clients + bank + other_current
    fixed_brut = corp_brut + other_fixed
    fixed_net = fixed_brut - corp_amort - other_amort
    assets_net = fixed_net + current
    exercise_result = result + result_equity
    equity_total = capital + retained + other_equity + exercise_result
    debt_total = loans + suppliers + tax_debts + other_debts
    liabilities_total = equity_total + provisions + debt_total
    if assets_net != liabilities_total:
        errors.append(
            {
                "code": "BILAN_2033A",
                "message": "Le total actif net du 2033-A ne retrouve pas le total passif.",
            }
        )
    rows = [
        ("CORPORELLES_BRUT", "028", "Immobilisations corporelles — brut", corp_brut),
        ("CORPORELLES_NET", "030", "Immobilisations corporelles — net", corp_brut - corp_amort),
        ("ACTIF_IMMOBILISE_BRUT", "044", "Total I actif — brut", fixed_brut),
        ("ACTIF_IMMOBILISE_NET", "048", "Total I actif — net", fixed_net),
        ("CLIENTS_BRUT", "068", "Clients et comptes rattachés — brut", clients),
        ("CLIENTS_NET", "070", "Clients et comptes rattachés — net", clients),
        ("DISPONIBILITES_BRUT", "084", "Disponibilités — brut", bank),
        ("DISPONIBILITES_NET", "086", "Disponibilités — net", bank),
        ("ACTIF_CIRCULANT_BRUT", "096", "Total II actif — brut", current),
        ("ACTIF_CIRCULANT_NET", "098", "Total II actif — net", current),
        ("ACTIF_TOTAL_BRUT", "110", "Total général actif — brut", fixed_brut + current),
        ("ACTIF_TOTAL_NET", "112", "Total général actif — net", assets_net),
        ("CAPITAL", "120", "Capital individuel — compte de l’exploitant", capital),
        ("REPORT_A_NOUVEAU", "134", "Report à nouveau", retained),
        ("RESULTAT_EXERCICE", "136", "Résultat de l’exercice", exercise_result),
        ("CAPITAUX_TOTAL", "142", "Total I passif — capitaux propres", equity_total),
        ("PROVISIONS", "154", "Provisions pour risques et charges", provisions),
        ("EMPRUNTS", "156", "Emprunts et dettes assimilées", loans),
        ("FOURNISSEURS", "166", "Fournisseurs et comptes rattachés", suppliers),
        ("DETTES_FISCALES", "172", "Dettes fiscales et sociales", tax_debts),
        ("AUTRES_DETTES", "175", "Autres dettes", other_debts),
        ("DETTES_TOTAL", "176", "Total III passif — dettes", debt_total),
        ("PASSIF_TOTAL", "180", "Total général passif", liabilities_total),
    ]
    return [
        _field(code=code, form_ref="2033-A-SD", official_case=case, label=label, value=value)
        for code, case, label, value in rows
        if value
        or code
        in {
            "ACTIF_TOTAL_NET",
            "PASSIF_TOTAL",
            "RESULTAT_EXERCICE",
            "CAPITAUX_TOTAL",
        }
    ]


def _valeur_ajoutee(report: dict[str, Any], warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    income = report["income_statement"]["income"]
    expenses = report["income_statement"]["expenses"]
    services = _prefixed(income, ("70",))
    purchases = _prefixed(expenses, ("60",), skip=("603",))
    external = _prefixed(expenses, ("61", "62"), skip=("612", "613"))
    rents = _prefixed(expenses, ("612", "613"))
    depreciation = _prefixed(expenses, ("681",))
    payroll = _prefixed(expenses, ("64",))
    extra_income = _prefixed(income, ("72", "74", "75", "79"))
    if payroll:
        warnings.append(
            {
                "code": "EFFECTIFS",
                "message": (
                    "Des charges de personnel existent. L’effectif du 2033-E n’est pas calculé."
                ),
            }
        )
    if extra_income:
        warnings.append(
            {
                "code": "CLASSEMENT_INCOMPLET",
                "message": "Des produits hors loyers ne sont pas détaillés sur le 2033-E.",
            }
        )
    total_1 = services
    total_3 = purchases + external + depreciation
    added_value = total_1 - total_3
    if total_1 <= _CVAE_THRESHOLD:
        warnings.append(
            {
                "code": "CVAE_NON_EXIGEE",
                "message": (
                    "Chiffre d’affaires de référence d’au plus 152 500 € : "
                    "le 2033-E n’est pas exigé. Aucune cotisation CVAE n’est calculée."
                ),
            }
        )
        base = 0
    else:
        base = max(0, added_value)
        warnings.append(
            {
                "code": "CVAE_BASE_SEULE",
                "message": "La case 117 est la base de CVAE, pas le montant de la cotisation.",
            }
        )
    rows = [
        ("CVAE_PRESTATIONS", "108", "Prestations de services et marchandises", services),
        ("CVAE_CA", "106", "Chiffre d’affaires de référence CVAE", total_1),
        ("CVAE_ACHATS", "121", "Achats", purchases),
        ("CVAE_SERVICES", "125", "Services extérieurs hors certains loyers", external),
        ("CVAE_LOYERS", "146", "Loyers non déductibles de la valeur ajoutée", rents),
        (
            "CVAE_DOTATIONS_LOCATION",
            "135",
            "Dotations des biens loués plus de 6 mois",
            depreciation,
        ),
        ("CVAE_TOTAL_2", "144", "Total 2 — autres produits", 0),
        ("CVAE_TOTAL_3", "152", "Total 3 — charges retenues", total_3),
        ("CVAE_VALEUR_AJOUTEE", "137", "Valeur ajoutée produite", added_value),
        ("CVAE_BASE", "117", "Valeur ajoutée assujettie à la CVAE", base),
    ]
    return [
        _field(code=code, form_ref="2033-E-SD", official_case=case, label=label, value=value)
        for code, case, label, value in rows
    ]


def _signed(rows: list[dict[str, str]]) -> list[tuple[str, int]]:
    return [(row["account_number"], _amount(row["amount"])) for row in rows]


def _prefixed(
    rows: list[dict[str, str]], prefixes: tuple[str, ...], skip: tuple[str, ...] = ()
) -> int:
    total = 0
    for number, amount in _signed(rows):
        if number.startswith(prefixes) and not number.startswith(skip):
            total += amount
    return total


def _out_of_scope(number: str) -> dict[str, str]:
    return {
        "code": "HORS_MVP",
        "message": (
            f"Le compte {number} relève de la TVA, d’une cession ou d’une plus-value, hors liasse."
        ),
    }


def _period_asset(session: Session, period: DepreciationPeriod) -> Asset | None:
    schedule = session.get(DepreciationSchedule, period.schedule_id)
    if schedule is None:
        return None
    if schedule.asset_id is not None:
        return session.get(Asset, schedule.asset_id)
    component = session.get(AssetComponent, schedule.component_id)
    if component is None:
        return None
    return session.get(Asset, component.asset_id)


def _deficits(session: Session, year: FiscalYear, fiscal: dict[str, Any]) -> list[dict[str, Any]]:
    opening = sum(stock["remaining"] for stock in _prior_remaining(session, year, "tax_loss"))
    used = _amount((fiscal.get("details") or {}).get("prior_tax_loss_used", "0"))
    current = _amount(fiscal["tax_loss"])
    remaining = opening - used + current
    return [
        _field(
            code="DEFICITS_ANTERIEURS",
            form_ref="2033-D-SD",
            official_case="982",
            label="Déficits restant à reporter au titre des exercices précédents",
            value=opening,
        ),
        _field(
            code="DEFICITS_EXERCICE",
            form_ref="2033-D-SD",
            official_case="860",
            label="Déficits de l’exercice",
            value=current,
        ),
        _field(
            code="DEFICITS_A_REPORTER",
            form_ref="2033-D-SD",
            official_case="870",
            label="Total des déficits restant à reporter",
            value=remaining,
        ),
    ]


def _result_2031(fiscal: dict[str, Any]) -> list[dict[str, Any]]:
    result = _amount(fiscal["fiscal_result"])
    benefit = max(0, result)
    deficit = max(0, -result)
    return [
        _field(
            code="2031_RESULTAT_BENEFICE",
            form_ref="2031-SD",
            official_case=None,
            label="2031 cadre 1 — bénéfice (report de la case 370 du 2033-B)",
            value=benefit,
        ),
        _field(
            code="2031_RESULTAT_DEFICIT",
            form_ref="2031-SD",
            official_case=None,
            label="2031 cadre 1 — déficit (report de la case 372 du 2033-B)",
            value=deficit,
        ),
    ]


def _segments(session: Session, year: FiscalYear) -> list[dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for prop in session.scalars(select(Property).order_by(Property.id)):
        rows[prop.id] = {
            "property_id": prop.id,
            "name": prop.name,
            "address": prop.address,
            "rents": 0,
            "expenses": 0,
            "depreciation": 0,
        }
    operations = session.execute(
        select(BusinessOperation)
        .join(AccountingEntry, AccountingEntry.id == BusinessOperation.accounting_entry_id)
        .where(
            BusinessOperation.fiscal_year_id == year.id,
            BusinessOperation.kind.in_(("REVENUE", "EXPENSE")),
            AccountingEntry.status == "VALIDATED",
        )
    )
    for (operation,) in operations:
        row = rows.get(operation.property_id)
        if row is None:
            continue
        cents = to_cents(operation.amount)
        if operation.kind == "REVENUE":
            row["rents"] += cents
        else:
            row["expenses"] += cents
    for period in session.scalars(
        select(DepreciationPeriod).where(
            DepreciationPeriod.fiscal_year_id == year.id,
            DepreciationPeriod.status == "POSTED",
        )
    ):
        asset = _period_asset(session, period)
        if asset is None:
            continue
        row = rows.get(asset.property_id)
        if row is not None:
            row["depreciation"] += to_cents(period.amount)
    return [
        {
            **row,
            "rents": money(row["rents"]),
            "expenses": money(row["expenses"]),
            "depreciation": money(row["depreciation"]),
        }
        for row in rows.values()
    ]


def _detail_warning(package: dict[str, Any]) -> None:
    by_code = {field["code"]: field["value"] for field in package["fields"]}
    needed = ("CHARGES", "CHARGES_EXTERNES", "IMPOTS_TAXES", "DOTATIONS")
    if not all(code in by_code for code in needed):
        return
    total = _amount(by_code["CHARGES"])
    detailed = sum(_amount(by_code[code]) for code in needed[1:])
    gap = total - detailed
    if gap:
        package["warnings"].append(
            {
                "code": "EXPLOITATION_DETAIL",
                "message": (
                    f"{money(gap)} € de charges d’exploitation sont dans la case 264 "
                    "sans ligne de détail (hors 60/61/62, impôts et dotations)."
                ),
            }
        )
