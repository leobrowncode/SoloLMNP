"""Common serialized write dependencies for the local API."""

from collections.abc import Callable, Iterator

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.database import Database
from app.services.ledger import fail

_GENERIC_INTEGRITY = "Opération refusée par les contraintes d’intégrité."
_INTEGRITY_MESSAGES: tuple[tuple[str, str, str], ...] = (
    (
        "OVERLAPPING_EXERCISE",
        "OVERLAPPING_EXERCISE",
        "Ces dates chevauchent un exercice existant. L’exercice suivant doit "
        "commencer le lendemain de la fin du précédent.",
    ),
    (
        "UNIQUE constraint failed: fiscal_year.rental_activity_id, fiscal_year.year",
        "DUPLICATE_CLOSING_YEAR",
        "Un exercice existe déjà pour cette année de clôture. Elle correspond "
        "à l’année civile de la date de fin.",
    ),
    (
        "UNIQUE constraint failed: loan.principal_account",
        "LOAN_ACCOUNT_IN_USE",
        "Ce compte 164 est déjà utilisé par un emprunt. Chaque emprunt exige "
        "un compte de capital distinct.",
    ),
    (
        "UNIQUE constraint failed: bank_account.account_number",
        "BANK_ACCOUNT_IN_USE",
        "Ce compte 512 est déjà rattaché à une banque. Chaque compte bancaire "
        "exige un compte comptable distinct.",
    ),
)


def integrity_conflict(error: IntegrityError) -> tuple[str, str]:
    """Translate user-reachable SQLite refusals. Unknown conflicts stay generic."""
    text = "" if error.orig is None else str(error.orig)
    for token, code, message in _INTEGRITY_MESSAGES:
        if token in text:
            return code, message
    return "INTEGRITY_CONFLICT", _GENERIC_INTEGRITY


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
        except IntegrityError as error:
            fail(*integrity_conflict(error), 409)
        except OperationalError:
            fail(
                "DATABASE_BUSY",
                "Base occupée ou indisponible. Vérifiez l’opération avant de réessayer.",
                503,
            )

    return read, write
