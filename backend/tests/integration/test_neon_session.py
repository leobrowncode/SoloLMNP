"""GET /api/status accepts a Neon JWT whose issuer is the auth origin."""

import pytest
from fastapi.testclient import TestClient

from app.core.auth import TEST_EMAIL
from app.core.config import Settings
from app.core.database import Database
from app.main import create_app
from tests.neon_jwt import KID, ed25519_jwks, install_jwks, sign_neon

BASE = "https://ep.example/neondb/auth"
ORIGIN = "https://ep.example"


def _settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "auth_mode": "neon",
            "neon_auth_base_url": BASE,
            "neon_auth_jwks_url": f"{BASE}/.well-known/jwks.json",
        }
    )


def _client(settings: Settings, token: str) -> TestClient:
    return TestClient(create_app(_settings(settings)), headers={"Authorization": "Bearer " + token})


def test_status_accepts_an_origin_issuer(
    settings: Settings, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    del database
    private, document = ed25519_jwks()
    install_jwks(monkeypatch, document)
    token = sign_neon(private, issuer=ORIGIN, audience=ORIGIN, email=TEST_EMAIL)
    with _client(settings, token) as client:
        response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["database"]["status"] == "ready"


def test_status_rejects_the_full_auth_url_as_issuer(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    private, document = ed25519_jwks()
    install_jwks(monkeypatch, document)
    token = sign_neon(private, issuer=BASE, audience=ORIGIN, email=TEST_EMAIL)
    with _client(settings, token) as client:
        response = client.get("/api/status")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_TOKEN"


def test_status_forbids_an_email_outside_the_allowlist(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    private, document = ed25519_jwks()
    install_jwks(monkeypatch, document)
    token = sign_neon(private, issuer=ORIGIN, audience=ORIGIN, email="intrus@example.com")
    with _client(settings, token) as client:
        response = client.get("/api/status")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "EMAIL_NOT_ALLOWED"


def test_status_rejects_a_bad_signature(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _published, document = ed25519_jwks()
    install_jwks(monkeypatch, document)
    other, _other_document = ed25519_jwks("other-key")
    token = sign_neon(other, issuer=ORIGIN, audience=ORIGIN, email=TEST_EMAIL, kid=KID)
    with _client(settings, token) as client:
        response = client.get("/api/status")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_TOKEN"
