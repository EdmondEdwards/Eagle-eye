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

SATELLITE_DDL = (
    """
    CREATE TABLE IF NOT EXISTS satellites_current (
      id TEXT PRIMARY KEY,
      catalog_number TEXT NOT NULL,
      satellite_name TEXT NOT NULL,
      international_designator TEXT,
      group_name TEXT,
      orbit_class TEXT,
      geom geometry(Point, 4326) NOT NULL,
      altitude_m DOUBLE PRECISION,
      velocity_kts DOUBLE PRECISION,
      tle_epoch TIMESTAMPTZ,
      source TEXT NOT NULL,
      source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
      observed_at TIMESTAMPTZ NOT NULL,
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_satellites_current_geom ON satellites_current USING GIST (geom)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_current_observed_at ON satellites_current (observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_current_catalog ON satellites_current (catalog_number)",
    """
    CREATE TABLE IF NOT EXISTS satellites_history (
      history_id BIGSERIAL PRIMARY KEY,
      entity_id TEXT NOT NULL,
      catalog_number TEXT NOT NULL,
      satellite_name TEXT NOT NULL,
      international_designator TEXT,
      group_name TEXT,
      orbit_class TEXT,
      geom geometry(Point, 4326) NOT NULL,
      altitude_m DOUBLE PRECISION,
      velocity_kts DOUBLE PRECISION,
      tle_epoch TIMESTAMPTZ,
      source TEXT NOT NULL,
      source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
      observed_at TIMESTAMPTZ NOT NULL,
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_satellites_history_entity_time ON satellites_history (entity_id, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_history_observed_at ON satellites_history (observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_history_geom ON satellites_history USING GIST (geom)",
)


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


def ensure_runtime_schema() -> None:
    with connection() as conn:
        for statement in SATELLITE_DDL:
            conn.execute(text(statement))
