from datetime import date
from decimal import Decimal
import pytest
from app.domain.accounting.entities import AccountingEntry, AccountingEntryLine, EntryStatus

def test_balanced_entry_can_be_validated() -> None:
    entry = AccountingEntry(1, "BQ", "BQ-1", date(2025,1,1), "P1", date(2025,1,1), "Loyer", [
        AccountingEntryLine("512000", "Banque", debit=Decimal("100.00")),
        AccountingEntryLine("706000", "Loyer", credit=Decimal("100.00")),
    ])
    entry.validate()
    assert entry.status is EntryStatus.VALIDATED

def test_unbalanced_entry_is_rejected() -> None:
    entry = AccountingEntry(1, "AC", "AC-1", date(2025,1,1), "P1", date(2025,1,1), "Erreur", [
        AccountingEntryLine("606000", "Charge", debit=Decimal("99.99")),
        AccountingEntryLine("401000", "Fournisseur", credit=Decimal("100.00")),
    ])
    with pytest.raises(ValueError, match="Unbalanced"):
        entry.validate()
