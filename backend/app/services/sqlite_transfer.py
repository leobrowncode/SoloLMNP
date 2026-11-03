"""Copy a SQLite dossier into Postgres and compare the ledger outputs.

Validated balances, the FEC and the liasse are read from each side after the
copy. The ledger stays the only source of those figures. User triggers are
disabled for the load so immutable validated rows can be inserted as they
were; foreign keys stay on. The copy is rolled back when the check fails.
"""

from __future__ import annotations

import hashlib
import re

from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Table

from app.core.config import Settings
from app.core.database import SCHEMA_REVISION, create_database_engine
from app.domain.filing.declaration import archival_csv, archival_json
from app.domain.filing.fec import render_fec
from app.models import Base
from app.services.efi import efi_worksheet, worksheet_pdf

_DOSSIER_TABLES = ("rental_activity", "fiscal_year", "accounting_entry")
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def copy_sqlite_to_postgres(
    source: Settings,
    target: Settings,
    *,
    replace: bool,
) -> dict[str, object]:
    if not source.uses_sqlite or target.uses_sqlite:
        raise RuntimeError("La copie va d’un fichier SQLite vers une base Postgres.")
    source_engine = create_database_engine(source)
    target_engine = create_database_engine(target)
    try:
        source_revision = _revision(source_engine)
        if source_revision != SCHEMA_REVISION:
            raise RuntimeError(
                f"La base SQLite est à la révision {source_revision or 'inconnue'}. "
                f"Ouvrez l’application, ou migrez-la, jusqu’à {SCHEMA_REVISION} avant la copie."
            )
        if _revision(target_engine) != SCHEMA_REVISION:
            raise RuntimeError(f"La base Postgres doit déjà être migrée jusqu’à {SCHEMA_REVISION}.")
        with (
            source_engine.connect() as source_connection,
            target_engine.begin() as target_connection,
        ):
            occupied = _dossier_rows(target_connection)
            if occupied and not replace:
                raise RuntimeError(
                    "La base Postgres contient déjà un dossier "
                    f"({occupied} ligne(s) d’activité, d’exercice ou d’écriture). "
                    "Relancez avec --replace pour la remplacer."
                )
            copied = _replace_rows(source_connection, target_connection)
            _reset_identities(target_connection)
            report = _compare(source_connection, target_connection)
        report["rows"] = copied
        return report
    finally:
        source_engine.dispose()
        target_engine.dispose()


def _revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        if "alembic_version" not in set(inspect(connection).get_table_names()):
            return None
        value = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return None if value is None else str(value)


def _dossier_rows(connection: Connection) -> int:
    total = 0
    for name in _DOSSIER_TABLES:
        table = Base.metadata.tables[name]
        total += int(connection.execute(select(func.count()).select_from(table)).scalar_one())
    return total


def _replace_rows(source: Connection, target: Connection) -> int:
    tables = list(Base.metadata.sorted_tables)
    for table in tables:
        _triggers(target, table, enabled=False)
    copied = 0
    try:
        for table in reversed(tables):
            target.execute(table.delete())
        for table in tables:
            rows = [dict(row) for row in source.execute(table.select()).mappings()]
            if not rows:
                continue
            primary_key = [column.name for column in table.primary_key.columns]
            if primary_key:
                rows.sort(key=lambda row: tuple(row[column] for column in primary_key))
            target.execute(table.insert(), rows)
            copied += len(rows)
    finally:
        for table in tables:
            _triggers(target, table, enabled=True)
    return copied


def _triggers(connection: Connection, table: Table, *, enabled: bool) -> None:
    state = "ENABLE" if enabled else "DISABLE"
    # Identifier is checked by _quote; ALTER TABLE cannot bind a table name.
    connection.execute(
        text(f"ALTER TABLE {_quote(table.name)} {state} TRIGGER USER")  # noqa: S608
    )


def _reset_identities(connection: Connection) -> None:
    for table in Base.metadata.sorted_tables:
        if len(table.primary_key.columns) != 1:
            continue
        column = table.primary_key.columns[0]
        sequence = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table.name, "column_name": column.name},
        ).scalar()
        if not sequence:
            continue
        highest = connection.scalar(select(func.max(column)))
        if highest is None:
            connection.execute(text("SELECT setval(:sequence, 1, false)"), {"sequence": sequence})
        else:
            connection.execute(
                text("SELECT setval(:sequence, :highest, true)"),
                {"sequence": sequence, "highest": int(highest)},
            )


def _compare(source: Connection, target: Connection) -> dict[str, object]:
    source_balances = _balances(source)
    target_balances = _balances(target)
    if source_balances != target_balances:
        raise RuntimeError(
            "Les balances validées diffèrent après la copie. "
            f"SQLite={source_balances} Postgres={target_balances}"
        )
    year_ids = [
        int(year_id)
        for year_id in source.execute(text("SELECT id FROM fiscal_year ORDER BY id")).scalars()
    ]
    fec_bytes = 0
    with Session(bind=source) as source_session, Session(bind=target) as target_session:
        for year_id in year_ids:
            source_fec = render_fec(source_session, year_id)["content"]
            target_fec = render_fec(target_session, year_id)["content"]
            if not isinstance(source_fec, bytes) or not isinstance(target_fec, bytes):
                raise RuntimeError(f"Le FEC de l’exercice {year_id} n’est pas un fichier binaire.")
            if source_fec != target_fec:
                raise RuntimeError(
                    f"Le FEC de l’exercice {year_id} diffère "
                    f"(SQLite {hashlib.sha256(source_fec).hexdigest()}, "
                    f"Postgres {hashlib.sha256(target_fec).hexdigest()})."
                )
            fec_bytes += len(source_fec)
            _same_liasse(source_session, target_session, year_id)
    return {
        "revision": SCHEMA_REVISION,
        "accounts": len(source_balances),
        "fiscal_years": len(year_ids),
        "fec_bytes": fec_bytes,
        "balances_equal": True,
        "fec_equal": True,
        "liasse_equal": True,
    }


def _same_liasse(source: Session, target: Session, year_id: int) -> None:
    source_sheet = efi_worksheet(source, year_id)
    target_sheet = efi_worksheet(target, year_id)
    for label, left, right in (
        ("json", archival_json(source_sheet)[0], archival_json(target_sheet)[0]),
        ("csv", archival_csv(source_sheet)[0], archival_csv(target_sheet)[0]),
        ("pdf", worksheet_pdf(source_sheet), worksheet_pdf(target_sheet)),
    ):
        if left != right:
            raise RuntimeError(f"La liasse {label} de l’exercice {year_id} diffère.")


def _balances(connection: Connection) -> list[tuple[str, int, int]]:
    rows = connection.execute(
        text(
            """
            SELECT l.account_number, COALESCE(SUM(l.debit), 0), COALESCE(SUM(l.credit), 0)
            FROM accounting_entry_line AS l
            JOIN accounting_entry AS e ON e.id = l.accounting_entry_id
            WHERE e.status = 'VALIDATED'
            GROUP BY l.account_number
            ORDER BY l.account_number
            """
        )
    )
    return [(str(number), int(debit), int(credit)) for number, debit, credit in rows]


def _quote(identifier: str) -> str:
    if _IDENT.fullmatch(identifier) is None:
        raise RuntimeError(f"Identifiant SQL inattendu : {identifier}")
    return f'"{identifier}"'
