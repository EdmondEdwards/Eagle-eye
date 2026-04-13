from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from source_adapters.adapters import FAAAirspaceAdapter, OpenSkyAdapter
from source_adapters.canonical import (
    AirspaceOverlayRecord,
    AircraftSnapshot,
    LiveEnvelope,
    SatelliteCatalogRecord,
    SatelliteIngestResult,
    SatelliteSnapshot,
    SatelliteSourceSnapshotRecord,
)
from source_adapters.celestrak_adapter import CelesTrakSatelliteAdapter
from source_adapters.n2yo_adapter import N2YOSatelliteAdapter
from source_adapters.satellite_propagation_service import SatellitePropagationService
from source_adapters.satellite_provider import SatelliteProvider
from source_adapters.spacetrack_adapter import SpaceTrackSatelliteAdapter
from .maritime import MARITIME_DDL, maritime_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger("eagle-eye-worker")

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
LIVE_CHANNEL = "eagle-eye:live"
ENABLE_SATELLITES = os.getenv("ENABLE_SATELLITES", "true").strip().lower() in {"1", "true", "yes", "on"}
SATELLITE_DEFAULT_SOURCE = os.getenv("SATELLITE_DEFAULT_SOURCE", "celestrak").strip().lower()
CELESTRAK_GROUP = os.getenv("CELESTRAK_GROUP", "active")
SPACETRACK_USERNAME = os.getenv("SPACETRACK_USERNAME")
SPACETRACK_PASSWORD = os.getenv("SPACETRACK_PASSWORD")
N2YO_API_KEY = os.getenv("N2YO_API_KEY")
SATELLITE_PROPAGATION_INTERVAL_SECONDS = int(os.getenv("SATELLITE_PROPAGATION_INTERVAL_SECONDS", "30"))
SATELLITE_SOURCE_REFRESH_SECONDS = int(os.getenv("SATELLITE_SOURCE_REFRESH_SECONDS", str(15 * 60)))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
redis = Redis.from_url(REDIS_URL, decode_responses=True)

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


def _split_groups(raw_value: str) -> tuple[str, ...]:
    groups = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    return groups or ("active",)


def ensure_runtime_schema() -> None:
    with engine.begin() as conn:
        for statement in (*MARITIME_DDL, *SATELLITE_DDL):
            try:
                conn.execute(text(statement))
            except IntegrityError as exc:
                message = str(exc.orig)
                if "pg_type_typname_nsp_index" in message or "already exists" in message:
                    continue
                raise


def _satellite_provider() -> SatelliteProvider:
    if SATELLITE_DEFAULT_SOURCE == "spacetrack" and SPACETRACK_USERNAME and SPACETRACK_PASSWORD:
        return SpaceTrackSatelliteAdapter(SPACETRACK_USERNAME, SPACETRACK_PASSWORD)
    if SATELLITE_DEFAULT_SOURCE == "n2yo" and N2YO_API_KEY:
        return N2YOSatelliteAdapter(N2YO_API_KEY)
    return CelesTrakSatelliteAdapter(groups=_split_groups(CELESTRAK_GROUP))


def persist_aircraft(records: list[AircraftSnapshot]) -> None:
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO aircraft_current (
                  id, icao24, callsign, registration, operator, geom, altitude_m, heading_deg, velocity_kts,
                  vertical_rate, source, source_confidence, observed_at, raw_reference, raw_payload, updated_at
                )
                VALUES (
                  :id, :icao24, :callsign, :registration, :operator, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :altitude_m, :heading_deg, :velocity_kts, :vertical_rate, :source, :source_confidence,
                  :observed_at, :raw_reference, CAST(:raw_payload AS jsonb), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                  icao24 = EXCLUDED.icao24,
                  callsign = EXCLUDED.callsign,
                  registration = EXCLUDED.registration,
                  operator = EXCLUDED.operator,
                  geom = EXCLUDED.geom,
                  altitude_m = EXCLUDED.altitude_m,
                  heading_deg = EXCLUDED.heading_deg,
                  velocity_kts = EXCLUDED.velocity_kts,
                  vertical_rate = EXCLUDED.vertical_rate,
                  source = EXCLUDED.source,
                  source_confidence = EXCLUDED.source_confidence,
                  observed_at = EXCLUDED.observed_at,
                  raw_reference = EXCLUDED.raw_reference,
                  raw_payload = EXCLUDED.raw_payload,
                  updated_at = NOW()
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in records],
        )
        conn.execute(
            text(
                """
                INSERT INTO aircraft_history (
                  entity_id, icao24, callsign, registration, operator, geom, altitude_m, heading_deg,
                  velocity_kts, vertical_rate, source, source_confidence, observed_at, raw_reference, raw_payload
                )
                VALUES (
                  :id, :icao24, :callsign, :registration, :operator, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :altitude_m, :heading_deg, :velocity_kts, :vertical_rate, :source, :source_confidence,
                  :observed_at, :raw_reference, CAST(:raw_payload AS jsonb)
                )
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in records],
        )


def persist_airspace(records: list[AirspaceOverlayRecord]) -> None:
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO airspace_overlays (
                  id, source_id, name, category, geom, active_from, active_to, source,
                  source_confidence, observed_at, raw_reference, raw_payload, updated_at
                )
                VALUES (
                  :id, :source_id, :name, :category,
                  CASE WHEN :geometry IS NULL THEN NULL ELSE ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326) END,
                  :active_from, :active_to, :source, :source_confidence, :observed_at, :raw_reference,
                  CAST(:raw_payload AS jsonb), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                  source_id = EXCLUDED.source_id,
                  name = EXCLUDED.name,
                  category = EXCLUDED.category,
                  geom = EXCLUDED.geom,
                  active_from = EXCLUDED.active_from,
                  active_to = EXCLUDED.active_to,
                  source = EXCLUDED.source,
                  source_confidence = EXCLUDED.source_confidence,
                  observed_at = EXCLUDED.observed_at,
                  raw_reference = EXCLUDED.raw_reference,
                  raw_payload = EXCLUDED.raw_payload,
                  updated_at = NOW()
                """
            ),
            [
                {
                    **record.to_dict(),
                    "geometry": json.dumps(record.geometry) if record.geometry else None,
                    "raw_payload": json.dumps(record.raw_payload),
                }
                for record in records
            ],
        )


def persist_satellite_catalog(records: list[SatelliteCatalogRecord]) -> None:
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO satellites_catalog (
                  id, norad_cat_id, international_designator, name, object_type, group_name, orbit_class, source,
                  tle_line1, tle_line2, epoch, inclination_deg, eccentricity, mean_motion, raan_deg,
                  arg_perigee_deg, mean_anomaly_deg, bstar, source_confidence, observed_at, raw_reference, raw_payload, updated_at
                )
                VALUES (
                  :id, :norad_cat_id, :international_designator, :name, :object_type, :group_name, :orbit_class, :source,
                  :tle_line1, :tle_line2, :epoch, :inclination_deg, :eccentricity, :mean_motion, :raan_deg,
                  :arg_perigee_deg, :mean_anomaly_deg, :bstar, :source_confidence, :observed_at, :raw_reference, CAST(:raw_payload AS jsonb), NOW()
                )
                ON CONFLICT (norad_cat_id) DO UPDATE SET
                  id = EXCLUDED.id,
                  international_designator = EXCLUDED.international_designator,
                  name = EXCLUDED.name,
                  object_type = EXCLUDED.object_type,
                  group_name = EXCLUDED.group_name,
                  orbit_class = EXCLUDED.orbit_class,
                  source = EXCLUDED.source,
                  tle_line1 = EXCLUDED.tle_line1,
                  tle_line2 = EXCLUDED.tle_line2,
                  epoch = EXCLUDED.epoch,
                  inclination_deg = EXCLUDED.inclination_deg,
                  eccentricity = EXCLUDED.eccentricity,
                  mean_motion = EXCLUDED.mean_motion,
                  raan_deg = EXCLUDED.raan_deg,
                  arg_perigee_deg = EXCLUDED.arg_perigee_deg,
                  mean_anomaly_deg = EXCLUDED.mean_anomaly_deg,
                  bstar = EXCLUDED.bstar,
                  source_confidence = EXCLUDED.source_confidence,
                  observed_at = EXCLUDED.observed_at,
                  raw_reference = EXCLUDED.raw_reference,
                  raw_payload = EXCLUDED.raw_payload,
                  updated_at = NOW()
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in records],
        )


def persist_satellite_source_snapshots(records: list[SatelliteSourceSnapshotRecord]) -> None:
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO satellite_source_snapshots (
                  snapshot_id, satellite_id, norad_cat_id, provider, group_name, payload_format, epoch,
                  observed_at, raw_reference, raw_payload
                )
                VALUES (
                  :snapshot_id, :satellite_id, :norad_cat_id, :provider, :group_name, :payload_format, :epoch,
                  :observed_at, :raw_reference, CAST(:raw_payload AS jsonb)
                )
                ON CONFLICT (snapshot_id) DO NOTHING
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in records],
        )


def persist_satellites(records: list[SatelliteSnapshot]) -> None:
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO satellites_current (
                  id, norad_cat_id, catalog_number, international_designator, name, satellite_name, object_type, group_name, orbit_class, source,
                  tle_line1, tle_line2, epoch, tle_epoch, inclination_deg, eccentricity, mean_motion, raan_deg, arg_perigee_deg,
                  mean_anomaly_deg, bstar, source_confidence, observed_at, altitude_m, velocity_kts,
                  computed_lat, computed_lon, computed_alt_km, computed_velocity_kms, geom, raw_reference, raw_payload, updated_at
                )
                VALUES (
                  :id, :norad_cat_id, :norad_cat_id, :international_designator, :name, :name, :object_type, :group_name, :orbit_class, :source,
                  :tle_line1, :tle_line2, :epoch, :epoch, :inclination_deg, :eccentricity, :mean_motion, :raan_deg, :arg_perigee_deg,
                  :mean_anomaly_deg, :bstar, :source_confidence, :observed_at,
                  CASE WHEN :computed_alt_km IS NULL THEN NULL ELSE :computed_alt_km * 1000.0 END,
                  CASE WHEN :computed_velocity_kms IS NULL THEN NULL ELSE :computed_velocity_kms * 1943.84 END,
                  :computed_lat, :computed_lon, :computed_alt_km, :computed_velocity_kms,
                  ST_SetSRID(ST_MakePoint(:computed_lon, :computed_lat), 4326),
                  :raw_reference, CAST(:raw_payload AS jsonb), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                  norad_cat_id = EXCLUDED.norad_cat_id,
                  catalog_number = EXCLUDED.catalog_number,
                  international_designator = EXCLUDED.international_designator,
                  name = EXCLUDED.name,
                  satellite_name = EXCLUDED.satellite_name,
                  object_type = EXCLUDED.object_type,
                  group_name = EXCLUDED.group_name,
                  orbit_class = EXCLUDED.orbit_class,
                  source = EXCLUDED.source,
                  tle_line1 = EXCLUDED.tle_line1,
                  tle_line2 = EXCLUDED.tle_line2,
                  epoch = EXCLUDED.epoch,
                  tle_epoch = EXCLUDED.tle_epoch,
                  inclination_deg = EXCLUDED.inclination_deg,
                  eccentricity = EXCLUDED.eccentricity,
                  mean_motion = EXCLUDED.mean_motion,
                  raan_deg = EXCLUDED.raan_deg,
                  arg_perigee_deg = EXCLUDED.arg_perigee_deg,
                  mean_anomaly_deg = EXCLUDED.mean_anomaly_deg,
                  bstar = EXCLUDED.bstar,
                  source_confidence = EXCLUDED.source_confidence,
                  observed_at = EXCLUDED.observed_at,
                  altitude_m = EXCLUDED.altitude_m,
                  velocity_kts = EXCLUDED.velocity_kts,
                  computed_lat = EXCLUDED.computed_lat,
                  computed_lon = EXCLUDED.computed_lon,
                  computed_alt_km = EXCLUDED.computed_alt_km,
                  computed_velocity_kms = EXCLUDED.computed_velocity_kms,
                  geom = EXCLUDED.geom,
                  raw_reference = EXCLUDED.raw_reference,
                  raw_payload = EXCLUDED.raw_payload,
                  updated_at = NOW()
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in records],
        )
        conn.execute(
            text(
                """
                INSERT INTO satellites_history (
                  entity_id, norad_cat_id, catalog_number, international_designator, name, satellite_name, object_type, group_name, orbit_class, source,
                  tle_line1, tle_line2, epoch, tle_epoch, inclination_deg, eccentricity, mean_motion, raan_deg, arg_perigee_deg,
                  mean_anomaly_deg, bstar, source_confidence, observed_at, altitude_m, velocity_kts,
                  computed_lat, computed_lon, computed_alt_km, computed_velocity_kms, playback_confidence, geom, raw_reference, raw_payload
                )
                VALUES (
                  :id, :norad_cat_id, :norad_cat_id, :international_designator, :name, :name, :object_type, :group_name, :orbit_class, :source,
                  :tle_line1, :tle_line2, :epoch, :epoch, :inclination_deg, :eccentricity, :mean_motion, :raan_deg, :arg_perigee_deg,
                  :mean_anomaly_deg, :bstar, :source_confidence, :observed_at,
                  CASE WHEN :computed_alt_km IS NULL THEN NULL ELSE :computed_alt_km * 1000.0 END,
                  CASE WHEN :computed_velocity_kms IS NULL THEN NULL ELSE :computed_velocity_kms * 1943.84 END,
                  :computed_lat, :computed_lon, :computed_alt_km, :computed_velocity_kms, :playback_confidence,
                  ST_SetSRID(ST_MakePoint(:computed_lon, :computed_lat), 4326),
                  :raw_reference, CAST(:raw_payload AS jsonb)
                )
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in records],
        )


async def publish(topic: str, payload: dict[str, Any]) -> None:
    envelope = LiveEnvelope(topic=topic, action="upsert", payload=payload)
    await redis.publish(LIVE_CHANNEL, json.dumps(envelope.to_dict(), default=str))


async def aircraft_loop() -> None:
    adapter = OpenSkyAdapter(os.getenv("OPENSKY_CLIENT_ID"), os.getenv("OPENSKY_CLIENT_SECRET"))
    backoff = 15
    while True:
        try:
            records = await adapter.poll()
            persist_aircraft(records)
            for record in records[:250]:
                await publish("aircraft", record.to_dict())
            LOGGER.info("OpenSky cycle persisted %s aircraft", len(records))
            backoff = 15
            await asyncio.sleep(30)
        except Exception as exc:  # pragma: no cover - network recovery path
            LOGGER.warning("OpenSky poll failed: %s", exc)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


async def airspace_loop() -> None:
    adapter = FAAAirspaceAdapter()
    while True:
        try:
            records = await adapter.fetch_active()
            persist_airspace(records)
            for record in records:
                await publish("airspace", record.to_dict())
            LOGGER.info("FAA cycle persisted %s overlays", len(records))
        except Exception as exc:  # pragma: no cover - network recovery path
            LOGGER.warning("FAA ingest failed: %s", exc)
        await asyncio.sleep(20 * 60)


async def satellite_loop() -> None:
    if not ENABLE_SATELLITES:
        LOGGER.info("Satellite ingest disabled via ENABLE_SATELLITES=false.")
        while True:
            await asyncio.sleep(300)

    provider = _satellite_provider()
    propagation = SatellitePropagationService()
    catalog_records: list[SatelliteCatalogRecord] = []
    last_refresh_at: datetime | None = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            should_refresh_catalog = (
                not catalog_records
                or last_refresh_at is None
                or (now - last_refresh_at).total_seconds() >= SATELLITE_SOURCE_REFRESH_SECONDS
            )

            if should_refresh_catalog:
                ingest_result: SatelliteIngestResult = await provider.fetch_catalog()
                if ingest_result.catalog_records:
                    catalog_records = ingest_result.catalog_records
                    last_refresh_at = ingest_result.observed_at
                    persist_satellite_catalog(ingest_result.catalog_records)
                    persist_satellite_source_snapshots(ingest_result.source_snapshots)
                    LOGGER.info(
                        "%s refreshed %s catalog records across groups=%s",
                        provider.provider_name,
                        len(ingest_result.catalog_records),
                        ",".join(sorted({record.group_name or "unknown" for record in ingest_result.catalog_records})),
                    )
                else:
                    LOGGER.warning("%s refresh returned no catalog records; retaining previous cache.", provider.provider_name)

            if catalog_records:
                observed_at = datetime.now(timezone.utc)
                current_records = propagation.propagate_many(
                    catalog_records,
                    observed_at,
                    observed_at=observed_at,
                )
                persist_satellites(current_records)
                for record in current_records[:300]:
                    await publish("satellite", record.to_dict())
                LOGGER.info("%s cycle persisted %s propagated satellites", provider.provider_name, len(current_records))
            else:
                LOGGER.warning("Satellite catalog cache is empty; current propagation skipped.")
        except Exception as exc:  # pragma: no cover - network recovery path
            LOGGER.warning("Satellite ingest failed: %s", exc)
        await asyncio.sleep(SATELLITE_PROPAGATION_INTERVAL_SECONDS)


async def retention_loop() -> None:
    while True:
        cutoff = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    DELETE FROM aircraft_history
                    WHERE observed_at < (:cutoff - (:retention_days || ' days')::interval)
                    """
                ),
                {"cutoff": cutoff, "retention_days": RETENTION_DAYS},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM vessels_history
                    WHERE observed_at < (:cutoff - (:retention_days || ' days')::interval)
                    """
                ),
                {"cutoff": cutoff, "retention_days": RETENTION_DAYS},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM vessel_source_snapshots
                    WHERE observed_at < (:cutoff - (:retention_days || ' days')::interval)
                    """
                ),
                {"cutoff": cutoff, "retention_days": RETENTION_DAYS},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM vessel_presence_overlays
                    WHERE observed_to < (:cutoff - (:retention_days || ' days')::interval)
                    """
                ),
                {"cutoff": cutoff, "retention_days": RETENTION_DAYS},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM airspace_overlays
                    WHERE active_to IS NOT NULL
                      AND active_to < (:cutoff - make_interval(days => 1))
                    """
                ),
                {"cutoff": cutoff},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM satellites_history
                    WHERE observed_at < (:cutoff - (:retention_days || ' days')::interval)
                    """
                ),
                {"cutoff": cutoff, "retention_days": RETENTION_DAYS},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM satellite_source_snapshots
                    WHERE observed_at < (:cutoff - (:retention_days || ' days')::interval)
                    """
                ),
                {"cutoff": cutoff, "retention_days": RETENTION_DAYS},
            )
        LOGGER.info("Retention cleanup completed.")
        await asyncio.sleep(60 * 60)


async def main() -> None:
    ensure_runtime_schema()
    await asyncio.gather(
        aircraft_loop(),
        maritime_loop(engine, publish),
        satellite_loop(),
        airspace_loop(),
        retention_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
