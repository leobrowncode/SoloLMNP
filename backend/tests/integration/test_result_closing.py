from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import AccountingEntry, AccountingEntryLine, LedgerEvent
from app.services import result_closing
from app.services.ledger import fail
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book, report


@pytest.fixture
def client(seeded_client):  # noqa: F811
    for number, label in (("120000", "Résultat bénéfice"), ("129000", "Résultat perte")):
        assert (
            seeded_client.post(
                "/api/ledger/accounts",
                json={"number": number, "label": label, "account_type": "EQUITY"},
            ).status_code
            == 201
        )
    return seeded_client


def counts(database):
    with database.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (AccountingEntry, AccountingEntryLine, LedgerEvent)
        )


def centralize(client, result, account="120000", request_id=None):
    return client.post(
        "/api/ledger/years/1/centralization",
        json={
            "request_id": request_id or str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "CENT-1",
            "justification": "Centralisation confirmée après contrôle du résultat.",
            "result_account": account,
            "expected_result": result,
        },
    )


def appropriate(client, amount, source="120000", target="108000", request_id=None):
    return client.post(
        "/api/ledger/years/1/appropriation",
        json={
            "request_id": request_id or str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "AFF-1",
            "justification": "Affectation confirmée vers le compte de l’exploitant.",
            "source_account": source,
            "target_account": target,
            "expected_amount": amount,
        },
    )


def test_profit_rubrics_centralization_and_appropriation(client):
    book(client, "512000", "108000", "2000.00")
    book(client, "411000", "706000", "900.25")
    book(client, "615000", "401000", "100.15")
    book(client, "661000", "512000", "0.10")
    result = report(client)
    cash = next(
        row for row in result["presentation"]["balance_rubrics"] if row["code"] == "TRESORERIE"
    )
    assert cash["total"] == "1999.90"
    natures = {row["code"]: row["total"] for row in result["presentation"]["income_rubrics"]}
    assert natures["PRODUITS_EXPLOITATION"] == "900.25"
    assert natures["SERVICES_EXTERIEURS"] == "100.15"
    assert natures["CHARGES_FINANCIERES"] == "0.10"
    assert result["presentation"]["reclassifications_applied"] is False
    preview = client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["result"] == "800.00"
    posted = centralize(client, "800.00")
    assert posted.status_code == 200, posted.text
    assert posted.json()["created"] is True
    after = report(client)
    assert after["income_statement"]["result"] == "0.00"
    equity = {row["account_number"]: row["amount"] for row in after["balance_sheet"]["equity"]}
    assert equity["120000"] == "800.00"
    assert equity["108000"] == "2000.00"
    proposal = client.get("/api/ledger/years/1/appropriation-preview").json()["proposals"][0]
    assert proposal["amount"] == "800.00"
    affected = appropriate(client, "800.00")
    assert affected.status_code == 200, affected.text
    final = report(client)
    equity = {row["account_number"]: row["amount"] for row in final["balance_sheet"]["equity"]}
    assert equity["108000"] == "2800.00"
    assert equity.get("120000", "0.00") == "0.00"
    assert final["balance_sheet"]["balanced"] is True


def test_loss_uses_129_and_cent_amounts(client):
    book(client, "615000", "401000", "10.01")
    assert (
        centralize(client, "-10.01", "120000").json()["detail"]["code"] == "INVALID_RESULT_ACCOUNT"
    )
    posted = centralize(client, "-10.01", "129000")
    assert posted.status_code == 200, posted.text
    equity = {
        row["account_number"]: row["amount"] for row in report(client)["balance_sheet"]["equity"]
    }
    assert equity["129000"] == "-10.01"
    affected = appropriate(client, "10.01", "129000", "108000")
    assert affected.status_code == 200, affected.text
    equity = {
        row["account_number"]: row["amount"] for row in report(client)["balance_sheet"]["equity"]
    }
    assert equity["108000"] == "-10.01"


def test_idempotent_retry_conflict_and_locked_year(client, database):
    from datetime import datetime

    from app.models import FiscalYear

    book(client, "512000", "706000", "50.00")
    request_id = str(uuid4())
    first = centralize(client, "50.00", request_id=request_id).json()
    before = counts(database)
    replay = centralize(client, "50.00", request_id=request_id).json()
    assert replay["created"] is False
    assert replay["entry"] == first["entry"]
    body = {
        "request_id": request_id,
        "journal_code": "OD",
        "piece_reference": "AUTRE",
        "justification": "Centralisation confirmée après contrôle du résultat.",
        "result_account": "120000",
        "expected_result": "50.00",
    }
    conflict = client.post("/api/ledger/years/1/centralization", json=body)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "RESULT_REQUEST_CONFLICT"
    other = centralize(client, "50.00")
    assert other.status_code == 409
    assert other.json()["detail"]["code"] == "CENTRALIZATION_EXISTS"
    assert counts(database) == before
    with database.sessions.begin() as session:
        year = session.get(FiscalYear, 1)
        assert year is not None
        year.status = "CLOSED"
        year.closed_at = datetime(2026, 1, 1)
    refused = centralize(client, "50.00")
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "YEAR_LOCKED"


def test_rollback_on_audit_failure_and_concurrency(client, database, monkeypatch):
    book(client, "512000", "706000", "20.00")

    def reject_audit(*args, **kwargs):
        fail("TEST_AUDIT_FAILURE", "Échec simulé après validation.")

    before = counts(database)
    with monkeypatch.context() as patch:
        patch.setattr(result_closing, "event", reject_audit)
        response = centralize(client, "20.00")
    assert response.status_code == 409
    assert counts(database) == before
    data_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: centralize(client, "20.00", request_id=data_id), range(2))
        )
    assert [item.status_code for item in responses] == [200, 200]
    assert responses[0].json()["entry"]["id"] == responses[1].json()["entry"]["id"]
    assert counts(database)[0] == before[0] + 1


def test_stale_result_drafts_and_overdraft_warning(client):
    book(client, "615000", "512000", "15.00")
    draft = client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": 1,
            "journal_code": "OD",
            "accounting_date": "2025-03-01",
            "piece_reference": "BROUILLON",
            "piece_date": "2025-03-01",
            "label": "Brouillon exclu",
            "lines": [
                {"account_number": "615000", "label": "Charge", "debit": "1.00", "credit": "0.00"},
                {"account_number": "401000", "label": "Dette", "debit": "0.00", "credit": "1.00"},
            ],
        },
    )
    assert draft.status_code == 201
    blocked = centralize(client, "-15.00", "129000")
    assert blocked.json()["detail"]["code"] == "YEAR_DRAFTS"
    warnings = report(client)["presentation"]["warnings"]
    assert any(
        item["code"] == "DECOUVERT" and item["account_number"] == "512000" for item in warnings
    )
    assert report(client)["presentation"]["balance_rubrics"]
    treso = next(
        r for r in report(client)["presentation"]["balance_rubrics"] if r["code"] == "TRESORERIE"
    )
    assert treso["accounts"][0]["account_number"] == "512000"


def test_zero_result_nets_classes_without_result_account(client):
    book(client, "512000", "706000", "40.00")
    book(client, "615000", "512000", "40.00")
    refused = centralize(client, "0.00", "120000")
    assert refused.json()["detail"]["code"] == "UNEXPECTED_RESULT_ACCOUNT"
    posted = centralize(client, "0.00", None)
    assert posted.status_code == 200, posted.text
    assert report(client)["income_statement"]["result"] == "0.00"
    assert client.get("/api/ledger/years/1/appropriation-preview").json()["proposals"] == []
