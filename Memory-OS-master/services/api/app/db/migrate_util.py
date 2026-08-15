"""Idempotent migration helpers."""
from __future__ import annotations

from sqlalchemy import inspect


def table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def column_exists(bind, table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def index_exists(bind, name: str) -> bool:
    for table in inspect(bind).get_table_names():
        for idx in inspect(bind).get_indexes(table):
            if idx.get("name") == name:
                return True
    return False
