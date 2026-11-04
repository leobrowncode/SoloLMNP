"""Typed SQLAlchemy base and exact monetary persistence."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, Numeric
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, TypeEngine

from app.core.money import from_cents, to_cents


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Cents(TypeDecorator[int]):
    """Whole cents.

    SQLite INTEGER is already 64-bit. Postgres NUMERIC keeps a fractional
    assignment visible so the existing ``typeof(...) = 'integer'`` checks can
    reject it; BIGINT would round it away before the check runs.
    """

    impl = Numeric
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Integer())
        return dialect.type_descriptor(Numeric())

    def process_bind_param(self, value: int | None, dialect: Dialect) -> int | None:
        if value is None:
            return None
        if type(value) is not int:
            raise TypeError("Stored cents must be an integer")
        return value

    def process_result_value(self, value: int | Decimal | None, dialect: Dialect) -> int | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            if value != value.to_integral_value():
                raise ValueError("Stored cents must be an integer")
            return int(value)
        if type(value) is not int:
            raise TypeError("Stored cents must be an integer")
        return value


def cents() -> Cents:
    return Cents()


class Money(TypeDecorator[Decimal]):
    impl = Numeric
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Integer())
        return dialect.type_descriptor(Numeric())

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> int | None:
        return None if value is None else to_cents(value)

    def process_result_value(self, value: int | Decimal | None, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            if value != value.to_integral_value():
                raise ValueError("Stored money must be an integer")
            value = int(value)
        return from_cents(value)


def utc_now() -> datetime:
    # SQLite stores timezone-free UTC, never local wall-clock time.
    return datetime.now(UTC).replace(tzinfo=None)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Owned:
    """Row belongs to one account. Services see only the session's owner."""

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("app_account.id", ondelete="RESTRICT"), index=True
    )
