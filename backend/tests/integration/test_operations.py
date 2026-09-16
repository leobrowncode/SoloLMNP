from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.main import create_app
from tests.conftest import migration_config


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        assert (
            client.post(
                "/api/ledger/activity",
                json={
                    "activity_name": "Opérations fictives",
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
        response = client.post(
            "/api/operations/properties",
            json={
                "name": "Bien fictif",
                "address": "Adresse fictive",
                "acquisition_date": "2025-01-01",
                "acquisition_price": "100000.00",
                "land_value": "20000.00",
                "building_value": "80000.00",
            },
        )
        assert response.status_code == 201, response.text
        assert (
            client.post(
                "/api/operations/banks",
                json={
                    "name": "Banque fictive",
                    "account_number": "512000",
                },
            ).status_code
            == 201
        )
        yield client


def operation(**changes):
    return {
        "request_id": "test-operation-001",
        "kind": "EXPENSE",
        "property_id": 1,
        "fiscal_year_id": 1,
        "date": "2025-02-01",
        "piece_date": "2025-02-01",
        "piece_reference": "FACT-001",
        "amount": "100.00",
        "description": "Assurance fictive",
        "counterparty": "Fournisseur fictif",
        "accounting_account": "616000",
        "bank_account_id": 1,
        "deductible_percentage": "80.00",
        "fiscal_treatment": "PARTIAL",
        **changes,
    }


def create(client, data=None):
    response = client.post("/api/operations", json=data or operation())
    assert response.status_code == 201, response.text
    return response.json()


def settlement(**changes):
    return {
        "request_id": "test-settlement-001",
        "fiscal_year_id": 1,
        "date": "2025-02-02",
        "piece_reference": "BANK-001",
        "amount": "100.00",
        "bank_account_id": 1,
        **changes,
    }


def reversal(**changes):
    return {
        "accounting_date": "2025-03-01",
        "piece_reference": "EXT-001",
        "reason": "Correction de test",
        **changes,
    }


def loan(client):
    response = client.post(
        "/api/operations/loans",
        json={
            "property_id": 1,
            "lender": "Banque fictive",
            "start_date": "2025-01-01",
            "initial_principal": "10000.00",
            "interest_rate": "3.50",
            "duration_months": 120,
            "principal_account": "164000",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_full_expense_preserved_with_partial_tax_metadata(client):
    row = create(client)
    assert row["deductible_percentage"] == "80.00"
    entry = client.get("/api/ledger/entries/1").json()
    assert entry["total_debit"] == entry["total_credit"] == "100.00"
    assert entry["source_type"] == "EXPENSE"
    assert entry["lines"][0]["debit"] == "100.00"
    assert client.post("/api/ledger/entries/1/reverse", json=reversal()).status_code == 409
    assert client.post("/api/operations/1/reverse", json=reversal()).status_code == 201
    assert client.get("/api/operations").json()[0]["status"] == "REVERSED"


def test_idempotent_retries_and_conflicting_payload(client):
    first = create(client)
    assert create(client) == first
    assert client.post("/api/operations", json=operation(amount="101.00")).status_code == 409
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 1


def test_concurrent_retry_creates_one_operation(client):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post("/api/operations", json=operation()), range(2))
        )
    assert all(response.status_code == 201 for response in responses)
    assert responses[0].json() == responses[1].json()
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 1


@pytest.mark.parametrize(
    "kind,control,number",
    [
        ("EXPENSE", "401000", "616000"),
        ("REVENUE", "411000", "706000"),
    ],
)
def test_accrual_and_partial_settlements(client, kind, control, number):
    row = create(client, operation(kind=kind, accounting_account=number, bank_account_id=None))
    assert row["remaining_to_settle"] == "100.00"
    entry = client.get("/api/ledger/entries/1").json()
    assert control in {line["account_number"] for line in entry["lines"]}
    response = client.post("/api/operations/1/settle", json=settlement(amount="40.00"))
    assert response.status_code == 201, response.text
    assert client.get("/api/operations").json()[-1]["remaining_to_settle"] == "60.00"
    assert client.post("/api/operations/1/reverse", json=reversal()).status_code == 409
    assert (
        client.post(
            "/api/operations/1/settle",
            json=settlement(
                request_id="test-settlement-002",
                amount="61.00",
            ),
        ).status_code
        == 409
    )
    assert client.post("/api/operations/2/reverse", json=reversal()).status_code == 201
    assert client.get("/api/operations").json()[-1]["remaining_to_settle"] == "100.00"


def test_loan_funding_payment_and_principal_from_ledger(client):
    assert loan(client)["remaining_principal"] == "0.00"
    response = client.post("/api/operations/loans/1/fund", json=settlement(amount="10000.00"))
    assert response.status_code == 201, response.text
    payment = settlement(
        request_id="test-payment-001",
        date="2025-02-03",
        amount="125.00",
        principal="100.00",
        interest="20.00",
        insurance="5.00",
        other_costs="0.00",
    )
    response = client.post("/api/operations/loans/1/payments", json=payment)
    assert response.status_code == 201, response.text
    entry = client.get("/api/ledger/entries/2").json()
    values = {line["account_number"]: line["debit"] for line in entry["lines"]}
    assert values["164000"] == "100.00"
    assert values["661000"] == "20.00"
    assert values["616000"] == "5.00"
    assert client.get("/api/operations/loans").json()[0]["remaining_principal"] == "9900.00"
    assert client.post("/api/operations/1/reverse", json=reversal()).status_code == 409
    assert client.post("/api/operations/2/reverse", json=reversal()).status_code == 201
    assert client.get("/api/operations/loans").json()[0]["remaining_principal"] == "10000.00"


def test_loan_payment_invalid_split_and_principal_overflow(client):
    loan(client)
    payload = settlement(principal="100.00", interest="1.00", insurance="0.00", other_costs="0.00")
    assert client.post("/api/operations/loans/1/payments", json=payload).status_code == 422
    payload["interest"] = "0.00"
    assert client.post("/api/operations/loans/1/payments", json=payload).status_code == 409
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0
    interest_only = settlement(
        request_id="test-interest-only",
        amount="10.00",
        principal="0.00",
        interest="10.00",
        insurance="0.00",
        other_costs="0.00",
    )
    assert client.post("/api/operations/loans/1/payments", json=interest_only).status_code == 409


CSV = "date;label;amount;reference\n2025-02-01;Assurance;-100,00;BANK-001\n"


def test_csv_preview_import_reimport_and_conflict_are_atomic(client):
    payload = {"bank_account_id": 1, "content": CSV}
    preview = client.post("/api/operations/bank/preview", json=payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["rows"][0]["suggested_account"] == "616000"
    assert client.get("/api/operations/bank/transactions?bank_account_id=1").json() == []
    assert client.post("/api/operations/bank/import", json=payload).json()["imported"] == 1
    assert client.post("/api/operations/bank/import", json=payload).json()["imported"] == 0
    conflict = CSV.replace("BANK-001", "BANK-002") + "2025-02-01;Assurance;-101.00;BANK-001\n"
    assert (
        client.post(
            "/api/operations/bank/import",
            json={
                "bank_account_id": 1,
                "content": conflict,
            },
        ).status_code
        == 409
    )
    assert len(client.get("/api/operations/bank/transactions?bank_account_id=1").json()) == 1
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0


@pytest.mark.parametrize(
    "content",
    [
        "date,label,amount,reference\n2025-02-01,Test,1,A",
        CSV.replace("-100,00", "NaN"),
        CSV.replace("-100,00", "1.001"),
        CSV.replace("2025-02-01", "2025-02-30"),
        CSV + "2025-02-01;Same;-100;BANK-001\n",
        "date;label;amount;reference\n",
    ],
)
def test_csv_invalid_input_rejected(client, content):
    assert (
        client.post(
            "/api/operations/bank/import",
            json={
                "bank_account_id": 1,
                "content": content,
            },
        ).status_code
        == 422
    )


def test_bank_link_posting_and_cancel_releases_match(client):
    client.post("/api/operations/bank/import", json={"bank_account_id": 1, "content": CSV})
    row = create(client, operation(bank_transaction_id=1))
    assert row["accounting_entry_id"] == 1
    transactions = client.get("/api/operations/bank/transactions?bank_account_id=1").json()
    assert transactions[0]["matched_entry_id"] == 1
    assert (
        client.post(
            "/api/operations",
            json=operation(
                request_id="test-operation-002",
                bank_transaction_id=1,
            ),
        ).status_code
        == 409
    )
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 1
    assert client.post("/api/operations/1/reverse", json=reversal()).status_code == 201
    assert (
        client.get("/api/operations/bank/transactions?bank_account_id=1").json()[0][
            "matched_entry_id"
        ]
        is None
    )


def test_matching_existing_entry_creates_no_extra_posting(client):
    create(client)
    client.post("/api/operations/bank/import", json={"bank_account_id": 1, "content": CSV})
    entry = client.get("/api/ledger/entries/1").json()
    line = next(line for line in entry["lines"] if line["account_number"] == "512000")
    for _ in range(2):
        assert (
            client.post(
                "/api/operations/bank/transactions/1/match",
                json={
                    "entry_line_id": line["id"],
                },
            ).status_code
            == 200
        )
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE business_operation SET amount=1",
        "DELETE FROM business_operation",
        "UPDATE bank_account SET account_number='108000'",
    ],
)
def test_business_records_cannot_be_changed_via_sql(client, database, statement):
    create(client)
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(text(statement))


def test_closed_year_blocks_business_posting(client, database):
    with database.engine.begin() as connection:
        connection.execute(
            text("UPDATE fiscal_year SET status='CLOSED', closed_at=CURRENT_TIMESTAMP WHERE id=1")
        )
    assert client.post("/api/operations", json=operation()).status_code == 409
    assert client.get("/api/operations").json() == []


@pytest.mark.parametrize(
    "changes",
    [
        {"accounting_account": "211000"},
        {"amount": 100.0},
        {"amount": "0.001"},
        {"deductible_percentage": "100.01"},
        {"property_id": 123},
        {"date": "2026-01-01"},
        {"deductible_percentage": "80.00", "fiscal_treatment": "DEDUCTIBLE"},
        {"deductible_percentage": "0.00", "fiscal_treatment": "PARTIAL"},
    ],
)
def test_invalid_operation_never_posts(client, changes):
    assert client.post("/api/operations", json=operation(**changes)).status_code in {404, 409, 422}
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0


def test_migration_refuses_to_discard_business_records(client, settings, database):
    create(client)
    database.engine.dispose()
    with pytest.raises(RuntimeError, match="Cannot discard business records"):
        command.downgrade(migration_config(settings), "0002_ledger")
    with database.engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003_operations"
        )
        assert connection.scalar(text("SELECT COUNT(*) FROM business_operation")) == 1
