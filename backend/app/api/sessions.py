"""Common serialized write dependencies for the local API."""

from collections.abc import Callable, Iterator

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.database import Database
from app.services.ledger import fail


def dependencies(
    database: Database,
) -> tuple[Callable[[], Iterator[Session]], Callable[[], Iterator[Session]]]:
    def read() -> Iterator[Session]:
        try:
            with database.sessions() as session:
                yield session
        except OperationalError:
            fail("DATABASE_UNAVAILABLE", "Base indisponible : vérifier les migrations.", 503)

    def write() -> Iterator[Session]:
        try:
            with database.engine.connect().execution_options(sqlite_write=True) as connection:
                with (
                    connection.begin(),
                    Session(bind=connection, expire_on_commit=False) as session,
                ):
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
