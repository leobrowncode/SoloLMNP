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
    blob_read_write_token: str = Field(default="", repr=False)

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
    def supported_database(cls, value: str) -> str:
        url = make_url(value)
        backend = url.get_backend_name()
        if backend == "sqlite":
            if (
                url.drivername not in {"sqlite", "sqlite+pysqlite"}
                or not url.database
                or url.database == ":memory:"
                or url.host
                or url.username
                or url.password
                or url.query
            ):
                raise ValueError(
                    "A SQLite DATABASE_URL must point to a local file without URL options"
                )
            path = Path(url.database)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return url.set(database=path.resolve().as_posix()).render_as_string(hide_password=False)
        if backend == "postgresql":
            if url.drivername in {"postgresql", "postgres"}:
                url = url.set(drivername="postgresql+psycopg")
            elif url.drivername != "postgresql+psycopg":
                raise ValueError("Postgres requires the psycopg driver (postgresql+psycopg)")
            if not url.host or not url.database:
                raise ValueError("Postgres DATABASE_URL needs a host and a database name")
            allowed = {"sslmode", "channel_binding", "connect_timeout", "application_name"}
            unknown = set(url.query) - allowed
            if unknown:
                raise ValueError("Unsupported Postgres URL options: " + ", ".join(sorted(unknown)))
            return url.render_as_string(hide_password=False)
        raise ValueError("DATABASE_URL must be a SQLite file or a Postgres URL")

    @field_validator("blob_read_write_token")
    @classmethod
    def plain_blob_token(cls, value: str) -> str:
        token = value.strip()
        if any(character.isspace() for character in token):
            raise ValueError("BLOB_READ_WRITE_TOKEN must be a single token")
        return token

    @property
    def uses_blob(self) -> bool:
        return bool(self.blob_read_write_token)

    @property
    def uses_sqlite(self) -> bool:
        return make_url(self.database_url).get_backend_name() == "sqlite"

    @property
    def database_path(self) -> Path:
        if not self.uses_sqlite:
            raise ValueError("database_path is only available for a SQLite file")
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
