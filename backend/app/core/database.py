"""SQLite and Postgres connections.

The engine belongs to a Database instance. Nothing in this module keeps a
process-wide connection. A Neon pooler host (``-pooler``) uses NullPool so the
serverless process does not hold sockets; Neon pools them. Direct Postgres,
including CI, keeps a small pool with pre-ping.
"""

import sqlite3
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, NullPool

from app.core.config import Settings

SCHEMA_REVISION = "0013_account_owner"


def create_database_engine(settings: Settings) -> Engine:
    if settings.uses_sqlite:
        return _sqlite_engine(settings.database_url)
    return _postgres_engine(settings.database_url)


def _sqlite_engine(url: str) -> Engine:
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure_connection(connection: sqlite3.Connection, record: ConnectionPoolEntry) -> None:
        # Explicit BEGIN below avoids sqlite3 legacy mode's non-transactional DDL.
        connection.isolation_level = None
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def explicit_begin(connection: Connection) -> None:
        connection.exec_driver_sql(
            "BEGIN IMMEDIATE" if connection.get_execution_options().get("sqlite_write") else "BEGIN"
        )

    return engine


def _postgres_engine(url: str) -> Engine:
    host = make_url(url).host or ""
    pooled = "-pooler" in host
    options: dict[str, Any] = {}
    connect_args: dict[str, Any] = {}
    if pooled:
        options["poolclass"] = NullPool
        # PgBouncer in transaction mode cannot reuse prepared statements.
        connect_args["prepare_threshold"] = None
    else:
        options["pool_pre_ping"] = True
        options["pool_recycle"] = 300
        options["pool_size"] = 5
        options["max_overflow"] = 0
    engine = create_engine(url, connect_args=connect_args, **options)

    @event.listens_for(engine, "connect")
    def configure_postgres(connection: Any, record: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        try:
            # SQLite date('now') is UTC. Keep CURRENT_DATE on the same clock.
            cursor.execute("SET TIME ZONE 'UTC'")
        finally:
            cursor.close()

    return engine


class Database:
    def __init__(self, settings: Settings) -> None:
        from app.core.ownership import install_ownership

        install_ownership()
        self.settings = settings
        self.engine = create_database_engine(settings)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def reopen(self) -> None:
        """Drop pooled connections and bind again. Used after an on-disk restore."""
        self.engine.dispose()
        self.engine = create_database_engine(self.settings)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
