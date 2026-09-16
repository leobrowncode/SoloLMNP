"""Atomic posting and projections from persisted lines only."""

from typing import Any, NoReturn

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import EntryInput, ReversalInput
from app.core.money import MAX_CENTS, to_cents
from app.models import (
    Account,
    AccountingEntry,
    AccountingEntryLine,
    AccountingJournal,
    FiscalYear,
    LedgerEvent,
)
from app.models.base import utc_now


def fail(code: str, message: str, status: int = 409) -> NoReturn:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, fractional = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fractional:02d}"


def entry_json(entry: AccountingEntry) -> dict[str, Any]:
    debit = sum(to_cents(line.debit) for line in entry.lines)
    credit = sum(to_cents(line.credit) for line in entry.lines)
    return {
        "id": entry.id,
        "fiscal_year_id": entry.fiscal_year_id,
        "journal_code": entry.journal_code,
        "journal_label": entry.journal_label,
        "entry_number": entry.entry_number,
        "sequence": entry.sequence,
        "accounting_date": entry.accounting_date.isoformat(),
        "piece_reference": entry.piece_reference,
        "piece_date": entry.piece_date.isoformat(),
        "label": entry.label,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "status": entry.status,
        "version": entry.version,
        "created_at": entry.created_at.isoformat() + "Z",
        "validated_at": entry.validated_at.isoformat() + "Z" if entry.validated_at else None,
        "reversal_of_id": entry.reversal_of_id,
        "total_debit": money(debit),
        "total_credit": money(credit),
        "balanced": debit == credit,
        "lines": [
            {
                "id": line.id,
                "position": line.position,
                "account_number": line.account_number,
                "account_label": line.account_label,
                "label": line.label,
                "debit": money(to_cents(line.debit)),
                "credit": money(to_cents(line.credit)),
            }
            for line in entry.lines
        ],
    }


def event(
    session: Session, action: str, entry: AccountingEntry | None, details: dict[str, Any]
) -> None:
    session.add(LedgerEvent(entry_id=entry.id if entry else None, action=action, details=details))
    session.flush()


def get_year(session: Session, year_id: int, writable: bool = False) -> FiscalYear:
    year = session.get(FiscalYear, year_id)
    if year is None:
        fail("YEAR_NOT_FOUND", "Exercice introuvable.", 404)
    assert year is not None  # noqa: S101
    if writable and year.status != "OPEN":
        fail("YEAR_LOCKED", "L’exercice doit être ouvert pour modifier sa comptabilité.")
    return year


def get_entry(session: Session, entry_id: int) -> AccountingEntry:
    entry = session.get(AccountingEntry, entry_id)
    if entry is None:
        fail("ENTRY_NOT_FOUND", "Écriture introuvable.", 404)
    assert entry is not None  # noqa: S101
    return entry


def check_draft(entry: AccountingEntry, version: int) -> None:
    if entry.version != version:
        fail("VERSION_CONFLICT", "Le brouillon a changé. Rechargez-le avant de continuer.")
    if entry.status != "DRAFT":
        fail("ENTRY_VALIDATED", "Une écriture validée ne peut plus être modifiée.")


def check_input(session: Session, data: EntryInput) -> None:
    year = get_year(session, data.fiscal_year_id, writable=True)
    if not year.start_date <= data.accounting_date <= year.end_date:
        fail("DATE_OUTSIDE_YEAR", "La date comptable doit appartenir à l’exercice.", 422)
    journal = session.get(AccountingJournal, data.journal_code)
    if journal is None or not journal.active:
        fail("INACTIVE_JOURNAL", "Journal absent ou inactif.", 422)
    for number in {line.account_number for line in data.lines}:
        account = session.get(Account, number)
        if account is None or not account.active:
            fail("INACTIVE_ACCOUNT", f"Compte {number} absent ou inactif.", 422)


def apply_input(entry: AccountingEntry, data: EntryInput) -> None:
    for field in (
        "fiscal_year_id",
        "journal_code",
        "accounting_date",
        "piece_reference",
        "piece_date",
        "label",
    ):
        setattr(entry, field, getattr(data, field))
    entry.lines = [
        AccountingEntryLine(
            position=index,
            account_number=line.account_number,
            label=line.label,
            debit=line.debit,
            credit=line.credit,
        )
        for index, line in enumerate(data.lines, 1)
    ]


def create_draft(session: Session, data: EntryInput) -> AccountingEntry:
    check_input(session, data)
    entry = AccountingEntry()
    apply_input(entry, data)
    session.add(entry)
    session.flush()
    event(session, "DRAFT_CREATED", entry, {"after": entry_json(entry)})
    return entry


def replace_draft(session: Session, entry: AccountingEntry, data: EntryInput, version: int) -> None:
    check_draft(entry, version)
    get_year(session, entry.fiscal_year_id, writable=True)
    check_input(session, data)
    before = entry_json(entry)
    # Flush deletions before reusing position numbers (UNIQUE constraint).
    entry.lines.clear()
    session.flush()
    apply_input(entry, data)
    entry.version += 1
    session.flush()
    event(session, "DRAFT_UPDATED", entry, {"before": before, "after": entry_json(entry)})


def post_entry(session: Session, entry: AccountingEntry, version: int) -> AccountingEntry:
    # Repeat validation is a read of the existing immutable result, never a new posting.
    if entry.status == "VALIDATED":
        return entry
    check_draft(entry, version)
    year = get_year(session, entry.fiscal_year_id, writable=True)
    journal = session.get(AccountingJournal, entry.journal_code)
    if journal is None or not journal.active:
        fail("INACTIVE_JOURNAL", "Le journal n’est plus actif.")
    if not year.start_date <= entry.accounting_date <= year.end_date:
        fail("DATE_OUTSIDE_YEAR", "Date hors exercice.")
    if entry.accounting_date > utc_now().date():
        fail("FUTURE_DATE", "Une écriture future ne peut pas être validée.")
    if len(entry.lines) < 2:
        fail("TOO_FEW_LINES", "Au moins deux lignes sont nécessaires.")
    debit = sum(to_cents(line.debit) for line in entry.lines)
    credit = sum(to_cents(line.credit) for line in entry.lines)
    if debit != credit:
        fail("UNBALANCED", "Le total débit doit être égal au total crédit.")
    if debit > MAX_CENTS:
        fail("TOTAL_TOO_LARGE", "Le total de l’écriture dépasse la capacité de stockage.")
    for line in entry.lines:
        account = session.get(Account, line.account_number)
        if account is None or not account.active:
            fail("INACTIVE_ACCOUNT", f"Compte {line.account_number} absent ou inactif.")
        line.account_label = account.label
    # Freeze the labels before the posting trigger observes the transition.
    session.flush()
    sequence = (
        session.scalar(
            select(func.max(AccountingEntry.sequence)).where(
                AccountingEntry.fiscal_year_id == year.id
            )
        )
        or 0
    )
    timestamp = utc_now()
    latest = session.scalar(
        select(func.max(AccountingEntry.validated_at)).where(
            AccountingEntry.fiscal_year_id == year.id
        )
    )
    if latest is not None and timestamp < latest:
        fail("CLOCK_REGRESSION", "L’horloge système précède la dernière validation.")
    entry.sequence = sequence + 1
    entry.entry_number = f"{year.year:04d}-{entry.sequence:06d}"
    entry.journal_label = journal.label
    entry.validated_at = timestamp
    entry.status = "VALIDATED"
    entry.version += 1
    session.flush()
    event(session, "ENTRY_VALIDATED", entry, {"after": entry_json(entry)})
    return entry


def reverse_entry(
    session: Session, original: AccountingEntry, data: ReversalInput, *, business: bool = False
) -> AccountingEntry:
    from app.models.operations import BankMatch

    if original.source_type not in {"MANUAL", "REVERSAL"} and not business:
        fail("BUSINESS_REVERSAL_REQUIRED", "Extournez cette écriture depuis son opération métier.")
    if session.scalar(
        select(BankMatch)
        .join(AccountingEntryLine)
        .where(AccountingEntryLine.accounting_entry_id == original.id)
    ):
        fail("BANK_MATCH_EXISTS", "Annulez d’abord le rapprochement bancaire avec un motif.")
    if original.status != "VALIDATED":
        fail("NOT_VALIDATED", "Seule une écriture validée peut être extournée.")
    if original.reversal_of_id is not None:
        fail("REVERSAL_CHAIN", "Créer une correction explicite plutôt qu’une chaîne d’extournes.")
    if session.scalar(
        select(AccountingEntry.id).where(AccountingEntry.reversal_of_id == original.id)
    ):
        fail("ALREADY_REVERSED", "Une extourne existe déjà pour cette écriture.")
    payload = EntryInput.model_validate(
        {
            "fiscal_year_id": original.fiscal_year_id,
            "journal_code": original.journal_code,
            "accounting_date": data.accounting_date,
            "piece_date": data.accounting_date,
            "piece_reference": data.piece_reference,
            "label": f"Extourne {original.entry_number}",
            "lines": [
                {
                    "account_number": line.account_number,
                    "label": line.label,
                    "debit": money(to_cents(line.credit)),
                    "credit": money(to_cents(line.debit)),
                }
                for line in original.lines
            ],
        }
    )
    entry = create_draft(session, payload)
    entry.reversal_of_id = original.id
    entry.source_type = "REVERSAL"
    entry.source_id = str(original.id)
    session.flush()
    post_entry(session, entry, entry.version)
    event(session, "ENTRY_REVERSED", original, {"reversal_id": entry.id, "reason": data.reason})
    return entry


def projection(session: Session, year_id: int, account: str | None = None) -> dict[str, Any]:
    get_year(session, year_id)
    rows = session.execute(
        select(AccountingEntryLine, AccountingEntry)
        .join(AccountingEntry, AccountingEntry.id == AccountingEntryLine.accounting_entry_id)
        .where(AccountingEntry.fiscal_year_id == year_id, AccountingEntry.status == "VALIDATED")
        .order_by(
            AccountingEntry.accounting_date, AccountingEntry.sequence, AccountingEntryLine.position
        )
    )
    balances: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    total_debit = total_credit = 0
    for line, entry in rows:
        debit, credit = to_cents(line.debit), to_cents(line.credit)
        total_debit += debit
        total_credit += credit
        cell = balances.setdefault(
            line.account_number,
            {
                "account_number": line.account_number,
                "label": line.account_label,
                "debit_cents": 0,
                "credit_cents": 0,
            },
        )
        cell["debit_cents"] += debit
        cell["credit_cents"] += credit
        if account is None or account == line.account_number:
            ledger.append(
                {
                    "account_number": line.account_number,
                    "account_label": line.account_label,
                    "entry_id": entry.id,
                    "entry_number": entry.entry_number,
                    "date": entry.accounting_date.isoformat(),
                    "journal_code": entry.journal_code,
                    "piece_reference": entry.piece_reference,
                    "label": line.label,
                    "debit": money(debit),
                    "credit": money(credit),
                    "balance": money(cell["debit_cents"] - cell["credit_cents"]),
                }
            )
    balance = []
    for number in sorted(balances):
        cell = balances[number]
        net = cell["debit_cents"] - cell["credit_cents"]
        balance.append(
            {
                "account_number": number,
                "label": cell["label"],
                "total_debit": money(cell["debit_cents"]),
                "total_credit": money(cell["credit_cents"]),
                "debit_balance": money(max(net, 0)),
                "credit_balance": money(max(-net, 0)),
            }
        )
    return {
        "fiscal_year_id": year_id,
        "validated_only": True,
        "total_debit": money(total_debit),
        "total_credit": money(total_credit),
        "balanced": total_debit == total_credit,
        "balance": balance,
        "ledger": ledger,
    }
