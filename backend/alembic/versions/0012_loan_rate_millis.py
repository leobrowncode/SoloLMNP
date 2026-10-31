"""Store loan rates as thousandths of a percent.

Revision ID: 0012_loan_rate_millis
Revises: 0011_entry_year_status

Existing rows used hundredths of a percent (3.50 % = 350). Multiply by 10
so 3.50 % stays 3500 and a later 3.125 % can be stored as 3125. The column
name stays interest_rate_basis_points.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_loan_rate_millis"
down_revision: str | None = "0011_entry_year_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE loan SET interest_rate_basis_points = interest_rate_basis_points * 10")


def downgrade() -> None:
    op.execute("UPDATE loan SET interest_rate_basis_points = interest_rate_basis_points / 10")
