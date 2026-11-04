"""Common serialized write dependencies for the local API."""

from collections.abc import Callable, Iterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.database import Database
from app.core.ownership import resolve_owner_id
from app.services.ledger import fail

# One lock for every write. SQLite uses BEGIN IMMEDIATE; Postgres has no equivalent.
_POSTGRES_WRITE_LOCK = 119_001


def dependencies(
    database: Database,
) -> tuple[Callable[[Request], Iterator[Session]], Callable[[Request], Iterator[Session]]]:
    def read(request: Request) -> Iterator[Session]:
        owner_id = resolve_owner_id(database, request.state.principal)
        try:
            with database.sessions() as session:
                session.info["owner_id"] = owner_id
                yield session
        except OperationalError:
            fail("DATABASE_UNAVAILABLE", "Base indisponible : vérifier les migrations.", 503)

    def write(request: Request) -> Iterator[Session]:
        owner_id = resolve_owner_id(database, request.state.principal)
        try:
            with database.engine.connect().execution_options(sqlite_write=True) as connection:
                with (
                    connection.begin(),
                    Session(bind=connection, expire_on_commit=False) as session,
                ):
                    if connection.dialect.name == "postgresql":
                        connection.execute(
                            text("SELECT pg_advisory_xact_lock(:key)"),
                            {"key": _POSTGRES_WRITE_LOCK},
                        )
                    session.info["owner_id"] = owner_id
                    yield session
                    session.flush()
        except IntegrityError:
            fail("INTEGRITY_CONFLICT", "Opération refusée par les contraintes d’intégrité.", 409)
        except OperationalError:
            fail(
                "DATABASE_BUSY",
                "Base occupée ou indisponible. Vérifiez l’opération avant de réessayer.",
                503,
            )

    return read, write
