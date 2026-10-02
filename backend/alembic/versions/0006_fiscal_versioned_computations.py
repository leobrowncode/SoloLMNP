"""Versioned fiscal computations and separate carry-forward registers.

Revision ID: 0006_fiscal
Revises: 0005_opening
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_fiscal"
down_revision: str | None = "0005_opening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fiscal_computation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_year_id", sa.Integer(), sa.ForeignKey("fiscal_year.id"), nullable=False),
        sa.Column("vintage", sa.String(4), nullable=False),
        sa.Column("rules_sha256", sa.String(64), nullable=False),
        sa.Column("ledger_sha256", sa.String(64), nullable=False),
        sa.Column("adjustments_sha256", sa.String(64), nullable=False),
        sa.Column("accounting_result", sa.Integer(), nullable=False),
        sa.Column("fiscal_result", sa.Integer(), nullable=False),
        sa.Column("deductible_depreciation", sa.Integer(), nullable=False),
        sa.Column("unused_depreciation", sa.Integer(), nullable=False),
        sa.Column("tax_loss", sa.Integer(), nullable=False),
        sa.Column("non_deductible", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status = 'research_only'", name="ck_fiscal_computation_not_ready"),
    )
    op.create_index(
        "ix_fiscal_computation_fiscal_year_id", "fiscal_computation", ["fiscal_year_id"]
    )
    op.create_table(
        "depreciation_carry_forward",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_year_id", sa.Integer(), sa.ForeignKey("fiscal_year.id"), nullable=False),
        sa.Column(
            "computation_id", sa.Integer(), sa.ForeignKey("fiscal_computation.id"), nullable=False
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.String(80), nullable=False),
        sa.UniqueConstraint("fiscal_year_id"),
        sa.CheckConstraint("amount >= 0", name="ck_depreciation_carry_forward_amount"),
    )
    op.create_table(
        "tax_loss_carry_forward",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_year_id", sa.Integer(), sa.ForeignKey("fiscal_year.id"), nullable=False),
        sa.Column(
            "computation_id", sa.Integer(), sa.ForeignKey("fiscal_computation.id"), nullable=False
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.String(80), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.UniqueConstraint("fiscal_year_id"),
        sa.CheckConstraint("amount >= 0", name="ck_tax_loss_carry_forward_amount"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    occupied = (
        ("tax_loss_carry_forward", "SELECT 1 FROM tax_loss_carry_forward LIMIT 1"),
        ("depreciation_carry_forward", "SELECT 1 FROM depreciation_carry_forward LIMIT 1"),
        ("fiscal_computation", "SELECT 1 FROM fiscal_computation LIMIT 1"),
    )
    for table, statement in occupied:
        if bind.execute(sa.text(statement)).first():
            raise RuntimeError(f"Refusing to drop {table} while it contains data")
    op.drop_table("tax_loss_carry_forward")
    op.drop_table("depreciation_carry_forward")
    op.drop_table("fiscal_computation")
