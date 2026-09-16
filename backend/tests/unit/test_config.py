from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import PROJECT_ROOT, Settings


@pytest.mark.parametrize(
    "value", ["*", "null", "https://*.example.com", "https://example.com/path"]
)
def test_unsafe_origins_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=(value,))


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://localhost/db",
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///data/db.sqlite3?mode=ro",
    ],
)
def test_database_must_be_local_file(value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=value)


def test_env_lists_support_documented_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    monkeypatch.setenv("ALLOWED_HOSTS", '["localhost", "127.0.0.1"]')
    config = Settings(_env_file=None)
    assert config.cors_origins == ("http://localhost:5173", "http://127.0.0.1:5173")
    assert config.allowed_hosts == ("localhost", "127.0.0.1")
    monkeypatch.setenv("CORS_ORIGINS", "[]")
    assert Settings(_env_file=None).cors_origins == ()


def test_relative_database_path_is_independent_of_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config = Settings(_env_file=None, database_url="sqlite:///data/sololmnp.sqlite3")
    assert config.database_path == PROJECT_ROOT / "data/sololmnp.sqlite3"


def test_wildcard_host_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_hosts=("*",))
