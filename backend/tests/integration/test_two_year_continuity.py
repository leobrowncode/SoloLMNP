"""Exercise P3/P4/P5 together; closure remains a synthetic fixture until P7."""

import pytest

from tests.integration.test_assets import furniture
from tests.integration.test_opening_posting import close, continuity, generate, request
from tests.integration.test_operations import client as seeded_client  # noqa: F401
from tests.integration.test_operations import create, loan, operation, settlement
from tests.integration.test_statements import book, report


@pytest.fixture
def client(seeded_client):  # noqa: F811 - imported fixture is resolved by pytest
    return seeded_client


def open_second_year(client, database):
    assert (
        client.post(
            "/api/ledger/years",
            json={
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "fiscal_vintage": "2026",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/ledger/accounts",
            json={"number": "120000", "label": "Résultat", "account_type": "EQUITY"},
        ).status_code
        == 201
    )
    close(database)
    data = request(
        client, "120000" if report(client)["income_statement"]["result"] != "0.00" else None
    )
    response = generate(client, data)
    assert response.status_code == 200, response.text
    return data, response.json()["entry"]


def pay(client, **changes):
    response = client.post(
        "/api/operations/loans/1/payments",
        json=settlement(
            request_id="payment-2026",
            fiscal_year_id=2,
            date="2026-01-03",
            amount="125.00",
            principal="100.00",
            interest="20.00",
            insurance="5.00",
            other_costs="0.00",
            **changes,
        ),
    )
    return response


def test_business_operations_assets_and_opening_across_two_years(client, database):
    loan(client)
    assert (
        client.post("/api/operations/loans/1/fund", json=settlement(amount="10000.00")).status_code
        == 201
    )
    book(client, "218400", "512000", "1200.00")
    revenue = create(
        client,
        operation(
            request_id="rent-2025",
            kind="REVENUE",
            accounting_account="706000",
            amount="900.25",
            bank_account_id=None,
        ),
    )
    expense = create(
        client,
        operation(
            request_id="expense-2025",
            amount="100.15",
            bank_account_id=None,
        ),
    )
    assert client.post("/api/assets", json=furniture()).status_code == 201
    period = client.post("/api/assets/years/1/calculate").json()[0]
    assert period["amount"] == "120.92"
    assert (
        client.post(
            f"/api/assets/periods/{period['id']}/post",
            json={"request_id": "dot-2025", "piece_reference": "DOT-2025"},
        ).status_code
        == 201
    )
    before = report(client)
    assert before["income_statement"]["result"] == "679.18"
    data, opening = open_second_year(client, database)
    assert report(client, 2)["income_statement"]["result"] == "0.00"
    # Opening carries a liability; it must not count as another loan funding.
    assert client.get("/api/operations/loans").json()[0]["remaining_principal"] == "10000.00"

    for row, value in ((revenue, "900.25"), (expense, "100.15")):
        payload = settlement(
            request_id=f"settle-2026-{row['id']}",
            fiscal_year_id=2,
            date="2026-01-02",
            amount=value,
        )
        result = client.post(f"/api/operations/{row['id']}/settle", json=payload)
        assert result.status_code == 201, result.text
        assert (
            client.post(f"/api/operations/{row['id']}/settle", json=payload).json() == result.json()
        )
    assert report(client, 2)["income_statement"]["result"] == "0.00"
    parents = client.get("/api/operations?fiscal_year_id=1").json()
    assert all(
        row["remaining_to_settle"] == "0.00"
        for row in parents
        if row["id"] in {revenue["id"], expense["id"]}
    )
    payment = pay(client)
    assert payment.status_code == 201, payment.text
    assert pay(client).json() == payment.json()
    assert client.get("/api/operations/loans").json()[0]["remaining_principal"] == "9900.00"
    period2 = client.post("/api/assets/years/2/calculate").json()[0]
    assert period2["amount"] == "20.37"
    assert (
        client.post(
            f"/api/assets/periods/{period2['id']}/post",
            json={"request_id": "dot-2026", "piece_reference": "DOT-2026"},
        ).status_code
        == 201
    )
    second = report(client, 2)
    assert second["income_statement"]["total_income"] == "0.00"
    assert second["income_statement"]["result"] == "-45.37"
    assert second["balance_sheet"]["total_liabilities"] == "9900.00"
    assert second["balance_sheet"]["total_assets"] == "10533.81"
    assert second["balance_sheet"]["balanced"] is True
    assert report(client) == before
    assert continuity(client)["balances_match"] is True
    assert generate(client, data).json() == {"created": False, "entry": opening}
    for year, source, expected in (
        (1, "DEPRECIATION", 1),
        (2, "DEPRECIATION", 1),
        (2, "OPENING", 1),
        (1, "OPENING", 0),
    ):
        filtered = client.get(f"/api/ledger/entries?fiscal_year_id={year}&source={source}")
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["count"] == expected
        assert all(row["source_type"] == source for row in filtered.json()["entries"])


@pytest.mark.parametrize("principal", ["10000.01", "20000.00"])
def test_opening_does_not_authorize_excess_principal_repayment(client, database, principal):
    loan(client)
    assert (
        client.post("/api/operations/loans/1/fund", json=settlement(amount="10000.00")).status_code
        == 201
    )
    open_second_year(client, database)
    before = client.get("/api/ledger/entries?fiscal_year_id=2").json()
    response = client.post(
        "/api/operations/loans/1/payments",
        json=settlement(
            request_id="excess-2026",
            fiscal_year_id=2,
            date="2026-01-03",
            amount=principal,
            principal=principal,
            interest="0.00",
            insurance="0.00",
            other_costs="0.00",
        ),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "PRINCIPAL_EXCEEDED"
    assert client.get("/api/ledger/entries?fiscal_year_id=2").json() == before


def test_manual_initial_principal_and_payment_reversal_survive_carryover(client, database):
    book(client, "512000", "164000", "10000.00")
    assert loan(client)["remaining_principal"] == "10000.00"
    open_second_year(client, database)
    response = pay(client)
    assert response.status_code == 201, response.text
    assert client.get("/api/operations/loans").json()[0]["remaining_principal"] == "9900.00"
    reversal = client.post(
        f"/api/operations/{response.json()['id']}/reverse",
        json={
            "accounting_date": "2026-01-04",
            "piece_reference": "EXT-2026",
            "reason": "Correction fictive",
        },
    )
    assert reversal.status_code == 201, reversal.text
    assert client.get("/api/operations/loans").json()[0]["remaining_principal"] == "10000.00"
    assert report(client, 2)["balance_sheet"]["total_liabilities"] == "10000.00"
    assert continuity(client)["balances_match"] is True
