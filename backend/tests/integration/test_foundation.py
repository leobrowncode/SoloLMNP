from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.core.database import SCHEMA_REVISION, Database
from app.models import FiscalYear, Property, RentalActivity
from tests.conftest import migration_config


def activity() -> RentalActivity:
    return RentalActivity(activity_name="Activité fictive", activity_start_date=date(2025, 1, 1))


def property_record() -> Property:
    return Property(
        rental_activity_id=1,
        name="Bien fictif",
        address="Adresse de test",
        acquisition_date=date(2025, 1, 1),
        acquisition_price=Decimal("123456.78"),
        acquisition_costs=Decimal("1234.56"),
        land_value=Decimal("23456.78"),
        building_value=Decimal("100000.00"),
    )


def fiscal_year(**changes: object) -> FiscalYear:
    fields: dict[str, object] = dict(
        rental_activity_id=1,
        year=2025,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        fiscal_vintage="2025",
    )
    fields.update(changes)
    return FiscalYear(**fields)


def test_migration_idempotent_and_metadata_matches(database: Database, settings: Settings) -> None:
    command.upgrade(migration_config(settings), "head")
    command.check(migration_config(settings))
    with database.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == SCHEMA_REVISION
        assert set(inspect(connection).get_table_names()) == {
            "alembic_version",
            "rental_activity",
            "property",
            "fiscal_year",
        }
        for pragma, expected in (("foreign_keys", 1), ("journal_mode", "wal"), ("synchronous", 2)):
            assert connection.exec_driver_sql(f"PRAGMA {pragma}").scalar() == expected


def test_exact_money_persists_across_sessions(database: Database) -> None:
    with database.sessions.begin() as session:
        session.add(activity())
        session.flush()
        session.add(property_record())
    with Session(database.engine) as session:
        result = session.scalars(select(Property)).one()
        assert result.acquisition_price == Decimal("123456.78")
        assert isinstance(result.acquisition_price, Decimal)
        stored = session.execute(
            text("SELECT acquisition_price, typeof(acquisition_price) FROM property")
        )
        assert stored.one() == (12345678, "integer")


def test_foreign_key_and_atomic_rollback(database: Database) -> None:
    with pytest.raises(IntegrityError), database.sessions.begin() as session:
        session.add(activity())
        session.flush()
        record = property_record()
        record.rental_activity_id = 999
        session.add(record)
    with Session(database.engine) as session:
        assert session.scalars(select(RentalActivity)).all() == []
        assert session.scalars(select(Property)).all() == []


def test_ddl_is_transactional(database: Database) -> None:
    with database.engine.connect() as connection:
        transaction = connection.begin()
        connection.exec_driver_sql("CREATE TABLE rollback_probe (id INTEGER)")
        transaction.rollback()
        assert "rollback_probe" not in inspect(connection).get_table_names()


@pytest.mark.parametrize("value", [Decimal("0.001"), Decimal("NaN"), 1.2, 1, True])
def test_money_adapter_rejects_unsafe_values(database: Database, value: object) -> None:
    with pytest.raises(StatementError), database.sessions.begin() as session:
        session.add(activity())
        session.flush()
        record = property_record()
        record.acquisition_price = value  # type: ignore[assignment]
        session.add(record)


@pytest.mark.parametrize("column,value", [("acquisition_price", -1), ("land_value", 1.5)])
def test_raw_sql_cannot_store_negative_or_fractional_money(
    database: Database,
    column: str,
    value: object,
) -> None:
    with database.sessions.begin() as session:
        session.add(activity())
        session.flush()
        session.add(property_record())
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        # Column comes exclusively from this test's fixed parameter list.
        connection.execute(text(f"UPDATE property SET {column} = :value"), {"value": value})  # noqa: S608


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "INVALID"},
        {"status": "CLOSED"},
        {"start_date": date(2026, 1, 1)},
        {"fiscal_vintage": " "},
    ],
)
def test_fiscal_year_database_constraints(database: Database, changes: dict[str, object]) -> None:
    with pytest.raises(IntegrityError), database.sessions.begin() as session:
        session.add(activity())
        session.flush()
        session.add(fiscal_year(**changes))


def test_duplicate_year_rejected(database: Database) -> None:
    with pytest.raises(IntegrityError), database.sessions.begin() as session:
        session.add(activity())
        session.flush()
        session.add_all([fiscal_year(), fiscal_year()])


def test_only_one_activity_per_instance(database: Database) -> None:
    with pytest.raises(IntegrityError), database.sessions.begin() as session:
        record = activity()
        record.id = 2
        session.add(record)


def test_migration_downgrade_and_reupgrade(settings: Settings) -> None:
    config = migration_config(settings)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            assert "property" not in inspect(connection).get_table_names()
    finally:
        database.engine.dispose()
    command.upgrade(config, "head")
    command.check(config)
