"""Explicit, justified inventory postings; no inferred accounting treatment."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.ledger_schemas import InventoryInput
from app.core.money import to_cents
from app.models import AccountingEntry, AccountingJournal, LedgerEvent
from app.services.ledger import create_draft, event, fail, money, post_entry


def post_inventory(session: Session, data: InventoryInput) -> AccountingEntry:
    # The API holds BEGIN IMMEDIATE before this lookup, including concurrent retries.
    request_id = str(data.request_id)
    parameters = data.model_dump(mode="json")
    for line, values in zip(data.lines, parameters["lines"], strict=True):
        values["debit"] = money(to_cents(line.debit))
        values["credit"] = money(to_cents(line.credit))
    existing = session.scalar(
        select(AccountingEntry).where(
            AccountingEntry.source_type == "INVENTORY",
            AccountingEntry.source_id == request_id,
        )
    )
    if existing is not None:
        audit = session.scalar(
            select(LedgerEvent).where(
                LedgerEvent.entry_id == existing.id,
                LedgerEvent.action == "INVENTORY_POSTED",
            )
        )
        if audit is None or audit.details.get("parameters") != parameters:
            fail(
                "INVENTORY_REQUEST_CONFLICT", "Cette demande d’inventaire a déjà un autre contenu."
            )
        return existing

    journal = session.get(AccountingJournal, data.journal_code)
    if journal is None or not journal.active or journal.journal_type != "GENERAL":
        fail("INVENTORY_JOURNAL", "Un journal actif d’opérations diverses est requis.", 422)
    entry = create_draft(session, data)
    entry.source_type = "INVENTORY"
    entry.source_id = request_id
    session.flush()
    post_entry(session, entry, entry.version)
    event(session, "INVENTORY_POSTED", entry, {"parameters": parameters})
    return entry
