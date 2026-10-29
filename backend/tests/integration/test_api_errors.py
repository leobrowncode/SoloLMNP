import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_operations import loan


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        assert (
            client.post(
                "/api/ledger/activity",
                json={"activity_name": "Opérations fictives", "activity_start_date": "2025-01-01"},
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
        assert (
            client.post(
                "/api/operations/properties",
                json={
                    "name": "Bien fictif",
                    "address": "Adresse fictive",
                    "acquisition_date": "2025-01-01",
                    "acquisition_price": "100000.00",
                    "land_value": "20000.00",
                    "building_value": "80000.00",
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/operations/banks",
                json={"name": "Banque fictive", "account_number": "512000"},
            ).status_code
            == 201
        )
        yield client


def test_validation_error_returns_structured_issues(client: TestClient) -> None:
    response = client.post("/api/ledger/entries", json={"fiscal_year_id": 1})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert detail["message"]
    assert isinstance(detail["issues"], list)
    assert detail["issues"][0]["field"]
    assert detail["issues"][0]["message"]


def test_business_error_includes_resolution_action(settings, database) -> None:
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as bare:
        response = bare.post(
            "/api/operations/properties",
            json={
                "name": "Studio",
                "address": "1 rue de test",
                "acquisition_date": "2025-01-01",
                "acquisition_price": "100000.00",
                "land_value": "20000.00",
                "building_value": "80000.00",
            },
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "ACTIVITY_REQUIRED"
        assert detail["action"]["href"] == "/comptabilite"
        assert detail["action"]["label"]


def test_csv_import_error_preserves_line(client: TestClient) -> None:
    loan(client)
    header = "Prêt\tDate\tCapital (€)\tIntérêts (€)\tAssurance banque (€)\tTotal banque (€)"
    row = "085644F\t05/03/2025\txxx\t20,00\t5,00\t125,00"
    response = client.post(
        "/api/operations/loans/1/payments/import/preview",
        json={
            "fiscal_year_id": 1,
            "bank_account_id": 1,
            "content": f"{header}\n{row}\n",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "LOAN_CSV_AMOUNT"
    assert detail["line"] == 2
    assert detail["location"] == "import"


def test_write_without_trusted_header_returns_structured_global_error(settings, database) -> None:
    with TestClient(create_app(settings)) as bare:
        response = bare.post(
            "/api/ledger/activity",
            json={"activity_name": "X", "activity_start_date": "2025-01-01"},
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["code"] == "ORIGIN_REJECTED"
        assert detail["message"]
