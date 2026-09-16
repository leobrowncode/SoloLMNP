"""SQLite connection invariants and explicit transaction boundaries."""

import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.core.config import Settings

SCHEMA_REVISION = "0001_foundation"


def create_database_engine(settings: Settings) -> Engine:
    engine = create_engine(
        settings.database_url,
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
        connection.exec_driver_sql("BEGIN")

    return engine


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_database_engine(settings)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
