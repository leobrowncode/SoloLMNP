from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from alembic import command
from app.core.config import Settings
from app.core.database import SCHEMA_REVISION, Database
from app.main import create_app
from tests.conftest import migration_config


def test_liveness_does_not_claim_readiness_or_migrate(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        response = client.get("/api/status")
        assert response.status_code == 503
        assert response.json()["database"]["schema_revision"] is None
        assert response.json()["fiscal"] == {"status": "research_only", "available_vintages": []}
        assert response.headers["Cache-Control"] == "no-store"


def test_readiness_after_migration_and_application_restart(settings: Settings) -> None:
    command.upgrade(migration_config(settings), "head")
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            response = client.get("/api/status")
            assert response.status_code == 200
            assert response.json()["database"] == {
                "status": "ready",
                "schema_revision": SCHEMA_REVISION,
                "expected_revision": SCHEMA_REVISION,
            }


def test_unknown_schema_revision_is_not_ready(settings: Settings, database: Database) -> None:
    with database.engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'future_revision'"))
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/status").status_code == 503


def test_corrupt_database_does_not_leak_path(settings: Settings) -> None:
    settings.database_path.write_bytes(b"not a sqlite database")
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/status")
        assert response.status_code == 503
        assert str(settings.database_path) not in response.text
        assert "SELECT" not in response.text


def test_host_and_cors_boundaries(settings: Settings) -> None:
    settings = settings.model_copy(update={"cors_origins": ("http://localhost:5173",)})
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400
        denied = client.get("/api/health", headers={"Origin": "https://attacker.example"})
        assert "access-control-allow-origin" not in denied.headers
        allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-credentials" not in allowed.headers
        assert client.post("/api/status").status_code == 405


def test_production_disables_interactive_api_docs(settings: Settings) -> None:
    settings = settings.model_copy(update={"app_env": "production"})
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/openapi.json").status_code == 404


def test_import_factory_does_not_create_database(tmp_path: Path) -> None:
    config = Settings(
        _env_file=None, database_url=f"sqlite:///{tmp_path.as_posix()}/nested/db.sqlite3"
    )
    application = create_app(config)
    assert not config.database_path.parent.exists()
    application.state.database.engine.dispose()
