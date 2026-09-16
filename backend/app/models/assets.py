"""Immutable fixed-asset register and accounting depreciation sub-ledger."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, utc_now


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = (
        CheckConstraint(
            "category IN ('LAND','BUILDING','FURNITURE','EQUIPMENT','IMPROVEMENT','OTHER')",
            name="category",
        ),
        CheckConstraint("method IN ('NONE','LINEAR')", name="method"),
        CheckConstraint(
            "typeof(acquisition_value)='integer' AND acquisition_value>0 AND "
            "typeof(depreciable_value)='integer' AND depreciable_value>=0 AND "
            "typeof(non_depreciable_value)='integer' AND non_depreciable_value>=0 AND "
            "typeof(residual_value)='integer' AND residual_value>=0 AND "
            "acquisition_value=depreciable_value+non_depreciable_value AND "
            "residual_value<=depreciable_value",
            name="values",
        ),
        CheckConstraint(
            "(category='LAND' AND method='NONE' AND depreciable_value=0 AND "
            "non_depreciable_value=acquisition_value AND residual_value=0 AND "
            "useful_life_months IS NULL AND depreciation_account IS NULL) OR "
            "(category!='LAND' AND method='LINEAR' AND depreciable_value>residual_value "
            "AND non_depreciable_value=0 AND useful_life_months>0 "
            "AND depreciation_account IS NOT NULL)",
            name="land_and_plan",
        ),
        CheckConstraint("disposed_at IS NULL OR disposed_at>=service_start_date", name="disposal"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("property.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(200))
    acquisition_date: Mapped[date] = mapped_column(Date)
    service_start_date: Mapped[date] = mapped_column(Date)
    acquisition_value: Mapped[Decimal] = mapped_column(Money)
    depreciable_value: Mapped[Decimal] = mapped_column(Money)
    non_depreciable_value: Mapped[Decimal] = mapped_column(Money)
    residual_value: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    method: Mapped[str] = mapped_column(String(20))
    useful_life_months: Mapped[int | None]
    asset_account: Mapped[str] = mapped_column(ForeignKey("account.number"))
    depreciation_account: Mapped[str | None] = mapped_column(ForeignKey("account.number"))
    basis_reason: Mapped[str] = mapped_column(Text)
    duration_reason: Mapped[str] = mapped_column(Text, default="")
    disposed_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AssetComponent(Base):
    __tablename__ = "asset_component"
    __table_args__ = (
        CheckConstraint("value>0 AND typeof(value)='integer'", name="value"),
        CheckConstraint("useful_life_months>0", name="life"),
        CheckConstraint(
            "length(trim(basis_reason))>0 AND length(trim(duration_reason))>0", name="reasons"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[Decimal] = mapped_column(Money)
    useful_life_months: Mapped[int]
    service_start_date: Mapped[date] = mapped_column(Date)
    asset_account: Mapped[str] = mapped_column(ForeignKey("account.number"))
    depreciation_account: Mapped[str] = mapped_column(ForeignKey("account.number"))
    basis_reason: Mapped[str] = mapped_column(Text)
    duration_reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DepreciationSchedule(Base):
    __tablename__ = "depreciation_schedule"
    __table_args__ = (
        UniqueConstraint("asset_id", "component_id"),
        CheckConstraint(
            "(asset_id IS NOT NULL AND component_id IS NULL) OR "
            "(asset_id IS NULL AND component_id IS NOT NULL)",
            name="one_target",
        ),
        CheckConstraint("method='LINEAR' AND base>0 AND useful_life_months>0", name="plan"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id"), unique=True)
    component_id: Mapped[int | None] = mapped_column(ForeignKey("asset_component.id"), unique=True)
    base: Mapped[Decimal] = mapped_column(Money)
    method: Mapped[str] = mapped_column(String(20), default="LINEAR")
    useful_life_months: Mapped[int]
    service_start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    asset_account: Mapped[str] = mapped_column(ForeignKey("account.number"))
    depreciation_account: Mapped[str] = mapped_column(ForeignKey("account.number"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DepreciationPeriod(Base):
    __tablename__ = "depreciation_period"
    __table_args__ = (
        UniqueConstraint("schedule_id", "fiscal_year_id"),
        CheckConstraint("status IN ('CALCULATED','POSTED')", name="status"),
        CheckConstraint("period_start<=period_end AND days>0", name="period"),
        CheckConstraint(
            "amount>=0 AND accumulated>=amount AND net_book_value>=0 AND "
            "typeof(amount)='integer' AND typeof(accumulated)='integer' AND "
            "typeof(net_book_value)='integer'",
            name="amounts",
        ),
        CheckConstraint(
            "(status='CALCULATED' AND accounting_entry_id IS NULL) OR "
            "(status='POSTED' AND accounting_entry_id IS NOT NULL)",
            name="posting",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("depreciation_schedule.id"), index=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    days: Mapped[int]
    amount: Mapped[Decimal] = mapped_column(Money)
    accumulated: Mapped[Decimal] = mapped_column(Money)
    net_book_value: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(20), default="CALCULATED")
    accounting_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounting_entry.id"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
