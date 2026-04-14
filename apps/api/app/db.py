from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import get_settings

settings = get_settings()
engine: Engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SQL_ROOT = Path(__file__).resolve().parents[3] / "infra" / "sql"


def _normalize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


@contextmanager
def session():
    with engine.begin() as conn:
        yield conn


def ensure_runtime_schema() -> None:
    sql_files = sorted(SQL_ROOT.glob("*.sql"))
    with session() as conn:
        for sql_file in sql_files:
            statement = sql_file.read_text()
            conn.exec_driver_sql(statement)


def fetch_all(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        result = conn.execute(text(query), _normalize(params or {}))
        return [dict(row._mapping) for row in result]


def fetch_one(query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: dict[str, Any] | None = None) -> None:
    with session() as conn:
        conn.execute(text(query), _normalize(params or {}))


def execute_many(query: str, params: Iterable[dict[str, Any]]) -> None:
    rows = [_normalize(row) for row in params]
    if not rows:
        return
    with session() as conn:
        conn.execute(text(query), rows)


def as_json(value: Any) -> str:
    return json.dumps(value)
