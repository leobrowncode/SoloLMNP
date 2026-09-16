"""Shared configuration for API and migrations, independent of working directory."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")
    app_env: Literal["development", "production", "test"] = "development"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data/sololmnp.sqlite3').as_posix()}"
    documents_dir: Path = PROJECT_ROOT / "data/documents"
    cors_origins: Annotated[tuple[str, ...], NoDecode] = ()
    allowed_hosts: Annotated[tuple[str, ...], NoDecode] = ("localhost", "127.0.0.1", "[::1]")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def parse_list(cls, value: object) -> object:
        if isinstance(value, str):
            if value.lstrip().startswith("["):
                return json.loads(value)
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError("CORS requires explicit HTTP(S) origins without paths")
            _ = parsed.port
        return origins

    @field_validator("allowed_hosts")
    @classmethod
    def explicit_hosts(cls, hosts: tuple[str, ...]) -> tuple[str, ...]:
        if not hosts or any(not host or any(c in host for c in "*/@?# ") for host in hosts):
            raise ValueError("At least one explicit host is required; wildcards are forbidden")
        return hosts

    @field_validator("database_url")
    @classmethod
    def file_sqlite_only(cls, value: str) -> str:
        url = make_url(value)
        if (
            url.drivername not in {"sqlite", "sqlite+pysqlite"}
            or not url.database
            or url.database == ":memory:"
            or url.host
            or url.username
            or url.password
            or url.query
        ):
            raise ValueError("DATABASE_URL must point to a local SQLite file without URL options")
        path = Path(url.database)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return url.set(database=path.resolve().as_posix()).render_as_string(hide_password=False)

    @property
    def database_path(self) -> Path:
        database = make_url(self.database_url).database
        if database is None:
            raise ValueError("SQLite database path is missing")
        return Path(database)

    @field_validator("documents_dir")
    @classmethod
    def absolute_documents_directory(cls, value: Path) -> Path:
        return (value if value.is_absolute() else PROJECT_ROOT / value).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
