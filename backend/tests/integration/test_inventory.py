from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.models import AccountingEntry, AccountingEntryLine, LedgerEvent
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_ledger import payload


@pytest.fixture
def client(seeded_client):  # noqa: F811
    return seeded_client


def inventory_payload():
    return {
        **payload(),
        "journal_code": "OD",
        "request_id": str(uuid4()),
        "justification": "Saisie technique fictive, calcul et comptes vérifiés dans TEST-001.",
    }


def counts(database):
    with database.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (AccountingEntry, AccountingEntryLine, LedgerEvent)
        )


def test_inventory_posting_audit_reports_and_reversal(client, database):
    data = inventory_payload()
    response = client.post("/api/ledger/inventory", json=data)
    assert response.status_code == 200, response.text
    entry = response.json()
    assert entry["status"] == "VALIDATED"
    assert entry["source_type"] == "INVENTORY"
    assert entry["source_id"] == data["request_id"]
    assert entry["entry_number"] == "2025-000001"
    events = client.get(f"/api/ledger/entries/{entry['id']}/events").json()
    assert events[-1]["action"] == "INVENTORY_POSTED"
    assert events[-1]["details"]["parameters"] == data
    result = client.get("/api/ledger/years/1/statements").json()
    assert result["income_statement"]["result"] == "123.45"
    assert result["balance_sheet"]["balanced"] is True
    filtered = client.get("/api/ledger/entries?fiscal_year_id=1&source=INVENTORY").json()
    assert filtered["entries"] == [entry]
    before = counts(database)
    assert client.post("/api/ledger/inventory", json=data).json() == entry
    assert counts(database) == before
    assert (
        client.put(
            f"/api/ledger/entries/{entry['id']}",
            json={**payload(), "expected_version": entry["version"]},
        ).status_code
        == 409
    )
    reverse = {
        "accounting_date": "2025-02-02",
        "piece_reference": "EXT-INV-1",
        "reason": "Correction de la saisie fictive",
    }
    assert (
        client.post(f"/api/ledger/entries/{entry['id']}/reverse", json=reverse).status_code == 201
    )
    assert (
        client.post(f"/api/ledger/entries/{entry['id']}/reverse", json=reverse).status_code == 409
    )
    assert (
        client.get("/api/ledger/years/1/statements").json()["income_statement"]["result"] == "0.00"
    )
    before = counts(database)
    # A retry after reversal must not recreate the cancelled accounting effect.
    assert client.post("/api/ledger/inventory", json=data).json() == entry
    assert counts(database) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("justification", "Justification différente et explicite"),
        ("piece_reference", "OTHER"),
        ("fiscal_year_id", 999),
    ],
)
def test_request_key_cannot_be_reused_with_different_parameters(client, database, field, value):
    data = inventory_payload()
    assert client.post("/api/ledger/inventory", json=data).status_code == 200
    before = counts(database)
    response = client.post("/api/ledger/inventory", json={**data, field: value})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVENTORY_REQUEST_CONFLICT"
    assert counts(database) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("justification", "   "),
        ("justification", "x" * 3001),
        ("request_id", "bad-key"),
        ("piece_reference", " "),
        ("journal_code", "BQ"),
        ("accounting_date", "2024-12-31"),
    ],
)
def test_invalid_inventory_refused_without_side_effects(client, database, field, value):
    before = counts(database)
    assert (
        client.post("/api/ledger/inventory", json={**inventory_payload(), field: value}).status_code
        == 422
    )
    assert counts(database) == before


def test_unbalanced_inventory_rolls_back_draft_lines_and_audit(client, database):
    data = inventory_payload()
    data["lines"][1]["credit"] = "123.44"
    before = counts(database)
    response = client.post("/api/ledger/inventory", json=data)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "UNBALANCED"
    assert counts(database) == before
    data["lines"][1]["credit"] = "123.45"
    # Rollback must also leave the request key and sequence available.
    assert client.post("/api/ledger/inventory", json=data).json()["entry_number"] == "2025-000001"


def test_inventory_concurrent_retry_creates_one_entry(client, database):
    data = inventory_payload()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post("/api/ledger/inventory", json=data), range(2))
        )
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert counts(database)[:2] == (1, 2)
    events = client.get(f"/api/ledger/entries/{responses[0].json()['id']}/events").json()
    assert [e["action"] for e in events].count("INVENTORY_POSTED") == 1


def test_inventory_retry_normalizes_money_and_rejects_changed_amount(client, database):
    data = inventory_payload()
    entry = client.post("/api/ledger/inventory", json=data).json()
    before = counts(database)
    data["lines"][0]["debit"] = "123.450"
    data["lines"][1]["debit"] = "0"
    assert client.post("/api/ledger/inventory", json=data).json() == entry
    data["lines"][0]["debit"] = "124.45"
    data["lines"][1]["credit"] = "124.45"
    response = client.post("/api/ledger/inventory", json=data)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVENTORY_REQUEST_CONFLICT"
    assert counts(database) == before


def test_inventory_audit_failure_rolls_back_posting(client, database, monkeypatch):
    from app.services import inventory
    from app.services.ledger import fail

    def reject_audit(*args, **kwargs):
        fail("TEST_AUDIT_FAILURE", "Échec simulé après validation.")

    before = counts(database)
    with monkeypatch.context() as patch:
        patch.setattr(inventory, "event", reject_audit)
        response = client.post("/api/ledger/inventory", json=inventory_payload())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TEST_AUDIT_FAILURE"
    assert counts(database) == before


@pytest.mark.parametrize("field", ["justification", "request_id", "piece_date"])
def test_inventory_requires_justification_key_and_dated_reference(client, database, field):
    data = inventory_payload()
    del data[field]
    before = counts(database)
    assert client.post("/api/ledger/inventory", json=data).status_code == 422
    assert counts(database) == before


@pytest.mark.parametrize("lock", ["year", "account", "journal"])
def test_inventory_retry_survives_lock_but_new_posting_is_refused(client, database, lock):
    data = inventory_payload()
    entry = client.post("/api/ledger/inventory", json=data).json()
    statements = {
        "year": "UPDATE fiscal_year SET status='CLOSED', closed_at=CURRENT_TIMESTAMP WHERE id=1",
        "account": "UPDATE account SET active=0 WHERE number='512000'",
        "journal": "UPDATE accounting_journal SET active=0 WHERE code='OD'",
    }
    with database.engine.begin() as connection:
        connection.execute(text(statements[lock]))
    before = counts(database)
    assert client.post("/api/ledger/inventory", json=data).json() == entry
    assert client.post("/api/ledger/inventory", json=inventory_payload()).status_code in (409, 422)
    assert counts(database) == before
