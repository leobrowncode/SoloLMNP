"""Tenants for long-term colocation, and accounts used by the copy liasse.

Revision ID: 0008_dwelling
Revises: 0007_filing
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_dwelling"
down_revision: str | None = "0007_filing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNTS = (("614000", "Charges de copropriété", "EXPENSE"),)


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("monthly_rent", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=True),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_tenant_name_required")),
        sa.CheckConstraint(
            "typeof(monthly_rent)='integer' AND monthly_rent > 0",
            name=op.f("ck_tenant_rent"),
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["property.id"],
            name=op.f("fk_tenant_property_id_property"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant")),
        sa.UniqueConstraint("property_id", "name", name="uq_tenant_property_name"),
    )
    op.create_index(op.f("ix_tenant_property_id"), "tenant", ["property_id"], unique=False)
    bind = op.get_bind()
    for number, label, kind in ACCOUNTS:
        exists = bind.execute(
            sa.text("SELECT 1 FROM account WHERE number = :number"),
            {"number": number},
        ).first()
        if exists is None:
            bind.execute(
                sa.text(
                    "INSERT INTO account (number, label, account_type, active) "
                    "VALUES (:number, :label, :kind, 1)"
                ),
                {"number": number, "label": label, "kind": kind},
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM tenant LIMIT 1")).first():
        raise RuntimeError("Refusing to drop tenant while it contains data")
    op.drop_index(op.f("ix_tenant_property_id"), table_name="tenant")
    op.drop_table("tenant")
    for number, _label, _kind in ACCOUNTS:
        used = bind.execute(
            sa.text("SELECT 1 FROM accounting_entry_line WHERE account_number = :number LIMIT 1"),
            {"number": number},
        ).first()
        if used is None:
            bind.execute(
                sa.text("DELETE FROM account WHERE number = :number"),
                {"number": number},
            )
