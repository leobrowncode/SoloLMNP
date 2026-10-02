"""Audit trail, tax snapshots and supporting documents.

Revision ID: 0007_filing
Revises: 0006_fiscal
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_filing"
down_revision: str | None = "0006_fiscal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(40), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_table(
        "tax_return_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_year_id", sa.Integer(), sa.ForeignKey("fiscal_year.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("ledger_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("fiscal_year_id", "generation"),
        sa.CheckConstraint(
            "status IN ('CURRENT','SUPERSEDED')", name="ck_tax_return_snapshot_status"
        ),
        sa.CheckConstraint("generation >= 1", name="ck_tax_return_snapshot_generation"),
    )
    op.create_index(
        "uq_current_snapshot_year",
        "tax_return_snapshot",
        ["fiscal_year_id"],
        unique=True,
        sqlite_where=sa.text("status = 'CURRENT'"),
    )
    op.create_table(
        "supporting_document",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(40), nullable=False),
        sa.Column("stored_name", sa.String(80), nullable=False),
        sa.Column("original_name", sa.String(200), nullable=False),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("accounting_entry.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("stored_name"),
        sa.CheckConstraint("size > 0", name="ck_supporting_document_size"),
        sa.CheckConstraint(
            "media_type IN ('application/pdf','image/jpeg','image/png')",
            name="ck_supporting_document_media_type",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table, statement in (
        ("supporting_document", "SELECT 1 FROM supporting_document LIMIT 1"),
        ("tax_return_snapshot", "SELECT 1 FROM tax_return_snapshot LIMIT 1"),
        ("audit_event", "SELECT 1 FROM audit_event LIMIT 1"),
    ):
        if bind.execute(sa.text(statement)).first():
            raise RuntimeError(f"Refusing to drop {table} while it contains data")
    op.drop_table("supporting_document")
    op.drop_index("uq_current_snapshot_year", table_name="tax_return_snapshot")
    op.drop_table("tax_return_snapshot")
    op.drop_table("audit_event")
