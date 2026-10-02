"""User-confirmed centralisation of classes 6/7 and result appropriation.

Neither operation infers a tax treatment or closes the fiscal year.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import AppropriationInput, CentralizationInput, EntryInput
from app.core.money import to_cents
from app.models import Account, AccountingEntry, AccountingJournal, LedgerEvent
from app.services.ledger import create_draft, entry_json, event, fail, get_year, money, post_entry
from app.services.statements import statements


def _cents(amount: str) -> int:
    return to_cents(Decimal(amount))


def centralization_preview(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    report = statements(session, year.id)
    result = _cents(report["income_statement"]["result"])
    lines = _closing_lines(report, result, None)
    if result:
        lines.append(
            {
                "account_number": "",
                "label": "Résultat — compte à confirmer",
                "debit": money(max(-result, 0)),
                "credit": money(max(result, 0)),
            }
        )
    live = _live(session, year.id, "CENTRALIZATION")
    return {
        "fiscal_year_id": year.id,
        "status": "PROVISIONAL",
        "read_only": True,
        "year_status": year.status,
        "result": money(result),
        "result_account_prefix": "120" if result > 0 else "129" if result < 0 else None,
        "excluded_draft_count": report["excluded_draft_count"],
        "lines": lines,
        "already_posted": live is not None,
        "existing_entry_id": live.id if live else None,
    }


def post_centralization(
    session: Session, year_id: int, data: CentralizationInput
) -> dict[str, Any]:
    parameters = _parameters(data)
    existing = _by_request(session, "CENTRALIZATION", str(data.request_id))
    if existing is not None:
        _same_request(session, existing, "CENTRALIZATION_POSTED", parameters)
        return {"created": False, "entry": entry_json(existing)}
    year = get_year(session, year_id, writable=True)
    if _live(session, year.id, "CENTRALIZATION") is not None:
        fail("CENTRALIZATION_EXISTS", "Une centralisation non extournée existe déjà.")
    report = statements(session, year.id)
    if report["excluded_draft_count"]:
        fail("YEAR_DRAFTS", "Validez ou supprimez les brouillons avant la centralisation.")
    result = _cents(report["income_statement"]["result"])
    if to_cents(data.expected_result) != result:
        fail("RESULT_CHANGED", "Le résultat a changé. Actualisez la prévisualisation.")
    if result == 0 and not _has_class_balance(report):
        fail("NOTHING_TO_CENTRALIZE", "Les comptes de charges et de produits sont déjà soldés.")
    _check_result_account(session, data.result_account, result)
    journal = _general_journal(session, data.journal_code)
    lines = _closing_lines(report, result, data.result_account)
    if len(lines) < 2 or len(lines) > 100:
        fail("CENTRALIZATION_SIZE", "La centralisation ne tient pas dans une seule écriture.")
    entry = _post(
        session,
        year_id=year.id,
        journal_code=journal.code,
        accounting_date=year.end_date,
        piece_reference=data.piece_reference,
        label="Centralisation des comptes de charges et de produits",
        lines=lines,
        source_type="CENTRALIZATION",
        source_id=str(data.request_id),
        action="CENTRALIZATION_POSTED",
        parameters=parameters,
    )
    return {"created": True, "entry": entry_json(entry)}


def appropriation_preview(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    central = _live(session, year.id, "CENTRALIZATION")
    live = _live(session, year.id, "APPROPRIATION")
    proposals = []
    if central is not None:
        for number in ("120", "129"):
            for account, net in _equity_balances(session, year.id):
                if (
                    account.number.startswith(number)
                    and not account.number.startswith("1209")
                    and net
                ):
                    proposals.append(
                        {
                            "source_account": account.number,
                            "label": account.label,
                            "amount": money(abs(net)),
                            "debit_source": net < 0,
                        }
                    )
    return {
        "fiscal_year_id": year.id,
        "status": "PROVISIONAL",
        "read_only": True,
        "centralization_posted": central is not None,
        "proposals": proposals,
        "already_posted": live is not None,
        "existing_entry_id": live.id if live else None,
    }


def post_appropriation(session: Session, year_id: int, data: AppropriationInput) -> dict[str, Any]:
    parameters = _parameters(data)
    existing = _by_request(session, "APPROPRIATION", str(data.request_id))
    if existing is not None:
        _same_request(session, existing, "APPROPRIATION_POSTED", parameters)
        return {"created": False, "entry": entry_json(existing)}
    year = get_year(session, year_id, writable=True)
    if _live(session, year.id, "CENTRALIZATION") is None:
        fail("CENTRALIZATION_REQUIRED", "Centralisez les charges et produits avant l’affectation.")
    if _live(session, year.id, "APPROPRIATION") is not None:
        fail("APPROPRIATION_EXISTS", "Une affectation non extournée existe déjà.")
    source = session.get(Account, data.source_account)
    target = session.get(Account, data.target_account)
    if (
        source is None
        or not source.active
        or source.account_type != "EQUITY"
        or source.number.startswith("1209")
        or not (source.number.startswith("120") or source.number.startswith("129"))
    ):
        fail(
            "INVALID_SOURCE_ACCOUNT",
            "Le compte source doit être un compte actif 120 (hors 1209) ou 129.",
        )
    if (
        target is None
        or not target.active
        or target.account_type != "EQUITY"
        or target.number.startswith(("120", "129"))
        or target.number == source.number
    ):
        fail(
            "INVALID_TARGET_ACCOUNT",
            "Affectez le résultat vers un autre compte actif de capitaux propres.",
        )
    net = _account_net(session, year.id, source.number)
    if source.number.startswith("120") and net >= 0:
        fail("NOTHING_TO_APPROPRIATE", "Le compte 120 n’a pas de solde créditeur à affecter.")
    if source.number.startswith("129") and net <= 0:
        fail("NOTHING_TO_APPROPRIATE", "Le compte 129 n’a pas de solde débiteur à affecter.")
    amount = abs(net)
    if to_cents(data.expected_amount) != amount:
        fail("AMOUNT_CHANGED", "Le montant à affecter a changé. Actualisez la prévisualisation.")
    _general_journal(session, data.journal_code)
    debit_source = net < 0
    lines = [
        {
            "account_number": source.number,
            "label": "Affectation du résultat",
            "debit": money(amount if debit_source else 0),
            "credit": money(0 if debit_source else amount),
        },
        {
            "account_number": target.number,
            "label": "Affectation du résultat",
            "debit": money(0 if debit_source else amount),
            "credit": money(amount if debit_source else 0),
        },
    ]
    entry = _post(
        session,
        year_id=year.id,
        journal_code=data.journal_code,
        accounting_date=year.end_date,
        piece_reference=data.piece_reference,
        label="Affectation du résultat",
        lines=lines,
        source_type="APPROPRIATION",
        source_id=str(data.request_id),
        action="APPROPRIATION_POSTED",
        parameters=parameters,
    )
    return {"created": True, "entry": entry_json(entry)}


def _parameters(data: CentralizationInput | AppropriationInput) -> dict[str, Any]:
    raw = data.model_dump(mode="json")
    if isinstance(data, CentralizationInput):
        raw["expected_result"] = money(to_cents(data.expected_result))
    else:
        raw["expected_amount"] = money(to_cents(data.expected_amount))
    return raw


def _same_request(
    session: Session, entry: AccountingEntry, action: str, parameters: dict[str, Any]
) -> None:
    audit = session.scalar(
        select(LedgerEvent).where(LedgerEvent.entry_id == entry.id, LedgerEvent.action == action)
    )
    if audit is None or audit.details.get("parameters") != parameters:
        fail("RESULT_REQUEST_CONFLICT", "Cette demande a déjà un autre contenu.")


def _by_request(session: Session, source_type: str, request_id: str) -> AccountingEntry | None:
    return session.scalar(
        select(AccountingEntry).where(
            AccountingEntry.source_type == source_type,
            AccountingEntry.source_id == request_id,
        )
    )


def _live(session: Session, year_id: int, source_type: str) -> AccountingEntry | None:
    rows = session.scalars(
        select(AccountingEntry).where(
            AccountingEntry.fiscal_year_id == year_id,
            AccountingEntry.source_type == source_type,
            AccountingEntry.status == "VALIDATED",
        )
    ).all()
    reversed_ids = {
        row.reversal_of_id
        for row in session.scalars(
            select(AccountingEntry).where(AccountingEntry.reversal_of_id.is_not(None))
        )
        if row.reversal_of_id is not None
    }
    live = [row for row in rows if row.id not in reversed_ids]
    if len(live) > 1:
        fail("RESULT_AMBIGUOUS", "Plusieurs écritures de résultat actives : états à contrôler.")
    return live[0] if live else None


def _general_journal(session: Session, code: str) -> AccountingJournal:
    journal = session.get(AccountingJournal, code)
    if journal is None or not journal.active or journal.journal_type != "GENERAL":
        fail("RESULT_JOURNAL", "Un journal actif d’opérations diverses est requis.", 422)
    return journal


def _check_result_account(session: Session, number: str | None, result: int) -> None:
    if result == 0:
        if number is not None:
            fail(
                "UNEXPECTED_RESULT_ACCOUNT",
                "Aucun compte de résultat n’est requis si le résultat est nul.",
            )
        return
    account = session.get(Account, number) if number else None
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
            f"Choisissez un compte actif de capitaux propres {prefix} (hors 1209).",
        )


def _has_class_balance(report: dict[str, Any]) -> bool:
    income = report["income_statement"]
    return any(_cents(row["amount"]) for row in income["income"] + income["expenses"])


def _closing_lines(
    report: dict[str, Any], result: int, result_account: str | None
) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    for row in report["income_statement"]["expenses"]:
        cents = _cents(row["amount"])
        if cents > 0:
            lines.append(_line(row["account_number"], 0, cents))
        elif cents < 0:
            lines.append(_line(row["account_number"], -cents, 0))
    for row in report["income_statement"]["income"]:
        cents = _cents(row["amount"])
        if cents > 0:
            lines.append(_line(row["account_number"], cents, 0))
        elif cents < 0:
            lines.append(_line(row["account_number"], 0, -cents))
    if result > 0 and result_account:
        lines.append(_line(result_account, 0, result))
    elif result < 0 and result_account:
        lines.append(_line(result_account, -result, 0))
    return lines


def _line(number: str, debit: int, credit: int) -> dict[str, str]:
    return {
        "account_number": number,
        "label": "Centralisation",
        "debit": money(debit),
        "credit": money(credit),
    }


def _equity_balances(session: Session, year_id: int) -> list[tuple[Account, int]]:
    report = statements(session, year_id)
    found = []
    for row in report["balance_sheet"]["equity"]:
        account = session.get(Account, row["account_number"])
        if account is None:
            continue
        # Equity display is credit-positive; a credit balance is a negative net.
        found.append((account, -_cents(row["amount"])))
    return found


def _account_net(session: Session, year_id: int, number: str) -> int:
    for account, net in _equity_balances(session, year_id):
        if account.number == number:
            return net
    return 0


def _post(
    session: Session,
    *,
    year_id: int,
    journal_code: str,
    accounting_date: date,
    piece_reference: str,
    label: str,
    lines: list[dict[str, str]],
    source_type: str,
    source_id: str,
    action: str,
    parameters: dict[str, Any],
) -> AccountingEntry:
    payload = EntryInput.model_validate(
        {
            "fiscal_year_id": year_id,
            "journal_code": journal_code,
            "accounting_date": accounting_date,
            "piece_date": accounting_date,
            "piece_reference": piece_reference,
            "label": label,
            "lines": lines,
        }
    )
    entry = create_draft(session, payload)
    entry.source_type = source_type
    entry.source_id = source_id
    session.flush()
    post_entry(session, entry, entry.version)
    event(session, action, entry, {"parameters": parameters})
    return entry
