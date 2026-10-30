"""Usage history for depreciation and tax-loss carry-forwards.

Revision ID: 0010_carry_events
Revises: 0009_structuring

Each row is one created, used or expired movement tied to the computation
that recorded it. Invalidating that computation drops the movement out of
the remaining balance. Depreciation rows cannot be expired.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_carry_events"
down_revision: str | None = "0009_structuring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carry_forward_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "computation_id",
            sa.Integer(),
            sa.ForeignKey("fiscal_computation.id"),
            nullable=False,
        ),
        sa.Column(
            "event_fiscal_year_id",
            sa.Integer(),
            sa.ForeignKey("fiscal_year.id"),
            nullable=False,
        ),
        sa.Column(
            "origin_fiscal_year_id",
            sa.Integer(),
            sa.ForeignKey("fiscal_year.id"),
            nullable=False,
        ),
        sa.Column("register", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("remaining_after", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.String(80), nullable=False),
        sa.UniqueConstraint(
            "computation_id",
            "register",
            "origin_fiscal_year_id",
            "kind",
            name="identity",
        ),
        sa.CheckConstraint(
            "register IN ('depreciation', 'tax_loss')",
            name="ck_carry_forward_event_register",
        ),
        sa.CheckConstraint(
            "kind IN ('created', 'used', 'expired')",
            name="ck_carry_forward_event_kind",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_carry_forward_event_amount"),
        sa.CheckConstraint("remaining_after >= 0", name="ck_carry_forward_event_remaining"),
        sa.CheckConstraint(
            "(register = 'tax_loss') OR (kind != 'expired')",
            name="ck_carry_forward_event_depreciation_open",
        ),
        sa.CheckConstraint(
            "(kind = 'created' AND origin_fiscal_year_id = event_fiscal_year_id)"
            " OR (kind != 'created' AND origin_fiscal_year_id != event_fiscal_year_id)",
            name="ck_carry_forward_event_origin",
        ),
    )
    op.create_index(
        "ix_carry_forward_event_computation_id",
        "carry_forward_event",
        ["computation_id"],
    )
    op.create_index(
        "ix_carry_forward_event_event_fiscal_year_id",
        "carry_forward_event",
        ["event_fiscal_year_id"],
    )
    op.create_index(
        "ix_carry_forward_event_origin_fiscal_year_id",
        "carry_forward_event",
        ["origin_fiscal_year_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM carry_forward_event LIMIT 1")).first():
        raise RuntimeError("Refusing to drop carry_forward_event while it contains data")
    op.drop_index("ix_carry_forward_event_origin_fiscal_year_id", "carry_forward_event")
    op.drop_index("ix_carry_forward_event_event_fiscal_year_id", "carry_forward_event")
    op.drop_index("ix_carry_forward_event_computation_id", "carry_forward_event")
    op.drop_table("carry_forward_event")
