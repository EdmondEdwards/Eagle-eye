from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import create_engine, text

from source_adapters import AISStreamAdapter, FAAAirspaceAdapter, OpenSkyAdapter
from source_adapters.canonical import AirspaceOverlayRecord, AircraftSnapshot, LiveEnvelope, VesselSnapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger("eagle-eye-worker")

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
LIVE_CHANNEL = "eagle-eye:live"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
redis = Redis.from_url(REDIS_URL, decode_responses=True)


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


def persist_vessels(records: list[VesselSnapshot]) -> None:
    if not records:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO vessels_current (
                  id, mmsi, imo, vessel_name, vessel_type, flag, geom, heading_deg, speed_kts,
                  source, source_confidence, observed_at, raw_reference, raw_payload, updated_at
                )
                VALUES (
                  :id, :mmsi, :imo, :vessel_name, :vessel_type, :flag, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :heading_deg, :speed_kts, :source, :source_confidence, :observed_at, :raw_reference, CAST(:raw_payload AS jsonb), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                  mmsi = EXCLUDED.mmsi,
                  imo = EXCLUDED.imo,
                  vessel_name = EXCLUDED.vessel_name,
                  vessel_type = EXCLUDED.vessel_type,
                  flag = EXCLUDED.flag,
                  geom = EXCLUDED.geom,
                  heading_deg = EXCLUDED.heading_deg,
                  speed_kts = EXCLUDED.speed_kts,
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
                INSERT INTO vessels_history (
                  entity_id, mmsi, imo, vessel_name, vessel_type, flag, geom, heading_deg, speed_kts,
                  source, source_confidence, observed_at, raw_reference, raw_payload
                )
                VALUES (
                  :id, :mmsi, :imo, :vessel_name, :vessel_type, :flag, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                  :heading_deg, :speed_kts, :source, :source_confidence, :observed_at, :raw_reference, CAST(:raw_payload AS jsonb)
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


async def vessel_loop() -> None:
    adapter = AISStreamAdapter(os.getenv("AISSTREAM_API_KEY"))
    buffer: list[VesselSnapshot] = []
    last_flush = asyncio.get_running_loop().time()
    async for record in adapter.stream():
        buffer.append(record)
        if len(buffer) >= 200 or asyncio.get_running_loop().time() - last_flush >= 2:
            flush_batch = buffer[:]
            buffer.clear()
            persist_vessels(flush_batch)
            for item in flush_batch[:250]:
                await publish("vessel", item.to_dict())
            last_flush = asyncio.get_running_loop().time()


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
                    DELETE FROM airspace_overlays
                    WHERE active_to IS NOT NULL
                      AND active_to < (:cutoff - make_interval(days => 1))
                    """
                ),
                {"cutoff": cutoff},
            )
        LOGGER.info("Retention cleanup completed.")
        await asyncio.sleep(60 * 60)


async def main() -> None:
    await asyncio.gather(
        aircraft_loop(),
        vessel_loop(),
        airspace_loop(),
        retention_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
