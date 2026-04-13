from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from source_adapters.aisstream_provider import AISStreamProvider
from source_adapters.aishub_provider import AISHubProvider
from source_adapters.canonical import MaritimeProviderDescriptor, VesselPresenceOverlayRecord, VesselSnapshot, VesselSourceHealthRecord, VesselSourceSnapshotRecord
from source_adapters.gfw_provider import GlobalFishingWatchProvider
from source_adapters.maritime_fusion import merge_vessel_records

LOGGER = logging.getLogger(__name__)

MARITIME_DDL = (
    """
    ALTER TABLE vessels_current
    ADD COLUMN IF NOT EXISTS callsign TEXT,
    ADD COLUMN IF NOT EXISTS course_deg DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS nav_status TEXT,
    ADD COLUMN IF NOT EXISTS destination TEXT,
    ADD COLUMN IF NOT EXISTS draught_m DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS source_record_id TEXT,
    ADD COLUMN IF NOT EXISTS merged_confidence DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS last_ingested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS stale BOOLEAN NOT NULL DEFAULT FALSE
    """,
    """
    ALTER TABLE vessels_history
    ADD COLUMN IF NOT EXISTS callsign TEXT,
    ADD COLUMN IF NOT EXISTS course_deg DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS nav_status TEXT,
    ADD COLUMN IF NOT EXISTS destination TEXT,
    ADD COLUMN IF NOT EXISTS draught_m DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS source_record_id TEXT,
    ADD COLUMN IF NOT EXISTS merged_confidence DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS last_ingested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS stale BOOLEAN NOT NULL DEFAULT FALSE
    """,
    """
    CREATE TABLE IF NOT EXISTS vessel_source_health (
      provider_name TEXT PRIMARY KEY,
      ingest_mode TEXT NOT NULL,
      enabled BOOLEAN NOT NULL DEFAULT TRUE,
      priority INTEGER NOT NULL DEFAULT 0,
      health_state TEXT NOT NULL,
      last_success TIMESTAMPTZ,
      last_attempt TIMESTAMPTZ,
      valid_message_count INTEGER NOT NULL DEFAULT 0,
      error_count INTEGER NOT NULL DEFAULT 0,
      stall_threshold_seconds INTEGER,
      last_error TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vessel_source_snapshots (
      snapshot_id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      source_record_id TEXT,
      mmsi TEXT,
      imo TEXT,
      vessel_name TEXT,
      observed_at TIMESTAMPTZ NOT NULL,
      ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      parse_error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vessel_presence_overlays (
      overlay_id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      dataset TEXT NOT NULL,
      label TEXT NOT NULL,
      category TEXT NOT NULL,
      geom geometry(Geometry, 4326) NOT NULL,
      density DOUBLE PRECISION,
      observed_from TIMESTAMPTZ NOT NULL,
      observed_to TIMESTAMPTZ NOT NULL,
      source TEXT NOT NULL,
      source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
      observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      raw_reference TEXT,
      raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_vessel_source_health_state ON vessel_source_health (health_state, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_vessel_source_snapshots_mmsi_time ON vessel_source_snapshots (mmsi, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_vessel_source_snapshots_provider_time ON vessel_source_snapshots (provider, ingested_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_vessel_presence_overlays_geom ON vessel_presence_overlays USING GIST (geom)",
    "CREATE INDEX IF NOT EXISTS idx_vessel_presence_overlays_window ON vessel_presence_overlays (observed_from DESC, observed_to DESC)",
    "CREATE INDEX IF NOT EXISTS idx_vessels_current_imo ON vessels_current (imo)",
    "CREATE INDEX IF NOT EXISTS idx_vessels_current_source ON vessels_current (source, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_vessels_current_flag ON vessels_current (flag)",
    "CREATE INDEX IF NOT EXISTS idx_vessels_current_type ON vessels_current (vessel_type)",
    "CREATE INDEX IF NOT EXISTS idx_vessels_history_mmsi_time ON vessels_history (mmsi, observed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_vessels_history_source ON vessels_history (source, observed_at DESC)",
)


def _parse_json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        LOGGER.warning("%s contains invalid JSON; using fallback.", name)
        return default


def provider_descriptors() -> list[MaritimeProviderDescriptor]:
    return [
        AISStreamProvider(
            api_key=os.getenv("AISSTREAM_API_KEY"),
            enabled=os.getenv("ENABLE_AISSTREAM", "true").strip().lower() in {"1", "true", "yes", "on"},
            bounding_boxes=_parse_json_env("AISSTREAM_BOUNDING_BOXES_JSON", [[[-90, -180], [90, 180]]]),
            filter_message_types=_parse_json_env("AISSTREAM_FILTER_MESSAGE_TYPES_JSON", []),
            stall_threshold_seconds=int(os.getenv("AISSTREAM_STALL_THRESHOLD_SECONDS", "90")),
        ).descriptor(),
        AISHubProvider(
            enabled=os.getenv("ENABLE_AISHUB", "false").strip().lower() in {"1", "true", "yes", "on"},
            username=os.getenv("AISHUB_USERNAME"),
            password=os.getenv("AISHUB_PASSWORD"),
            poll_interval_seconds=int(os.getenv("AISHUB_POLL_INTERVAL_SECONDS", "60")),
            bounding_boxes=_parse_json_env("AISSTREAM_BOUNDING_BOXES_JSON", [[[-90, -180], [90, 180]]]),
        ).descriptor(),
        GlobalFishingWatchProvider(
            enabled=os.getenv("ENABLE_GFW", "false").strip().lower() in {"1", "true", "yes", "on"},
            api_token=os.getenv("GFW_API_TOKEN"),
            poll_interval_seconds=int(os.getenv("GFW_POLL_INTERVAL_SECONDS", "3600")),
        ).descriptor(),
    ]


def persist_vessels(engine: Engine, records: list[VesselSnapshot]) -> None:
    if not records:
        return
    fused_records = merge_vessel_records(records)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO vessels_current (
                  id, mmsi, imo, vessel_name, callsign, vessel_type, flag, geom, heading_deg, course_deg,
                  speed_kts, nav_status, destination, draught_m, source, source_record_id, source_confidence,
                  merged_confidence, observed_at, last_ingested_at, stale, raw_reference, raw_payload, updated_at
                )
                VALUES (
                  :id, :mmsi, :imo, :vessel_name, :callsign, :vessel_type, :flag, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :heading_deg, :course_deg, :speed_kts, :nav_status, :destination, :draught_m, :source, :source_record_id,
                  :source_confidence, :merged_confidence, :observed_at, :last_ingested_at, :stale, :raw_reference,
                  CAST(:raw_payload AS jsonb), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                  mmsi = EXCLUDED.mmsi,
                  imo = EXCLUDED.imo,
                  vessel_name = EXCLUDED.vessel_name,
                  callsign = EXCLUDED.callsign,
                  vessel_type = EXCLUDED.vessel_type,
                  flag = EXCLUDED.flag,
                  geom = EXCLUDED.geom,
                  heading_deg = EXCLUDED.heading_deg,
                  course_deg = EXCLUDED.course_deg,
                  speed_kts = EXCLUDED.speed_kts,
                  nav_status = EXCLUDED.nav_status,
                  destination = EXCLUDED.destination,
                  draught_m = EXCLUDED.draught_m,
                  source = EXCLUDED.source,
                  source_record_id = EXCLUDED.source_record_id,
                  source_confidence = EXCLUDED.source_confidence,
                  merged_confidence = EXCLUDED.merged_confidence,
                  observed_at = EXCLUDED.observed_at,
                  last_ingested_at = EXCLUDED.last_ingested_at,
                  stale = EXCLUDED.stale,
                  raw_reference = EXCLUDED.raw_reference,
                  raw_payload = EXCLUDED.raw_payload,
                  updated_at = NOW()
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in fused_records],
        )
        conn.execute(
            text(
                """
                INSERT INTO vessels_history (
                  entity_id, mmsi, imo, vessel_name, callsign, vessel_type, flag, geom, heading_deg, course_deg,
                  speed_kts, nav_status, destination, draught_m, source, source_record_id, source_confidence,
                  merged_confidence, observed_at, last_ingested_at, stale, raw_reference, raw_payload
                )
                VALUES (
                  :id, :mmsi, :imo, :vessel_name, :callsign, :vessel_type, :flag, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :heading_deg, :course_deg, :speed_kts, :nav_status, :destination, :draught_m, :source, :source_record_id,
                  :source_confidence, :merged_confidence, :observed_at, :last_ingested_at, :stale, :raw_reference, CAST(:raw_payload AS jsonb)
                )
                """
            ),
            [{**record.to_dict(), "raw_payload": json.dumps(record.raw_payload)} for record in fused_records],
        )


def persist_source_snapshots(engine: Engine, snapshots: list[VesselSourceSnapshotRecord]) -> None:
    if not snapshots:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO vessel_source_snapshots (
                  snapshot_id, provider, source_record_id, mmsi, imo, vessel_name, observed_at,
                  ingested_at, raw_reference, raw_payload, parse_error
                )
                VALUES (
                  :snapshot_id, :provider, :source_record_id, :mmsi, :imo, :vessel_name, :observed_at,
                  :ingested_at, :raw_reference, CAST(:raw_payload AS jsonb), :parse_error
                )
                ON CONFLICT (snapshot_id) DO NOTHING
                """
            ),
            [{**snapshot.to_dict(), "raw_payload": json.dumps(snapshot.raw_payload)} for snapshot in snapshots],
        )


def persist_source_health(engine: Engine, records: list[VesselSourceHealthRecord]) -> None:
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO vessel_source_health (
                  provider_name, ingest_mode, enabled, priority, health_state, last_success, last_attempt,
                  valid_message_count, error_count, stall_threshold_seconds, last_error, updated_at
                )
                VALUES (
                  :provider_name, :ingest_mode, :enabled, :priority, :health_state, :last_success, :last_attempt,
                  :valid_message_count, :error_count, :stall_threshold_seconds, :last_error, :updated_at
                )
                ON CONFLICT (provider_name) DO UPDATE SET
                  ingest_mode = EXCLUDED.ingest_mode,
                  enabled = EXCLUDED.enabled,
                  priority = EXCLUDED.priority,
                  health_state = EXCLUDED.health_state,
                  last_success = EXCLUDED.last_success,
                  last_attempt = EXCLUDED.last_attempt,
                  valid_message_count = EXCLUDED.valid_message_count,
                  error_count = EXCLUDED.error_count,
                  stall_threshold_seconds = EXCLUDED.stall_threshold_seconds,
                  last_error = EXCLUDED.last_error,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            [record.to_dict() for record in records],
        )


def persist_presence_overlays(engine: Engine, overlays: list[VesselPresenceOverlayRecord]) -> None:
    if not overlays:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO vessel_presence_overlays (
                  overlay_id, provider, dataset, label, category, geom, density, observed_from, observed_to,
                  source, source_confidence, observed_at, raw_reference, raw_payload, updated_at
                )
                VALUES (
                  :overlay_id, :provider, :dataset, :label, :category,
                  ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326),
                  :density, :observed_from, :observed_to, :provider, :source_confidence, :observed_to,
                  :raw_reference, CAST(:raw_payload AS jsonb), NOW()
                )
                ON CONFLICT (overlay_id) DO UPDATE SET
                  provider = EXCLUDED.provider,
                  dataset = EXCLUDED.dataset,
                  label = EXCLUDED.label,
                  category = EXCLUDED.category,
                  geom = EXCLUDED.geom,
                  density = EXCLUDED.density,
                  observed_from = EXCLUDED.observed_from,
                  observed_to = EXCLUDED.observed_to,
                  source = EXCLUDED.source,
                  source_confidence = EXCLUDED.source_confidence,
                  observed_at = EXCLUDED.observed_at,
                  raw_reference = EXCLUDED.raw_reference,
                  raw_payload = EXCLUDED.raw_payload,
                  updated_at = NOW()
                """
            ),
            [{**overlay.to_dict(), "geometry": json.dumps(overlay.geometry), "raw_payload": json.dumps(overlay.raw_payload)} for overlay in overlays],
        )


def provider_health_summary(providers: list[Any]) -> list[VesselSourceHealthRecord]:
    return [provider.health_snapshot() for provider in providers]


async def maritime_loop(engine: Engine, publish: Callable[[str, dict[str, Any]], asyncio.Future]) -> None:
    providers = [
        AISStreamProvider(
            api_key=os.getenv("AISSTREAM_API_KEY"),
            enabled=os.getenv("ENABLE_AISSTREAM", "true").strip().lower() in {"1", "true", "yes", "on"},
            bounding_boxes=_parse_json_env("AISSTREAM_BOUNDING_BOXES_JSON", [[[-90, -180], [90, 180]]]),
            filter_message_types=_parse_json_env("AISSTREAM_FILTER_MESSAGE_TYPES_JSON", []),
            stall_threshold_seconds=int(os.getenv("AISSTREAM_STALL_THRESHOLD_SECONDS", "90")),
        ),
        AISHubProvider(
            enabled=os.getenv("ENABLE_AISHUB", "false").strip().lower() in {"1", "true", "yes", "on"},
            username=os.getenv("AISHUB_USERNAME"),
            password=os.getenv("AISHUB_PASSWORD"),
            poll_interval_seconds=int(os.getenv("AISHUB_POLL_INTERVAL_SECONDS", "60")),
            bounding_boxes=_parse_json_env("AISSTREAM_BOUNDING_BOXES_JSON", [[[-90, -180], [90, 180]]]),
        ),
        GlobalFishingWatchProvider(
            enabled=os.getenv("ENABLE_GFW", "false").strip().lower() in {"1", "true", "yes", "on"},
            api_token=os.getenv("GFW_API_TOKEN"),
            poll_interval_seconds=int(os.getenv("GFW_POLL_INTERVAL_SECONDS", "3600")),
        ),
    ]

    async def publish_health() -> None:
        health_rows = provider_health_summary(providers)
        persist_source_health(engine, health_rows)
        await publish(
            "vessel.source-health",
            {"providers": [row.to_dict() for row in health_rows]},
        )

    async def consume_aisstream(provider: AISStreamProvider) -> None:
        async for record, snapshot in provider.stream_records():
            if snapshot is not None:
                persist_source_snapshots(engine, [snapshot])
            if record is None:
                await publish_health()
                continue
            persist_vessels(engine, [record])
            await publish("vessel", record.to_dict())
            await publish_health()

    async def poll_aishub(provider: AISHubProvider) -> None:
        while True:
            records, snapshots = await provider.poll_records()
            persist_source_snapshots(engine, snapshots)
            if records:
                persist_vessels(engine, records)
                for record in records[:250]:
                    await publish("vessel", record.to_dict())
            await publish_health()
            await asyncio.sleep(provider.poll_interval_seconds)

    async def poll_gfw(provider: GlobalFishingWatchProvider) -> None:
        while True:
            overlays = await provider.poll_presence_overlay()
            if overlays:
                persist_presence_overlays(engine, overlays)
            await publish_health()
            await asyncio.sleep(provider.poll_interval_seconds)

    tasks = [asyncio.create_task(consume_aisstream(providers[0]))]
    if providers[1].enabled:
        tasks.append(asyncio.create_task(poll_aishub(providers[1])))
    if providers[2].enabled:
        tasks.append(asyncio.create_task(poll_gfw(providers[2])))
    await publish_health()
    await asyncio.gather(*tasks)
