from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import get_settings

settings = get_settings()
engine: Engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def row_to_dict(row: Any) -> dict[str, Any]:
    return {key: _normalize_value(value) for key, value in row._mapping.items()}


@contextmanager
def connection():
    with engine.begin() as conn:
        yield conn


def fetch_all(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        result = conn.execute(text(query), params or {})
        return [row_to_dict(row) for row in result]


def fetch_one(query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: dict[str, Any] | None = None) -> None:
    with connection() as conn:
        conn.execute(text(query), params or {})


def execute_many(query: str, payloads: Iterable[dict[str, Any]]) -> None:
    payload_list = list(payloads)
    if not payload_list:
        return
    with connection() as conn:
        conn.execute(text(query), payload_list)

