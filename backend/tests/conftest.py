import os
import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from alembic import command
from app.core.config import Settings
from app.core.database import Database

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_IDENT = re.compile(r"^[a-z0-9_]+$")
_TEMPLATE = "sololmnp_template"


def migration_config(settings: Settings) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["settings"] = settings
    return config


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "sqlite_file: test needs the on-disk SQLite file and its backup path",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    if not os.environ.get("TEST_DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="Sauvegarde fichier réservée à SQLite")
    for item in items:
        if item.get_closest_marker("sqlite_file") is not None:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def postgres_template(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str | None]:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        yield None
        return
    _drop_database(admin_url, _TEMPLATE)
    _create_database(admin_url, _TEMPLATE)
    template_settings = _postgres_settings(
        admin_url,
        _TEMPLATE,
        documents_dir=tmp_path_factory.mktemp("template-documents"),
    )
    command.upgrade(migration_config(template_settings), "head")
    _terminate(admin_url, _TEMPLATE)
    try:
        yield _TEMPLATE
    finally:
        _drop_database(admin_url, _TEMPLATE)


@pytest.fixture
def settings(tmp_path: Path, postgres_template: str | None) -> Iterator[Settings]:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url or postgres_template is None:
        yield Settings(
            _env_file=None,
            app_env="test",
            database_url=f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
            documents_dir=tmp_path / "documents",
            allowed_hosts=("testserver", "localhost", "127.0.0.1"),
        )
        return
    name = f"sololmnp_t_{uuid.uuid4().hex}"
    _create_database(admin_url, name, template=postgres_template)
    try:
        yield _postgres_settings(admin_url, name, documents_dir=tmp_path / "documents")
    finally:
        _drop_database(admin_url, name)


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    if settings.uses_sqlite:
        command.upgrade(migration_config(settings), "head")
    database = Database(settings)
    try:
        yield database
    finally:
        database.engine.dispose()


def _postgres_settings(admin_url: str, name: str, documents_dir: Path) -> Settings:
    database_url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=database_url,
        documents_dir=documents_dir,
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )


def _admin(url: str):
    return create_engine(make_url(url), isolation_level="AUTOCOMMIT", poolclass=NullPool)


def _checked(name: str) -> str:
    if _IDENT.fullmatch(name) is None:
        raise RuntimeError(f"Nom de base inattendu : {name}")
    return name


def _create_database(url: str, name: str, template: str | None = None) -> None:
    database = _checked(name)
    clause = f'CREATE DATABASE "{database}"'
    if template is not None:
        clause += f' TEMPLATE "{_checked(template)}"'
    engine = _admin(url)
    try:
        with engine.connect() as connection:
            if template is not None:
                _terminate_connection(connection, template)
            connection.exec_driver_sql(clause)
    finally:
        engine.dispose()


def _drop_database(url: str, name: str) -> None:
    database = _checked(name)
    engine = _admin(url)
    try:
        with engine.connect() as connection:
            _terminate_connection(connection, database)
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database}"')
    finally:
        engine.dispose()


def _terminate(url: str, name: str) -> None:
    engine = _admin(url)
    try:
        with engine.connect() as connection:
            _terminate_connection(connection, name)
    finally:
        engine.dispose()


def _terminate_connection(connection, name: str) -> None:
    connection.execute(
        text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :name AND pid <> pg_backend_pid()"
        ),
        {"name": name},
    )
