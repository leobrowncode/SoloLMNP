import pytest

from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book, report


@pytest.fixture
def client(seeded_client):  # noqa: F811
    return seeded_client


def test_depreciation_limit_is_separate_from_the_ledger(client):
    book(client, "411000", "706000", "1000.00")
    book(client, "615000", "401000", "400.00")
    book(client, "681100", "281840", "800.00")
    before = report(client)
    first = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "research_only"
    assert body["declarable"] is False
    assert body["accounting_result"] == before["income_statement"]["result"] == "-200.00"
    assert body["deductible_depreciation"] == "600.00"
    assert body["unused_depreciation"] == "200.00"
    assert body["fiscal_result"] == "0.00"
    assert body["tax_loss"] == "0.00"
    assert body["imputed_on_global_income"] == "0.00"
    assert report(client)["income_statement"]["total_expenses"] == "1200.00"
    replay = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert replay.json()["replayed"] is True
    assert replay.json()["id"] == body["id"]


def test_tax_loss_is_not_a_depreciation_carry_forward(client):
    book(client, "615000", "401000", "250.00")
    book(client, "512000", "706000", "100.00")
    body = client.post("/api/fiscal/years/1", json={"adjustments": []}).json()
    assert body["fiscal_result"] == "-150.00"
    assert body["tax_loss"] == "150.00"
    assert body["unused_depreciation"] == "0.00"
    assert "RULE-LMNP-LOSS-001" in body["details"]["applied_rules"]
    assert "RULE-LMNP-BIC-001" in body["details"]["blocked_rules"]


def test_partial_charge_stays_in_the_ledger(client):
    book(client, "512000", "706000", "100.00")
    book(client, "622000", "401000", "80.00")
    body = client.post(
        "/api/fiscal/years/1",
        json={
            "adjustments": [
                {
                    "account_number": "622000",
                    "amount": "30.00",
                    "justification": "Quote-part non déductible confirmée, hors ledger.",
                }
            ]
        },
    ).json()
    assert body["non_deductible"] == "30.00"
    assert body["fiscal_result"] == "50.00"
    assert report(client)["income_statement"]["total_expenses"] == "80.00"
    too_much = client.post(
        "/api/fiscal/years/1",
        json={
            "adjustments": [
                {
                    "account_number": "622000",
                    "amount": "80.01",
                    "justification": "Montant supérieur à la charge comptabilisée.",
                }
            ]
        },
    )
    assert too_much.status_code == 422
    assert too_much.json()["detail"]["code"] == "ADJUSTMENT_TOO_LARGE"


def test_vintages_stay_research_only(client):
    payload = client.get("/api/fiscal/vintages").json()
    assert payload["declarable"] is False
    assert payload["status"] == "research_only"
    assert {row["vintage"] for row in payload["vintages"]} == {"2025", "2026"}
    assert client.get("/api/status").json()["fiscal"]["status"] == "research_only"
