from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from app.core.config import Settings
from app.core.database import Database

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(settings: Settings) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["settings"] = settings
    return config


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    command.upgrade(migration_config(settings), "head")
    database = Database(settings)
    try:
        yield database
    finally:
        database.engine.dispose()
