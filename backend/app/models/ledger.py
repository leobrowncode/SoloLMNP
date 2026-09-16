"""Persistent ledger. Drafts never contribute to accounting projections."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, utc_now


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        CheckConstraint(
            "length(number) BETWEEN 3 AND 10 AND number NOT GLOB '*[^0-9]*'", name="number"
        ),
        CheckConstraint("length(trim(label)) > 0", name="label"),
        CheckConstraint(
            "account_type IN ('ASSET','LIABILITY','EQUITY','EXPENSE','INCOME')", name="type"
        ),
        CheckConstraint("active IN (0,1)", name="active"),
    )
    number: Mapped[str] = mapped_column(String(10), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountingJournal(Base):
    __tablename__ = "accounting_journal"
    __table_args__ = (
        CheckConstraint(
            "length(code) BETWEEN 2 AND 10 AND code NOT GLOB '*[^A-Z0-9]*'", name="code"
        ),
        CheckConstraint("length(trim(label)) > 0", name="label"),
        CheckConstraint(
            "journal_type IN ('GENERAL','BANK','SALES','PURCHASE','OPENING')", name="type"
        ),
        CheckConstraint("active IN (0,1)", name="active"),
    )
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    journal_type: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountingEntry(Base):
    __tablename__ = "accounting_entry"
    __table_args__ = (
        UniqueConstraint("fiscal_year_id", "sequence", name="uq_entry_year_sequence"),
        UniqueConstraint("fiscal_year_id", "entry_number", name="uq_entry_year_number"),
        CheckConstraint("status IN ('DRAFT','VALIDATED')", name="status"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(
            "length(trim(label)) > 0 AND length(trim(piece_reference)) > 0", name="references"
        ),
        CheckConstraint(
            "(status='DRAFT' AND sequence IS NULL"
            " AND entry_number IS NULL AND validated_at IS NULL)"
            " OR (status='VALIDATED' AND sequence > 0 AND entry_number IS NOT NULL"
            " AND validated_at IS NOT NULL)",
            name="validation",
        ),
        {"sqlite_autoincrement": True},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"), index=True)
    journal_code: Mapped[str] = mapped_column(ForeignKey("accounting_journal.code"))
    entry_number: Mapped[str | None] = mapped_column(String(40))
    sequence: Mapped[int | None] = mapped_column(Integer)
    accounting_date: Mapped[date] = mapped_column(Date, index=True)
    piece_reference: Mapped[str] = mapped_column(String(200))
    piece_date: Mapped[date] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(30), default="MANUAL")
    source_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime)
    reversal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounting_entry.id"), unique=True
    )
    journal_label: Mapped[str | None] = mapped_column(String(200))
    lines: Mapped[list["AccountingEntryLine"]] = relationship(
        cascade="all, delete-orphan",
        order_by="AccountingEntryLine.position",
        lazy="selectin",
    )


class AccountingEntryLine(Base):
    __tablename__ = "accounting_entry_line"
    __table_args__ = (
        UniqueConstraint("accounting_entry_id", "position"),
        CheckConstraint("position >= 1", name="position"),
        CheckConstraint(
            "typeof(debit)='integer' AND typeof(credit)='integer' "
            "AND ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))",
            name="one_positive_side",
        ),
        CheckConstraint("length(trim(label)) > 0", name="label"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    accounting_entry_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_entry.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int]
    account_number: Mapped[str] = mapped_column(ForeignKey("account.number"), index=True)
    label: Mapped[str] = mapped_column(String(300))
    debit: Mapped[Decimal] = mapped_column(Money)
    credit: Mapped[Decimal] = mapped_column(Money)
    account_label: Mapped[str | None] = mapped_column(String(200))


class LedgerEvent(Base):
    __tablename__ = "ledger_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(40))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    details: Mapped[dict[str, object]] = mapped_column(JSON)
