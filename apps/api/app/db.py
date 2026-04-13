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
    CREATE TABLE IF NOT EXISTS satellites_catalog (
      id TEXT PRIMARY KEY,
      norad_cat_id TEXT NOT NULL UNIQUE,
      international_designator TEXT,
      name TEXT NOT NULL,
      object_type TEXT,
      group_name TEXT,
      orbit_class TEXT,
      source TEXT NOT NULL,
      tle_line1 TEXT,
      tle_line2 TEXT,
      epoch TIMESTAMPTZ,
      inclination_deg DOUBLE PRECISION,
      eccentricity DOUBLE PRECISION,
      mean_motion DOUBLE PRECISION,
      raan_deg DOUBLE PRECISION,
      arg_perigee_deg DOUBLE PRECISION,
      mean_anomaly_deg DOUBLE PRECISION,
      bstar DOUBLE PRECISION,
      source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
      observed_at TIMESTAMPTZ NOT NULL,
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_satellites_catalog_norad ON satellites_catalog (norad_cat_id)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_catalog_group ON satellites_catalog (group_name)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_catalog_name ON satellites_catalog (name)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_catalog_epoch ON satellites_catalog (epoch DESC)",
    """
    CREATE TABLE IF NOT EXISTS satellites_current (
      id TEXT PRIMARY KEY,
      norad_cat_id TEXT NOT NULL UNIQUE,
      catalog_number TEXT,
      international_designator TEXT,
      name TEXT NOT NULL,
      satellite_name TEXT,
      object_type TEXT,
      group_name TEXT,
      orbit_class TEXT,
      source TEXT NOT NULL,
      tle_line1 TEXT,
      tle_line2 TEXT,
      epoch TIMESTAMPTZ,
      tle_epoch TIMESTAMPTZ,
      inclination_deg DOUBLE PRECISION,
      eccentricity DOUBLE PRECISION,
      mean_motion DOUBLE PRECISION,
      raan_deg DOUBLE PRECISION,
      arg_perigee_deg DOUBLE PRECISION,
      mean_anomaly_deg DOUBLE PRECISION,
      bstar DOUBLE PRECISION,
      source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
      observed_at TIMESTAMPTZ NOT NULL,
      altitude_m DOUBLE PRECISION,
      velocity_kts DOUBLE PRECISION,
      computed_lat DOUBLE PRECISION NOT NULL,
      computed_lon DOUBLE PRECISION NOT NULL,
      computed_alt_km DOUBLE PRECISION,
      computed_velocity_kms DOUBLE PRECISION,
      geom geometry(Point, 4326) NOT NULL,
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS satellites_history (
      history_id BIGSERIAL PRIMARY KEY,
      entity_id TEXT NOT NULL,
      norad_cat_id TEXT NOT NULL,
      catalog_number TEXT,
      international_designator TEXT,
      name TEXT NOT NULL,
      satellite_name TEXT,
      object_type TEXT,
      group_name TEXT,
      orbit_class TEXT,
      source TEXT NOT NULL,
      tle_line1 TEXT,
      tle_line2 TEXT,
      epoch TIMESTAMPTZ,
      tle_epoch TIMESTAMPTZ,
      inclination_deg DOUBLE PRECISION,
      eccentricity DOUBLE PRECISION,
      mean_motion DOUBLE PRECISION,
      raan_deg DOUBLE PRECISION,
      arg_perigee_deg DOUBLE PRECISION,
      mean_anomaly_deg DOUBLE PRECISION,
      bstar DOUBLE PRECISION,
      source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
      observed_at TIMESTAMPTZ NOT NULL,
      altitude_m DOUBLE PRECISION,
      velocity_kts DOUBLE PRECISION,
      computed_lat DOUBLE PRECISION NOT NULL,
      computed_lon DOUBLE PRECISION NOT NULL,
      computed_alt_km DOUBLE PRECISION,
      computed_velocity_kms DOUBLE PRECISION,
      playback_confidence DOUBLE PRECISION,
      geom geometry(Point, 4326) NOT NULL,
      source_snapshot_id UUID,
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS satellite_source_snapshots (
      snapshot_id UUID PRIMARY KEY,
      satellite_id TEXT NOT NULL,
      norad_cat_id TEXT NOT NULL,
      provider TEXT NOT NULL,
      group_name TEXT,
      payload_format TEXT NOT NULL,
      epoch TIMESTAMPTZ,
      observed_at TIMESTAMPTZ NOT NULL,
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_satellite_source_snapshots_norad_time ON satellite_source_snapshots (norad_cat_id, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellite_source_snapshots_provider_time ON satellite_source_snapshots (provider, observed_at DESC)",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS norad_cat_id TEXT",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS name TEXT",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS object_type TEXT",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS tle_line1 TEXT",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS tle_line2 TEXT",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS epoch TIMESTAMPTZ",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS inclination_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS eccentricity DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS mean_motion DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS raan_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS arg_perigee_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS mean_anomaly_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS bstar DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS computed_lat DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS computed_lon DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS computed_alt_km DOUBLE PRECISION",
    "ALTER TABLE satellites_current ADD COLUMN IF NOT EXISTS computed_velocity_kms DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS norad_cat_id TEXT",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS name TEXT",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS object_type TEXT",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS tle_line1 TEXT",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS tle_line2 TEXT",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS epoch TIMESTAMPTZ",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS inclination_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS eccentricity DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS mean_motion DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS raan_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS arg_perigee_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS mean_anomaly_deg DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS bstar DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS computed_lat DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS computed_lon DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS computed_alt_km DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS computed_velocity_kms DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS playback_confidence DOUBLE PRECISION",
    "ALTER TABLE satellites_history ADD COLUMN IF NOT EXISTS source_snapshot_id UUID",
    "CREATE INDEX IF NOT EXISTS idx_satellites_current_geom ON satellites_current USING GIST (geom)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_current_observed_at ON satellites_current (observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_current_norad ON satellites_current (norad_cat_id)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_current_group ON satellites_current (group_name)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_history_entity_time ON satellites_history (entity_id, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_history_norad_time ON satellites_history (norad_cat_id, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_history_observed_at ON satellites_history (observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_satellites_history_geom ON satellites_history USING GIST (geom)",
    """
    UPDATE satellites_current
    SET
      norad_cat_id = COALESCE(norad_cat_id, catalog_number),
      name = COALESCE(name, satellite_name),
      epoch = COALESCE(epoch, tle_epoch),
      computed_lat = COALESCE(computed_lat, ST_Y(geom)),
      computed_lon = COALESCE(computed_lon, ST_X(geom)),
      computed_alt_km = COALESCE(computed_alt_km, altitude_m / 1000.0),
      computed_velocity_kms = COALESCE(computed_velocity_kms, velocity_kts / 1943.84)
    WHERE
      norad_cat_id IS NOT NULL
      OR catalog_number IS NOT NULL
      OR name IS NOT NULL
      OR satellite_name IS NOT NULL
      OR computed_lat IS NOT NULL
      OR computed_lon IS NOT NULL
      OR computed_alt_km IS NOT NULL
      OR computed_velocity_kms IS NOT NULL
    """,
    """
    UPDATE satellites_history
    SET
      norad_cat_id = COALESCE(norad_cat_id, catalog_number),
      name = COALESCE(name, satellite_name),
      epoch = COALESCE(epoch, tle_epoch),
      computed_lat = COALESCE(computed_lat, ST_Y(geom)),
      computed_lon = COALESCE(computed_lon, ST_X(geom)),
      computed_alt_km = COALESCE(computed_alt_km, altitude_m / 1000.0),
      computed_velocity_kms = COALESCE(computed_velocity_kms, velocity_kts / 1943.84)
    WHERE
      norad_cat_id IS NOT NULL
      OR catalog_number IS NOT NULL
      OR name IS NOT NULL
      OR satellite_name IS NOT NULL
      OR computed_lat IS NOT NULL
      OR computed_lon IS NOT NULL
      OR computed_alt_km IS NOT NULL
      OR computed_velocity_kms IS NOT NULL
    """,
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
