"""Administrative schema. No accounting or tax calculation lives here."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, Timestamps


class RentalActivity(Timestamps, Base):
    __tablename__ = "rental_activity"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("length(trim(activity_name)) > 0", name="name_required"),
        CheckConstraint("tax_regime = 'REAL_SIMPLIFIED_BIC'", name="tax_regime"),
        CheckConstraint("accounting_method = 'ACCRUAL'", name="accounting_method"),
        CheckConstraint(
            "siren IS NULL OR (length(siren) = 9 AND siren NOT GLOB '*[^0-9]*')",
            name="siren_format",
        ),
        CheckConstraint(
            "siret IS NULL OR (length(siret) = 14 AND siret NOT GLOB '*[^0-9]*' "
            "AND siren IS NOT NULL AND substr(siret, 1, 9) = siren)",
            name="siret_format",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    activity_name: Mapped[str] = mapped_column(String(200))
    siren: Mapped[str | None] = mapped_column(String(9))
    siret: Mapped[str | None] = mapped_column(String(14))
    activity_start_date: Mapped[date] = mapped_column(Date)
    tax_regime: Mapped[str] = mapped_column(String(40), default="REAL_SIMPLIFIED_BIC")
    accounting_method: Mapped[str] = mapped_column(String(20), default="ACCRUAL")
    notes: Mapped[str] = mapped_column(Text, default="")


class Property(Timestamps, Base):
    __tablename__ = "property"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_required"),
        *(
            CheckConstraint(f"typeof({column}) = 'integer' AND {column} >= 0", name=column)
            for column in ("acquisition_price", "acquisition_costs", "land_value", "building_value")
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    rental_activity_id: Mapped[int] = mapped_column(
        ForeignKey("rental_activity.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text)
    acquisition_date: Mapped[date] = mapped_column(Date)
    rental_start_date: Mapped[date | None] = mapped_column(Date)
    acquisition_price: Mapped[Decimal] = mapped_column(Money)
    acquisition_costs: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    land_value: Mapped[Decimal] = mapped_column(Money)
    building_value: Mapped[Decimal] = mapped_column(Money)
    notes: Mapped[str] = mapped_column(Text, default="")


class FiscalYear(Timestamps, Base):
    __tablename__ = "fiscal_year"
    __table_args__ = (
        UniqueConstraint("rental_activity_id", "year"),
        CheckConstraint("year BETWEEN 1900 AND 9999", name="year_range"),
        CheckConstraint("start_date <= end_date", name="date_order"),
        CheckConstraint("length(trim(fiscal_vintage)) > 0", name="vintage_required"),
        CheckConstraint("status IN ('OPEN', 'READY_TO_CLOSE', 'CLOSED')", name="status"),
        CheckConstraint(
            "(status = 'CLOSED' AND closed_at IS NOT NULL) OR "
            "(status != 'CLOSED' AND closed_at IS NULL)",
            name="closure_timestamp",
        ),
        CheckConstraint(
            "(reopened_at IS NULL AND reopening_reason IS NULL) OR "
            "(reopened_at IS NOT NULL AND reopening_reason IS NOT NULL "
            "AND length(trim(reopening_reason)) > 0)",
            name="reopening_reason",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    rental_activity_id: Mapped[int] = mapped_column(
        ForeignKey("rental_activity.id", ondelete="RESTRICT"), index=True
    )
    year: Mapped[int]
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    fiscal_vintage: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime)
    reopening_reason: Mapped[str | None] = mapped_column(Text)
