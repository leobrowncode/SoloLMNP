"""Translate the SQLite migration SQL to Postgres at execution time.

The migration files stay the SQLite source of truth. On Postgres, checks, seed
booleans and triggers are rewritten so the same invariants hold: integer cents,
immutable validated entries, and the ledger as the only place balances live.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import Connection

TYPEOF_SQL = """
CREATE OR REPLACE FUNCTION typeof(value anyelement)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $typeof$
  SELECT CASE
    WHEN value IS NULL THEN 'null'
    WHEN pg_typeof(value)::text IN ('smallint', 'integer', 'bigint') THEN 'integer'
    WHEN pg_typeof(value)::text = 'numeric'
      AND value::numeric = trunc(value::numeric) THEN 'integer'
    WHEN pg_typeof(value)::text IN ('real', 'double precision', 'numeric') THEN 'real'
    ELSE 'text'
  END
$typeof$
"""

_VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"
_CREATE = re.compile(
    r"^CREATE TRIGGER (?P<name>\w+)\s+BEFORE\s+(?P<event>INSERT|UPDATE|DELETE)\s+"
    r"ON\s+(?P<table>\w+)\s+(?:WHEN\s+(?P<when>.*?)\s+)?BEGIN\s+(?P<body>.*?)\s*END\s*$",
    re.S | re.IGNORECASE,
)
_DROP = re.compile(r"^DROP TRIGGER (?:IF EXISTS\s+)?(\w+)\s*$", re.IGNORECASE)
_CASE = re.compile(
    r"SELECT\s+CASE\s+WHEN\s+(.*?)\s+THEN\s+RAISE\(ABORT,'([^']+)'\)\s+END\s*;?",
    re.S | re.IGNORECASE,
)
_PLAIN_RAISE = re.compile(r"SELECT\s+RAISE\(ABORT,'([^']+)'\)\s*;?", re.IGNORECASE)
# SQLAlchemy doubles % before the DBAPI sees the statement, so both forms occur.
_PRINTF = re.compile(
    r"printf\('(?:%%|%)04d-(?:%%|%)06d',\s*"
    r"(\((?:[^()]|\([^()]*\))*\)|[^,]+),\s*([^)]+)\)"
)
_TENANT_GLOB = re.compile(
    r"request_id\s+GLOB\s+'rent-p'\s*\|\|\s*OLD\.property_id\s*\|\|\s*'-t'\s*\|\|\s*"
    r"OLD\.id\s*\|\|\s*'-\[0-9\]\[0-9\]\[0-9\]\[0-9\]\[0-9\]\[0-9\]'",
    re.S,
)
_JULIAN_DAYS = re.compile(
    r"CAST\(julianday\(([^()]+)\)\s*-\s*julianday\(([^()]+)\)\s*\+\s*1\s+AS\s+INTEGER\)",
    re.IGNORECASE,
)
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_TRIGGER_TABLES: dict[str, str] | None = None


@dataclass(frozen=True)
class AdaptedSQL:
    statement: str
    function_sql: str | None = None
    drop_function: str | None = None


def trigger_tables() -> dict[str, str]:
    global _TRIGGER_TABLES
    if _TRIGGER_TABLES is None:
        found: dict[str, str] = {}
        pattern = re.compile(
            r"CREATE TRIGGER (\w+) BEFORE (?:INSERT|UPDATE|DELETE) ON (\w+)",
        )
        for path in _VERSIONS.glob("*.py"):
            for name, table in pattern.findall(path.read_text(encoding="utf-8")):
                found[name] = table
        _TRIGGER_TABLES = found
    return _TRIGGER_TABLES


def adapt_postgres_sql(statement: str) -> AdaptedSQL:
    sql = statement.strip()
    created = _CREATE.match(sql)
    if created is not None:
        return _create_trigger(created)
    dropped = _DROP.match(sql)
    if dropped is not None:
        name = dropped.group(1)
        table = trigger_tables().get(name)
        if table is None:
            raise RuntimeError(f"Table inconnue pour le trigger {name}")
        return AdaptedSQL(
            statement=f"DROP TRIGGER IF EXISTS {name} ON {table}",
            drop_function=f"sololmnp_{name}",
        )
    return AdaptedSQL(statement=_rewrite_expression(sql))


def install_postgres_ddl_adapter(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    if connection.info.get("sololmnp_postgres_ddl"):
        return
    connection.info["sololmnp_postgres_ddl"] = True
    pending: list[str] = []
    depth = {"n": 0}

    @event.listens_for(connection, "before_cursor_execute", retval=True)
    def adapt(  # type: ignore[no-untyped-def]
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        if depth["n"] or not isinstance(statement, str):
            return statement, parameters
        adapted = adapt_postgres_sql(statement)
        depth["n"] += 1
        try:
            if adapted.function_sql is not None:
                cursor.execute(adapted.function_sql)
            if adapted.drop_function is not None:
                pending.append(adapted.drop_function)
        finally:
            depth["n"] -= 1
        return adapted.statement, parameters

    @event.listens_for(connection, "after_cursor_execute")
    def drop_function(  # type: ignore[no-untyped-def]
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if depth["n"] or not pending:
            return
        if not isinstance(statement, str) or not statement.lstrip().upper().startswith(
            "DROP TRIGGER"
        ):
            return
        depth["n"] += 1
        try:
            while pending:
                cursor.execute(f"DROP FUNCTION IF EXISTS {pending.pop()}()")
        finally:
            depth["n"] -= 1


def _create_trigger(match: re.Match[str]) -> AdaptedSQL:
    name = match.group("name")
    event_name = match.group("event").upper()
    table = match.group("table")
    returning = "OLD" if event_name == "DELETE" else "NEW"
    lines = _statements(match.group("body"), match.group("when"), returning)
    body = "\n  ".join(lines)
    function_sql = (
        f"CREATE OR REPLACE FUNCTION sololmnp_{name}() RETURNS trigger "
        f"LANGUAGE plpgsql AS $body$\nBEGIN\n  {body}\nEND;\n$body$"
    )
    trigger_sql = (
        f"CREATE TRIGGER {name} BEFORE {event_name} ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION sololmnp_{name}()"
    )
    return AdaptedSQL(statement=trigger_sql, function_sql=function_sql)


def _statements(body: str, when: str | None, returning: str) -> list[str]:
    lines: list[str] = []
    if when is not None:
        lines.append(
            f"IF NOT ({_rewrite_expression(when.strip())}) THEN\n    RETURN {returning};\n  END IF;"
        )
    remaining = body.strip()
    while remaining:
        remaining = remaining.lstrip(";").strip()
        if not remaining:
            break
        case = _CASE.match(remaining)
        plain = _PLAIN_RAISE.match(remaining)
        if case is not None and (plain is None or case.start() <= plain.start()):
            condition, code = case.group(1), case.group(2)
            lines.append(
                f"IF {_rewrite_expression(condition.strip())} THEN\n"
                f"    RAISE EXCEPTION '{code}' USING ERRCODE = '23514';\n"
                f"  END IF;"
            )
            remaining = remaining[case.end() :]
            continue
        if plain is not None:
            lines.append(f"RAISE EXCEPTION '{plain.group(1)}' USING ERRCODE = '23514';")
            remaining = remaining[plain.end() :]
            continue
        raise RuntimeError(f"Trigger SQL non traduit : {remaining[:180]}")
    lines.append(f"RETURN {returning};")
    return lines


def _rewrite_expression(sql: str) -> str:
    sql = sql.replace("date('now')", "CURRENT_DATE")
    sql = re.sub(r"\bdate\(([^()]+)\)", r"(\1)", sql)
    sql = _JULIAN_DAYS.sub(r"((\1) - (\2) + 1)", sql)
    sql = _PRINTF.sub(
        r"(lpad((\1)::text, 4, '0') || '-' || lpad((\2)::text, 6, '0'))",
        sql,
    )
    sql = re.sub(r"\bIFNULL\s*\(", "COALESCE(", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bactive\s*=\s*1\b", "active IS TRUE", sql)
    sql = re.sub(r"\bactive\s*=\s*0\b", "active IS FALSE", sql)
    sql = sql.replace("NOT GLOB '*[^0-9]*'", "~ '^[0-9]*$'")
    sql = sql.replace("NOT GLOB '*[^A-Z0-9]*'", "~ '^[A-Z0-9]*$'")
    sql = sql.replace("active IN (0,1)", "active IN (TRUE, FALSE)")
    sql = _TENANT_GLOB.sub(
        "request_id ~ ('^rent-p' || OLD.property_id::text || '-t' || OLD.id::text || '-[0-9]{6}$')",
        sql,
    )
    if re.match(r"INSERT INTO (account|accounting_journal)\b", sql, re.IGNORECASE):
        sql = re.sub(r",\s*1\)\s*$", ", TRUE)", sql)
    return sql


def ensure_postgres_identities(connection: Connection) -> None:
    """Give integer primary keys a default. SQLite rowids have no Postgres equivalent."""
    if connection.dialect.name != "postgresql":
        return
    rows = connection.execute(
        text(
            """
            SELECT c.table_name, c.column_name
            FROM information_schema.columns AS c
            JOIN information_schema.table_constraints AS tc
              ON tc.table_schema = c.table_schema
             AND tc.table_name = c.table_name
             AND tc.constraint_type = 'PRIMARY KEY'
            JOIN information_schema.key_column_usage AS k
              ON k.constraint_schema = tc.table_schema
             AND k.constraint_name = tc.constraint_name
             AND k.column_name = c.column_name
            WHERE c.table_schema = 'public'
              AND c.data_type = 'integer'
              AND c.is_identity = 'NO'
              AND c.column_default IS NULL
              AND (
                SELECT COUNT(*)
                FROM information_schema.key_column_usage AS kk
                WHERE kk.constraint_schema = tc.table_schema
                  AND kk.constraint_name = tc.constraint_name
              ) = 1
            """
        )
    ).all()
    for table_name, column_name in rows:
        if _IDENT.fullmatch(str(table_name)) is None or _IDENT.fullmatch(str(column_name)) is None:
            raise RuntimeError(f"Identifiant SQL inattendu : {table_name}.{column_name}")
        connection.execute(
            text(
                f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" '
                "ADD GENERATED BY DEFAULT AS IDENTITY"
            )
        )
