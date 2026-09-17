"""Business postings reuse the ledger; no parallel accounting totals."""

import csv
import hashlib
import io
import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import EntryInput, ReversalInput
from app.api.operation_schemas import LoanPaymentInput, OperationInput, SettlementInput
from app.core.money import to_cents
from app.models import Account, AccountingEntry, AccountingEntryLine, Property
from app.models.operations import BankAccount, BankMatch, BankTransaction, BusinessOperation, Loan
from app.services.ledger import (
    create_draft,
    event,
    fail,
    get_entry,
    get_year,
    money,
    post_entry,
    reverse_entry,
)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def account(session: Session, number: str, prefix: str) -> Account:
    row = session.get(Account, number)
    if row is None or not row.active or not number.startswith(prefix):
        fail("ACCOUNT_KIND", f"Compte actif de classe {prefix} requis.", 422)
    return row


def bank(session: Session, bank_id: int) -> BankAccount:
    row = session.get(BankAccount, bank_id)
    if row is None:
        fail("BANK_NOT_FOUND", "Compte bancaire introuvable.", 404)
    account(session, row.account_number, "512")
    return row


def property_exists(session: Session, property_id: int) -> Property:
    row = session.get(Property, property_id)
    if row is None:
        fail("PROPERTY_NOT_FOUND", "Bien introuvable.", 404)
    return row


def reversed_entry(session: Session, entry_id: int) -> AccountingEntry | None:
    return session.scalar(
        select(AccountingEntry).where(
            AccountingEntry.reversal_of_id == entry_id, AccountingEntry.status == "VALIDATED"
        )
    )


def remaining(session: Session, row: BusinessOperation) -> int:
    if row.bank_account_id is not None or reversed_entry(session, row.accounting_entry_id):
        return 0
    used = sum(
        to_cents(child.amount)
        for child in session.scalars(
            select(BusinessOperation).where(BusinessOperation.parent_id == row.id)
        )
        if not reversed_entry(session, child.accounting_entry_id)
    )
    return to_cents(row.amount) - used


def operation_json(session: Session, row: BusinessOperation) -> dict[str, Any]:
    reversal = reversed_entry(session, row.accounting_entry_id)
    return {
        "id": row.id,
        "request_id": row.request_id,
        "kind": row.kind,
        "property_id": row.property_id,
        "fiscal_year_id": row.fiscal_year_id,
        "date": row.date.isoformat(),
        "amount": money(to_cents(row.amount)),
        "description": row.description,
        "counterparty": row.counterparty,
        "accounting_account": row.accounting_account,
        "bank_account_id": row.bank_account_id,
        "accounting_entry_id": row.accounting_entry_id,
        "loan_id": row.loan_id,
        "parent_id": row.parent_id,
        "status": "REVERSED" if reversal else "POSTED",
        "reversal_entry_id": reversal.id if reversal else None,
        "remaining_to_settle": money(remaining(session, row))
        if row.kind in {"REVENUE", "EXPENSE"}
        else None,
        "deductible_percentage": money(row.deductible_basis_points),
        "fiscal_treatment": row.fiscal_treatment,
        **{
            key: money(to_cents(getattr(row, key)))
            for key in ("principal", "interest", "insurance", "other_costs")
        },
    }


def replay(session: Session, request_id: str, payload: dict[str, Any]) -> BusinessOperation | None:
    existing = session.scalar(
        select(BusinessOperation).where(BusinessOperation.request_id == request_id)
    )
    if existing and existing.request_hash != digest(payload):
        fail("IDEMPOTENCY_CONFLICT", "Cette référence de requête correspond à une autre opération.")
    return existing


def line(number: str, debit: int, credit: int, label: str) -> dict[str, str]:
    return {
        "account_number": number,
        "label": label,
        "debit": money(debit),
        "credit": money(credit),
    }


def post_business(
    session: Session,
    *,
    payload: dict[str, Any],
    kind: str,
    property_id: int,
    year_id: int,
    day: date,
    piece_date: date,
    piece: str,
    description: str,
    amount: Decimal,
    accounting_account: str,
    lines: list[dict[str, str]],
    bank_id: int | None,
    bank_transaction_id: int | None = None,
    counterparty: str = "",
    parent_id: int | None = None,
    loan_id: int | None = None,
    deductible: int = 10000,
    fiscal_treatment: str = "REQUIRES_REVIEW",
    principal: Decimal = Decimal("0.00"),
    interest: Decimal = Decimal("0.00"),
    insurance: Decimal = Decimal("0.00"),
    other_costs: Decimal = Decimal("0.00"),
) -> BusinessOperation:
    property_exists(session, property_id)
    entry = create_draft(
        session,
        EntryInput.model_validate(
            {
                "fiscal_year_id": year_id,
                "journal_code": "BQ" if bank_id else ("VE" if kind == "REVENUE" else "AC"),
                "accounting_date": day,
                "piece_date": piece_date,
                "piece_reference": piece,
                "label": description,
                "lines": lines,
            }
        ),
    )
    entry.source_type = kind
    entry.source_id = payload["request_id"]
    post_entry(session, entry, entry.version)
    row = BusinessOperation(
        request_id=payload["request_id"],
        request_hash=digest(payload),
        kind=kind,
        property_id=property_id,
        fiscal_year_id=year_id,
        date=day,
        amount=amount,
        description=description,
        counterparty=counterparty,
        accounting_account=accounting_account,
        bank_account_id=bank_id,
        parent_id=parent_id,
        loan_id=loan_id,
        accounting_entry_id=entry.id,
        deductible_basis_points=deductible,
        fiscal_treatment=fiscal_treatment,
        principal=principal,
        interest=interest,
        insurance=insurance,
        other_costs=other_costs,
    )
    session.add(row)
    session.flush()
    if bank_transaction_id is not None:
        if bank_id is None:
            fail("BANK_REQUIRED", "Un mouvement bancaire exige un règlement bancaire.", 422)
        number = bank(session, bank_id).account_number
        candidates = [item for item in entry.lines if item.account_number == number]
        if len(candidates) != 1:
            fail("BANK_LINE_AMBIGUOUS", "Une ligne bancaire unique est requise.")
        match(session, bank_transaction_id, candidates[0].id)
    event(session, "BUSINESS_POSTED", entry, {"operation_id": row.id, "kind": kind})
    return row


def create_operation(session: Session, data: OperationInput) -> BusinessOperation:
    payload = data.model_dump(mode="json")
    old = replay(session, data.request_id, payload)
    if old:
        return old
    account(session, data.accounting_account, "7" if data.kind == "REVENUE" else "6")
    number = (
        bank(session, data.bank_account_id).account_number
        if data.bank_account_id
        else ("411000" if data.kind == "REVENUE" else "401000")
    )
    account(
        session,
        number,
        "512" if data.bank_account_id else ("411" if data.kind == "REVENUE" else "401"),
    )
    amount = to_cents(data.amount)
    lines = (
        [
            line(number, amount, 0, data.description),
            line(data.accounting_account, 0, amount, data.description),
        ]
        if data.kind == "REVENUE"
        else [
            line(data.accounting_account, amount, 0, data.description),
            line(number, 0, amount, data.description),
        ]
    )
    return post_business(
        session,
        payload=payload,
        kind=data.kind,
        property_id=data.property_id,
        year_id=data.fiscal_year_id,
        day=data.date,
        piece_date=data.piece_date,
        piece=data.piece_reference,
        description=data.description,
        amount=data.amount,
        accounting_account=data.accounting_account,
        lines=lines,
        bank_id=data.bank_account_id,
        bank_transaction_id=data.bank_transaction_id,
        counterparty=data.counterparty,
        deductible=to_cents(data.deductible_percentage),
        fiscal_treatment=data.fiscal_treatment,
    )


def settle(session: Session, parent_id: int, data: SettlementInput) -> BusinessOperation:
    payload = {**data.model_dump(mode="json"), "parent_id": parent_id, "kind": "SETTLEMENT"}
    old = replay(session, data.request_id, payload)
    if old:
        return old
    parent = session.get(BusinessOperation, parent_id)
    if parent is None or parent.kind not in {"REVENUE", "EXPENSE"}:
        fail("OPERATION_NOT_FOUND", "Recette ou dépense introuvable.", 404)
    if data.date < parent.date or to_cents(data.amount) > remaining(session, parent):
        fail("SETTLEMENT_EXCEEDS", "Date antérieure à l’opération ou règlement supérieur au solde.")
    number = bank(session, data.bank_account_id).account_number
    control = "411000" if parent.kind == "REVENUE" else "401000"
    amount = to_cents(data.amount)
    description = "Règlement : " + parent.description[:280]
    lines = (
        [line(number, amount, 0, description), line(control, 0, amount, description)]
        if parent.kind == "REVENUE"
        else [line(control, amount, 0, description), line(number, 0, amount, description)]
    )
    return post_business(
        session,
        payload=payload,
        kind="SETTLEMENT",
        property_id=parent.property_id,
        year_id=data.fiscal_year_id,
        day=data.date,
        piece_date=data.date,
        piece=data.piece_reference,
        description=description,
        amount=data.amount,
        accounting_account=control,
        lines=lines,
        bank_id=data.bank_account_id,
        bank_transaction_id=data.bank_transaction_id,
        parent_id=parent.id,
    )


def principal_balance(session: Session, loan: Loan) -> int:
    # This is a lifetime movement sum, not an annual balance. Generated openings
    # repeat historical liabilities already included below. Keep manual initial
    # balances and reversals; exclude only the application's generated carryovers.
    rows = session.execute(
        select(AccountingEntryLine.credit, AccountingEntryLine.debit)
        .join(AccountingEntry)
        .where(
            AccountingEntry.status == "VALIDATED",
            AccountingEntry.source_type != "OPENING",
            AccountingEntryLine.account_number == loan.principal_account,
        )
    )
    return sum(to_cents(credit) - to_cents(debit) for credit, debit in rows)


def loan_post(
    session: Session, loan_id: int, data: SettlementInput, funding: bool
) -> BusinessOperation:
    payload = {
        **data.model_dump(mode="json"),
        "loan_id": loan_id,
        "kind": "LOAN_FUNDING" if funding else "LOAN_PAYMENT",
    }
    old = replay(session, data.request_id, payload)
    if old:
        return old
    loan = session.get(Loan, loan_id)
    if loan is None:
        fail("LOAN_NOT_FOUND", "Emprunt introuvable.", 404)
    account(session, loan.principal_account, "164")
    bank_number = bank(session, data.bank_account_id).account_number
    latest = session.scalar(
        select(AccountingEntry.accounting_date)
        .join(AccountingEntryLine)
        .where(
            AccountingEntry.status == "VALIDATED",
            AccountingEntryLine.account_number == loan.principal_account,
        )
        .order_by(AccountingEntry.accounting_date.desc())
        .limit(1)
    )
    if data.date < loan.start_date or (latest is not None and data.date < latest):
        fail("LOAN_CHRONOLOGY", "Saisissez les mouvements de l’emprunt dans l’ordre chronologique.")
    description = ("Déblocage" if funding else "Échéance") + " : " + loan.lender
    amount = to_cents(data.amount)
    extra: dict[str, Any] = {}
    if funding:
        prior = session.scalars(
            select(BusinessOperation).where(BusinessOperation.loan_id == loan.id)
        ).all()
        if (
            principal_balance(session, loan) != 0
            or any(not reversed_entry(session, p.accounting_entry_id) for p in prior)
            or data.amount != loan.initial_principal
        ):
            fail(
                "LOAN_ALREADY_FUNDED",
                "Le déblocage unique doit égaler le capital initial d’un emprunt non financé.",
            )
        lines = [
            line(bank_number, amount, 0, description),
            line(loan.principal_account, 0, amount, description),
        ]
    else:
        if not isinstance(data, LoanPaymentInput):
            fail("INVALID_PAYMENT", "Ventilation de l’échéance requise.", 422)
        account(session, data.interest_account, "661")
        account(session, data.insurance_account, "616")
        account(session, data.other_costs_account, "6")
        balance = principal_balance(session, loan)
        if balance <= 0:
            fail("LOAN_NOT_FUNDED", "Aucun capital comptable à rembourser pour cet emprunt.")
        if to_cents(data.principal) > balance:
            fail("PRINCIPAL_EXCEEDED", "Le capital remboursé dépasse le solde du compte d’emprunt.")
        lines = []
        for number, value in (
            (loan.principal_account, data.principal),
            (data.interest_account, data.interest),
            (data.insurance_account, data.insurance),
            (data.other_costs_account, data.other_costs),
        ):
            account(session, number, "164" if number == loan.principal_account else "6")
            if to_cents(value):
                lines.append(line(number, to_cents(value), 0, description))
        lines.append(line(bank_number, 0, amount, description))
        extra = {
            key: getattr(data, key) for key in ("principal", "interest", "insurance", "other_costs")
        }
    return post_business(
        session,
        payload=payload,
        kind=payload["kind"],
        property_id=loan.property_id,
        year_id=data.fiscal_year_id,
        day=data.date,
        piece_date=data.date,
        piece=data.piece_reference,
        description=description,
        amount=data.amount,
        accounting_account=loan.principal_account,
        lines=lines,
        bank_id=data.bank_account_id,
        bank_transaction_id=data.bank_transaction_id,
        loan_id=loan.id,
        **extra,
    )


def match(session: Session, transaction_id: int, line_id: int) -> BankMatch:
    transaction = session.get(BankTransaction, transaction_id)
    row = session.get(AccountingEntryLine, line_id)
    if transaction is None or row is None:
        fail("MATCH_NOT_FOUND", "Mouvement ou ligne introuvable.", 404)
    entry = get_entry(session, row.accounting_entry_id)
    year = get_year(session, entry.fiscal_year_id, writable=True)
    number = bank(session, transaction.bank_account_id).account_number
    if (
        entry.status != "VALIDATED"
        or reversed_entry(session, entry.id)
        or row.account_number != number
        or to_cents(row.debit) - to_cents(row.credit) != to_cents(transaction.amount)
        or not year.start_date <= transaction.date <= year.end_date
        or entry.accounting_date != transaction.date
    ):
        fail("MATCH_INCONSISTENT", "Compte, montant signé, exercice ou écriture incompatibles.")
    old = session.get(BankMatch, transaction_id)
    if old:
        if old.entry_line_id == line_id:
            return old
        fail("ALREADY_MATCHED", "Ce mouvement est déjà rapproché.")
    result = BankMatch(transaction_id=transaction_id, entry_line_id=line_id)
    session.add(result)
    event(session, "BANK_MATCHED", entry, {"transaction_id": transaction_id, "line_id": line_id})
    return result


def unmatch(session: Session, transaction_id: int, reason: str) -> None:
    row = session.get(BankMatch, transaction_id)
    if row is None:
        fail("NOT_MATCHED", "Mouvement non rapproché.", 404)
    entry_line = session.get(AccountingEntryLine, row.entry_line_id)
    if entry_line is None:
        fail("LINE_NOT_FOUND", "Ligne introuvable.", 404)
    entry = get_entry(session, entry_line.accounting_entry_id)
    get_year(session, entry.fiscal_year_id, writable=True)
    event(session, "BANK_UNMATCHED", entry, {"transaction_id": transaction_id, "reason": reason})
    session.delete(row)
    session.flush()


def cancel(session: Session, operation_id: int, data: ReversalInput) -> AccountingEntry:
    row = session.get(BusinessOperation, operation_id)
    if row is None:
        fail("OPERATION_NOT_FOUND", "Opération introuvable.", 404)
    if data.accounting_date < row.date:
        fail("REVERSAL_DATE", "L’extourne ne peut pas précéder l’opération.")
    if any(
        not reversed_entry(session, child.accounting_entry_id)
        for child in session.scalars(
            select(BusinessOperation).where(BusinessOperation.parent_id == row.id)
        )
    ):
        fail("SETTLEMENTS_EXIST", "Extournez d’abord les règlements de cette opération.")
    if row.kind == "LOAN_FUNDING":
        loan = session.get(Loan, row.loan_id)
        if loan is None or principal_balance(session, loan) < to_cents(row.amount):
            fail("LOAN_PAYMENTS_EXIST", "Le déblocage ne peut pas être annulé après remboursement.")
    entry = get_entry(session, row.accounting_entry_id)
    matches = session.scalars(
        select(BankMatch)
        .join(AccountingEntryLine)
        .where(AccountingEntryLine.accounting_entry_id == entry.id)
    ).all()
    for item in matches:
        unmatch(session, item.transaction_id, data.reason)
    reversal = reverse_entry(session, entry, data, business=True)
    event(session, "BUSINESS_REVERSED", entry, {"operation_id": row.id, "reason": data.reason})
    return reversal


def parse_csv(content: str) -> list[dict[str, Any]]:
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter=";", strict=True)
        if reader.fieldnames != ["date", "label", "amount", "reference"]:
            fail("CSV_HEADER", "En-tête attendu : date;label;amount;reference", 422)
        rows: list[dict[str, Any]] = []
        references: set[str] = set()
        for index, raw in enumerate(reader, 2):
            if index > 5001 or None in raw or any(value is None for value in raw.values()):
                fail(
                    "CSV_SHAPE", f"Ligne {index} invalide ou limite de 5 000 lignes dépassée.", 422
                )
            label, ref = raw["label"].strip(), raw["reference"].strip()
            value = raw["amount"].strip().replace(",", ".")
            if not label or len(label) > 300 or not ref or len(ref) > 200 or ref in references:
                fail("CSV_REFERENCE", f"Libellé ou référence unique invalide, ligne {index}.", 422)
            if not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]{1,2})?", value):
                fail("CSV_AMOUNT", f"Montant au centime invalide, ligne {index}.", 422)
            amount = to_cents(Decimal(value))
            if not amount:
                fail("CSV_ZERO", f"Mouvement nul, ligne {index}.", 422)
            day = date.fromisoformat(raw["date"].strip())
            normalized = {
                "date": day.isoformat(),
                "label": label,
                "amount": money(amount),
                "reference": ref,
            }
            rows.append({**normalized, "fingerprint": digest(normalized)})
            references.add(ref)
        if not rows:
            fail("CSV_EMPTY", "Le fichier ne contient aucun mouvement.", 422)
        return rows
    except (csv.Error, ValueError, ArithmeticError):
        fail("CSV_INVALID", "CSV invalide : dates ISO et montants au centime requis.", 422)


def import_csv(session: Session, bank_id: int, content: str, commit: bool) -> dict[str, Any]:
    bank(session, bank_id)
    rows = parse_csv(content)
    result = []
    imported = 0
    for data in rows:
        old = session.scalar(
            select(BankTransaction).where(
                BankTransaction.bank_account_id == bank_id,
                BankTransaction.external_reference == data["reference"],
            )
        )
        if old and old.fingerprint != data["fingerprint"]:
            fail("CSV_CONFLICT", "Une référence bancaire existante possède un contenu différent.")
        suggestion = None
        label = data["label"].casefold()
        if Decimal(data["amount"]) > 0 and "loyer" in label:
            suggestion = "706000"
        elif Decimal(data["amount"]) < 0:
            suggestion = (
                "616000" if "assurance" in label else ("627000" if "frais" in label else None)
            )
        result.append({**data, "duplicate": old is not None, "suggested_account": suggestion})
        if commit and old is None:
            session.add(
                BankTransaction(
                    bank_account_id=bank_id,
                    external_reference=data["reference"],
                    date=date.fromisoformat(data["date"]),
                    label=data["label"],
                    amount=Decimal(data["amount"]),
                    fingerprint=data["fingerprint"],
                    import_hash=hashlib.sha256(content.encode()).hexdigest(),
                )
            )
            imported += 1
    if commit:
        event(
            session,
            "BANK_IMPORTED",
            None,
            {
                "bank_account_id": bank_id,
                "imported": imported,
                "duplicates": len(rows) - imported,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
            },
        )
    return {"rows": result, "imported": imported, "count": len(rows)}
