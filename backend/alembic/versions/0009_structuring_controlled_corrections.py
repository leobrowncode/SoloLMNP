"""Allow audited corrections of structuring rows; keep posted plans frozen.

Revision ID: 0009_structuring
Revises: 0008_dwelling

Deletes stay forbidden. A posted depreciation period still blocks the value,
duration, dates and accounts that explain it. A referenced loan keeps its
opening principal and start date. A bank number with movements stays put.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_structuring"
down_revision: str | None = "0008_dwelling"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ASSET_UPDATE = """
CREATE TRIGGER assets_asset_update BEFORE UPDATE ON asset
BEGIN
 SELECT CASE WHEN OLD.property_id!=NEW.property_id OR OLD.category!=NEW.category
  OR OLD.method!=NEW.method THEN RAISE(ABORT,'ASSET_IDENTITY_IMMUTABLE') END;
 SELECT CASE WHEN (
    OLD.acquisition_value!=NEW.acquisition_value
    OR OLD.depreciable_value!=NEW.depreciable_value
    OR OLD.non_depreciable_value!=NEW.non_depreciable_value
    OR OLD.residual_value!=NEW.residual_value
    OR OLD.asset_account!=NEW.asset_account
    OR IFNULL(OLD.depreciation_account,'')!=IFNULL(NEW.depreciation_account,'')
  ) AND EXISTS (
    SELECT 1 FROM depreciation_schedule s
    JOIN depreciation_period p ON p.schedule_id=s.id
    WHERE p.status='POSTED' AND (
      s.asset_id=OLD.id OR s.component_id IN (
        SELECT id FROM asset_component WHERE asset_id=OLD.id
      )
    )
  ) THEN RAISE(ABORT,'ASSET_HAS_POSTED_DEPRECIATION') END;
 SELECT CASE WHEN (
    IFNULL(OLD.useful_life_months,-1)!=IFNULL(NEW.useful_life_months,-1)
    OR OLD.service_start_date!=NEW.service_start_date
    OR OLD.acquisition_date!=NEW.acquisition_date
  ) AND EXISTS (
    SELECT 1 FROM depreciation_schedule s
    JOIN depreciation_period p ON p.schedule_id=s.id
    WHERE p.status='POSTED' AND s.asset_id=OLD.id
  ) THEN RAISE(ABORT,'ASSET_HAS_POSTED_DEPRECIATION') END;
 SELECT CASE WHEN EXISTS (SELECT 1 FROM asset_component WHERE asset_id=NEW.id)
  AND (SELECT COALESCE(SUM(value),0) FROM asset_component WHERE asset_id=NEW.id)
      > NEW.depreciable_value-NEW.residual_value
  THEN RAISE(ABORT,'COMPONENT_TOTAL_EXCEEDS_BASE') END;
 SELECT CASE WHEN EXISTS (
    SELECT 1 FROM asset_component
    WHERE asset_id=NEW.id AND service_start_date<NEW.service_start_date
  ) THEN RAISE(ABORT,'COMPONENT_DATE_INVALID') END;
END
"""

COMPONENT_UPDATE = """
CREATE TRIGGER assets_component_update BEFORE UPDATE ON asset_component
BEGIN
 SELECT CASE WHEN OLD.asset_id!=NEW.asset_id
  THEN RAISE(ABORT,'COMPONENT_IDENTITY_IMMUTABLE') END;
 SELECT CASE WHEN NEW.service_start_date<(
    SELECT service_start_date FROM asset WHERE id=NEW.asset_id
  ) THEN RAISE(ABORT,'COMPONENT_DATE_INVALID') END;
 SELECT CASE WHEN NEW.value+(
    SELECT COALESCE(SUM(value),0) FROM asset_component
    WHERE asset_id=NEW.asset_id AND id!=NEW.id
  )>(SELECT depreciable_value-residual_value FROM asset WHERE id=NEW.asset_id)
  THEN RAISE(ABORT,'COMPONENT_TOTAL_EXCEEDS_BASE') END;
 SELECT CASE WHEN (
    OLD.value!=NEW.value OR OLD.useful_life_months!=NEW.useful_life_months
    OR OLD.service_start_date!=NEW.service_start_date
    OR OLD.asset_account!=NEW.asset_account
    OR OLD.depreciation_account!=NEW.depreciation_account
  ) AND EXISTS (
    SELECT 1 FROM depreciation_schedule s
    JOIN depreciation_period p ON p.schedule_id=s.id
    WHERE s.component_id=OLD.id AND p.status='POSTED'
  ) THEN RAISE(ABORT,'COMPONENT_HAS_POSTED_DEPRECIATION') END;
END
"""

SCHEDULE_UPDATE = """
CREATE TRIGGER assets_schedule_update BEFORE UPDATE ON depreciation_schedule
BEGIN
 SELECT CASE WHEN EXISTS (
    SELECT 1 FROM depreciation_period
    WHERE schedule_id=OLD.id AND status='POSTED'
  ) THEN RAISE(ABORT,'SCHEDULE_IMMUTABLE') END;
 SELECT CASE WHEN NEW.asset_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM asset a WHERE a.id=NEW.asset_id AND a.category!='LAND'
    AND NOT EXISTS(SELECT 1 FROM asset_component c WHERE c.asset_id=a.id)
    AND NEW.base=a.depreciable_value-a.residual_value
    AND NEW.service_start_date=a.service_start_date
    AND NEW.useful_life_months=a.useful_life_months
    AND NEW.asset_account=a.asset_account
    AND NEW.depreciation_account=a.depreciation_account
  ) THEN RAISE(ABORT,'ASSET_SCHEDULE_INVALID') END;
 SELECT CASE WHEN NEW.component_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM asset_component c JOIN asset a ON a.id=c.asset_id
    WHERE c.id=NEW.component_id
    AND (SELECT SUM(value) FROM asset_component WHERE asset_id=a.id)
        =a.depreciable_value-a.residual_value
    AND NEW.base=c.value
    AND NEW.service_start_date=c.service_start_date
    AND NEW.useful_life_months=c.useful_life_months
    AND NEW.asset_account=c.asset_account
    AND NEW.depreciation_account=c.depreciation_account
  ) THEN RAISE(ABORT,'COMPONENT_SCHEDULE_INVALID') END;
END
"""

LOAN_UPDATE = """
CREATE TRIGGER operations_loan_update BEFORE UPDATE ON loan
BEGIN
 SELECT CASE WHEN OLD.property_id!=NEW.property_id
  OR OLD.principal_account!=NEW.principal_account
  THEN RAISE(ABORT,'LOAN_IDENTITY_IMMUTABLE') END;
 SELECT CASE WHEN (OLD.initial_principal!=NEW.initial_principal
  OR OLD.start_date!=NEW.start_date) AND (
    EXISTS (SELECT 1 FROM business_operation WHERE loan_id=OLD.id)
    OR EXISTS (
      SELECT 1 FROM accounting_entry_line l
      JOIN accounting_entry e ON e.id=l.accounting_entry_id
      WHERE l.account_number=OLD.principal_account AND e.status='VALIDATED'
    )
  ) THEN RAISE(ABORT,'LOAN_REFERENCED') END;
END
"""

BANK_UPDATE = """
CREATE TRIGGER operations_bank_account_update BEFORE UPDATE ON bank_account
BEGIN
 SELECT CASE WHEN OLD.account_number!=NEW.account_number AND (
    EXISTS (SELECT 1 FROM bank_transaction WHERE bank_account_id=OLD.id)
    OR EXISTS (SELECT 1 FROM business_operation WHERE bank_account_id=OLD.id)
    OR EXISTS (
      SELECT 1 FROM accounting_entry_line l
      JOIN accounting_entry e ON e.id=l.accounting_entry_id
      WHERE l.account_number=OLD.account_number AND e.status='VALIDATED'
    )
  ) THEN RAISE(ABORT,'BANK_HAS_MOVEMENTS') END;
END
"""

PROPERTY_UPDATE = """
CREATE TRIGGER foundation_property_financial_update BEFORE UPDATE ON property
WHEN (
  OLD.acquisition_price!=NEW.acquisition_price
  OR OLD.acquisition_costs!=NEW.acquisition_costs
  OR OLD.land_value!=NEW.land_value
  OR OLD.building_value!=NEW.building_value
  OR OLD.acquisition_date!=NEW.acquisition_date
) AND EXISTS (SELECT 1 FROM asset WHERE property_id=OLD.id)
BEGIN SELECT RAISE(ABORT,'PROPERTY_HAS_ASSETS'); END
"""

TENANT_UPDATE = """
CREATE TRIGGER dwelling_tenant_update BEFORE UPDATE ON tenant
WHEN (
  OLD.name!=NEW.name OR OLD.monthly_rent!=NEW.monthly_rent
  OR OLD.entry_date!=NEW.entry_date
) AND EXISTS (
  SELECT 1 FROM business_operation
  WHERE request_id GLOB 'rent-p' || OLD.property_id || '-t' || OLD.id
    || '-[0-9][0-9][0-9][0-9][0-9][0-9]'
)
BEGIN SELECT RAISE(ABORT,'TENANT_HAS_RENTS'); END
"""

_REPLACED = (
    "assets_asset_update",
    "assets_component_update",
    "assets_schedule_update",
    "operations_loan_update",
    "operations_bank_account_update",
)

_CREATED = (
    ASSET_UPDATE,
    COMPONENT_UPDATE,
    SCHEDULE_UPDATE,
    LOAN_UPDATE,
    BANK_UPDATE,
    PROPERTY_UPDATE,
    TENANT_UPDATE,
)

_PREVIOUS = (
    "CREATE TRIGGER assets_asset_update BEFORE UPDATE ON asset "
    "BEGIN SELECT RAISE(ABORT,'ASSET_IMMUTABLE'); END",
    "CREATE TRIGGER assets_component_update BEFORE UPDATE ON asset_component "
    "BEGIN SELECT RAISE(ABORT,'COMPONENT_IMMUTABLE'); END",
    "CREATE TRIGGER assets_schedule_update BEFORE UPDATE ON depreciation_schedule "
    "BEGIN SELECT RAISE(ABORT,'SCHEDULE_IMMUTABLE'); END",
    "CREATE TRIGGER operations_loan_update BEFORE UPDATE ON loan "
    "BEGIN SELECT RAISE(ABORT,'BUSINESS_RECORD_IMMUTABLE'); END",
    "CREATE TRIGGER operations_bank_account_update BEFORE UPDATE ON bank_account "
    "BEGIN SELECT RAISE(ABORT,'BUSINESS_RECORD_IMMUTABLE'); END",
)


def upgrade() -> None:
    for name in _REPLACED:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    for statement in _CREATED:
        op.execute(statement)


def downgrade() -> None:
    for name in (
        "assets_asset_update",
        "assets_component_update",
        "assets_schedule_update",
        "operations_loan_update",
        "operations_bank_account_update",
        "foundation_property_financial_update",
        "dwelling_tenant_update",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    for statement in _PREVIOUS:
        op.execute(statement)
