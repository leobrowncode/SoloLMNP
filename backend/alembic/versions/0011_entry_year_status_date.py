"""Index validated entries by exercise, status and date.

Revision ID: 0011_entry_year_status
Revises: 0010_carry_events

Journal, balance, statements and FEC all filter validated lines of one
exercise and then order them by date. A composite index avoids scanning
every entry of the file when several years are stored.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_entry_year_status"
down_revision: str | None = "0010_carry_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_accounting_entry_year_status_date",
        "accounting_entry",
        ["fiscal_year_id", "status", "accounting_date", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_accounting_entry_year_status_date", table_name="accounting_entry")
