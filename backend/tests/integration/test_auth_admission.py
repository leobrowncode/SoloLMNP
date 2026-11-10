"""GET /api/auth/admission checks ALLOWED_EMAILS without creating a Neon account."""

from fastapi.testclient import TestClient

from app.core.auth import TEST_EMAIL
from app.main import create_app


def test_admission_allows_a_listed_address(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/auth/admission", params={"email": TEST_EMAIL})
    assert response.status_code == 200
    assert response.json() == {"status": "allowed"}


def test_admission_rejects_an_unknown_address(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/auth/admission", params={"email": "intrus@example.com"})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "EMAIL_NOT_ALLOWED"


def test_admission_rejects_a_malformed_address(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/auth/admission", params={"email": "pas-un-email"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_EMAIL"


def test_admission_works_without_authorization(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/auth/admission", params={"email": TEST_EMAIL})
    assert response.status_code == 200
