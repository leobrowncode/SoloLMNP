"""Explicit, atomic opening posting and account-by-account continuity checks."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import EntryInput, OpeningInput
from app.core.money import MAX_CENTS, to_cents
from app.models import Account, AccountingEntry, AccountingJournal, LedgerEvent
from app.services.ledger import create_draft, entry_json, event, fail, get_year, money, post_entry
from app.services.opening import _report_cents, opening_preview


def existing_opening(session: Session, year_id: int) -> AccountingEntry | None:
    return session.scalar(
        select(AccountingEntry).where(
            AccountingEntry.fiscal_year_id == year_id,
            AccountingEntry.source_type == "OPENING",
        )
    )


def opening_request(session: Session, entry: AccountingEntry) -> dict[str, Any]:
    audit = session.scalar(
        select(LedgerEvent).where(
            LedgerEvent.entry_id == entry.id,
            LedgerEvent.action == "OPENING_GENERATED",
        )
    )
    if audit is None:
        fail("OPENING_AUDIT_MISSING", "La trace de génération des à-nouveaux est absente.")
    assert audit is not None  # noqa: S101
    return dict(audit.details)


def expected_balances(preview: dict[str, Any], result_account: str | None) -> dict[str, int]:
    balances = {
        row["account_number"]: _report_cents(row["debit"]) - _report_cents(row["credit"])
        for row in preview["lines"]
    }
    result = _report_cents(preview["previous_result"])
    if result:
        if result_account is None:
            fail("RESULT_ACCOUNT_REQUIRED", "Choisissez un compte de reprise du résultat.")
        assert result_account is not None  # noqa: S101
        balances[result_account] = balances.get(result_account, 0) - result
    return {number: net for number, net in balances.items() if net}


def generate_opening(session: Session, year_id: int, data: OpeningInput) -> dict[str, Any]:
    preview = opening_preview(session, year_id)
    if data.preview_token != preview["preview_token"]:
        fail(
            "OPENING_PREVIEW_CHANGED",
            "Les soldes source ont changé. Actualisez la prévisualisation.",
        )
    source = get_year(session, preview["source_fiscal_year_id"])
    if source.status != "CLOSED":
        fail("SOURCE_NOT_CLOSED", "Clôturez l’exercice précédent avant de générer les à-nouveaux.")
    if preview["excluded_draft_count"]:
        fail("SOURCE_DRAFTS", "L’exercice précédent contient encore des brouillons.")
    request = data.model_dump(mode="json")
    existing = existing_opening(session, year_id)
    if existing is not None:
        if opening_request(session, existing)["request"] != request:
            fail("OPENING_ALREADY_EXISTS", "Des à-nouveaux existent avec d’autres paramètres.")
        return {"created": False, "entry": entry_json(existing)}
    target = get_year(session, year_id, writable=True)
    # Until reconciliation of manual imports is implemented, refuse any target
    # entry (including drafts) instead of risking a duplicate opening balance.
    if preview["target_entry_count"]:
        fail("TARGET_HAS_ENTRIES", "L’exercice destinataire doit être vide avant la génération.")
    journal = session.get(AccountingJournal, data.journal_code)
    if journal is None or not journal.active or journal.journal_type != "OPENING":
        fail("OPENING_JOURNAL_REQUIRED", "Choisissez un journal actif de type à-nouveaux.")
    result = _report_cents(preview["previous_result"])
    if result:
        account = session.get(Account, data.result_account) if data.result_account else None
        prefix = "120" if result > 0 else "129"
        if (
            account is None
            or not account.active
            or account.account_type != "EQUITY"
            or not account.number.startswith(prefix)
            or account.number.startswith("1209")
        ):
            fail(
                "INVALID_RESULT_ACCOUNT",
                f"Choisissez un compte actif de capitaux propres {prefix} "
                "(hors acomptes sur dividendes) pour la reprise avant affectation.",
            )
    elif data.result_account is not None:
        fail(
            "UNEXPECTED_RESULT_ACCOUNT",
            "Aucun compte de résultat n’est requis pour un résultat nul.",
        )
    if any(w["code"] == "INACTIVE_ACCOUNTS" for w in preview["warnings"]):
        fail("INACTIVE_ACCOUNT", "Réactivez les comptes de bilan à reprendre avant la génération.")
    balances = expected_balances(preview, data.result_account)
    if not balances:
        fail("EMPTY_OPENING", "Aucun solde à reprendre : aucune écriture n’est nécessaire.")
    if len(balances) > 100 or sum(max(net, 0) for net in balances.values()) > MAX_CENTS:
        fail("OPENING_TOO_LARGE", "Les soldes dépassent la capacité d’une écriture de reprise.")
    payload = EntryInput.model_validate(
        {
            "fiscal_year_id": target.id,
            "journal_code": data.journal_code,
            "accounting_date": target.start_date,
            "piece_date": source.end_date,
            "piece_reference": data.piece_reference,
            "label": f"À-nouveaux de l’exercice {source.year}",
            "lines": [
                {
                    "account_number": number,
                    "label": "Reprise avant affectation du résultat",
                    "debit": money(max(net, 0)),
                    "credit": money(max(-net, 0)),
                }
                for number, net in sorted(balances.items())
            ],
        }
    )
    entry = create_draft(session, payload)
    entry.source_type = "OPENING"
    entry.source_id = str(source.id)
    session.flush()
    post_entry(session, entry, entry.version)
    event(
        session,
        "OPENING_GENERATED",
        entry,
        {
            "source_fiscal_year_id": source.id,
            "target_fiscal_year_id": target.id,
            "request": request,
        },
    )
    return {"created": True, "entry": entry_json(entry)}


def opening_continuity(session: Session, year_id: int) -> dict[str, Any]:
    preview = opening_preview(session, year_id)
    entry = existing_opening(session, year_id)
    if entry is None:
        return {
            "status": "PROVISIONAL",
            "read_only": True,
            "opening_entry_id": None,
            "balances_match": False,
            "differences": [],
            "reason": "OPENING_NOT_GENERATED",
        }
    audit = opening_request(session, entry)
    result_account = audit["request"]["result_account"]
    expected = expected_balances(preview, result_account)
    actual: dict[str, int] = {}
    for line in entry.lines:
        actual[line.account_number] = actual.get(line.account_number, 0) + (
            to_cents(line.debit) - to_cents(line.credit)
        )
    differences = [
        {
            "account_number": number,
            "expected_balance": money(expected.get(number, 0)),
            "opening_balance": money(actual.get(number, 0)),
            "difference": money(actual.get(number, 0) - expected.get(number, 0)),
        }
        for number in sorted(expected.keys() | actual.keys())
        if expected.get(number, 0) != actual.get(number, 0)
    ]
    source = get_year(session, preview["source_fiscal_year_id"])
    matches = not differences and (
        entry.status == "VALIDATED"
        and entry.accounting_date.isoformat() == preview["opening_date"]
        and entry.source_id == str(source.id)
    )
    return {
        "status": "PROVISIONAL",
        "read_only": True,
        "opening_entry_id": entry.id,
        "balances_match": matches,
        "differences": differences,
        "source_closed": source.status == "CLOSED",
        "excluded_draft_count": preview["excluded_draft_count"],
        "source_unchanged": audit["request"]["preview_token"] == preview["preview_token"],
        "reason": "BALANCES_MATCH" if matches else "OPENING_MISMATCH",
    }
