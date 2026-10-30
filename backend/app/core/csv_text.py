"""Keep exported CSV cells from being read as spreadsheet formulas."""

import re


def safe_cell(value: str) -> str:
    if value[:1] in {"=", "+", "@", "\t", "\r"}:
        return "'" + value
    if value.startswith("-") and not re.fullmatch(r"-[\d\s\u00a0\u202f.,]+", value):
        return "'" + value
    return value
