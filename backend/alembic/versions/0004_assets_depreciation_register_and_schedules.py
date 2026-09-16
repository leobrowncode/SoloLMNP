"""asset register and accounting depreciation schedules

Revision ID: 0004_assets
Revises: 0003_operations
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_assets"
down_revision: str | None = "0003_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GUARDS = {
    "asset_update": "CREATE TRIGGER assets_asset_update BEFORE UPDATE ON asset BEGIN SELECT RAISE(ABORT,'ASSET_IMMUTABLE'); END",
    "asset_delete": "CREATE TRIGGER assets_asset_delete BEFORE DELETE ON asset BEGIN SELECT RAISE(ABORT,'ASSET_IMMUTABLE'); END",
    "component_update": "CREATE TRIGGER assets_component_update BEFORE UPDATE ON asset_component BEGIN SELECT RAISE(ABORT,'COMPONENT_IMMUTABLE'); END",
    "component_delete": "CREATE TRIGGER assets_component_delete BEFORE DELETE ON asset_component BEGIN SELECT RAISE(ABORT,'COMPONENT_IMMUTABLE'); END",
    "component_insert": "CREATE TRIGGER assets_component_insert BEFORE INSERT ON asset_component BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM asset a WHERE a.id=NEW.asset_id AND a.category='BUILDING' AND NEW.service_start_date>=a.service_start_date AND NOT EXISTS(SELECT 1 FROM depreciation_schedule s WHERE s.asset_id=a.id)) THEN RAISE(ABORT,'COMPONENT_PARENT_INVALID') END;\n SELECT CASE WHEN NEW.value+(SELECT COALESCE(SUM(value),0) FROM asset_component WHERE asset_id=NEW.asset_id)>(SELECT depreciable_value-residual_value FROM asset WHERE id=NEW.asset_id) THEN RAISE(ABORT,'COMPONENT_TOTAL_EXCEEDS_BASE') END;\nEND",
    "schedule_insert": "CREATE TRIGGER assets_schedule_insert BEFORE INSERT ON depreciation_schedule BEGIN\n SELECT CASE WHEN NEW.asset_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM asset a WHERE a.id=NEW.asset_id AND a.category!='LAND' AND NOT EXISTS(SELECT 1 FROM asset_component c WHERE c.asset_id=a.id) AND NEW.base=a.depreciable_value-a.residual_value AND NEW.service_start_date=a.service_start_date AND NEW.useful_life_months=a.useful_life_months AND NEW.asset_account=a.asset_account AND NEW.depreciation_account=a.depreciation_account) THEN RAISE(ABORT,'ASSET_SCHEDULE_INVALID') END;\n SELECT CASE WHEN NEW.component_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM asset_component c JOIN asset a ON a.id=c.asset_id WHERE c.id=NEW.component_id AND (SELECT SUM(value) FROM asset_component WHERE asset_id=a.id)=a.depreciable_value-a.residual_value AND NEW.base=c.value AND NEW.service_start_date=c.service_start_date AND NEW.useful_life_months=c.useful_life_months AND NEW.asset_account=c.asset_account AND NEW.depreciation_account=c.depreciation_account) THEN RAISE(ABORT,'COMPONENT_SCHEDULE_INVALID') END;\nEND",
    "schedule_update": "CREATE TRIGGER assets_schedule_update BEFORE UPDATE ON depreciation_schedule BEGIN SELECT RAISE(ABORT,'SCHEDULE_IMMUTABLE'); END",
    "schedule_delete": "CREATE TRIGGER assets_schedule_delete BEFORE DELETE ON depreciation_schedule BEGIN SELECT RAISE(ABORT,'SCHEDULE_IMMUTABLE'); END",
    "period_insert": "CREATE TRIGGER assets_period_insert BEFORE INSERT ON depreciation_period BEGIN\n SELECT CASE WHEN NEW.status!='CALCULATED' OR NEW.accounting_entry_id IS NOT NULL OR NOT EXISTS(SELECT 1 FROM depreciation_schedule s JOIN fiscal_year y ON y.id=NEW.fiscal_year_id WHERE s.id=NEW.schedule_id AND y.status='OPEN' AND NEW.period_start>=s.service_start_date AND NEW.period_end<=s.end_date AND NEW.period_start>=y.start_date AND NEW.period_end<=y.end_date AND NEW.days=CAST(julianday(NEW.period_end)-julianday(NEW.period_start)+1 AS INTEGER) AND NEW.accumulated<=s.base AND NEW.net_book_value=s.base-NEW.accumulated) THEN RAISE(ABORT,'DEPRECIATION_PERIOD_INVALID') END;\nEND",
    "period_update": "CREATE TRIGGER assets_period_update BEFORE UPDATE ON depreciation_period BEGIN\n SELECT CASE WHEN NOT(OLD.status='CALCULATED' AND OLD.accounting_entry_id IS NULL AND NEW.status='POSTED' AND NEW.accounting_entry_id IS NOT NULL AND OLD.schedule_id=NEW.schedule_id AND OLD.fiscal_year_id=NEW.fiscal_year_id AND OLD.period_start=NEW.period_start AND OLD.period_end=NEW.period_end AND OLD.days=NEW.days AND OLD.amount=NEW.amount AND OLD.accumulated=NEW.accumulated AND OLD.net_book_value=NEW.net_book_value) THEN RAISE(ABORT,'PERIOD_IMMUTABLE') END;\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM accounting_entry e JOIN fiscal_year y ON y.id=e.fiscal_year_id JOIN depreciation_schedule s ON s.id=NEW.schedule_id WHERE e.id=NEW.accounting_entry_id AND e.status='VALIDATED' AND e.source_type='DEPRECIATION' AND e.fiscal_year_id=NEW.fiscal_year_id AND e.accounting_date=NEW.period_end AND y.status='OPEN' AND (SELECT SUM(debit) FROM accounting_entry_line WHERE accounting_entry_id=e.id)=NEW.amount AND EXISTS(SELECT 1 FROM accounting_entry_line WHERE accounting_entry_id=e.id AND account_number='681100' AND debit=NEW.amount AND credit=0) AND EXISTS(SELECT 1 FROM accounting_entry_line WHERE accounting_entry_id=e.id AND account_number=s.depreciation_account AND credit=NEW.amount AND debit=0)) THEN RAISE(ABORT,'DEPRECIATION_POSTING_INVALID') END;\nEND",
    "period_delete": "CREATE TRIGGER assets_period_delete BEFORE DELETE ON depreciation_period WHEN OLD.status!='CALCULATED' OR (SELECT status FROM fiscal_year WHERE id=OLD.fiscal_year_id)!='OPEN' BEGIN SELECT RAISE(ABORT,'PERIOD_IMMUTABLE'); END",
}


def upgrade() -> None:
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('213500','Installations générales des constructions','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('281350','Amortissements des installations générales','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('281830','Amortissements du matériel de bureau et informatique','ASSET',1)"
    )
    op.create_table(
        "asset",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("service_start_date", sa.Date(), nullable=False),
        sa.Column("acquisition_value", sa.Integer(), nullable=False),
        sa.Column("depreciable_value", sa.Integer(), nullable=False),
        sa.Column("non_depreciable_value", sa.Integer(), nullable=False),
        sa.Column("residual_value", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("useful_life_months", sa.Integer()),
        sa.Column("asset_account", sa.String(10), nullable=False),
        sa.Column("depreciation_account", sa.String(10)),
        sa.Column("basis_reason", sa.Text(), nullable=False),
        sa.Column("duration_reason", sa.Text(), nullable=False),
        sa.Column("disposed_at", sa.Date()),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "category IN ('LAND','BUILDING','FURNITURE','EQUIPMENT','IMPROVEMENT','OTHER')",
            name=op.f("ck_asset_category"),
        ),
        sa.CheckConstraint("method IN ('NONE','LINEAR')", name=op.f("ck_asset_method")),
        sa.CheckConstraint(
            "typeof(acquisition_value)='integer' AND acquisition_value>0 AND typeof(depreciable_value)='integer' AND depreciable_value>=0 AND typeof(non_depreciable_value)='integer' AND non_depreciable_value>=0 AND typeof(residual_value)='integer' AND residual_value>=0 AND acquisition_value=depreciable_value+non_depreciable_value AND residual_value<=depreciable_value",
            name=op.f("ck_asset_values"),
        ),
        sa.CheckConstraint(
            "(category='LAND' AND method='NONE' AND depreciable_value=0 AND non_depreciable_value=acquisition_value AND residual_value=0 AND useful_life_months IS NULL AND depreciation_account IS NULL) OR (category!='LAND' AND method='LINEAR' AND depreciable_value>residual_value AND non_depreciable_value=0 AND useful_life_months>0 AND depreciation_account IS NOT NULL)",
            name=op.f("ck_asset_land_and_plan"),
        ),
        sa.CheckConstraint(
            "disposed_at IS NULL OR disposed_at>=service_start_date", name=op.f("ck_asset_disposal")
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property.id"], name=op.f("fk_asset_property_id_property")
        ),
        sa.ForeignKeyConstraint(
            ["asset_account"], ["account.number"], name=op.f("fk_asset_asset_account_account")
        ),
        sa.ForeignKeyConstraint(
            ["depreciation_account"],
            ["account.number"],
            name=op.f("fk_asset_depreciation_account_account"),
        ),
    )
    op.create_index(op.f("ix_asset_property_id"), "asset", ["property_id"])
    op.create_table(
        "asset_component",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("service_start_date", sa.Date(), nullable=False),
        sa.Column("asset_account", sa.String(10), nullable=False),
        sa.Column("depreciation_account", sa.String(10), nullable=False),
        sa.Column("basis_reason", sa.Text(), nullable=False),
        sa.Column("duration_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "value>0 AND typeof(value)='integer'", name=op.f("ck_asset_component_value")
        ),
        sa.CheckConstraint("useful_life_months>0", name=op.f("ck_asset_component_life")),
        sa.CheckConstraint(
            "length(trim(basis_reason))>0 AND length(trim(duration_reason))>0",
            name=op.f("ck_asset_component_reasons"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["asset.id"], name=op.f("fk_asset_component_asset_id_asset")
        ),
        sa.ForeignKeyConstraint(
            ["asset_account"],
            ["account.number"],
            name=op.f("fk_asset_component_asset_account_account"),
        ),
        sa.ForeignKeyConstraint(
            ["depreciation_account"],
            ["account.number"],
            name=op.f("fk_asset_component_depreciation_account_account"),
        ),
    )
    op.create_index(op.f("ix_asset_component_asset_id"), "asset_component", ["asset_id"])
    op.create_table(
        "depreciation_schedule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), unique=True),
        sa.Column("component_id", sa.Integer(), unique=True),
        sa.Column("base", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("service_start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("asset_account", sa.String(10), nullable=False),
        sa.Column("depreciation_account", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(asset_id IS NOT NULL AND component_id IS NULL) OR (asset_id IS NULL AND component_id IS NOT NULL)",
            name=op.f("ck_depreciation_schedule_one_target"),
        ),
        sa.CheckConstraint(
            "method='LINEAR' AND base>0 AND useful_life_months>0",
            name=op.f("ck_depreciation_schedule_plan"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["asset.id"], name=op.f("fk_depreciation_schedule_asset_id_asset")
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["asset_component.id"],
            name=op.f("fk_depreciation_schedule_component_id_asset_component"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_account"],
            ["account.number"],
            name=op.f("fk_depreciation_schedule_asset_account_account"),
        ),
        sa.ForeignKeyConstraint(
            ["depreciation_account"],
            ["account.number"],
            name=op.f("fk_depreciation_schedule_depreciation_account_account"),
        ),
        sa.UniqueConstraint(
            "asset_id", "component_id", name=op.f("uq_depreciation_schedule_asset_id")
        ),
    )
    op.create_table(
        "depreciation_period",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("accumulated", sa.Integer(), nullable=False),
        sa.Column("net_book_value", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("accounting_entry_id", sa.Integer(), unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('CALCULATED','POSTED')", name=op.f("ck_depreciation_period_status")
        ),
        sa.CheckConstraint(
            "period_start<=period_end AND days>0", name=op.f("ck_depreciation_period_period")
        ),
        sa.CheckConstraint(
            "amount>=0 AND accumulated>=amount AND net_book_value>=0 AND typeof(amount)='integer' AND typeof(accumulated)='integer' AND typeof(net_book_value)='integer'",
            name=op.f("ck_depreciation_period_amounts"),
        ),
        sa.CheckConstraint(
            "(status='CALCULATED' AND accounting_entry_id IS NULL) OR (status='POSTED' AND accounting_entry_id IS NOT NULL)",
            name=op.f("ck_depreciation_period_posting"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["depreciation_schedule.id"],
            name=op.f("fk_depreciation_period_schedule_id_depreciation_schedule"),
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_year_id"],
            ["fiscal_year.id"],
            name=op.f("fk_depreciation_period_fiscal_year_id_fiscal_year"),
        ),
        sa.ForeignKeyConstraint(
            ["accounting_entry_id"],
            ["accounting_entry.id"],
            name=op.f("fk_depreciation_period_accounting_entry_id_accounting_entry"),
        ),
        sa.UniqueConstraint(
            "schedule_id", "fiscal_year_id", name=op.f("uq_depreciation_period_schedule_id")
        ),
    )
    op.create_index(
        op.f("ix_depreciation_period_schedule_id"), "depreciation_period", ["schedule_id"]
    )
    op.create_index(
        op.f("ix_depreciation_period_fiscal_year_id"), "depreciation_period", ["fiscal_year_id"]
    )
    for sql in GUARDS.values():
        op.execute(sql)


def downgrade() -> None:
    connection = op.get_bind()
    probes = (
        "SELECT 1 FROM depreciation_period LIMIT 1",
        "SELECT 1 FROM depreciation_schedule LIMIT 1",
        "SELECT 1 FROM asset_component LIMIT 1",
        "SELECT 1 FROM asset LIMIT 1",
    )
    for probe in probes:
        if connection.execute(sa.text(probe)).first():
            raise RuntimeError("Refusing to remove the asset register while it contains data")
    for name in GUARDS:
        op.execute(f"DROP TRIGGER IF EXISTS assets_{name}")
    op.drop_table("depreciation_period")
    op.drop_table("depreciation_schedule")
    op.drop_table("asset_component")
    op.drop_table("asset")
    op.execute("DELETE FROM account WHERE number IN ('213500','281350','281830')")
