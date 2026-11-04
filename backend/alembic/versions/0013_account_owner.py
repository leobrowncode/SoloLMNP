"""Attach every dossier to an account.

Revision ID: 0013_account_owner
Revises: 0012_loan_rate_millis

The first account is unclaimed (subject NULL). Existing rows point at it.
A later login of an allowlisted user claims that row. The chart of accounts
and the journals stay shared: their keys are the account numbers.
"""

import re
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0013_account_owner"
down_revision: str | None = "0012_loan_rate_millis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED_TABLES = (
    "rental_activity",
    "property",
    "fiscal_year",
    "accounting_entry",
    "accounting_entry_line",
    "ledger_event",
    "business_operation",
    "bank_account",
    "bank_transaction",
    "bank_match",
    "loan",
    "asset",
    "asset_component",
    "depreciation_schedule",
    "depreciation_period",
    "fiscal_computation",
    "depreciation_carry_forward",
    "tax_loss_carry_forward",
    "carry_forward_event",
    "audit_event",
    "tax_return_snapshot",
    "supporting_document",
    "tenant",
)


def upgrade() -> None:
    sqlite = op.get_bind().dialect.name == "sqlite"
    if sqlite:
        # SQLite refuses to rebuild a referenced table while foreign keys are
        # on, and it cannot change that pragma inside the migration transaction.
        _sqlite_foreign_keys(False)
    op.create_table(
        "app_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_account")),
        sa.UniqueConstraint("subject", name=op.f("uq_app_account_subject")),
        sa.UniqueConstraint("email", name=op.f("uq_app_account_email")),
    )
    # Omit id so SQLite rowid and the Postgres sequence both land on 1.
    # An explicit 1 would leave nextval() ready to insert 1 again.
    created = datetime.now(UTC).replace(tzinfo=None)
    op.execute(
        text(
            "INSERT INTO app_account (subject, email, created_at) VALUES (NULL, NULL, :created)"
        ).bindparams(sa.bindparam("created", created, type_=sa.DateTime()))
    )
    op.create_table(
        "dossier_archive",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["app_account.id"],
            name=op.f("fk_dossier_archive_owner_id_app_account"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dossier_archive")),
        sa.UniqueConstraint("filename", name=op.f("uq_dossier_archive_filename")),
    )
    op.create_index(
        op.f("ix_dossier_archive_owner_id"), "dossier_archive", ["owner_id"], unique=False
    )
    triggers = _all_trigger_sql() if sqlite else []
    if sqlite:
        _drop_triggers(triggers)
    for table in OWNED_TABLES:
        _add_owner(table)
    _drop_activity_singleton()
    if sqlite:
        for statement in triggers:
            op.execute(sa.text(statement))
        _sqlite_foreign_keys(True)
        broken = op.get_bind().execute(text("PRAGMA foreign_key_check")).all()
        if broken:
            raise RuntimeError(f"Clés étrangères en échec après 0013 : {broken}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # Stay inside Alembic's transaction. A commit here would make a later
        # refusal leave the schema half-downgraded.
        for table in reversed(OWNED_TABLES):
            _sqlite_drop_owner(table)
    else:
        op.drop_index("uq_rental_activity_owner_id", table_name="rental_activity")
        for table in reversed(OWNED_TABLES):
            op.drop_index(op.f(f"ix_{table}_owner_id"), table_name=table)
            op.drop_constraint(op.f(f"fk_{table}_owner_id_app_account"), table, type_="foreignkey")
            op.drop_column(table, "owner_id")
    op.drop_index(op.f("ix_dossier_archive_owner_id"), table_name="dossier_archive")
    op.drop_table("dossier_archive")
    op.drop_table("app_account")


def _add_owner(table: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        kwargs: dict[str, bool] = {}
        if table == "accounting_entry":
            # Batch copy drops AUTOINCREMENT unless it is asked for again.
            kwargs["sqlite_autoincrement"] = True
        with op.batch_alter_table(table, table_kwargs=kwargs) as batch:
            batch.add_column(
                sa.Column(
                    "owner_id",
                    sa.Integer(),
                    sa.ForeignKey("app_account.id", ondelete="RESTRICT"),
                    nullable=False,
                    server_default=sa.text("1"),
                )
            )
            batch.create_index(batch.f(f"ix_{table}_owner_id"), ["owner_id"], unique=False)
    else:
        # Constant default: existing rows become account 1 without an UPDATE,
        # so immutability triggers stay quiet. The default also matches SQLite.
        op.add_column(
            table,
            sa.Column(
                "owner_id",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            ),
        )
        op.create_foreign_key(
            op.f(f"fk_{table}_owner_id_app_account"),
            table,
            "app_account",
            ["owner_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(op.f(f"ix_{table}_owner_id"), table, ["owner_id"], unique=False)


def _sqlite_foreign_keys(enabled: bool) -> None:
    raw = op.get_bind().connection.driver_connection
    raw.commit()
    raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _drop_activity_singleton() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        sql = bind.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'rental_activity'")
        ).scalar()
        with op.batch_alter_table("rental_activity") as batch:
            if sql and "id = 1" in str(sql):
                # The convention turns "singleton" into ck_rental_activity_singleton.
                batch.drop_constraint("singleton", type_="check")
            # A unique index can be dropped before the column. A table UNIQUE
            # constraint cannot, and rebuilding the parent breaks the downgrade
            # transaction.
            batch.create_index("uq_rental_activity_owner_id", ["owner_id"], unique=True)
        return
    names = {item["name"] for item in sa.inspect(bind).get_check_constraints("rental_activity")}
    if "ck_rental_activity_singleton" in names:
        op.drop_constraint(op.f("ck_rental_activity_singleton"), "rental_activity", type_="check")
    op.create_index("uq_rental_activity_owner_id", "rental_activity", ["owner_id"], unique=True)


def _sqlite_drop_owner(table: str) -> None:
    if table not in OWNED_TABLES:
        raise RuntimeError(f"Table inattendue : {table}")
    # A named table FOREIGN KEY is not removed by DROP COLUMN. Editing the
    # stored CREATE statement first lets the drop stay inside this transaction.
    bind = op.get_bind()
    current = bind.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": table},
    ).scalar()
    if not isinstance(current, str):
        raise RuntimeError(f"Table introuvable : {table}")
    rewritten, removed = re.subn(
        rf",\s*CONSTRAINT fk_{table}_owner_id_app_account "
        r"FOREIGN KEY\(owner_id\) REFERENCES app_account \(id\) ON DELETE RESTRICT",
        "",
        current,
        count=1,
    )
    if removed != 1:
        raise RuntimeError(f"Contrainte de compte introuvable sur {table}")
    bind.execute(text("PRAGMA writable_schema=ON"))
    bind.execute(
        text("UPDATE sqlite_master SET sql = :sql WHERE type = 'table' AND name = :name"),
        {"sql": rewritten, "name": table},
    )
    bind.execute(text("PRAGMA writable_schema=RESET"))
    if table == "rental_activity":
        op.execute(sa.text('DROP INDEX IF EXISTS "uq_rental_activity_owner_id"'))
    op.execute(sa.text(f'DROP INDEX IF EXISTS "ix_{table}_owner_id"'))  # noqa: S608
    op.execute(sa.text(f'ALTER TABLE "{table}" DROP COLUMN owner_id'))  # noqa: S608


def _all_trigger_sql() -> list[str]:
    rows = op.get_bind().execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'trigger' AND sql IS NOT NULL")
    )
    return [str(row[0]) for row in rows if row[0]]


def _drop_triggers(statements: list[str]) -> None:
    for statement in statements:
        name = statement.split()[2]
        if name.startswith('"') or not name.replace("_", "").isalnum():
            raise RuntimeError(f"Nom de trigger inattendu : {name}")
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{name}"'))
