"""User-facing CSV assistant. Parsing stays in the domain; posting stays in the engine."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, NoReturn, cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.money import to_cents
from app.domain.csv_assistant import (
    CsvReadError,
    add_issue,
    add_warning,
    analyze,
    french_date,
    make_issue,
    rejects_csv,
    settle,
    summarize,
)
from app.domain.csv_import_batch import (
    batch_items,
    fingerprint,
    guard_operations_commit,
    paid_lines_need_bank,
    summarize_batch,
)
from app.models import AccountingEntry, LedgerEvent
from app.models.base import utc_now
from app.models.operations import BankTransaction, BusinessOperation, Loan
from app.services.ledger import event, fail, get_year
from app.services.operations import (
    _same_imported_loan_payment,
    bank,
    digest,
    import_csv,
    import_loan_payments_csv,
    import_operations_csv,
    import_request_id,
    latest_active_principal_movement,
    operations_for_piece,
    principal_balance,
    property_exists,
    replaces_reversed_loan_payment,
    reversed_entry,
    same_imported_operation,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_BATCH_ACTION = "CSV_OPERATIONS_BATCH"
_IMPORT_ACTION = {
    "label": "Revenir à l’import",
    "href": "/operations/transactions#import-operations",
}
_BANK_ACTION = {
    "label": "Ajouter un compte bancaire",
    "href": "/operations/banque#ajouter-banque",
}


def suggest_account(label: str, amount: str) -> str | None:
    folded = label.casefold()
    if Decimal(amount) > 0 and "loyer" in folded:
        return "706000"
    if Decimal(amount) < 0:
        return "616000" if "assurance" in folded else ("627000" if "frais" in folded else None)
    return None


def _fail_read(exc: CsvReadError) -> NoReturn:
    fail(exc.code, exc.message, 422, issues=exc.issues)


def preview_import(
    session: Session,
    profile: str,
    content: str,
    mapping: dict[str, str] | None,
    *,
    bank_account_id: int | None,
    property_id: int | None,
    fiscal_year_id: int | None,
    loan_id: int | None,
) -> dict[str, Any]:
    try:
        result = analyze(profile, content, mapping)
    except CsvReadError as exc:
        _fail_read(exc)
    if not result["ready"]:
        return result
    if profile == "bank":
        if bank_account_id is None:
            fail("BANK_REQUIRED", "Choisissez le compte bancaire.", 422, field="bank_account_id")
        bank(session, bank_account_id)
        _annotate_bank(session, bank_account_id, result["rows"])
    elif profile == "operations":
        if property_id is None:
            fail("PROPERTY_NOT_FOUND", "Choisissez le bien.", 422, field="property_id")
        if fiscal_year_id is None:
            fail("CSV_HEADER", "Choisissez l’exercice ouvert.", 422, field="fiscal_year_id")
        property_exists(session, property_id)
        year = get_year(session, fiscal_year_id, writable=True)
        if bank_account_id is not None:
            bank(session, bank_account_id)
        _annotate_operations(session, property_id, year.id, year, bank_account_id, result["rows"])
        if paid_lines_need_bank(result["rows"], bank_account_id):
            fail(
                "BANK_REQUIRED",
                "Choisissez le compte bancaire des lignes déjà payées.",
                422,
                field="bank_account_id",
                action=_BANK_ACTION,
            )
    else:
        if loan_id is None:
            fail("LOAN_NOT_FOUND", "Choisissez l’emprunt.", 422, field="loan_id")
        if fiscal_year_id is None:
            fail("CSV_HEADER", "Choisissez l’exercice ouvert.", 422, field="fiscal_year_id")
        if bank_account_id is None:
            fail("BANK_REQUIRED", "Choisissez le compte bancaire.", 422, field="bank_account_id")
        loan = session.get(Loan, loan_id)
        if loan is None:
            fail("LOAN_NOT_FOUND", "Emprunt introuvable.", 404)
        year = get_year(session, fiscal_year_id, writable=True)
        bank(session, bank_account_id)
        _annotate_loans(session, loan, year.id, year, bank_account_id, result)
    result["summary"] = summarize(result["rows"])
    result["rejects_csv"] = rejects_csv(profile, result["rows"])
    return result


def commit_import(
    session: Session,
    profile: str,
    content: str,
    mapping: dict[str, str] | None,
    *,
    bank_account_id: int | None,
    property_id: int | None,
    fiscal_year_id: int | None,
    loan_id: int | None,
    confirmed_loan_reference: str | None,
    import_valid_only: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    result = preview_import(
        session,
        profile,
        content,
        mapping,
        bank_account_id=bank_account_id,
        property_id=property_id,
        fiscal_year_id=fiscal_year_id,
        loan_id=loan_id,
    )
    if profile == "operations":
        return _commit_operations(
            session,
            result,
            content,
            mapping,
            property_id=property_id,
            fiscal_year_id=fiscal_year_id,
            bank_account_id=bank_account_id,
            import_valid_only=import_valid_only,
            idempotency_key=idempotency_key,
        )
    if not result["ready"]:
        fail(
            "CSV_HEADER",
            "Associez les colonnes obligatoires avant d’importer.",
            422,
            issues=result["issues"],
        )
    importable = [row for row in result["rows"] if row["importable"]]
    if profile == "loan_payments" and importable:
        reference = result.get("loan_reference")
        if not isinstance(reference, str) or confirmed_loan_reference != reference:
            fail(
                "LOAN_PREVIEW_REQUIRED",
                "Confirmez que le prêt du fichier correspond à l’emprunt choisi.",
            )
    if not importable:
        issues = list(result["issues"])
        for row in result["rows"]:
            issues.extend(row["issues"])
        fail(
            str(issues[0]["code"]) if issues else "CSV_EMPTY",
            str(issues[0]["message"]) if issues else "Aucune ligne importable.",
            422,
            issues=issues or None,
        )
    if profile == "bank":
        if bank_account_id is None:
            fail("BANK_REQUIRED", "Choisissez le compte bancaire.", 422, field="bank_account_id")
        outcome = import_csv(
            session, bank_account_id, content, True, parsed_rows=_bank_payload(importable)
        )
    else:
        if loan_id is None:
            fail("LOAN_NOT_FOUND", "Choisissez l’emprunt.", 422, field="loan_id")
        if fiscal_year_id is None:
            fail("CSV_HEADER", "Choisissez l’exercice ouvert.", 422, field="fiscal_year_id")
        if bank_account_id is None:
            fail("BANK_REQUIRED", "Choisissez le compte bancaire.", 422, field="bank_account_id")
        outcome = import_loan_payments_csv(
            session,
            loan_id,
            fiscal_year_id,
            bank_account_id,
            content,
            True,
            confirmed_loan_reference=confirmed_loan_reference,
            prepared_rows=_loan_payload(importable),
            require_preview_token=False,
        )
    result["imported"] = outcome["imported"]
    return result


def _require_idempotency_key(value: str | None) -> str:
    if value is None or _IDEMPOTENCY_KEY.fullmatch(value) is None:
        fail(
            "IDEMPOTENCY_KEY_REQUIRED",
            "L’en-tête Idempotency-Key est requis : 8 à 80 caractères (lettres, chiffres, _ ou -).",
            422,
            field="Idempotency-Key",
            location="header",
            action=_IMPORT_ACTION,
        )
    return value


def _stored_operations_batch(session: Session, key: str) -> tuple[str, dict[str, Any]] | None:
    row = session.scalar(
        select(LedgerEvent)
        .where(
            LedgerEvent.action == _BATCH_ACTION,
            func.json_extract(LedgerEvent.details, "$.idempotency_key") == key,
        )
        .order_by(LedgerEvent.id.desc())
    )
    if row is None:
        return None
    stored_fingerprint = row.details.get("fingerprint")
    stored_result = row.details.get("result")
    if not isinstance(stored_fingerprint, str) or not isinstance(stored_result, dict):
        fail("IDEMPOTENCY_RECORD_INVALID", "L’import enregistré est illisible.", 500)
    return stored_fingerprint, cast(dict[str, Any], stored_result)


def _replay_operations(
    session: Session,
    idempotency_key: str | None,
    digest: str,
) -> dict[str, Any] | None:
    if idempotency_key is None or _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
        return None
    stored = _stored_operations_batch(session, idempotency_key)
    if stored is None:
        return None
    stored_fingerprint, stored_result = stored
    if stored_fingerprint != digest:
        fail(
            "IDEMPOTENCY_CONFLICT",
            "Cette clé d’idempotence a déjà servi pour un autre import.",
            409,
            action=_IMPORT_ACTION,
        )
    batch = dict(cast(dict[str, Any], stored_result["batch"]))
    batch["replayed"] = True
    return {**stored_result, "batch": batch}


def _commit_operations(
    session: Session,
    result: dict[str, Any],
    content: str,
    mapping: dict[str, str] | None,
    *,
    property_id: int | None,
    fiscal_year_id: int | None,
    bank_account_id: int | None,
    import_valid_only: bool,
    idempotency_key: str | None,
) -> dict[str, Any]:
    digest = fingerprint(
        content=content,
        mapping=mapping,
        property_id=property_id,
        fiscal_year_id=fiscal_year_id,
        bank_account_id=bank_account_id,
        import_valid_only=import_valid_only,
    )
    replayed = _replay_operations(session, idempotency_key, digest)
    if replayed is not None:
        return replayed
    if not result["ready"]:
        fail(
            "CSV_HEADER",
            "Associez les colonnes obligatoires avant d’importer.",
            422,
            issues=result["issues"],
            action=_IMPORT_ACTION,
        )
    if property_id is None:
        fail("PROPERTY_NOT_FOUND", "Choisissez le bien.", 422, field="property_id")
    if fiscal_year_id is None:
        fail("CSV_HEADER", "Choisissez l’exercice ouvert.", 422, field="fiscal_year_id")
    decision = guard_operations_commit(
        result["rows"],
        bank_account_id=bank_account_id,
        import_valid_only=import_valid_only,
    )
    if not decision["ok"]:
        code = str(decision["code"])
        fail(
            code,
            str(decision["message"]),
            int(decision["status"]),
            field="bank_account_id" if code == "BANK_REQUIRED" else None,
            action=_BANK_ACTION if code == "BANK_REQUIRED" else _IMPORT_ACTION,
            issues=decision["issues"],
        )
    key = _require_idempotency_key(idempotency_key)
    outcome = import_operations_csv(
        session,
        property_id,
        fiscal_year_id,
        content,
        True,
        bank_account_id,
        parsed_rows=_operation_payload(decision["importable"]),
    )
    batch = summarize_batch(key, batch_items(result["rows"]), replayed=False)
    stored = {
        "profile": "operations",
        "imported": outcome["imported"],
        "summary": result["summary"],
        "batch": batch,
    }
    event(
        session,
        _BATCH_ACTION,
        None,
        {"idempotency_key": key, "fingerprint": digest, "result": stored},
    )
    result["imported"] = outcome["imported"]
    result["batch"] = batch
    return result


def _bank_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for row in rows:
        normalized = {
            "date": row["values"]["date"],
            "label": row["values"]["label"],
            "amount": row["values"]["amount"],
            "reference": row["values"]["reference"],
        }
        payload.append({**normalized, "fingerprint": digest(normalized)})
    return payload


def _operation_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for row in rows:
        values = row["values"]
        payload.append(
            {
                "kind": values["kind"],
                "date": values["date"],
                "piece_date": values["piece_date"],
                "type": values["type"],
                "accounting_account": values["accounting_account"],
                "counterparty": values["counterparty"],
                "amount": values["amount"],
                "description": values["description"],
                "piece_reference": values["piece_reference"],
                "source_file": values.get("source_file", ""),
                "paid": bool(row["paid"]),
            }
        )
    return payload


def _loan_payload(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    payload = []
    for row in rows:
        values = row["values"]
        payload.append(
            {
                "loan_reference": str(values["loan_reference"]),
                "rank": str(values.get("rank", "")),
                "due_date": str(values["due_date"]),
                "date": str(values["date"]),
                "principal": str(values["principal"]),
                "interest": str(values["interest"]),
                "insurance": str(values["insurance"]),
                "other_costs": str(values["other_costs"]),
                "amount": str(values["amount"]),
            }
        )
    return payload


def _annotate_bank(session: Session, bank_id: int, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row["status"] == "error":
            continue
        values = row["values"]
        row["suggested_account"] = suggest_account(str(values["label"]), str(values["amount"]))
        normalized = {
            "date": values["date"],
            "label": values["label"],
            "amount": values["amount"],
            "reference": values["reference"],
        }
        old = session.scalar(
            select(BankTransaction).where(
                BankTransaction.bank_account_id == bank_id,
                BankTransaction.external_reference == values["reference"],
            )
        )
        if old is None:
            continue
        if old.fingerprint != digest(normalized):
            add_issue(
                row,
                make_issue(
                    "CSV_CONFLICT",
                    "Cette référence existe déjà avec un autre contenu.",
                    field="reference",
                    column="Référence",
                    value=str(values["reference"]),
                    correction=(
                        "Corrigez la ligne pour qu’elle soit identique, ou changez la référence. "
                        "Un mouvement déjà importé ne se réécrit pas."
                    ),
                    line=row["line"],
                ),
            )
        else:
            row["duplicate"] = True
            settle(row)


def _annotate_operations(
    session: Session,
    property_id: int,
    year_id: int,
    year: Any,
    bank_account_id: int | None,
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        values = row["values"]
        if "date" in values:
            day = date.fromisoformat(str(values["date"]))
            if not year.start_date <= day <= year.end_date:
                add_issue(
                    row,
                    make_issue(
                        "DATE_OUTSIDE_YEAR",
                        "Date comptable hors exercice.",
                        field="date",
                        column="Date",
                        value=str(row["display"].get("date") or values["date"]),
                        correction=(
                            "Saisissez une date entre le "
                            f"{french_date(year.start_date.isoformat())} et le "
                            f"{french_date(year.end_date.isoformat())}."
                        ),
                        line=row["line"],
                        help_id="exercice",
                    ),
                )
        if row.get("paid") and bank_account_id is None and not row["issues"]:
            add_issue(
                row,
                make_issue(
                    "BANK_REQUIRED",
                    "Choisissez le compte bancaire des lignes déjà payées.",
                    field="paid",
                    column="Déjà payée",
                    value="oui",
                    correction=(
                        "Choisissez le compte, ou indiquez non pour laisser la ligne à régler."
                    ),
                    line=row["line"],
                    help_id="compte-512",
                ),
            )
        if row["status"] == "error" or "piece_reference" not in values:
            continue
        data = {
            "kind": values["kind"],
            "date": values["date"],
            "piece_date": values["piece_date"],
            "amount": values["amount"],
            "description": values["description"],
            "counterparty": values["counterparty"],
            "accounting_account": values["accounting_account"],
            "piece_reference": values["piece_reference"],
        }
        request_id = import_request_id(str(data["piece_reference"]))
        by_request = session.scalar(
            select(BusinessOperation).where(BusinessOperation.request_id == request_id)
        )
        matches = operations_for_piece(session, str(data["piece_reference"]))
        found = {item.id: item for item in matches}
        if by_request is not None:
            found[by_request.id] = by_request
        reference = str(data["piece_reference"])
        if len(found) > 1:
            add_issue(
                row,
                make_issue(
                    "CSV_CONFLICT",
                    f"La référence {reference} correspond à plusieurs opérations.",
                    field="piece_reference",
                    column="Référence de pièce",
                    value=reference,
                    correction="Une référence ne peut viser qu’une opération. Corrigez le fichier.",
                    line=row["line"],
                ),
            )
        elif found:
            existing = next(iter(found.values()))
            if not same_imported_operation(session, existing, data, property_id, year_id):
                add_issue(
                    row,
                    make_issue(
                        "CSV_CONFLICT",
                        f"La référence {reference} existe avec un contenu différent.",
                        field="piece_reference",
                        column="Référence de pièce",
                        value=reference,
                        correction="Alignez le montant, le tiers et les dates sur l’opération déjà "
                        "comptabilisée, ou extournez-la avant un nouvel import. "
                        "Une écriture validée ne se modifie pas.",
                        line=row["line"],
                    ),
                )
            else:
                row["duplicate"] = True
                settle(row)


def _loan_refs(rows: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for row in rows:
        reference = str(row["values"].get("loan_reference") or "")
        if reference and reference not in found:
            found.append(reference)
    return found


def _annotate_loans(
    session: Session,
    loan: Loan,
    year_id: int,
    year: Any,
    bank_id: int,
    result: dict[str, Any],
) -> None:
    rows: list[dict[str, Any]] = result["rows"]
    references = _loan_refs(rows)
    result["loan_reference"] = references[0] if len(references) == 1 else None
    if len(references) > 1:
        result["issues"].append(
            make_issue(
                "LOAN_CSV_MULTIPLE_LOANS",
                "Plusieurs références de prêt sont présentes.",
                field="loan_reference",
                column="Prêt",
                value=", ".join(references),
                correction="Découpez le fichier pour n’importer qu’un seul prêt à la fois.",
                line=1,
                help_id="emprunt",
            )
        )
        for row in rows:
            reference = str(row["values"].get("loan_reference") or "")
            if reference:
                add_issue(
                    row,
                    make_issue(
                        "LOAN_CSV_MULTIPLE_LOANS",
                        "Cette ligne appartient à un fichier qui mélange plusieurs prêts.",
                        field="loan_reference",
                        column="Prêt",
                        value=reference,
                        correction="Laissez une seule référence de prêt dans le fichier.",
                        line=row["line"],
                        help_id="emprunt",
                    ),
                )
    today = utc_now().date()
    for row in rows:
        if row["status"] == "error":
            continue
        values = row["values"]
        if "date" not in values or "due_date" not in values:
            continue
        payment_day = date.fromisoformat(str(values["date"]))
        due_day = date.fromisoformat(str(values["due_date"]))
        if payment_day < loan.start_date:
            add_issue(
                row,
                make_issue(
                    "LOAN_CSV_BEFORE_START",
                    "L’échéance du "
                    f"{french_date(payment_day.isoformat())} précède le début de l’emprunt.",
                    field="payment_date",
                    column="Date de débit",
                    value=str(row["display"].get("payment_date") or values["date"]),
                    correction=(
                        "Saisissez une date à partir du "
                        f"{french_date(loan.start_date.isoformat())}."
                    ),
                    line=row["line"],
                    help_id="emprunt",
                ),
            )
            continue
        if not year.start_date <= payment_day <= year.end_date:
            add_warning(
                row,
                make_issue(
                    "DATE_OUTSIDE_YEAR",
                    "Échéance hors exercice : elle ne sera pas comptabilisée.",
                    field="payment_date",
                    column="Date de débit",
                    value=str(row["display"].get("payment_date") or values["date"]),
                    correction=(
                        "Réservez cette ligne à l’exercice du "
                        f"{french_date(year.start_date.isoformat())} au "
                        f"{french_date(year.end_date.isoformat())}."
                    ),
                    line=row["line"],
                    help_id="exercice",
                ),
                importable=False,
            )
            continue
        if payment_day > today:
            add_warning(
                row,
                make_issue(
                    "LOAN_CSV_DATE",
                    "Échéance future : elle ne sera pas comptabilisée avant sa date.",
                    field="payment_date",
                    column="Date de débit",
                    value=str(row["display"].get("payment_date") or values["date"]),
                    correction="Importez cette échéance le jour où elle est prélevée, ou après.",
                    line=row["line"],
                    help_id="emprunt",
                ),
                importable=False,
            )
            continue
        piece_base = f"ECH-{loan.principal_account}-{due_day.isoformat()}"
        prior = list(
            session.scalars(
                select(BusinessOperation)
                .join(AccountingEntry)
                .where(
                    BusinessOperation.kind == "LOAN_PAYMENT",
                    BusinessOperation.loan_id == loan.id,
                    or_(
                        BusinessOperation.date == payment_day,
                        AccountingEntry.piece_reference.like(piece_base + "%"),
                    ),
                )
            )
        )
        active = [
            item for item in prior if reversed_entry(session, item.accounting_entry_id) is None
        ]
        data = {
            "date": values["date"],
            "amount": values["amount"],
            "principal": values["principal"],
            "interest": values["interest"],
            "insurance": values["insurance"],
            "other_costs": values["other_costs"],
        }
        if len(active) > 1:
            add_issue(
                row,
                make_issue(
                    "LOAN_CSV_CONFLICT",
                    f"Plusieurs échéances actives existent déjà le {values['date']}.",
                    field="payment_date",
                    column="Date de débit",
                    value=str(values["date"]),
                    correction="Extournez les échéances en trop avant un nouvel import.",
                    line=row["line"],
                    help_id="emprunt",
                ),
            )
        elif active and not _same_imported_loan_payment(active[0], data, loan, year_id, bank_id):
            add_issue(
                row,
                make_issue(
                    "LOAN_CSV_CONFLICT",
                    f"L’échéance du {values['date']} existe avec une ventilation différente.",
                    field="amount",
                    column="Total banque",
                    value=str(row["display"].get("amount") or values["amount"]),
                    correction=(
                        "Reprenez la ventilation déjà comptabilisée, ou extournez l’échéance. "
                        "Une écriture validée ne se modifie pas."
                    ),
                    line=row["line"],
                    help_id="emprunt",
                ),
            )
        elif active:
            row["duplicate"] = True
            settle(row)
    new_rows = [row for row in rows if row["importable"]]
    if not new_rows:
        return
    latest = latest_active_principal_movement(session, loan)
    balance = principal_balance(session, loan)
    running = 0
    ordered = sorted(new_rows, key=lambda item: str(item["values"]["date"]))
    for row in ordered:
        if not row["importable"]:
            continue
        values = row["values"]
        day = date.fromisoformat(str(values["date"]))
        piece = f"ECH-{loan.principal_account}-{values['due_date']}"
        if (
            latest is not None
            and day < latest
            and not replaces_reversed_loan_payment(session, loan.id, day, piece)
        ):
            add_issue(
                row,
                make_issue(
                    "LOAN_CHRONOLOGY",
                    "Cette échéance précède le dernier mouvement comptable de l’emprunt.",
                    field="payment_date",
                    column="Date de débit",
                    value=str(row["display"].get("payment_date") or values["date"]),
                    correction="Importez les échéances dans l’ordre, après le dernier mouvement.",
                    line=row["line"],
                    help_id="emprunt",
                ),
            )
            continue
        running += to_cents(Decimal(str(values["principal"])))
        if balance <= 0:
            add_issue(
                row,
                make_issue(
                    "LOAN_NOT_FUNDED",
                    "Reprenez le capital restant dû ou comptabilisez le déblocage avant l’import.",
                    field="principal",
                    column="Capital",
                    value=str(row["display"].get("principal") or values["principal"]),
                    correction=(
                        "Comptabilisez le déblocage, ou saisissez le capital restant dû à l’entrée."
                    ),
                    line=row["line"],
                    help_id="compte-164",
                ),
            )
        elif running > balance:
            add_issue(
                row,
                make_issue(
                    "PRINCIPAL_EXCEEDED",
                    "Le capital cumulé de cette échéance dépasse le solde de l’emprunt.",
                    field="principal",
                    column="Capital",
                    value=str(row["display"].get("principal") or values["principal"]),
                    correction=(
                        "Réduisez le capital de la ligne pour rester dans le solde restant dû."
                    ),
                    line=row["line"],
                    help_id="compte-164",
                ),
            )
