"""JSON field lookup that compiles on SQLite and Postgres."""

from typing import Any, cast

from sqlalchemy.sql.elements import ColumnElement


def json_text(expression: Any, key: str) -> ColumnElement[str]:
    return cast(ColumnElement[str], expression[key].as_string())
