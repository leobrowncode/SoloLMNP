"""French CSV import assistant: templates, mapping, and row verdicts.

Pure parsing. Database duplicates and the accounting year stay in the service.
Amounts are whole cents. Existing import endpoints keep their own parsers.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal, cast

from app.core.csv_text import safe_cell
from app.core.money import to_cents

Profile = Literal["bank", "operations", "loan_payments"]
PROFILES: tuple[Profile, ...] = ("bank", "operations", "loan_payments")

TEMPLATE_NAMES: dict[Profile, str] = {
    "bank": "modele-releve-bancaire.csv",
    "operations": "modele-recettes-depenses.csv",
    "loan_payments": "modele-echeances-emprunt.csv",
}

# Same accounts as services.operations.OPERATION_TYPE_ACCOUNTS.
OPERATION_TYPE_ACCOUNTS: dict[str, dict[str, str]] = {
    "REVENUE": {"LOY": "706000", "TROP": "706000", "CHG": "706000", "AUT": "706000"},
    "EXPENSE": {
        "ASS": "616000",
        "ENT": "615000",
        "FOU": "606000",
        "HON": "622000",
        "BAN": "627000",
        "TAX": "635000",
        "FON": "635000",
        "COP": "614000",
        "GES": "622000",
        "INT": "661000",
        "AUT": "606000",
    },
}

KIND_LABELS = {"REVENUE": "Recette", "EXPENSE": "Dépense"}
KIND_ALIASES = {
    "recette": "REVENUE",
    "revenue": "REVENUE",
    "produit": "REVENUE",
    "depense": "EXPENSE",
    "expense": "EXPENSE",
    "charge": "EXPENSE",
}
PAID_VALUES = {
    "": False,
    "non": False,
    "n": False,
    "no": False,
    "0": False,
    "oui": True,
    "o": True,
    "yes": True,
    "x": True,
    "1": True,
}
TYPE_BY_LABEL: dict[str, dict[str, str]] = {
    "REVENUE": {
        "loy": "LOY",
        "loyer": "LOY",
        "trop": "TROP",
        "trop percu": "TROP",
        "trop percu regularisation": "TROP",
        "chg": "CHG",
        "charges": "CHG",
        "charges locataires refacturees": "CHG",
        "aut": "AUT",
        "autre recette": "AUT",
    },
    "EXPENSE": {
        "ass": "ASS",
        "assurance": "ASS",
        "ent": "ENT",
        "entretien": "ENT",
        "entretien reparations": "ENT",
        "fou": "FOU",
        "fournitures": "FOU",
        "hon": "HON",
        "honoraires": "HON",
        "ban": "BAN",
        "frais bancaires": "BAN",
        "cop": "COP",
        "copropriete": "COP",
        "fon": "FON",
        "taxe fonciere": "FON",
        "tax": "TAX",
        "autres impots et taxes": "TAX",
        "ges": "GES",
        "gestion locative": "GES",
        "int": "INT",
        "interets": "INT",
        "interets d emprunt": "INT",
        "aut": "AUT",
        "autre depense": "AUT",
    },
}

CODE_HELP: dict[str, str] = {
    "BANK_REQUIRED": "compte-512",
    "CSV_AMOUNT": "import-csv",
    "CSV_CONFLICT": "import-csv",
    "CSV_EMPTY": "import-csv",
    "CSV_HEADER": "import-csv",
    "CSV_INVALID": "import-csv",
    "CSV_PAID": "import-csv",
    "CSV_REFERENCE": "import-csv",
    "CSV_SHAPE": "import-csv",
    "CSV_TYPE": "import-csv",
    "CSV_ZERO": "import-csv",
    "DATE_OUTSIDE_YEAR": "exercice",
    "LOAN_CHRONOLOGY": "emprunt",
    "LOAN_CSV_AMOUNT": "import-csv",
    "LOAN_CSV_BEFORE_START": "emprunt",
    "LOAN_CSV_CONFLICT": "emprunt",
    "LOAN_CSV_DATE": "import-csv",
    "LOAN_CSV_DUPLICATE_DATE": "import-csv",
    "LOAN_CSV_DUPLICATE_PAYMENT_DATE": "import-csv",
    "LOAN_CSV_EMPTY": "import-csv",
    "LOAN_CSV_EXTERNAL_INSURANCE": "emprunt",
    "LOAN_CSV_HEADER": "import-csv",
    "LOAN_CSV_MULTIPLE_LOANS": "emprunt",
    "LOAN_CSV_REFERENCE": "import-csv",
    "LOAN_CSV_SHAPE": "import-csv",
    "LOAN_CSV_SPLIT": "emprunt",
    "LOAN_NOT_FUNDED": "compte-164",
    "PRINCIPAL_EXCEEDED": "compte-164",
}

DATE_CORRECTION = "Saisissez une date au format JJ/MM/AAAA, par exemple 05/03/2026."
MONEY_CORRECTION = "Saisissez un montant positif au centime, par exemple 800,00."
SIGNED_MONEY_CORRECTION = (
    "Saisissez un montant au centime, positif ou négatif, par exemple 800,00 ou -42,50."
)


class CsvReadError(Exception):
    def __init__(self, code: str, message: str, issues: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = issues


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    required: bool
    examples: tuple[str, str]
    correction: str
    help_id: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Table:
    delimiter: str
    headers: list[str]
    rows: list[tuple[int, dict[str, str]]]
    wide_lines: set[int]


def normalize(value: str) -> str:
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    text = text.lower().replace("€", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[_/–—-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clip(value: str, limit: int = 200) -> str:
    text = value.replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, fractional = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fractional:02d}"


def french_date(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def french_amount(canonical: str) -> str:
    return canonical.replace(".", ",")


def make_issue(
    code: str,
    message: str,
    *,
    field: str,
    column: str,
    value: str,
    correction: str,
    line: int,
    help_id: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "field": field,
        "column": column,
        "value": clip(value),
        "correction": correction,
        "line": line,
        "location": "import",
        "help": help_id or CODE_HELP.get(code, "import-csv"),
    }


def rejection_text(issue: dict[str, Any]) -> str:
    shown = f"« {issue['value']} »" if issue.get("value") else "vide"
    return (
        f"Ligne {issue['line']}, colonne {issue['column']}, valeur {shown}. {issue['correction']}"
    )


BANK_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "date",
        "Date",
        True,
        ("05/03/2026", "06/03/2026"),
        DATE_CORRECTION,
        "import-csv",
        ("date operation", "date valeur"),
    ),
    FieldSpec(
        "label",
        "Libellé",
        True,
        ("Loyer mars Dupont", "Prélèvement assurance PNO"),
        "Saisissez le libellé du relevé (300 caractères au plus).",
        "import-csv",
        ("libelle", "label", "description"),
    ),
    FieldSpec(
        "amount",
        "Montant",
        True,
        ("800,00", "-42,50"),
        SIGNED_MONEY_CORRECTION,
        "import-csv",
        ("montant", "amount", "somme"),
    ),
    FieldSpec(
        "reference",
        "Référence",
        True,
        ("REL-2026-03-05", "REL-2026-03-06"),
        "Saisissez une référence unique, 200 caractères au plus.",
        "import-csv",
        ("reference", "ref", "id"),
    ),
)

OPERATION_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "kind",
        "Nature",
        True,
        ("Recette", "Dépense"),
        "Indiquez Recette ou Dépense.",
        "import-csv",
        ("kind", "nature", "sens"),
    ),
    FieldSpec(
        "date",
        "Date",
        True,
        ("05/03/2026", "06/03/2026"),
        DATE_CORRECTION,
        "exercice",
        ("date", "date comptable"),
    ),
    FieldSpec(
        "piece_date",
        "Date de la pièce",
        False,
        ("05/03/2026", "01/03/2026"),
        DATE_CORRECTION,
        "import-csv",
        ("piece date", "date piece", "date de piece"),
    ),
    FieldSpec(
        "type",
        "Type",
        True,
        ("LOY", "ASS"),
        "Indiquez un type compatible avec la nature, par exemple LOY ou ASS.",
        "import-csv",
        ("type", "categorie"),
    ),
    FieldSpec(
        "counterparty",
        "Tiers",
        True,
        ("Dupont", "Assureur"),
        "Saisissez le locataire ou le fournisseur (200 caractères au plus).",
        "import-csv",
        ("counterparty", "tiers", "locataire", "fournisseur"),
    ),
    FieldSpec(
        "amount",
        "Montant",
        True,
        ("800,00", "42,50"),
        MONEY_CORRECTION,
        "import-csv",
        ("amount", "montant"),
    ),
    FieldSpec(
        "description",
        "Libellé",
        True,
        ("Loyer mars 2026", "Assurance PNO mars"),
        "Saisissez le libellé de l’opération (300 caractères au plus).",
        "import-csv",
        ("description", "libelle"),
    ),
    FieldSpec(
        "piece_reference",
        "Référence de pièce",
        True,
        ("LOY-2026-03", "ASS-2026-03"),
        "Saisissez une référence de pièce unique (200 caractères au plus).",
        "import-csv",
        ("piece reference", "reference", "reference de piece"),
    ),
    FieldSpec(
        "source_file",
        "Justificatif",
        False,
        ("bail-dupont.pdf", "facture-pno.pdf"),
        "Indiquez le nom du fichier justificatif, 300 caractères au plus.",
        "import-csv",
        ("source file", "justificatif", "fichier"),
    ),
    FieldSpec(
        "paid",
        "Déjà payée",
        False,
        ("oui", "non"),
        "Indiquez oui si la ligne est déjà payée, sinon non.",
        "compte-512",
        ("paid", "payee", "deja payee", "reglee"),
    ),
)

LOAN_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "loan_reference",
        "Prêt",
        True,
        ("PRET-HABITAT", "PRET-HABITAT"),
        "Saisissez la référence d’un seul prêt (200 caractères au plus).",
        "emprunt",
        ("pret", "reference pret", "loan reference"),
    ),
    FieldSpec(
        "rank",
        "Rang",
        False,
        ("1", "2"),
        "Indiquez le rang de l’échéance, ou laissez la cellule vide.",
        "emprunt",
        ("rang", "numero", "n"),
    ),
    FieldSpec(
        "due_date",
        "Date",
        True,
        ("05/03/2026", "05/04/2026"),
        DATE_CORRECTION,
        "emprunt",
        ("date", "date echeance", "echeance"),
    ),
    FieldSpec(
        "payment_date",
        "Date de débit",
        False,
        ("05/03/2026", "05/04/2026"),
        DATE_CORRECTION,
        "emprunt",
        ("date de debit", "date debit", "date comptable", "date paiement", "date effective"),
    ),
    FieldSpec(
        "principal",
        "Capital",
        True,
        ("450,00", "452,10"),
        MONEY_CORRECTION,
        "compte-164",
        ("capital", "principal", "montant amorti"),
    ),
    FieldSpec(
        "interest",
        "Intérêts",
        True,
        ("310,00", "307,90"),
        "Saisissez les intérêts au centime, ou 0,00.",
        "emprunt",
        ("interet", "interets", "interest"),
    ),
    FieldSpec(
        "insurance",
        "Assurance banque",
        True,
        ("40,00", "40,00"),
        "Saisissez l’assurance banque au centime, ou 0,00.",
        "emprunt",
        ("assurance", "assurance banque"),
    ),
    FieldSpec(
        "external_insurance",
        "Assurance externe",
        False,
        ("0,00", "0,00"),
        "Laissez 0,00. L’assurance externe s’importe comme une dépense ASS.",
        "emprunt",
        ("assurance externe", "assurance externe a completer"),
    ),
    FieldSpec(
        "other_costs",
        "Autres frais",
        False,
        ("0,00", "0,00"),
        "Saisissez les autres frais au centime, ou 0,00.",
        "emprunt",
        ("autres frais", "frais", "other costs"),
    ),
    FieldSpec(
        "amount",
        "Total banque",
        True,
        ("800,00", "800,00"),
        "Saisissez le total prélevé par la banque, égal à la ventilation.",
        "emprunt",
        ("total", "total banque", "mensualite", "echeance", "amount"),
    ),
)

FIELDS: dict[Profile, tuple[FieldSpec, ...]] = {
    "bank": BANK_FIELDS,
    "operations": OPERATION_FIELDS,
    "loan_payments": LOAN_FIELDS,
}


def is_profile(value: str) -> bool:
    return value in PROFILES


def profile_fields(profile: str) -> tuple[FieldSpec, ...]:
    if not is_profile(profile):
        raise CsvReadError(
            "CSV_PROFILE",
            "Import inconnu.",
            [
                make_issue(
                    "CSV_PROFILE",
                    "Import inconnu.",
                    field="profile",
                    column="",
                    value=profile,
                    correction="Choisissez le relevé, les opérations ou les échéances.",
                    line=1,
                )
            ],
        )
    return FIELDS[cast(Profile, profile)]


def public_field(field: FieldSpec) -> dict[str, Any]:
    return {
        "key": field.key,
        "label": field.label,
        "required": field.required,
        "help": field.help_id,
    }


def field_map(fields: tuple[FieldSpec, ...]) -> dict[str, FieldSpec]:
    return {field.key: field for field in fields}


def detect_delimiter(line: str) -> str:
    tabs = line.count("\t")
    semicolons = line.count(";")
    if tabs and tabs >= semicolons:
        return "\t"
    if semicolons:
        return ";"
    if "," in line:
        return ","
    return ";"


def read_table(content: str) -> Table:
    text = content.lstrip("\ufeff")
    first = next((line for line in text.splitlines() if line.strip()), "")
    if not first:
        raise CsvReadError(
            "CSV_EMPTY",
            "Le fichier ne contient aucune ligne.",
            [
                make_issue(
                    "CSV_EMPTY",
                    "Le fichier ne contient aucune ligne.",
                    field="",
                    column="",
                    value="",
                    correction="Ajoutez une ligne d’en-tête puis au moins une ligne d’exemple.",
                    line=1,
                )
            ],
        )
    delimiter = detect_delimiter(first)
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter, restkey="_extra")
        headers = [name.strip() for name in reader.fieldnames or [] if name is not None]
        reader.fieldnames = [name.strip() if name else "" for name in reader.fieldnames or []]
        rows: list[tuple[int, dict[str, str]]] = []
        wide: set[int] = set()
        for index, raw in enumerate(reader, start=2):
            if index > 5001:
                raise CsvReadError(
                    "CSV_SHAPE",
                    "Limite de 5 000 lignes dépassée.",
                    [
                        make_issue(
                            "CSV_SHAPE",
                            "Limite de 5 000 lignes dépassée.",
                            field="",
                            column="",
                            value="",
                            correction="Découpez le fichier en plusieurs imports de 5 000 lignes.",
                            line=index,
                        )
                    ],
                )
            cells = {
                key: ("" if value is None else value)
                for key, value in raw.items()
                if key != "_extra"
            }
            extra = raw.get("_extra") or []
            if not any(value.strip() for value in cells.values()) and not extra:
                continue
            if extra or any(value is None for value in raw.values()):
                wide.add(index)
            rows.append((index, {key: value.strip() for key, value in cells.items()}))
    except csv.Error as exc:
        raise CsvReadError(
            "CSV_INVALID",
            "CSV illisible. Vérifiez les guillemets et le séparateur point-virgule.",
            [
                make_issue(
                    "CSV_INVALID",
                    "CSV illisible. Vérifiez les guillemets et le séparateur point-virgule.",
                    field="",
                    column="",
                    value=clip(str(exc)),
                    correction="Enregistrez le fichier en UTF-8, séparateur point-virgule.",
                    line=1,
                )
            ],
        ) from exc
    return Table(delimiter=delimiter, headers=headers, rows=rows, wide_lines=wide)


def candidates(field: FieldSpec) -> set[str]:
    return {normalize(value) for value in (field.label, field.key, *field.aliases)}


def resolve_mapping(
    headers: list[str],
    fields: tuple[FieldSpec, ...],
    explicit: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if any(not header for header in headers) or len(headers) != len(set(headers)):
        issues.append(
            make_issue(
                "CSV_HEADER",
                "Les colonnes du fichier doivent avoir un nom unique.",
                field="",
                column="",
                value="",
                correction="Renommez ou supprimez les colonnes vides et les doublons d’en-tête.",
                line=1,
            )
        )
    by_norm: dict[str, list[str]] = {}
    for header in headers:
        if header:
            by_norm.setdefault(normalize(header), []).append(header)
    mapping: dict[str, str] = {}
    used: set[str] = set()
    known = {field.key for field in fields}
    for key, header in explicit.items():
        if key not in known:
            continue
        field = next(item for item in fields if item.key == key)
        if header and header not in headers:
            issues.append(
                make_issue(
                    "CSV_HEADER",
                    f"La colonne « {header} » n’est pas dans le fichier.",
                    field=field.key,
                    column=field.label,
                    value=header,
                    correction=f"Choisissez une colonne du fichier pour « {field.label} ».",
                    line=1,
                    help_id=field.help_id,
                )
            )
            mapping[key] = ""
        else:
            if header and header in used:
                issues.append(
                    make_issue(
                        "CSV_HEADER",
                        f"La colonne « {header} » est associée deux fois.",
                        field=field.key,
                        column=field.label,
                        value=header,
                        correction="Associez chaque colonne à un seul champ.",
                        line=1,
                        help_id=field.help_id,
                    )
                )
            mapping[key] = header
            if header:
                used.add(header)
    for field in fields:
        if field.key in mapping:
            continue
        found: list[str] = []
        for candidate in candidates(field):
            for header in by_norm.get(candidate, []):
                if header not in found:
                    found.append(header)
        available = [header for header in found if header not in used]
        if len(available) == 1:
            mapping[field.key] = available[0]
            used.add(available[0])
        else:
            if len(available) > 1:
                issues.append(
                    make_issue(
                        "CSV_HEADER",
                        f"Plusieurs colonnes peuvent correspondre à « {field.label} ».",
                        field=field.key,
                        column=field.label,
                        value=", ".join(available),
                        correction=f"Choisissez une seule colonne pour « {field.label} ».",
                        line=1,
                        help_id=field.help_id,
                    )
                )
            mapping[field.key] = ""
    if not any(issue["code"] == "CSV_HEADER" and issue["field"] == "" for issue in issues):
        for field in fields:
            if field.required and not mapping.get(field.key):
                issues.append(
                    make_issue(
                        "CSV_HEADER",
                        f"Associez une colonne à « {field.label} ».",
                        field=field.key,
                        column=field.label,
                        value="",
                        correction=field.correction,
                        line=1,
                        help_id=field.help_id,
                    )
                )
    return mapping, issues


def parse_day(value: str) -> date | None:
    french = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if french:
        try:
            return date(int(french[3]), int(french[2]), int(french[1]))
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def parse_amount(value: str, *, signed: bool) -> int | None:
    text = re.sub(r"[\s\u00a0\u202f€]", "", value)
    text = text.replace("EUR", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    pattern = r"[+-]?[0-9]+(?:\.[0-9]{1,2})?" if signed else r"[0-9]+(?:\.[0-9]{1,2})?"
    if not re.fullmatch(pattern, text):
        return None
    try:
        return to_cents(Decimal(text))
    except (ValueError, ArithmeticError):
        return None


def blank_row() -> dict[str, Any]:
    return {
        "line": 0,
        "status": "valid",
        "importable": True,
        "duplicate": False,
        "values": {},
        "display": {},
        "raw": {},
        "issues": [],
        "warnings": [],
        "suggested_account": None,
        "paid": False,
    }


def settle(row: dict[str, Any]) -> None:
    if row["issues"]:
        row["status"] = "error"
        row["importable"] = False
        row["duplicate"] = False
    elif row["duplicate"]:
        row["status"] = "duplicate"
        row["importable"] = False
    elif row["warnings"]:
        row["status"] = "warning"
    else:
        row["status"] = "valid"
        row["importable"] = True
        row["duplicate"] = False


def add_issue(row: dict[str, Any], issue: dict[str, Any]) -> None:
    row["issues"].append(issue)
    settle(row)


def add_warning(row: dict[str, Any], issue: dict[str, Any], *, importable: bool = True) -> None:
    row["warnings"].append(issue)
    if not importable:
        row["importable"] = False
    settle(row)


def flag_duplicates(
    rows: list[dict[str, Any]],
    key: str,
    code: str,
    column: str,
    correction: str,
) -> None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = str(row["values"].get(key) or "")
        if not value or any(issue["field"] == key for issue in row["issues"]):
            continue
        groups.setdefault(value, []).append(row)
    for value, group in groups.items():
        if len(group) < 2:
            continue
        lines = ", ".join(str(item["line"]) for item in group)
        for row in group:
            add_issue(
                row,
                make_issue(
                    code,
                    f"Cette valeur est répétée aux lignes {lines}.",
                    field=key,
                    column=column,
                    value=value,
                    correction=correction,
                    line=row["line"],
                ),
            )


def text_cell(
    row: dict[str, Any],
    field: FieldSpec,
    raw_value: str,
    *,
    required: bool,
    limit: int,
    code: str,
) -> str:
    row["raw"][field.key] = raw_value
    row["display"][field.key] = raw_value
    if required and not raw_value:
        add_issue(
            row,
            make_issue(
                code,
                f"« {field.label} » est vide.",
                field=field.key,
                column=field.label,
                value="",
                correction=field.correction,
                line=row["line"],
                help_id=field.help_id,
            ),
        )
        return ""
    if len(raw_value) > limit:
        add_issue(
            row,
            make_issue(
                code,
                f"« {field.label} » dépasse {limit} caractères.",
                field=field.key,
                column=field.label,
                value=raw_value,
                correction=field.correction,
                line=row["line"],
                help_id=field.help_id,
            ),
        )
        return ""
    row["values"][field.key] = raw_value
    return raw_value


def date_cell(
    row: dict[str, Any],
    field: FieldSpec,
    raw_value: str,
    *,
    required: bool,
    code: str,
) -> date | None:
    row["raw"][field.key] = raw_value
    row["display"][field.key] = raw_value
    if not raw_value and not required:
        return None
    parsed = parse_day(raw_value) if raw_value else None
    if parsed is None:
        add_issue(
            row,
            make_issue(
                code,
                f"Date invalide dans « {field.label} ».",
                field=field.key,
                column=field.label,
                value=raw_value,
                correction=field.correction,
                line=row["line"],
                help_id=field.help_id,
            ),
        )
        return None
    iso = parsed.isoformat()
    row["values"][field.key] = iso
    row["display"][field.key] = french_date(iso)
    return parsed


def money_cell(
    row: dict[str, Any],
    field: FieldSpec,
    raw_value: str,
    *,
    signed: bool,
    blank_zero: bool,
    code: str,
    allow_zero: bool,
    warn_blank: bool = False,
) -> str | None:
    row["raw"][field.key] = raw_value
    row["display"][field.key] = raw_value
    if not raw_value and blank_zero:
        row["values"][field.key] = "0.00"
        row["display"][field.key] = "0,00"
        if warn_blank:
            add_warning(
                row,
                make_issue(
                    code,
                    f"« {field.label} » est vide : 0,00 sera utilisé.",
                    field=field.key,
                    column=field.label,
                    value="",
                    correction=field.correction,
                    line=row["line"],
                    help_id=field.help_id,
                ),
            )
        return "0.00"
    cents = parse_amount(raw_value, signed=signed) if raw_value else None
    if cents is None or (not allow_zero and cents == 0) or (not signed and cents < 0):
        zero_code = "CSV_ZERO" if cents == 0 and not allow_zero else code
        add_issue(
            row,
            make_issue(
                zero_code,
                f"Montant invalide dans « {field.label} ».",
                field=field.key,
                column=field.label,
                value=raw_value,
                correction=field.correction,
                line=row["line"],
                help_id=field.help_id,
            ),
        )
        return None
    canonical = format_cents(cents)
    row["values"][field.key] = canonical
    row["display"][field.key] = french_amount(canonical)
    return canonical


def parse_bank_row(
    line: int,
    cells: dict[str, str],
    mapping: dict[str, str],
    fields: dict[str, FieldSpec],
    wide: bool,
) -> dict[str, Any]:
    row = blank_row()
    row["line"] = line
    if wide:
        add_issue(
            row,
            make_issue(
                "CSV_SHAPE",
                "La ligne n’a pas le nombre de colonnes de l’en-tête.",
                field="",
                column="",
                value="",
                correction="Utilisez le point-virgule et mettez les montants entre guillemets "
                "si vous gardez la virgule comme séparateur.",
                line=line,
            ),
        )
        return row
    pulled = {key: cells.get(mapping.get(key, ""), "").strip() for key in fields}
    date_cell(row, fields["date"], pulled["date"], required=True, code="CSV_INVALID")
    text_cell(row, fields["label"], pulled["label"], required=True, limit=300, code="CSV_REFERENCE")
    money_cell(
        row,
        fields["amount"],
        pulled["amount"],
        signed=True,
        blank_zero=False,
        code="CSV_AMOUNT",
        allow_zero=False,
    )
    text_cell(
        row,
        fields["reference"],
        pulled["reference"],
        required=True,
        limit=200,
        code="CSV_REFERENCE",
    )
    settle(row)
    return row


def parse_operation_row(
    line: int,
    cells: dict[str, str],
    mapping: dict[str, str],
    fields: dict[str, FieldSpec],
    wide: bool,
) -> dict[str, Any]:
    row = blank_row()
    row["line"] = line
    if wide:
        add_issue(
            row,
            make_issue(
                "CSV_SHAPE",
                "La ligne n’a pas le nombre de colonnes de l’en-tête.",
                field="",
                column="",
                value="",
                correction="Utilisez le point-virgule. Les montants français restent en 800,00.",
                line=line,
            ),
        )
        return row
    pulled = {key: cells.get(mapping.get(key, ""), "").strip() for key in fields}
    kind = KIND_ALIASES.get(normalize(pulled["kind"]))
    row["raw"]["kind"] = pulled["kind"]
    row["display"]["kind"] = pulled["kind"]
    if kind is None:
        add_issue(
            row,
            make_issue(
                "CSV_TYPE",
                "Nature inconnue.",
                field="kind",
                column=fields["kind"].label,
                value=pulled["kind"],
                correction=fields["kind"].correction,
                line=line,
                help_id=fields["kind"].help_id,
            ),
        )
    else:
        row["values"]["kind"] = kind
        row["display"]["kind"] = KIND_LABELS[kind]
    day = date_cell(row, fields["date"], pulled["date"], required=True, code="CSV_INVALID")
    piece = date_cell(
        row, fields["piece_date"], pulled["piece_date"], required=False, code="CSV_INVALID"
    )
    if piece is None and day is not None and not pulled["piece_date"]:
        row["values"]["piece_date"] = day.isoformat()
        row["display"]["piece_date"] = french_date(day.isoformat())
        add_warning(
            row,
            make_issue(
                "CSV_INVALID",
                "Date de la pièce absente : la date comptable est reprise.",
                field="piece_date",
                column=fields["piece_date"].label,
                value="",
                correction=(
                    "Indiquez la date du justificatif si elle diffère, au format JJ/MM/AAAA."
                ),
                line=line,
                help_id="import-csv",
            ),
        )
    type_code = resolve_type(kind, pulled["type"]) if kind else None
    row["raw"]["type"] = pulled["type"]
    row["display"]["type"] = pulled["type"]
    if kind and type_code is None:
        add_issue(
            row,
            make_issue(
                "CSV_TYPE",
                "Type incompatible avec la nature de l’opération.",
                field="type",
                column=fields["type"].label,
                value=pulled["type"],
                correction=type_correction(kind),
                line=line,
            ),
        )
    elif type_code and kind:
        row["values"]["type"] = type_code
        row["values"]["accounting_account"] = OPERATION_TYPE_ACCOUNTS[kind][type_code]
        row["display"]["type"] = type_code
    text_cell(
        row,
        fields["counterparty"],
        pulled["counterparty"],
        required=True,
        limit=200,
        code="CSV_REFERENCE",
    )
    money_cell(
        row,
        fields["amount"],
        pulled["amount"],
        signed=False,
        blank_zero=False,
        code="CSV_AMOUNT",
        allow_zero=False,
    )
    text_cell(
        row,
        fields["description"],
        pulled["description"],
        required=True,
        limit=300,
        code="CSV_REFERENCE",
    )
    text_cell(
        row,
        fields["piece_reference"],
        pulled["piece_reference"],
        required=True,
        limit=200,
        code="CSV_REFERENCE",
    )
    source = text_cell(
        row,
        fields["source_file"],
        pulled["source_file"],
        required=False,
        limit=300,
        code="CSV_REFERENCE",
    )
    if source == "" and not any(issue["field"] == "source_file" for issue in row["issues"]):
        add_warning(
            row,
            make_issue(
                "CSV_REFERENCE",
                "Aucun nom de justificatif. La ligne peut être importée.",
                field="source_file",
                column=fields["source_file"].label,
                value="",
                correction=fields["source_file"].correction,
                line=line,
            ),
        )
    paid_raw = pulled["paid"].lower()
    row["raw"]["paid"] = pulled["paid"]
    row["display"]["paid"] = pulled["paid"] or "non"
    if paid_raw not in PAID_VALUES:
        add_issue(
            row,
            make_issue(
                "CSV_PAID",
                "Colonne « Déjà payée » : indiquez oui ou non.",
                field="paid",
                column=fields["paid"].label,
                value=pulled["paid"],
                correction=fields["paid"].correction,
                line=line,
                help_id="compte-512",
            ),
        )
    else:
        row["paid"] = PAID_VALUES[paid_raw]
        row["values"]["paid"] = "oui" if row["paid"] else "non"
        row["display"]["paid"] = row["values"]["paid"]
    settle(row)
    return row


def resolve_type(kind: str | None, raw: str) -> str | None:
    if kind is None:
        return None
    accounts = OPERATION_TYPE_ACCOUNTS[kind]
    code = raw.strip().upper()
    if code in accounts:
        return code
    return TYPE_BY_LABEL[kind].get(normalize(raw))


def type_correction(kind: str) -> str:
    label = "recette" if kind == "REVENUE" else "dépense"
    codes = ", ".join(OPERATION_TYPE_ACCOUNTS[kind])
    return f"Indiquez un type de {label} : {codes}."


def parse_loan_row(
    line: int,
    cells: dict[str, str],
    mapping: dict[str, str],
    fields: dict[str, FieldSpec],
    wide: bool,
) -> dict[str, Any]:
    row = blank_row()
    row["line"] = line
    if wide:
        add_issue(
            row,
            make_issue(
                "LOAN_CSV_SHAPE",
                "La ligne n’a pas le nombre de colonnes de l’en-tête.",
                field="",
                column="",
                value="",
                correction="Utilisez le point-virgule. Un seul prêt par fichier.",
                line=line,
            ),
        )
        return row
    pulled = {key: cells.get(mapping.get(key, ""), "").strip() for key in fields}
    text_cell(
        row,
        fields["loan_reference"],
        pulled["loan_reference"],
        required=True,
        limit=200,
        code="LOAN_CSV_REFERENCE",
    )
    text_cell(row, fields["rank"], pulled["rank"], required=False, limit=40, code="LOAN_CSV_SHAPE")
    due = date_cell(
        row, fields["due_date"], pulled["due_date"], required=True, code="LOAN_CSV_DATE"
    )
    payment = date_cell(
        row,
        fields["payment_date"],
        pulled["payment_date"],
        required=False,
        code="LOAN_CSV_DATE",
    )
    if payment is None and due is not None and not pulled["payment_date"]:
        row["values"]["date"] = due.isoformat()
        row["values"]["payment_date"] = due.isoformat()
        row["display"]["payment_date"] = french_date(due.isoformat())
    elif payment is not None:
        row["values"]["date"] = payment.isoformat()
    principal = money_cell(
        row,
        fields["principal"],
        pulled["principal"],
        signed=False,
        blank_zero=False,
        code="LOAN_CSV_AMOUNT",
        allow_zero=True,
    )
    interest = money_cell(
        row,
        fields["interest"],
        pulled["interest"],
        signed=False,
        blank_zero=True,
        code="LOAN_CSV_AMOUNT",
        allow_zero=True,
        warn_blank=bool(mapping.get("interest")),
    )
    insurance = money_cell(
        row,
        fields["insurance"],
        pulled["insurance"],
        signed=False,
        blank_zero=True,
        code="LOAN_CSV_AMOUNT",
        allow_zero=True,
        warn_blank=bool(mapping.get("insurance")),
    )
    external = money_cell(
        row,
        fields["external_insurance"],
        pulled["external_insurance"],
        signed=False,
        blank_zero=True,
        code="LOAN_CSV_AMOUNT",
        allow_zero=True,
    )
    other = money_cell(
        row,
        fields["other_costs"],
        pulled["other_costs"],
        signed=False,
        blank_zero=True,
        code="LOAN_CSV_AMOUNT",
        allow_zero=True,
        warn_blank=bool(mapping.get("other_costs")),
    )
    total = money_cell(
        row,
        fields["amount"],
        pulled["amount"],
        signed=False,
        blank_zero=False,
        code="LOAN_CSV_AMOUNT",
        allow_zero=False,
    )
    if external not in {None, "0.00"}:
        add_issue(
            row,
            make_issue(
                "LOAN_CSV_EXTERNAL_INSURANCE",
                "L’assurance externe est un prélèvement distinct.",
                field="external_insurance",
                column=fields["external_insurance"].label,
                value=pulled["external_insurance"],
                correction=fields["external_insurance"].correction,
                line=line,
                help_id="emprunt",
            ),
        )
    parts = (principal, interest, insurance, other)
    if total is not None and all(part is not None for part in parts):
        expected = sum(to_cents(Decimal(part)) for part in parts if part is not None)
        if expected <= 0 or expected != to_cents(Decimal(total)):
            add_issue(
                row,
                make_issue(
                    "LOAN_CSV_SPLIT",
                    "Capital + intérêts + assurance banque + autres frais doit égaler "
                    "le total banque.",
                    field="amount",
                    column=fields["amount"].label,
                    value=pulled["amount"],
                    correction=(
                        "Recalculez le total banque pour qu’il égale la ventilation au centime."
                    ),
                    line=line,
                    help_id="emprunt",
                ),
            )
    settle(row)
    return row


def parse_rows(profile: Profile, table: Table, mapping: dict[str, str]) -> list[dict[str, Any]]:
    fields = field_map(FIELDS[profile])
    rows: list[dict[str, Any]] = []
    for line, cells in table.rows:
        wide = line in table.wide_lines
        if profile == "bank":
            rows.append(parse_bank_row(line, cells, mapping, fields, wide))
        elif profile == "operations":
            rows.append(parse_operation_row(line, cells, mapping, fields, wide))
        else:
            rows.append(parse_loan_row(line, cells, mapping, fields, wide))
    if profile == "bank":
        flag_duplicates(
            rows,
            "reference",
            "CSV_REFERENCE",
            "Référence",
            "Laissez une seule ligne pour cette référence.",
        )
    elif profile == "operations":
        flag_duplicates(
            rows,
            "piece_reference",
            "CSV_REFERENCE",
            "Référence de pièce",
            "Laissez une seule ligne pour cette référence de pièce.",
        )
    else:
        flag_duplicates(
            rows,
            "due_date",
            "LOAN_CSV_DUPLICATE_DATE",
            "Date",
            "Collez un seul prêt, avec une date d’échéance unique.",
        )
        flag_duplicates(
            rows,
            "date",
            "LOAN_CSV_DUPLICATE_PAYMENT_DATE",
            "Date de débit",
            "Deux échéances ne peuvent pas partager la même date comptable.",
        )
    return rows


def empty_summary() -> dict[str, int]:
    return {"valid": 0, "duplicate": 0, "warning": 0, "error": 0, "count": 0, "importable": 0}


def summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = empty_summary()
    for row in rows:
        status = str(row["status"])
        if status in {"valid", "duplicate", "warning", "error"}:
            summary[status] += 1
        if row["importable"]:
            summary["importable"] += 1
    summary["count"] = len(rows)
    return summary


def analyze(profile: str, content: str, mapping: dict[str, str] | None = None) -> dict[str, Any]:
    fields = profile_fields(profile)
    table = read_table(content)
    resolved, issues = resolve_mapping(table.headers, fields, mapping or {})
    ready = not issues
    rows = parse_rows(cast(Profile, profile), table, resolved) if ready else []
    if ready and not rows:
        issues.append(
            make_issue(
                "CSV_EMPTY" if profile != "loan_payments" else "LOAN_CSV_EMPTY",
                "Le fichier ne contient aucune ligne à importer.",
                field="",
                column="",
                value="",
                correction="Ajoutez au moins une ligne sous l’en-tête, ou téléchargez le modèle.",
                line=1,
            )
        )
    return {
        "profile": profile,
        "ready": ready,
        "delimiter": ";" if table.delimiter == ";" else table.delimiter,
        "headers": table.headers,
        "fields": [public_field(field) for field in fields],
        "mapping": resolved,
        "issues": issues,
        "rows": rows,
        "summary": summarize(rows),
        "rejects_csv": "",
        "loan_reference": None,
        "imported": 0,
    }


def inspect_content(content: str) -> dict[str, Any]:
    table = read_table(content)
    suggestions: dict[str, dict[str, str]] = {}
    fields: dict[str, list[dict[str, Any]]] = {}
    for profile in PROFILES:
        resolved, _issues = resolve_mapping(table.headers, FIELDS[profile], {})
        suggestions[profile] = resolved
        fields[profile] = [public_field(field) for field in FIELDS[profile]]
    return {
        "delimiter": table.delimiter,
        "headers": table.headers,
        "fields": fields,
        "suggestions": suggestions,
    }


def template_csv(profile: str) -> str:
    fields = profile_fields(profile)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow([field.label for field in fields])
    for index in range(2):
        writer.writerow([field.examples[index] for field in fields])
    return "\ufeff" + buffer.getvalue()


def rejects_csv(profile: str, rows: list[dict[str, Any]]) -> str:
    fields = profile_fields(profile)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow([field.label for field in fields] + ["Correction"])
    written = 0
    for row in rows:
        if row["status"] != "error":
            continue
        raw = row["raw"]
        cells = [safe_cell(str(raw.get(field.key, ""))) for field in fields]
        cells.append(safe_cell(" | ".join(rejection_text(issue) for issue in row["issues"])))
        writer.writerow(cells)
        written += 1
    if written == 0:
        return ""
    return "\ufeff" + buffer.getvalue()
