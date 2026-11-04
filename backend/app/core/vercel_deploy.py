"""Decide where a Vercel build may run Alembic.

Preview deployments use the Neon branch injected for that deployment. They
refuse the production host. The advisory lock is session-scoped, so the
migration connection must be the direct Neon URL, not the pooler.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import psycopg
from psycopg import Connection
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings

MIGRATION_LOCK_KEY = 872_122
_REQUIRED = (
    "DATABASE_URL",
    "DATABASE_URL_UNPOOLED",
    "NEON_AUTH_BASE_URL",
    "VITE_NEON_AUTH_URL",
    "BLOB_READ_WRITE_TOKEN",
    "ALLOWED_EMAILS",
)


class DeployGuardError(RuntimeError):
    """The build must stop. The message never includes a URL or a secret."""


@dataclass(frozen=True)
class MigrationPlan:
    vercel_env: str
    host: str
    sqlalchemy_url: str


def endpoint_identity(value: str) -> str:
    """Compare a pooled host and its direct host as the same Neon endpoint."""
    host = host_only(value)
    label, dot, rest = host.partition(".")
    if label.endswith("-pooler"):
        label = label[: -len("-pooler")]
    return f"{label}{dot}{rest}"


def host_only(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlsplit(raw).hostname or ""
    else:
        raw = raw.split("/")[0]
        if raw.startswith("[") and "]" in raw:
            raw = raw[1 : raw.index("]")]
        elif ":" in raw:
            raw = raw.split(":", 1)[0]
    return raw.lower()


def plan_migration(env: Mapping[str, str]) -> MigrationPlan:
    vercel_env = env.get("VERCEL_ENV", "")
    if vercel_env not in {"preview", "production"}:
        raise DeployGuardError("Migration Vercel réservée à preview et production.")
    if env.get("APP_ENV") != "production":
        raise DeployGuardError("APP_ENV doit valoir production sur Vercel.")
    auth_mode = env.get("AUTH_MODE", "neon").strip() or "neon"
    if auth_mode != "neon":
        raise DeployGuardError("AUTH_MODE=test est refusé sur Vercel.")
    missing = [name for name in _REQUIRED if not env.get(name, "").strip()]
    if missing:
        raise DeployGuardError("Variable manquante : " + ", ".join(missing) + ".")
    base_url = env["NEON_AUTH_BASE_URL"].strip().rstrip("/")
    vite_url = env["VITE_NEON_AUTH_URL"].strip().rstrip("/")
    _require_https("NEON_AUTH_BASE_URL", base_url)
    _require_https("VITE_NEON_AUTH_URL", vite_url)
    if base_url != vite_url:
        raise DeployGuardError("VITE_NEON_AUTH_URL doit être la même URL que NEON_AUTH_BASE_URL.")
    pooled = _postgres_settings("DATABASE_URL", env["DATABASE_URL"])
    direct = _postgres_settings("DATABASE_URL_UNPOOLED", env["DATABASE_URL_UNPOOLED"])
    pooled_host = make_url(pooled.database_url).host or ""
    direct_host = make_url(direct.database_url).host or ""
    if endpoint_identity(pooled_host) != endpoint_identity(direct_host):
        raise DeployGuardError(
            "DATABASE_URL et DATABASE_URL_UNPOOLED ne visent pas le même endpoint Neon."
        )
    if vercel_env == "preview":
        production_host = env.get("SOLOLMNP_PRODUCTION_DB_HOST", "").strip()
        if not production_host:
            raise DeployGuardError(
                "Preview : SOLOLMNP_PRODUCTION_DB_HOST est requis "
                "(hôte Neon de production, sans identifiant). "
                "La migration est refusée tant qu’il manque."
            )
        if endpoint_identity(direct_host) == endpoint_identity(production_host):
            raise DeployGuardError("Preview : refus de migrer la base de production.")
    return MigrationPlan(
        vercel_env=vercel_env, host=direct_host, sqlalchemy_url=direct.database_url
    )


def psycopg_dsn(sqlalchemy_url: str) -> str:
    url = make_url(sqlalchemy_url)
    if url.drivername == "postgresql+psycopg":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


@contextmanager
def advisory_migration_lock(
    connection: Connection[Any], *, timeout: str = "180s"
) -> Iterator[None]:
    """One migration at a time. A timeout fails the build instead of waiting forever."""
    connection.execute("SELECT set_config('lock_timeout', %s, false)", (timeout,))
    try:
        connection.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
    except psycopg.errors.LockNotAvailable as exc:
        raise DeployGuardError(
            "Une autre migration tient le verrou. Le déploiement s’arrête."
        ) from exc
    try:
        yield
    finally:
        connection.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_KEY,))


def _require_https(name: str, value: str) -> None:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise DeployGuardError(f"{name} doit être une URL https sans secret.")


def _postgres_settings(name: str, url: str) -> Settings:
    try:
        settings = Settings(_env_file=None, database_url=url)
    except ValidationError as exc:
        fields = ", ".join(
            ".".join(str(part) for part in error["loc"]) or name for error in exc.errors()
        )
        raise DeployGuardError(f"Configuration refusée ({fields}).") from None
    if settings.uses_sqlite:
        raise DeployGuardError(f"{name} doit être une URL Postgres.")
    return settings
