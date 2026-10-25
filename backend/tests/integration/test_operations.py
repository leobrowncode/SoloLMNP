from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.database import SCHEMA_REVISION
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


def test_second_loan_line_gets_its_own_164_account(client):
    first = loan(client)
    assert first["principal_account"] == "164000"
    conflict = client.post(
        "/api/operations/loans",
        json={
            "property_id": 1,
            "lender": "Deuxième ligne",
            "start_date": "2025-01-01",
            "initial_principal": "195000.00",
            "interest_rate": "3.50",
            "duration_months": 300,
            "principal_account": "164000",
        },
    )
    assert conflict.status_code == 422, conflict.text
    assert "propre compte 164" in conflict.json()["detail"]["message"]
    second = client.post(
        "/api/operations/loans",
        json={
            "property_id": 1,
            "lender": "Deuxième ligne",
            "start_date": "2025-01-01",
            "initial_principal": "195000.00",
            "interest_rate": "3.50",
            "duration_months": 300,
        },
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["initial_principal"] == "195000.00"
    assert body["principal_account"] == "164001"
    assert body["principal_account"] != first["principal_account"]
    accounts = {row["number"] for row in client.get("/api/ledger/accounts").json()}
    assert "164001" in accounts


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


LOAN_SHEET = (
    "Prêt\tRang\tDate\tCapital (€)\tIntérêts (€)\tAssurance banque (€)\t"
    "Assurance externe à compléter (€)\tTotal banque (€)\n"
    "085644F\t0\t05/12/2024\t99,00\t21,00\t5,00\t\t125,00\n"
    "085644F\t1\t05/02/2025\t100,00\t20,00\t5,00\t\t125,00\n"
    "085644F\t2\t05/03/2025\t101,00\t19,00\t5,00\t\t125,00\n"
    "085644F\t3\t05/01/2026\t102,00\t18,00\t5,00\t\t125,00\n"
)


def test_loan_sheet_preview_import_reimport_and_conflict(client):
    loan(client)
    funded = client.post(
        "/api/operations/loans/1/fund",
        json=settlement(amount="10000.00"),
    )
    assert funded.status_code == 201, funded.text
    payload = {
        "fiscal_year_id": 1,
        "bank_account_id": 1,
        "content": LOAN_SHEET,
    }
    preview = client.post("/api/operations/loans/1/payments/import/preview", json=payload)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["source_count"] == 4
    assert body["outside_year"] == 2
    assert body["future"] == 0
    assert body["count"] == 2
    assert body["loan_reference"] == "085644F"
    assert body["rows"][0] == {
        "loan_reference": "085644F",
        "rank": "1",
        "date": "2025-02-05",
        "principal": "100.00",
        "interest": "20.00",
        "insurance": "5.00",
        "other_costs": "0.00",
        "amount": "125.00",
        "duplicate": False,
        "piece_reference": "ECH-164000-2025-02-05",
    }
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 1

    imported = client.post("/api/operations/loans/1/payments/import", json=payload)
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported"] == 2
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 3
    assert client.get("/api/operations/loans").json()[0]["remaining_principal"] == "9799.00"
    payments = {
        row["date"]: row
        for row in client.get("/api/operations?fiscal_year_id=1").json()
        if row["kind"] == "LOAN_PAYMENT"
    }
    assert payments["2025-02-05"]["principal"] == "100.00"
    assert payments["2025-02-05"]["interest"] == "20.00"
    assert payments["2025-02-05"]["insurance"] == "5.00"

    repeated = client.post("/api/operations/loans/1/payments/import", json=payload)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["imported"] == 0
    assert all(row["duplicate"] for row in repeated.json()["rows"])

    conflict = LOAN_SHEET.replace(
        "100,00\t20,00\t5,00\t\t125,00",
        "100,00\t21,00\t5,00\t\t126,00",
    )
    refused = client.post(
        "/api/operations/loans/1/payments/import",
        json={**payload, "content": conflict},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "LOAN_CSV_CONFLICT"
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 3


def test_loan_sheet_requires_existing_principal_balance(client):
    loan(client)
    payload = {
        "fiscal_year_id": 1,
        "bank_account_id": 1,
        "content": LOAN_SHEET,
    }
    response = client.post("/api/operations/loans/1/payments/import/preview", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "LOAN_NOT_FUNDED"
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0


def test_loan_sheet_accepts_google_csv_export(client):
    loan(client)
    funded = client.post(
        "/api/operations/loans/1/fund",
        json=settlement(amount="10000.00"),
    )
    assert funded.status_code == 201, funded.text
    content = (
        "Prêt,Rang,Date,Capital (€),Intérêts (€),Assurance banque (€),"
        "Assurance externe à compléter (€),Total banque (€)\n"
        "085644F,1,2025-02-05,100.00,20.00,5.00,,125.00\n"
    )
    response = client.post(
        "/api/operations/loans/1/payments/import/preview",
        json={"fiscal_year_id": 1, "bank_account_id": 1, "content": content},
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows"][0]["amount"] == "125.00"


@pytest.mark.parametrize(
    "content,code",
    [
        (
            LOAN_SHEET.replace("085644F\t2", "085645F\t2"),
            "LOAN_CSV_MULTIPLE_LOANS",
        ),
        (
            LOAN_SHEET.replace(
                "100,00\t20,00\t5,00\t\t125,00",
                "100,00\t20,00\t5,00\t3,00\t125,00",
            ),
            "LOAN_CSV_EXTERNAL_INSURANCE",
        ),
        (
            LOAN_SHEET.replace("100,00\t20,00\t5,00\t\t125,00", "100,00\t20,00\t5,00\t\t124,00"),
            "LOAN_CSV_SPLIT",
        ),
        (
            LOAN_SHEET.replace("05/03/2025", "05/02/2025"),
            "LOAN_CSV_DUPLICATE_DATE",
        ),
        (
            LOAN_SHEET.replace("Capital (€)", "Montant amorti"),
            "LOAN_CSV_HEADER",
        ),
    ],
)
def test_loan_sheet_invalid_input_is_rejected(client, content, code):
    loan(client)
    response = client.post(
        "/api/operations/loans/1/payments/import/preview",
        json={"fiscal_year_id": 1, "bank_account_id": 1, "content": content},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0


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


OPS = (
    "kind;date;piece_date;type;counterparty;amount;description;piece_reference;source_file\n"
    "REVENUE;2025-03-01;2025-03-01;LOY;Martin;850,00;Loyer mars;LOY-2025-03-Martin;quittance.pdf\n"
    "EXPENSE;2025-02-12;2025-02-12;ASS;MAIF;186.40;Assurance PNO;ASS-2025-02-MAIF;maif.pdf\n"
)


def test_operations_csv_preview_import_reimport_and_conflict(client):
    payload = {"property_id": 1, "fiscal_year_id": 1, "content": OPS}
    preview = client.post("/api/operations/import/preview", json=payload)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["imported"] == 0
    assert body["rows"][0]["accounting_account"] == "706000"
    assert body["rows"][0]["duplicate"] is False
    assert body["rows"][1]["accounting_account"] == "616000"
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0
    imported = client.post("/api/operations/import", json=payload)
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported"] == 2
    assert client.post("/api/operations/import", json=payload).json()["imported"] == 0
    operations = client.get("/api/operations?fiscal_year_id=1").json()
    revenue = next(row for row in operations if row["kind"] == "REVENUE")
    expense = next(row for row in operations if row["kind"] == "EXPENSE")
    assert revenue["remaining_to_settle"] == "850.00"
    assert revenue["fiscal_treatment"] == "REQUIRES_REVIEW"
    assert expense["remaining_to_settle"] == "186.40"
    rent_entry = client.get("/api/ledger/entries/" + str(revenue["accounting_entry_id"])).json()
    charge_entry = client.get("/api/ledger/entries/" + str(expense["accounting_entry_id"])).json()
    assert {line["account_number"] for line in rent_entry["lines"]} == {"411000", "706000"}
    assert {line["account_number"] for line in charge_entry["lines"]} == {"401000", "616000"}
    assert rent_entry["journal_code"] == "VE"
    assert charge_entry["journal_code"] == "AC"
    conflict = OPS.replace("850,00", "851.00")
    assert (
        client.post("/api/operations/import", json={**payload, "content": conflict}).status_code
        == 409
    )
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 2


@pytest.mark.parametrize(
    "content",
    [
        "kind,date,piece_date,type,counterparty,amount,description,piece_reference,source_file\n",
        OPS.replace("LOY", "ASS", 1),
        OPS.replace("850,00", "0"),
        OPS.replace("850,00", "-10.00"),
        OPS.replace("2025-03-01", "2025-02-30", 1),
        OPS.replace("2025-03-01", "2024-03-01", 1),
        OPS + "REVENUE;2025-04-01;2025-04-01;LOY;Martin;1.00;Loyer;LOY-2025-03-Martin;\n",
        "kind;date;piece_date;type;counterparty;amount;description;piece_reference;source_file\n",
    ],
)
def test_operations_csv_invalid_input_rejected(client, content):
    assert (
        client.post(
            "/api/operations/import",
            json={"property_id": 1, "fiscal_year_id": 1, "content": content},
        ).status_code
        == 422
    )
    assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0


SHEET_PASTE = (
    "kind\tdate\tpiece_date\ttype\tcounterparty\tamount\tdescription\tpiece_reference\t"
    "source_file\tpaid\n"
    "Recette\t06/04/2025\t\tloy\tMartin\t850,00 €\tLoyer avril\tLOY-2025-04\tquittance.pdf\toui\n"
    "Dépense\t15/10/2025\t10/10/2025\tFON\tTrésor public\t1\u202f200,00\tTaxe foncière\t"
    "FON-2025\tavis.pdf\tnon\n"
    "\t\t\t\t\t\t\t\t\t\n"
)


def test_google_sheet_paste_imports_paid_and_unpaid_rows(client):
    payload = {"property_id": 1, "fiscal_year_id": 1, "content": SHEET_PASTE}
    refused = client.post("/api/operations/import/preview", json=payload)
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "BANK_REQUIRED"
    preview = client.post("/api/operations/import/preview", json={**payload, "bank_account_id": 1})
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    assert [row["date"] for row in rows] == ["2025-04-06", "2025-10-15"]
    assert rows[0]["piece_date"] == "2025-04-06"
    assert [row["amount"] for row in rows] == ["850.00", "1200.00"]
    assert [row["paid"] for row in rows] == [True, False]
    imported = client.post("/api/operations/import", json={**payload, "bank_account_id": 1})
    assert imported.json()["imported"] == 2
    operations = {row["kind"]: row for row in client.get("/api/operations").json()}
    assert operations["REVENUE"]["remaining_to_settle"] == "0.00"
    assert operations["EXPENSE"]["remaining_to_settle"] == "1200.00"
    rent = client.get(f"/api/ledger/entries/{operations['REVENUE']['accounting_entry_id']}").json()
    assert {line["account_number"] for line in rent["lines"]} == {"512000", "706000"}


def test_migration_refuses_to_discard_business_records(client, settings, database):
    create(client)
    database.engine.dispose()
    with pytest.raises(RuntimeError, match="Cannot discard business records"):
        command.downgrade(migration_config(settings), "0002_ledger")
    with database.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == SCHEMA_REVISION
        assert connection.scalar(text("SELECT COUNT(*) FROM business_operation")) == 1
