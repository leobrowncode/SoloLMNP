import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.models import Account, AccountingEntry, LedgerEvent


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        assert (
            client.post(
                "/api/ledger/activity",
                json={"activity_name": "Test fictif", "activity_start_date": "2025-01-01"},
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


def test_close_locks_year_without_allocating_result(client, database):
    created = client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": 1,
            "journal_code": "BQ",
            "accounting_date": "2025-02-01",
            "piece_reference": "TEST-001",
            "piece_date": "2025-02-01",
            "label": "Loyer fictif",
            "lines": [
                {
                    "account_number": "512000",
                    "label": "Banque",
                    "debit": "123.45",
                    "credit": "0.00",
                },
                {
                    "account_number": "706000",
                    "label": "Produit",
                    "debit": "0.00",
                    "credit": "123.45",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    validated = client.post(
        "/api/ledger/entries/1/validate",
        json={"expected_version": created.json()["version"]},
    )
    assert validated.status_code == 200, validated.text
    before = client.get("/api/ledger/accounts").json()
    closed = client.post("/api/ledger/years/1/close")
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["closed_at"]
    assert client.get("/api/ledger/accounts").json() == before
    assert "120000" not in {row["number"] for row in before}
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 1
    assert client.post("/api/ledger/years/1/close").status_code == 409
    assert (
        client.post(
            "/api/ledger/entries",
            json={
                "fiscal_year_id": 1,
                "journal_code": "OD",
                "accounting_date": "2025-03-01",
                "piece_reference": "TEST-002",
                "piece_date": "2025-03-01",
                "label": "Après clôture",
                "lines": [
                    {
                        "account_number": "512000",
                        "label": "Banque",
                        "debit": "1.00",
                        "credit": "0.00",
                    },
                    {
                        "account_number": "706000",
                        "label": "Produit",
                        "debit": "0.00",
                        "credit": "1.00",
                    },
                ],
            },
        ).status_code
        == 409
    )
    with database.sessions() as session:
        audit = session.scalar(select(LedgerEvent).where(LedgerEvent.action == "YEAR_CLOSED"))
        assert audit is not None
        assert audit.details["allocates_result"] is False
        assert audit.details["result"] == "123.45"
        assert session.scalar(select(func.count()).select_from(AccountingEntry)) == 1
        assert session.get(Account, "120000") is None
        assert session.get(Account, "129000") is None


def test_drafts_block_close_and_reopen_is_audited(client, database):
    draft = client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": 1,
            "journal_code": "OD",
            "accounting_date": "2025-02-01",
            "piece_reference": "BROUILLON",
            "piece_date": "2025-02-01",
            "label": "Brouillon",
            "lines": [
                {"account_number": "512000", "label": "Banque", "debit": "10.00", "credit": "0.00"},
                {
                    "account_number": "706000",
                    "label": "Produit",
                    "debit": "0.00",
                    "credit": "10.00",
                },
            ],
        },
    )
    assert draft.status_code == 201, draft.text
    refused = client.post("/api/ledger/years/1/close")
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "YEAR_HAS_DRAFTS"
    assert client.get("/api/ledger/setup").json()["years"][0]["status"] == "OPEN"
    refused_reopen = client.post("/api/ledger/years/1/reopen", json={"reason": "Correction"})
    assert refused_reopen.status_code == 409

    deleted = client.request(
        "DELETE",
        "/api/ledger/entries/1",
        json={"expected_version": draft.json()["version"]},
    )
    assert deleted.status_code == 200, deleted.text
    assert client.post("/api/ledger/years/1/close").status_code == 200
    short = client.post("/api/ledger/years/1/reopen", json={"reason": "non"})
    assert short.status_code == 422
    assert client.get("/api/ledger/setup").json()["years"][0]["status"] == "CLOSED"

    reopened = client.post(
        "/api/ledger/years/1/reopen",
        json={"reason": "  Oubli d’une facture  "},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "OPEN"
    assert reopened.json()["closed_at"] is None
    assert reopened.json()["reopening_reason"] == "Oubli d’une facture"
    again = client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": 1,
            "journal_code": "OD",
            "accounting_date": "2025-04-01",
            "piece_reference": "APRES",
            "piece_date": "2025-04-01",
            "label": "Après réouverture",
            "lines": [
                {"account_number": "512000", "label": "Banque", "debit": "2.00", "credit": "0.00"},
                {"account_number": "706000", "label": "Produit", "debit": "0.00", "credit": "2.00"},
            ],
        },
    )
    assert again.status_code == 201, again.text
    with database.sessions() as session:
        audit = session.scalar(select(LedgerEvent).where(LedgerEvent.action == "YEAR_REOPENED"))
        assert audit is not None
        assert audit.details["previous_status"] == "CLOSED"
        assert audit.details["reason"] == "Oubli d’une facture"

    assert client.post("/api/ledger/years/1/close").status_code == 409
    validated = client.post(
        f"/api/ledger/entries/{again.json()['id']}/validate",
        json={"expected_version": again.json()["version"]},
    )
    assert validated.status_code == 200, validated.text
    assert client.post("/api/ledger/years/1/close").status_code == 200
