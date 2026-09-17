"""One generated opening entry per target year.

Revision ID: 0005_opening
Revises: 0004_assets
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_opening"
down_revision: str | None = "0004_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_opening_entry_year",
        "accounting_entry",
        ["fiscal_year_id"],
        unique=True,
        sqlite_where=sa.text("source_type = 'OPENING'"),
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM accounting_entry WHERE source_type='OPENING' LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Refusing to remove opening uniqueness while generated entries exist")
    op.drop_index("uq_opening_entry_year", table_name="accounting_entry")
