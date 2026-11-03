"""Migrations use the same engine configuration as the API."""

from sqlalchemy import text

from alembic import context
from app.core.config import Settings
from app.core.database import create_database_engine
from app.core.postgres_ddl import (
    TYPEOF_SQL,
    ensure_postgres_identities,
    install_postgres_ddl_adapter,
)
from app.models import Base

settings = context.config.attributes.get("settings") or Settings()
target_metadata = Base.metadata


def _configure_kwargs() -> dict[str, object]:
    return {
        "target_metadata": target_metadata,
        "render_as_batch": settings.uses_sqlite,
        "compare_type": True,
        "transactional_ddl": True,
    }


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_kwargs(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if settings.uses_sqlite:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            install_postgres_ddl_adapter(connection)
            context.configure(connection=connection, **_configure_kwargs())
            with context.begin_transaction():
                if connection.dialect.name == "postgresql":
                    connection.execute(text(TYPEOF_SQL))
                context.run_migrations()
                ensure_postgres_identities(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
