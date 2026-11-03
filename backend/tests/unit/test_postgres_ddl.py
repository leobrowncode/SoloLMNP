import ast
from pathlib import Path

from fastapi import HTTPException

from app.core.config import Settings
from app.core.postgres_ddl import adapt_postgres_sql
from app.services.backup import create_backup

_VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _trigger_statements() -> list[str]:
    found: list[str] = []
    for path in sorted(_VERSIONS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.lstrip().startswith("CREATE TRIGGER")
            ):
                found.append(node.value.strip())
    return found


def test_every_migration_trigger_translates() -> None:
    statements = _trigger_statements()
    assert len(statements) >= 20
    for sql in statements:
        # The driver sees percent signs doubled, which is how Alembic sends printf.
        for variant in (sql, sql.replace("%", "%%")):
            adapted = adapt_postgres_sql(variant)
            assert adapted.function_sql is not None
            combined = adapted.function_sql + adapted.statement
            folded = combined.lower()
            assert "CREATE TRIGGER" in adapted.statement
            assert "EXECUTE FUNCTION" in adapted.statement
            assert "FOR EACH ROW" in adapted.statement
            assert "RAISE(ABORT" not in combined
            assert "GLOB" not in combined
            assert "date('now')" not in combined
            assert "printf(" not in folded
            assert "ifnull(" not in folded
            assert "julianday(" not in folded
            assert "active=1" not in combined.replace(" ", "")
            assert "active=0" not in combined.replace(" ", "")
            assert "RAISE EXCEPTION" in adapted.function_sql
            assert "ERRCODE = '23514'" in adapted.function_sql


def test_drop_trigger_names_its_table() -> None:
    adapted = adapt_postgres_sql("DROP TRIGGER IF EXISTS ledger_entry_update")
    assert adapted.statement == "DROP TRIGGER IF EXISTS ledger_entry_update ON accounting_entry"
    assert adapted.drop_function == "sololmnp_ledger_entry_update"


def test_seed_booleans_and_digit_checks() -> None:
    compact = adapt_postgres_sql(
        "INSERT INTO account (number,label,account_type,active) "
        "VALUES ('108000','Compte','EQUITY',1)"
    )
    spaced = adapt_postgres_sql(
        "INSERT INTO account (number, label, account_type, active) "
        "VALUES (:number, :label, :kind, 1)"
    )
    assert compact.statement.endswith(", TRUE)")
    assert spaced.statement.endswith(", TRUE)")
    check = adapt_postgres_sql("length(number) BETWEEN 3 AND 10 AND number NOT GLOB '*[^0-9]*'")
    assert "~ '^[0-9]*$'" in check.statement
    assert "active IN (TRUE, FALSE)" in adapt_postgres_sql("active IN (0,1)").statement


def test_backup_refuses_postgres_without_touching_a_server() -> None:
    settings = Settings(_env_file=None, database_url="postgresql://localhost/sololmnp")
    try:
        create_backup(settings)
    except HTTPException as error:
        assert error.status_code == 409
        assert error.detail["code"] == "BACKUP_SQLITE_ONLY"
    else:
        raise AssertionError("la sauvegarde fichier aurait dû être refusée")
