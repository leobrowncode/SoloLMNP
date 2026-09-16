from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.main import create_app


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        assert (
            client.post(
                "/api/ledger/activity",
                json={
                    "activity_name": "Test fictif",
                    "activity_start_date": "2025-01-01",
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/ledger/years",
                json={
                    "year": 2025,
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "fiscal_vintage": "2025",
                },
            ).status_code
            == 201
        )
        yield client


def payload():
    return {
        "fiscal_year_id": 1,
        "journal_code": "BQ",
        "accounting_date": "2025-02-01",
        "piece_reference": "TEST-001",
        "piece_date": "2025-02-01",
        "label": "Loyer fictif",
        "lines": [
            {"account_number": "512000", "label": "Banque", "debit": "123.45", "credit": "0.00"},
            {"account_number": "706000", "label": "Produit", "debit": "0.00", "credit": "123.45"},
        ],
    }


def draft(client, data=None):
    response = client.post("/api/ledger/entries", json=data or payload())
    assert response.status_code == 201, response.text
    return response.json()


def post(client, entry):
    return client.post(
        f"/api/ledger/entries/{entry['id']}/validate", json={"expected_version": entry["version"]}
    )


def test_posting_projection_reversal_and_idempotence(client):
    entry = draft(client)
    assert client.get("/api/ledger/years/1/balance").json()["balance"] == []
    posted = post(client, entry)
    assert posted.status_code == 200, posted.text
    assert posted.json()["entry_number"] == "2025-000001"
    assert post(client, entry).json() == posted.json()
    balance = client.get("/api/ledger/years/1/balance").json()
    assert balance["total_debit"] == balance["total_credit"] == "123.45"
    assert balance["balanced"]
    ledger = client.get("/api/ledger/years/1/general-ledger?account_number=512000").json()
    assert ledger["lines"][0]["balance"] == "123.45"
    reversal = client.post(
        f"/api/ledger/entries/{entry['id']}/reverse",
        json={
            "accounting_date": "2025-02-02",
            "piece_reference": "EXT-001",
            "reason": "Correction fictive",
        },
    )
    assert reversal.status_code == 201, reversal.text
    assert reversal.json()["entry_number"] == "2025-000002"
    ledger = client.get("/api/ledger/years/1/general-ledger?account_number=512000").json()
    assert [line["balance"] for line in ledger["lines"]] == ["123.45", "0.00"]
    assert (
        client.post(
            f"/api/ledger/entries/{entry['id']}/reverse",
            json={
                "accounting_date": "2025-02-02",
                "piece_reference": "EXT-002",
                "reason": "Seconde correction",
            },
        ).status_code
        == 409
    )


def test_unbalanced_draft_edit_conflict_and_delete_audit(client):
    data = payload()
    data["lines"][1]["credit"] = "100.00"
    entry = draft(client, data)
    assert post(client, entry).status_code == 409
    edited = client.put(
        f"/api/ledger/entries/{entry['id']}", json={**payload(), "expected_version": 1}
    )
    assert edited.status_code == 200, edited.text
    assert (
        client.put(
            f"/api/ledger/entries/{entry['id']}", json={**payload(), "expected_version": 1}
        ).status_code
        == 409
    )
    deleted = client.request(
        "DELETE", f"/api/ledger/entries/{entry['id']}", json={"expected_version": 2}
    )
    assert deleted.status_code == 200
    assert client.get(f"/api/ledger/entries/{entry['id']}").status_code == 404
    events = client.get(f"/api/ledger/entries/{entry['id']}/events").json()
    assert events[-1]["action"] == "DRAFT_DELETED"
    assert draft(client)["id"] > entry["id"]


@pytest.mark.parametrize("amount", [1.25, 1, None, "NaN", "Infinity", "-1", "0.001"])
def test_invalid_money_rejected(client, amount):
    data = deepcopy(payload())
    data["lines"][0]["debit"] = amount
    assert client.post("/api/ledger/entries", json=data).status_code == 422


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE accounting_entry SET label='changed' WHERE id=1",
        "DELETE FROM accounting_entry WHERE id=1",
        "UPDATE accounting_entry_line SET debit=1 WHERE accounting_entry_id=1",
        "DELETE FROM accounting_entry_line WHERE accounting_entry_id=1",
        "UPDATE account SET label='changed' WHERE number='512000'",
        "UPDATE accounting_journal SET label='changed' WHERE code='BQ'",
        "UPDATE fiscal_year SET fiscal_vintage='2026' WHERE id=1",
        "DELETE FROM ledger_event",
        "UPDATE ledger_event SET action='changed'",
    ],
)
def test_sql_bypass_cannot_mutate_posted_history(client, database, statement):
    assert post(client, draft(client)).status_code == 200
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(text(statement))


def test_closed_year_blocks_all_draft_changes(client, database):
    entry = draft(client)
    with database.engine.begin() as connection:
        connection.execute(
            text("UPDATE fiscal_year SET status='CLOSED', closed_at=CURRENT_TIMESTAMP WHERE id=1")
        )
    assert post(client, entry).status_code == 409
    assert client.post("/api/ledger/entries", json=payload()).status_code == 409
    assert (
        client.put("/api/ledger/entries/1", json={**payload(), "expected_version": 1}).status_code
        == 409
    )
    assert (
        client.request("DELETE", "/api/ledger/entries/1", json={"expected_version": 1}).status_code
        == 409
    )


def test_concurrent_validation_serializes_numbers(client):
    entries = [draft(client), draft(client)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda entry: post(client, entry), entries))
    assert [response.status_code for response in responses] == [200, 200]
    assert {response.json()["sequence"] for response in responses} == {1, 2}


def test_filter_keeps_whole_entry_and_pagination(client):
    for _ in range(3):
        assert post(client, draft(client)).status_code == 200
    response = client.get(
        "/api/ledger/entries",
        params={
            "fiscal_year_id": 1,
            "account_number": "512000",
            "limit": 1,
            "offset": 1,
        },
    ).json()
    assert response["count"] == 3
    assert len(response["entries"]) == 1
    assert len(response["entries"][0]["lines"]) == 2
    assert client.get("/api/ledger/entries?fiscal_year_id=1&piece=%25").json()["count"] == 0


def test_cross_origin_write_rejected(client):
    response = client.post(
        "/api/ledger/entries", json=payload(), headers={"Origin": "https://attacker.example"}
    )
    assert response.status_code == 403
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0


def test_sql_cannot_validate_unbalanced_entry(client, database):
    data = payload()
    data["lines"][1]["credit"] = "100.00"
    draft(client, data)
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE accounting_entry_line SET account_label="
                "(SELECT label FROM account WHERE number=account_number)"
            )
        )
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE accounting_entry SET status='VALIDATED', sequence=1, "
                "entry_number='2025-000001', validated_at=CURRENT_TIMESTAMP, journal_label='Banque'"
            )
        )
    assert client.get("/api/ledger/years/1/balance").json()["balance"] == []


def test_account_deactivation_and_overlapping_year(client):
    entry = draft(client)
    assert (
        client.patch("/api/ledger/accounts/512000/active", json={"active": False}).status_code
        == 200
    )
    assert post(client, entry).status_code == 409
    assert (
        client.post(
            "/api/ledger/years",
            json={
                "year": 2026,
                "start_date": "2025-12-01",
                "end_date": "2026-12-31",
                "fiscal_vintage": "2026",
            },
        ).status_code
        == 409
    )


def test_concurrent_revalidation_is_one_posting(client):
    entry = draft(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: post(client, entry), range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()
    events = client.get("/api/ledger/entries/1/events").json()
    assert sum(event["action"] == "ENTRY_VALIDATED" for event in events) == 1
