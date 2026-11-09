import os
from collections.abc import Mapping

import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.core.vercel_deploy import (
    MIGRATION_LOCK_KEY,
    DeployGuardError,
    advisory_migration_lock,
    endpoint_identity,
    plan_migration,
    psycopg_dsn,
)

_AUTH = "https://ep-preview.neonauth.eu-central-1.aws.neon.tech/neondb/auth"
_DIRECT = "postgresql://user:secret@ep-preview.eu-central-1.aws.neon.tech/db?sslmode=require"
_POOLED = "postgresql://user:secret@ep-preview-pooler.eu-central-1.aws.neon.tech/db?sslmode=require"


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "VERCEL_ENV": "preview",
        "APP_ENV": "production",
        "AUTH_MODE": "neon",
        "DATABASE_URL": _POOLED,
        "DATABASE_URL_UNPOOLED": _DIRECT,
        "NEON_AUTH_BASE_URL": _AUTH,
        "VITE_NEON_AUTH_URL": _AUTH,
        "BLOB_READ_WRITE_TOKEN": "vercel_blob_rw_store_secret",
        "ALLOWED_EMAILS": "ada@example.com",
        "SOLOLMNP_PRODUCTION_DB_HOST": "ep-prod.eu-central-1.aws.neon.tech",
    }
    base.update(overrides)
    return base


def test_preview_plans_the_direct_url_of_its_own_branch() -> None:
    plan = plan_migration(_env())
    assert plan.host == "ep-preview.eu-central-1.aws.neon.tech"
    assert plan.vercel_env == "preview"
    assert "ep-preview-pooler" not in plan.sqlalchemy_url
    assert plan.sqlalchemy_url.startswith("postgresql+psycopg://")


def test_preview_refuses_the_production_host() -> None:
    with pytest.raises(DeployGuardError, match="production"):
        plan_migration(
            _env(
                DATABASE_URL=(
                    "postgresql://user:secret@ep-prod-pooler.eu-central-1.aws.neon.tech/db"
                    "?sslmode=require"
                ),
                DATABASE_URL_UNPOOLED=(
                    "postgresql://user:secret@ep-prod.eu-central-1.aws.neon.tech/db?sslmode=require"
                ),
            )
        )


def test_preview_refuses_to_migrate_without_the_production_host() -> None:
    env = _env()
    del env["SOLOLMNP_PRODUCTION_DB_HOST"]
    with pytest.raises(DeployGuardError, match="SOLOLMNP_PRODUCTION_DB_HOST"):
        plan_migration(env)


def test_production_does_not_need_the_preview_guard() -> None:
    env = _env(VERCEL_ENV="production")
    del env["SOLOLMNP_PRODUCTION_DB_HOST"]
    assert plan_migration(env).vercel_env == "production"


@pytest.mark.parametrize(
    "overrides",
    [
        {"AUTH_MODE": "test"},
        {"AUTH_MODE": "local"},
        {"VITE_AUTH_MODE": "local"},
        {"VITE_AUTH_MODE": "test"},
        {"APP_ENV": "development"},
        {"ALLOWED_EMAILS": ""},
        {"BLOB_READ_WRITE_TOKEN": ""},
        {"VITE_NEON_AUTH_URL": "https://other.example/auth"},
        {"DATABASE_URL": "sqlite:///data/sololmnp.sqlite3"},
        {
            "DATABASE_URL_UNPOOLED": (
                "postgresql://user:secret@ep-other.eu-central-1.aws.neon.tech/db?sslmode=require"
            )
        },
    ],
)
def test_unsafe_deployment_env_is_refused(overrides: Mapping[str, str]) -> None:
    with pytest.raises(DeployGuardError) as caught:
        plan_migration(_env(**dict(overrides)))
    message = str(caught.value)
    assert "://" not in message
    assert "secret" not in message


def test_pooler_suffix_is_the_same_endpoint() -> None:
    assert endpoint_identity(
        "ep-preview-pooler.c-3.eu-central-1.aws.neon.tech"
    ) == endpoint_identity("ep-preview.c-3.eu-central-1.aws.neon.tech")


def test_psycopg_dsn_drops_the_sqlalchemy_driver() -> None:
    plan = plan_migration(_env(VERCEL_ENV="production"))
    dsn = psycopg_dsn(plan.sqlalchemy_url)
    assert make_url(dsn).drivername == "postgresql"
    assert "secret" in dsn


def test_migration_lock_blocks_a_second_session() -> None:
    admin = os.environ.get("TEST_DATABASE_URL")
    if not admin:
        pytest.skip("Verrou de migration : Postgres uniquement")
    dsn = psycopg_dsn(admin) if "+psycopg" in admin else admin
    with (
        psycopg.connect(dsn, autocommit=True) as holder,
        psycopg.connect(dsn, autocommit=True) as waiter,
    ):
        with advisory_migration_lock(holder):
            waiter.execute("SELECT set_config('lock_timeout', '200ms', false)")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                waiter.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
