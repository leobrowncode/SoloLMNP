"""Append-only audit trail and immutable tax-return snapshots."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(40))
    before: Mapped[dict[str, object] | None] = mapped_column(JSON)
    after: Mapped[dict[str, object] | None] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)


class TaxReturnSnapshot(Base):
    __tablename__ = "tax_return_snapshot"
    __table_args__ = (
        UniqueConstraint("fiscal_year_id", "generation"),
        CheckConstraint("status IN ('CURRENT','SUPERSEDED')", name="status"),
        CheckConstraint("generation >= 1", name="generation"),
        Index(
            "uq_current_snapshot_year",
            "fiscal_year_id",
            unique=True,
            sqlite_where=text("status = 'CURRENT'"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"))
    generation: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    canonical_json: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    ledger_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SupportingDocument(Base):
    __tablename__ = "supporting_document"
    __table_args__ = (
        CheckConstraint("size > 0", name="size"),
        CheckConstraint(
            "media_type IN ('application/pdf','image/jpeg','image/png')", name="media_type"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int]
    media_type: Mapped[str] = mapped_column(String(40))
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    original_name: Mapped[str] = mapped_column(String(200))
    entry_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_entry.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
