"""A closed dossier copied from SQLite keeps the same FEC and liasse bytes."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alembic import command
from app.core.config import Settings
from app.core.database import Database
from app.main import create_app
from app.services.sqlite_transfer import copy_sqlite_to_postgres
from tests.conftest import migration_config
from tests.integration.test_closing import centralize
from tests.integration.test_statements import book

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="La parité Postgres se lance avec TEST_DATABASE_URL",
)


def test_closed_dossier_fec_and_liasse_match(
    tmp_path: Path,
    settings: Settings,
    database: Database,
) -> None:
    del database
    source_file = tmp_path / "source.sqlite3"
    source = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{source_file.as_posix()}",
        documents_dir=tmp_path / "documents",
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )
    command.upgrade(migration_config(source), "head")
    with TestClient(create_app(source), headers={"X-SoloLMNP-Request": "1"}) as client:
        _close_dossier(client)
    report = copy_sqlite_to_postgres(source, settings, replace=False)
    assert report["balances_equal"] is True
    assert report["fec_equal"] is True
    assert report["liasse_equal"] is True
    assert int(report["fec_bytes"]) > 0
    assert int(report["fiscal_years"]) == 1


def _close_dossier(client: TestClient) -> None:
    assert (
        client.post(
            "/api/ledger/activity",
            json={"activity_name": "Test fictif", "activity_start_date": "2025-01-01"},
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
    for number, label in (("120000", "Résultat bénéfice"), ("129000", "Résultat perte")):
        assert (
            client.post(
                "/api/ledger/accounts",
                json={"number": number, "label": label, "account_type": "EQUITY"},
            ).status_code
            == 201
        )
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "40.00")
    centralize(client, "60.00")
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    precheck = client.get("/api/filing/years/1/precheck")
    assert precheck.status_code == 200, precheck.text
    codes = [item["code"] for item in precheck.json()["warnings"]]
    ready = client.post("/api/filing/years/1/ready", json={"acknowledged": codes})
    assert ready.status_code == 200, ready.text
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
