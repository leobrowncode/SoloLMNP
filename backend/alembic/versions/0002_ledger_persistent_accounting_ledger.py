"""persistent accounting ledger

Revision ID: 0002_ledger
Revises: 0001_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_ledger"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GUARDS: dict[str, str] = {
    "entry_insert": "CREATE TRIGGER ledger_entry_insert BEFORE INSERT ON accounting_entry BEGIN\n SELECT CASE WHEN NEW.status != 'DRAFT' THEN RAISE(ABORT,'ENTRY_MUST_START_DRAFT') END;\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM fiscal_year WHERE id=NEW.fiscal_year_id AND status='OPEN'\n AND NEW.accounting_date BETWEEN start_date AND end_date)\n OR date(NEW.accounting_date) IS NULL OR date(NEW.piece_date) IS NULL\n THEN RAISE(ABORT,'EXERCISE_NOT_OPEN_OR_DATE_INVALID') END;\nEND",
    "entry_update": "CREATE TRIGGER ledger_entry_update BEFORE UPDATE ON accounting_entry BEGIN\n SELECT CASE WHEN OLD.status='VALIDATED' THEN RAISE(ABORT,'VALIDATED_ENTRY_IMMUTABLE') END;\n SELECT CASE WHEN (SELECT status FROM fiscal_year WHERE id=OLD.fiscal_year_id)!='OPEN'\n OR NOT EXISTS(SELECT 1 FROM fiscal_year WHERE id=NEW.fiscal_year_id AND status='OPEN'\n AND NEW.accounting_date BETWEEN start_date AND end_date)\n OR date(NEW.accounting_date) IS NULL OR date(NEW.piece_date) IS NULL\n THEN RAISE(ABORT,'EXERCISE_NOT_OPEN_OR_DATE_INVALID') END;\n SELECT CASE WHEN NEW.status='VALIDATED' AND (\n (SELECT COUNT(*) FROM accounting_entry_line WHERE accounting_entry_id=NEW.id)<2\n OR (SELECT SUM(debit) FROM accounting_entry_line WHERE accounting_entry_id=NEW.id)\n !=(SELECT SUM(credit) FROM accounting_entry_line WHERE accounting_entry_id=NEW.id)\n OR NOT EXISTS(SELECT 1 FROM accounting_journal WHERE code=NEW.journal_code AND active=1 AND label=NEW.journal_label)\n OR EXISTS(SELECT 1 FROM accounting_entry_line l JOIN account a ON a.number=l.account_number\n WHERE l.accounting_entry_id=NEW.id AND (a.active=0 OR l.account_label IS NULL OR l.account_label!=a.label))\n OR NEW.sequence != (SELECT COALESCE(MAX(sequence),0)+1 FROM accounting_entry WHERE fiscal_year_id=NEW.fiscal_year_id)\n OR NEW.entry_number != printf('%04d-%06d',(SELECT year FROM fiscal_year WHERE id=NEW.fiscal_year_id),NEW.sequence)\n OR NEW.accounting_date > date('now')\n OR NEW.validated_at < (SELECT MAX(validated_at) FROM accounting_entry WHERE fiscal_year_id=NEW.fiscal_year_id)\n ) THEN RAISE(ABORT,'POSTING_CONSTRAINT') END;\nEND",
    "entry_delete": "CREATE TRIGGER ledger_entry_delete BEFORE DELETE ON accounting_entry BEGIN\n SELECT CASE WHEN OLD.status='VALIDATED' OR (SELECT status FROM fiscal_year WHERE id=OLD.fiscal_year_id)!='OPEN'\n THEN RAISE(ABORT,'ENTRY_LOCKED') END;\nEND",
    "year_identity": "CREATE TRIGGER ledger_year_identity BEFORE UPDATE ON fiscal_year\n WHEN EXISTS(SELECT 1 FROM accounting_entry WHERE fiscal_year_id=OLD.id)\n AND (NEW.id!=OLD.id OR NEW.start_date!=OLD.start_date OR NEW.end_date!=OLD.end_date\n OR NEW.year!=OLD.year OR NEW.fiscal_vintage!=OLD.fiscal_vintage OR NEW.rental_activity_id!=OLD.rental_activity_id)\n BEGIN SELECT RAISE(ABORT,'EXERCISE_WITH_ENTRIES_IMMUTABLE'); END",
    "year_overlap_insert": "CREATE TRIGGER ledger_year_overlap_insert BEFORE INSERT ON fiscal_year\n WHEN EXISTS(SELECT 1 FROM fiscal_year WHERE rental_activity_id=NEW.rental_activity_id\n AND start_date<=NEW.end_date AND end_date>=NEW.start_date)\n BEGIN SELECT RAISE(ABORT,'OVERLAPPING_EXERCISE'); END",
    "year_overlap_update": "CREATE TRIGGER ledger_year_overlap_update BEFORE UPDATE ON fiscal_year\n WHEN EXISTS(SELECT 1 FROM fiscal_year WHERE id!=OLD.id AND rental_activity_id=NEW.rental_activity_id\n AND start_date<=NEW.end_date AND end_date>=NEW.start_date)\n BEGIN SELECT RAISE(ABORT,'OVERLAPPING_EXERCISE'); END",
    "account_freeze": "CREATE TRIGGER ledger_account_freeze BEFORE UPDATE ON account\n WHEN (NEW.number!=OLD.number OR NEW.label!=OLD.label OR NEW.account_type!=OLD.account_type)\n AND EXISTS(SELECT 1 FROM accounting_entry_line l JOIN accounting_entry e ON e.id=l.accounting_entry_id\n WHERE l.account_number=OLD.number AND e.status='VALIDATED')\n BEGIN SELECT RAISE(ABORT,'USED_ACCOUNT_IMMUTABLE'); END",
    "journal_freeze": "CREATE TRIGGER ledger_journal_freeze BEFORE UPDATE ON accounting_journal\n WHEN (NEW.code!=OLD.code OR NEW.label!=OLD.label OR NEW.journal_type!=OLD.journal_type)\n AND EXISTS(SELECT 1 FROM accounting_entry WHERE journal_code=OLD.code AND status='VALIDATED')\n BEGIN SELECT RAISE(ABORT,'USED_JOURNAL_IMMUTABLE'); END",
    "line_insert": "CREATE TRIGGER ledger_line_insert BEFORE INSERT ON accounting_entry_line WHEN NOT EXISTS(SELECT 1 FROM accounting_entry e JOIN fiscal_year y ON y.id=e.fiscal_year_id WHERE e.id=NEW.accounting_entry_id AND e.status='DRAFT' AND y.status='OPEN') BEGIN SELECT RAISE(ABORT,'LINE_LOCKED'); END",
    "line_update": "CREATE TRIGGER ledger_line_update BEFORE UPDATE ON accounting_entry_line WHEN NOT EXISTS(SELECT 1 FROM accounting_entry e JOIN fiscal_year y ON y.id=e.fiscal_year_id WHERE e.id=OLD.accounting_entry_id AND e.status='DRAFT' AND y.status='OPEN') OR NOT EXISTS(SELECT 1 FROM accounting_entry e JOIN fiscal_year y ON y.id=e.fiscal_year_id WHERE e.id=NEW.accounting_entry_id AND e.status='DRAFT' AND y.status='OPEN') BEGIN SELECT RAISE(ABORT,'LINE_LOCKED'); END",
    "line_delete": "CREATE TRIGGER ledger_line_delete BEFORE DELETE ON accounting_entry_line WHEN NOT EXISTS(SELECT 1 FROM accounting_entry e JOIN fiscal_year y ON y.id=e.fiscal_year_id WHERE e.id=OLD.accounting_entry_id AND e.status='DRAFT' AND y.status='OPEN') BEGIN SELECT RAISE(ABORT,'LINE_LOCKED'); END",
    "event_update": "CREATE TRIGGER ledger_event_update BEFORE UPDATE ON ledger_event BEGIN SELECT RAISE(ABORT,'LEDGER_EVENT_IMMUTABLE'); END",
    "event_delete": "CREATE TRIGGER ledger_event_delete BEFORE DELETE ON ledger_event BEGIN SELECT RAISE(ABORT,'LEDGER_EVENT_IMMUTABLE'); END",
}


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "account",
        sa.Column("number", sa.String(length=10), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "account_type IN ('ASSET','LIABILITY','EQUITY','EXPENSE','INCOME')",
            name=op.f("ck_account_type"),
        ),
        sa.CheckConstraint(
            "length(number) BETWEEN 3 AND 10 AND number NOT GLOB '*[^0-9]*'",
            name=op.f("ck_account_number"),
        ),
        sa.CheckConstraint("active IN (0,1)", name=op.f("ck_account_active")),
        sa.CheckConstraint("length(trim(label)) > 0", name=op.f("ck_account_label")),
        sa.PrimaryKeyConstraint("number", name=op.f("pk_account")),
    )
    op.create_table(
        "accounting_journal",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("journal_type", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "journal_type IN ('GENERAL','BANK','SALES','PURCHASE','OPENING')",
            name=op.f("ck_accounting_journal_type"),
        ),
        sa.CheckConstraint(
            "length(code) BETWEEN 2 AND 10 AND code NOT GLOB '*[^A-Z0-9]*'",
            name=op.f("ck_accounting_journal_code"),
        ),
        sa.CheckConstraint("active IN (0,1)", name=op.f("ck_accounting_journal_active")),
        sa.CheckConstraint("length(trim(label)) > 0", name=op.f("ck_accounting_journal_label")),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_accounting_journal")),
    )
    op.create_table(
        "ledger_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ledger_event")),
    )
    with op.batch_alter_table("ledger_event", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ledger_event_entry_id"), ["entry_id"], unique=False)

    op.create_table(
        "accounting_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year_id", sa.Integer(), nullable=False),
        sa.Column("journal_code", sa.String(length=10), nullable=False),
        sa.Column("entry_number", sa.String(length=40), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("accounting_date", sa.Date(), nullable=False),
        sa.Column("piece_reference", sa.String(length=200), nullable=False),
        sa.Column("piece_date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("reversal_of_id", sa.Integer(), nullable=True),
        sa.Column("journal_label", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "(status='DRAFT' AND sequence IS NULL AND entry_number IS NULL AND validated_at IS NULL) OR (status='VALIDATED' AND sequence > 0 AND entry_number IS NOT NULL AND validated_at IS NOT NULL)",
            name=op.f("ck_accounting_entry_validation"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','VALIDATED')", name=op.f("ck_accounting_entry_status")
        ),
        sa.CheckConstraint(
            "length(trim(label)) > 0 AND length(trim(piece_reference)) > 0",
            name=op.f("ck_accounting_entry_references"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_accounting_entry_version")),
        sa.ForeignKeyConstraint(
            ["fiscal_year_id"],
            ["fiscal_year.id"],
            name=op.f("fk_accounting_entry_fiscal_year_id_fiscal_year"),
        ),
        sa.ForeignKeyConstraint(
            ["journal_code"],
            ["accounting_journal.code"],
            name=op.f("fk_accounting_entry_journal_code_accounting_journal"),
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_id"],
            ["accounting_entry.id"],
            name=op.f("fk_accounting_entry_reversal_of_id_accounting_entry"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounting_entry")),
        sa.UniqueConstraint("fiscal_year_id", "entry_number", name="uq_entry_year_number"),
        sa.UniqueConstraint("fiscal_year_id", "sequence", name="uq_entry_year_sequence"),
        sa.UniqueConstraint("reversal_of_id", name=op.f("uq_accounting_entry_reversal_of_id")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("accounting_entry", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_accounting_entry_accounting_date"), ["accounting_date"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_accounting_entry_fiscal_year_id"), ["fiscal_year_id"], unique=False
        )

    op.create_table(
        "accounting_entry_line",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("accounting_entry_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("account_number", sa.String(length=10), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("debit", sa.Integer(), nullable=False),
        sa.Column("credit", sa.Integer(), nullable=False),
        sa.Column("account_label", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "typeof(debit)='integer' AND typeof(credit)='integer' AND ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))",
            name=op.f("ck_accounting_entry_line_one_positive_side"),
        ),
        sa.CheckConstraint("length(trim(label)) > 0", name=op.f("ck_accounting_entry_line_label")),
        sa.CheckConstraint("position >= 1", name=op.f("ck_accounting_entry_line_position")),
        sa.ForeignKeyConstraint(
            ["account_number"],
            ["account.number"],
            name=op.f("fk_accounting_entry_line_account_number_account"),
        ),
        sa.ForeignKeyConstraint(
            ["accounting_entry_id"],
            ["accounting_entry.id"],
            name=op.f("fk_accounting_entry_line_accounting_entry_id_accounting_entry"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounting_entry_line")),
        sa.UniqueConstraint(
            "accounting_entry_id",
            "position",
            name=op.f("uq_accounting_entry_line_accounting_entry_id"),
        ),
    )
    with op.batch_alter_table("accounting_entry_line", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_accounting_entry_line_account_number"), ["account_number"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_accounting_entry_line_accounting_entry_id"),
            ["accounting_entry_id"],
            unique=False,
        )

    # ### end Alembic commands ###

    for statement in GUARDS.values():
        op.execute(statement)

    # Frozen seed: also supports activities created before the ledger migration.
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('108000','Compte de l’exploitant','EQUITY',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('164000','Emprunts auprès des établissements de crédit','LIABILITY',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('211000','Terrains','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('213000','Constructions','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('218300','Matériel de bureau et matériel informatique','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('218400','Mobilier','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('281300','Amortissements des constructions','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('281840','Amortissements du mobilier','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('401000','Fournisseurs','LIABILITY',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('411000','Clients','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('512000','Banques','ASSET',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('606000','Achats non stockés de matières et fournitures','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('615000','Entretien et réparations','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('616000','Primes d’assurances','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('622000','Rémunérations d’intermédiaires et honoraires','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('627000','Services bancaires et assimilés','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('635000','Autres impôts, taxes et versements assimilés','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('661000','Charges d’intérêts','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('681100','Dotations aux amortissements sur immobilisations','EXPENSE',1)"
    )
    op.execute(
        "INSERT INTO account (number,label,account_type,active) VALUES ('706000','Prestations de services','INCOME',1)"
    )
    op.execute(
        "INSERT INTO accounting_journal (code,label,journal_type,active) VALUES ('OD','Opérations diverses','GENERAL',1)"
    )
    op.execute(
        "INSERT INTO accounting_journal (code,label,journal_type,active) VALUES ('BQ','Banque','BANK',1)"
    )
    op.execute(
        "INSERT INTO accounting_journal (code,label,journal_type,active) VALUES ('AC','Achats','PURCHASE',1)"
    )
    op.execute(
        "INSERT INTO accounting_journal (code,label,journal_type,active) VALUES ('VE','Ventes','SALES',1)"
    )
    op.execute(
        "INSERT INTO accounting_journal (code,label,journal_type,active) VALUES ('AN','À-nouveaux','OPENING',1)"
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM accounting_entry")
    ) or op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM ledger_event")):
        raise RuntimeError("Refusing to discard a populated ledger; restore a backup instead")
    for name in GUARDS:
        op.execute("DROP TRIGGER ledger_" + name)
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("accounting_entry_line", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_accounting_entry_line_accounting_entry_id"))
        batch_op.drop_index(batch_op.f("ix_accounting_entry_line_account_number"))

    op.drop_table("accounting_entry_line")
    with op.batch_alter_table("accounting_entry", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_accounting_entry_fiscal_year_id"))
        batch_op.drop_index(batch_op.f("ix_accounting_entry_accounting_date"))

    op.drop_table("accounting_entry")
    with op.batch_alter_table("ledger_event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ledger_event_entry_id"))

    op.drop_table("ledger_event")
    op.drop_table("accounting_journal")
    op.drop_table("account")
    # ### end Alembic commands ###
