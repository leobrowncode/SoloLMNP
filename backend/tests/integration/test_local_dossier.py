"""The local dossier opens without a Neon secret. Production does not claim that account."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.auth import LOCAL_EMAIL, LOCAL_SUBJECT
from app.core.config import Settings
from app.core.database import Database
from app.main import create_app
from app.models.account import AppAccount


def test_local_mode_opens_one_fixed_owner(
    settings: Settings, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    local = settings.model_copy(update={"app_env": "development", "auth_mode": "local"})
    with TestClient(create_app(local), headers={"Authorization": ""}) as client:
        first = client.get("/api/status")
        second = client.get("/api/status", headers={"Authorization": "Bearer autre-personne"})
    assert first.status_code == 200
    assert second.status_code == 200
    with database.sessions() as session:
        row = session.get(AppAccount, 1)
        count = session.scalar(select(func.count()).select_from(AppAccount))
    assert row is not None
    assert row.id == 1
    assert row.subject == LOCAL_SUBJECT
    assert row.email == LOCAL_EMAIL
    assert count == 1


def test_production_does_not_open_the_local_dossier(
    settings: Settings, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    production = settings.model_copy(
        update={
            "app_env": "production",
            "auth_mode": "neon",
            "neon_auth_base_url": "",
            "neon_auth_jwks_url": "",
        }
    )
    with TestClient(create_app(production), headers={"Authorization": ""}) as client:
        anonymous = client.get("/api/status")
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"]["code"] == "UNAUTHENTICATED"
    with TestClient(create_app(production)) as client:
        forged = client.get("/api/status")
    assert forged.status_code == 401
    assert forged.json()["detail"]["code"] == "AUTH_NOT_CONFIGURED"
    with database.sessions() as session:
        row = session.get(AppAccount, 1)
    assert row is not None
    assert row.subject is None
