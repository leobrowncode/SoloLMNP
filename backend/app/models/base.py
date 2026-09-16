"""Typed SQLAlchemy base and exact monetary persistence."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, MetaData
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

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


class Money(TypeDecorator[Decimal]):
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> int | None:
        return None if value is None else to_cents(value)

    def process_result_value(self, value: int | None, dialect: Dialect) -> Decimal | None:
        return None if value is None else from_cents(value)


def utc_now() -> datetime:
    # SQLite stores timezone-free UTC, never local wall-clock time.
    return datetime.now(UTC).replace(tzinfo=None)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
