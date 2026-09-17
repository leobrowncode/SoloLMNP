from decimal import Decimal

import pytest

from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_ledger import draft, payload, post


@pytest.fixture
def client(seeded_client):  # noqa: F811 - pytest resolves imported fixtures by name
    return seeded_client


def book(client, debit, credit, amount):
    data = payload()
    data["lines"] = [
        {"account_number": debit, "label": "Débit", "debit": amount},
        {"account_number": credit, "label": "Crédit", "credit": amount},
    ]
    response = post(client, draft(client, data))
    assert response.status_code == 200, response.text
    return response.json()


def report(client, year=1):
    response = client.get(f"/api/ledger/years/{year}/statements")
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_statements_and_unknown_year(client):
    result = report(client)
    assert result["status"] == "PROVISIONAL"
    assert result["validated_only"] is True
    assert result["income_statement"]["result"] == "0.00"
    assert result["balance_sheet"]["assets"] == []
    assert result["balance_sheet"]["balanced"] is True
    assert client.get("/api/ledger/years/999/statements").status_code == 404


def test_profit_assets_depreciation_and_drafts(client):
    book(client, "512000", "108000", "2000.00")
    book(client, "218400", "512000", "1200.00")
    book(client, "411000", "706000", "900.25")
    book(client, "615000", "401000", "100.15")
    book(client, "681100", "281840", "200.00")
    draft(client)  # Unvalidated cash receipt must not appear in any report total.
    result = report(client)
    income, balance = result["income_statement"], result["balance_sheet"]
    assert result["excluded_draft_count"] == 1
    assert income["total_income"] == "900.25"
    assert income["total_expenses"] == "300.15"
    assert income["result"] == balance["current_result"] == "600.10"
    assert balance["total_assets"] == balance["total_liabilities_and_equity"] == "2700.25"
    assert balance["total_liabilities"] == "100.15"
    assert balance["total_equity"] == "2000.00"
    assert (
        next(row for row in balance["assets"] if row["account_number"] == "281840")["amount"]
        == "-200.00"
    )
    assert report(client) == result  # Reproducible, read-only projection.


def test_loss_reversal_and_year_isolation(client):
    entry = book(client, "615000", "401000", "10.01")
    assert report(client)["income_statement"]["result"] == "-10.01"
    assert report(client)["balance_sheet"]["total_liabilities_and_equity"] == "0.00"
    assert (
        client.post(
            f"/api/ledger/entries/{entry['id']}/reverse",
            json={
                "accounting_date": "2025-02-02",
                "piece_reference": "EXT",
                "reason": "Correction",
            },
        ).status_code
        == 201
    )
    assert report(client)["income_statement"]["result"] == "0.00"
    book(client, "512000", "706000", "33.33")
    assert (
        client.post(
            "/api/ledger/years",
            json={
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "fiscal_vintage": "2026",
            },
        ).status_code
        == 201
    )
    assert report(client, 2)["income_statement"]["result"] == "0.00"
    assert report(client)["income_statement"]["result"] == "33.33"


@pytest.mark.parametrize(
    "number,kind", [("699000", "ASSET"), ("799000", "LIABILITY"), ("499000", "INCOME")]
)
def test_inconsistent_custom_classification_blocks_statements(client, number, kind):
    assert (
        client.post(
            "/api/ledger/accounts",
            json={
                "number": number,
                "label": "Compte mal classé",
                "account_type": kind,
            },
        ).status_code
        == 201
    )
    book(client, number, "512000", "1.00")
    response = client.get("/api/ledger/years/1/statements")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_STATEMENT_ACCOUNT"


def test_custom_account_inactive_account_and_integer_totals(client):
    assert (
        client.post(
            "/api/ledger/accounts",
            json={
                "number": "708000",
                "label": "Autres produits",
                "account_type": "INCOME",
            },
        ).status_code
        == 201
    )
    for amount in ("0.01", "0.02", "100000000.99"):
        book(client, "512000", "708000", amount)
    assert (
        client.patch("/api/ledger/accounts/708000/active", json={"active": False}).status_code
        == 200
    )
    result = report(client)
    assert result["income_statement"]["result"] == "100000001.02"
    assert result["income_statement"]["income"][0]["label"] == "Autres produits"


def test_corrupt_unbalanced_ledger_is_blocked(client):
    # Simulate corrupt historical data without removing production integrity triggers.
    from app.models import AccountingEntryLine

    book(client, "512000", "706000", "10.00")
    from sqlalchemy import event

    def corrupt(line, context):
        if line.account_number == "512000":
            line.debit = Decimal("10.01")

    event.listen(AccountingEntryLine, "load", corrupt)
    try:
        response = client.get("/api/ledger/years/1/statements")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "UNBALANCED_STATEMENTS"
    finally:
        event.remove(AccountingEntryLine, "load", corrupt)
