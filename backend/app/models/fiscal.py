"""Fiscal computations and carry-forward registers. They never post ledger entries."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now


class FiscalComputation(Base):
    __tablename__ = "fiscal_computation"
    __table_args__ = (
        CheckConstraint("status = 'research_only'", name="not_ready"),
        CheckConstraint("length(rules_sha256) = 64 AND length(ledger_sha256) = 64", name="hashes"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"), index=True)
    vintage: Mapped[str] = mapped_column(String(4))
    rules_sha256: Mapped[str] = mapped_column(String(64))
    ledger_sha256: Mapped[str] = mapped_column(String(64))
    adjustments_sha256: Mapped[str] = mapped_column(String(64))
    accounting_result: Mapped[int]
    fiscal_result: Mapped[int]
    deductible_depreciation: Mapped[int]
    unused_depreciation: Mapped[int]
    tax_loss: Mapped[int]
    non_deductible: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="research_only")
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime)


class DepreciationCarryForward(Base):
    __tablename__ = "depreciation_carry_forward"
    __table_args__ = (
        UniqueConstraint("fiscal_year_id"),
        CheckConstraint("amount >= 0", name="amount"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"))
    computation_id: Mapped[int] = mapped_column(ForeignKey("fiscal_computation.id"))
    amount: Mapped[int]
    rule_id: Mapped[str] = mapped_column(String(80))


class TaxLossCarryForward(Base):
    __tablename__ = "tax_loss_carry_forward"
    __table_args__ = (
        UniqueConstraint("fiscal_year_id"),
        CheckConstraint("amount >= 0", name="amount"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"))
    computation_id: Mapped[int] = mapped_column(ForeignKey("fiscal_computation.id"))
    amount: Mapped[int]
    rule_id: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(Text, default="")


class CarryForwardEvent(Base):
    """One created, used or expired movement of a carry-forward stock.

    The origin register keeps the amount created by that year. This table is
    the usage history. A recomputed or reopened year invalidates its
    computation, and these rows stop counting with it. Depreciation never
    expires; only a tax loss can be ``expired``.
    """

    __tablename__ = "carry_forward_event"
    __table_args__ = (
        UniqueConstraint(
            "computation_id",
            "register",
            "origin_fiscal_year_id",
            "kind",
            name="identity",
        ),
        CheckConstraint("register IN ('depreciation', 'tax_loss')", name="register"),
        CheckConstraint("kind IN ('created', 'used', 'expired')", name="kind"),
        CheckConstraint("amount >= 0", name="amount"),
        CheckConstraint("remaining_after >= 0", name="remaining"),
        CheckConstraint(
            "(register = 'tax_loss') OR (kind != 'expired')",
            name="depreciation_open",
        ),
        CheckConstraint(
            "(kind = 'created' AND origin_fiscal_year_id = event_fiscal_year_id)"
            " OR (kind != 'created' AND origin_fiscal_year_id != event_fiscal_year_id)",
            name="origin",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    computation_id: Mapped[int] = mapped_column(ForeignKey("fiscal_computation.id"), index=True)
    event_fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"), index=True)
    origin_fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"), index=True)
    register: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int]
    remaining_after: Mapped[int]
    rule_id: Mapped[str] = mapped_column(String(80))
