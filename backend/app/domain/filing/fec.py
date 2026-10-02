"""Deterministic FEC built only from validated ledger lines.

Column order follows the project contract in docs/FEC.md (LPF art. A47 A-1 annex).
"""

import hashlib
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.models import Account, AccountingEntry, AccountingEntryLine, AccountingJournal
from app.services.ledger import fail, get_year

COLUMNS = (
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "CompAuxNum",
    "CompAuxLib",
    "PieceRef",
    "PieceDate",
    "EcritureLib",
    "Debit",
    "Credit",
    "EcritureLet",
    "DateLet",
    "ValidDate",
    "Montantdevise",
    "Idevise",
)


def render_fec(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    rows = session.execute(
        select(AccountingEntryLine, AccountingEntry, AccountingJournal, Account)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .join(AccountingJournal, AccountingJournal.code == AccountingEntry.journal_code)
        .join(Account, Account.number == AccountingEntryLine.account_number)
        .where(
            AccountingEntry.fiscal_year_id == year.id,
            AccountingEntry.status == "VALIDATED",
            # A47 A-1 : après inventaire, hors centralisation et hors solde des classes 6/7.
            AccountingEntry.source_type != "CENTRALIZATION",
        )
        .order_by(
            AccountingEntry.accounting_date,
            AccountingEntry.journal_code,
            AccountingEntry.sequence,
            AccountingEntryLine.position,
            AccountingEntryLine.id,
        )
    )
    lines = [_row(line, entry, journal, account) for line, entry, journal, account in rows]
    payload = ("\t".join(COLUMNS) + "\r\n" + "".join(_format(line) for line in lines)).encode(
        "utf-8"
    )
    return {
        "fiscal_year_id": year.id,
        "filename": f"FEC{year.end_date.strftime('%Y%m%d')}.txt",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "content": payload,
        "line_count": len(lines),
        "validation": validate_fec(payload, year.start_date, year.end_date),
    }


def export_fec(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    if year.status != "CLOSED":
        fail("YEAR_NOT_CLOSED", "Le FEC s’exporte depuis un exercice clôturé.")
    rendered = render_fec(session, year_id)
    if rendered["validation"]["errors"]:
        fail("FEC_INVALID", "Le FEC contient des erreurs et n’est pas exportable.")
    return rendered


def validate_fec(payload: bytes, start: date, end: date) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    text = payload.decode("utf-8")
    raw_lines = text.split("\r\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]
    if not raw_lines or raw_lines[0].split("\t") != list(COLUMNS):
        errors.append({"code": "HEADER", "message": "En-tête FEC absent ou dans le mauvais ordre."})
        return _report(errors, warnings, payload)
    parsed: list[dict[str, str]] = []
    for index, raw in enumerate(raw_lines[1:], start=2):
        cells = raw.split("\t")
        if len(cells) != 18:
            errors.append({"code": "COLUMN_COUNT", "message": f"Ligne {index} : 18 champs requis."})
            continue
        row = dict(zip(COLUMNS, cells, strict=True))
        parsed.append(row)
        if not all(
            row[name] for name in ("JournalCode", "EcritureNum", "CompteNum", "EcritureLib")
        ):
            errors.append(
                {"code": "REQUIRED", "message": f"Ligne {index} : champ obligatoire vide."}
            )
        for field in ("EcritureDate", "PieceDate", "ValidDate"):
            if _date(row[field]) is None:
                errors.append({"code": "DATE", "message": f"Ligne {index} : {field} invalide."})
        if _amount(row["Debit"]) is None or _amount(row["Credit"]) is None:
            errors.append({"code": "AMOUNT", "message": f"Ligne {index} : montant invalide."})
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in parsed:
        grouped.setdefault(row["EcritureNum"], []).append(row)
    for number, group in grouped.items():
        debit = sum(_amount(row["Debit"]) or 0 for row in group)
        credit = sum(_amount(row["Credit"]) or 0 for row in group)
        if debit != credit:
            errors.append({"code": "UNBALANCED", "message": f"Écriture {number} déséquilibrée."})
        dates = [_date(row["EcritureDate"]) for row in group]
        if any(value is None or not start <= value <= end for value in dates):
            errors.append(
                {"code": "DATE_OUTSIDE_YEAR", "message": f"Écriture {number} hors exercice."}
            )
    if not any(row["JournalCode"] == "AN" for row in parsed) and parsed:
        warnings.append(
            {"code": "OPENING_ABSENT", "message": "Aucune ligne d’à-nouveaux détectée."}
        )
    return _report(errors, warnings, payload)


def _row(
    line: AccountingEntryLine,
    entry: AccountingEntry,
    journal: AccountingJournal,
    account: Account,
) -> dict[str, str]:
    validated = entry.validated_at or datetime.min
    return {
        "JournalCode": entry.journal_code,
        "JournalLib": entry.journal_label or journal.label,
        "EcritureNum": entry.entry_number or "",
        "EcritureDate": entry.accounting_date.strftime("%Y%m%d"),
        "CompteNum": line.account_number,
        "CompteLib": line.account_label or account.label,
        "CompAuxNum": "",
        "CompAuxLib": "",
        "PieceRef": entry.piece_reference,
        "PieceDate": entry.piece_date.strftime("%Y%m%d"),
        "EcritureLib": line.label,
        "Debit": _money(to_cents(line.debit)),
        "Credit": _money(to_cents(line.credit)),
        "EcritureLet": "",
        "DateLet": "",
        "ValidDate": validated.strftime("%Y%m%d"),
        "Montantdevise": "",
        "Idevise": "",
    }


def _format(row: dict[str, str]) -> str:
    return "\t".join(row[column] for column in COLUMNS) + "\r\n"


def _money(cents: int) -> str:
    whole, fractional = divmod(abs(cents), 100)
    return f"{whole},{fractional:02d}"


def _amount(value: str) -> int | None:
    if not value or "," not in value:
        return None
    whole, fractional = value.split(",", 1)
    if not whole.isdigit() or len(fractional) != 2 or not fractional.isdigit():
        return None
    return int(whole) * 100 + int(fractional)


def _date(value: str) -> date | None:
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _report(
    errors: list[dict[str, str]], warnings: list[dict[str, str]], payload: bytes
) -> dict[str, Any]:
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
