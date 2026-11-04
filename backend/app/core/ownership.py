"""Bind a session to one account and hide every other account's rows.

Chart accounts and journals stay shared: their primary keys are the numbers
of the French chart. Every other mapped row carries owner_id.
"""

from __future__ import annotations

from sqlalchemy import event, select, text
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.core.auth import Principal
from app.core.database import Database
from app.models.account import AppAccount
from app.models.base import Owned
from app.models.foundation import RentalActivity

_OWNER_LOCK = 119_002
_INSTALLED = False


def install_ownership() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    event.listen(Session, "do_orm_execute", _filter_owned_rows)
    event.listen(Session, "before_flush", _stamp_owner)


def _filter_owned_rows(execute_state: ORMExecuteState) -> None:
    if not execute_state.is_select:
        return
    # session.get() is a primary-key load. It must still hide other accounts.
    if execute_state.is_relationship_load:
        return
    owner_id = execute_state.session.info.get("owner_id")
    if type(owner_id) is not int:
        return

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            Owned,
            lambda cls: cls.owner_id == owner_id,  # noqa: B023
            include_aliases=True,
        )
    )


def _stamp_owner(session: Session, flush_context: object, instances: object) -> None:
    del flush_context, instances
    owner_id = session.info.get("owner_id")
    if type(owner_id) is not int:
        return
    pending = [obj for obj in session.new if isinstance(obj, Owned)]
    for obj in pending:
        if obj.owner_id is None:
            obj.owner_id = owner_id


def resolve_owner_id(database: Database, principal: Principal) -> int:
    with database.sessions() as session:
        found = session.scalar(select(AppAccount.id).where(AppAccount.subject == principal.subject))
        if found is not None:
            return int(found)
    with database.engine.connect().execution_options(sqlite_write=True) as connection:
        with connection.begin(), Session(bind=connection, expire_on_commit=False) as session:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _OWNER_LOCK})
            existing = session.scalar(
                select(AppAccount).where(AppAccount.subject == principal.subject)
            )
            if existing is not None:
                if existing.email != principal.email:
                    existing.email = principal.email
                session.flush()
                return existing.id
            legacy = session.scalar(
                select(AppAccount)
                .where(AppAccount.subject.is_(None))
                .order_by(AppAccount.id)
                .limit(1)
            )
            if legacy is not None:
                legacy.subject = principal.subject
                legacy.email = principal.email
                session.flush()
                return legacy.id
            row = AppAccount(subject=principal.subject, email=principal.email)
            session.add(row)
            session.flush()
            return row.id


def claimed_accounts(database: Database) -> int:
    with database.engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM app_account WHERE subject IS NOT NULL")
        ).scalar_one()
    return int(count)


def owned_activity(session: Session) -> RentalActivity | None:
    owner_id = session.info.get("owner_id")
    statement = select(RentalActivity).order_by(RentalActivity.id)
    if type(owner_id) is int:
        statement = statement.where(RentalActivity.owner_id == owner_id)
    return session.scalars(statement.limit(1)).first()
