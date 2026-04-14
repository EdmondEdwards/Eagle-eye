from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


async def event_loop(engine: Engine, publish: Callable[[str, dict[str, Any]], Awaitable[None]]) -> None:
    while True:
        emitted = 0
        with engine.begin() as conn:
            emitted += conn.execute(
                text(
                    """
                    INSERT INTO events (
                      event_type, category, severity, title, summary, entity_kind, entity_id, geom,
                      start_time, detected_at, status, confidence, source, source_confidence, raw_payload
                    )
                    SELECT
                      'stale_track',
                      'track-health',
                      'medium',
                      'Stale aircraft track',
                      'Aircraft telemetry has not updated within the stale threshold.',
                      'aircraft',
                      a.id,
                      a.geom,
                      a.observed_at,
                      NOW(),
                      'open',
                      0.72,
                      'system',
                      0.72,
                      jsonb_build_object('observed_at', a.observed_at)
                    FROM aircraft_current a
                    WHERE a.observed_at < NOW() - interval '15 minutes'
                      AND NOT EXISTS (
                        SELECT 1
                        FROM events e
                        WHERE e.event_type = 'stale_track'
                          AND e.entity_id = a.id
                          AND e.start_time > NOW() - interval '30 minutes'
                      )
                    """
                )
            ).rowcount or 0
            emitted += conn.execute(
                text(
                    """
                    INSERT INTO events (
                      event_type, category, severity, title, summary, entity_kind, entity_id, related_entity_kind, related_entity_id, geom,
                      start_time, detected_at, status, confidence, source, source_confidence, raw_payload
                    )
                    SELECT
                      'airspace_violation',
                      'airspace',
                      'high',
                      'Aircraft entered restricted airspace',
                      CONCAT(COALESCE(a.callsign, a.icao24), ' is inside ', o.name),
                      'aircraft',
                      a.id,
                      'airspace',
                      o.id,
                      a.geom,
                      GREATEST(a.observed_at, COALESCE(o.active_from, a.observed_at)),
                      NOW(),
                      'open',
                      0.84,
                      'system',
                      0.84,
                      jsonb_build_object('overlay_name', o.name, 'overlay_category', o.category)
                    FROM aircraft_current a
                    JOIN airspace_overlays o
                      ON o.geom IS NOT NULL
                     AND ST_Intersects(a.geom, o.geom)
                    WHERE COALESCE(o.active_to, NOW() + interval '1 hour') >= NOW()
                      AND COALESCE(o.active_from, NOW() - interval '1 hour') <= NOW()
                      AND NOT EXISTS (
                        SELECT 1
                        FROM events e
                        WHERE e.event_type = 'airspace_violation'
                          AND e.entity_id = a.id
                          AND e.related_entity_id = o.id
                          AND e.start_time > NOW() - interval '45 minutes'
                      )
                    """
                )
            ).rowcount or 0
            emitted += conn.execute(
                text(
                    """
                    INSERT INTO events (
                      event_type, category, severity, title, summary, entity_kind, entity_id, geom,
                      start_time, detected_at, status, confidence, source, source_confidence, raw_payload
                    )
                    SELECT
                      'vessel_loitering',
                      'maritime-pattern',
                      'medium',
                      'Vessel loitering detected',
                      'Recent vessel history indicates repeated movement inside a small area.',
                      'vessel',
                      h.entity_id,
                      ST_Centroid(ST_Collect(h.geom)),
                      MAX(h.observed_at),
                      NOW(),
                      'open',
                      0.69,
                      'system',
                      0.69,
                      jsonb_build_object('samples', COUNT(*))
                    FROM vessels_history h
                    WHERE h.observed_at > NOW() - interval '2 hours'
                    GROUP BY h.entity_id
                    HAVING COUNT(*) >= 6
                       AND ST_MaxDistance(ST_Collect(h.geom)::geometry, ST_Centroid(ST_Collect(h.geom))::geometry) < 0.25
                       AND NOT EXISTS (
                         SELECT 1
                         FROM events e
                         WHERE e.event_type = 'vessel_loitering'
                           AND e.entity_id = h.entity_id
                           AND e.start_time > NOW() - interval '2 hours'
                       )
                    """
                )
            ).rowcount or 0
            emitted += conn.execute(
                text(
                    """
                    INSERT INTO events (
                      event_type, category, severity, title, summary, entity_kind, entity_id, related_entity_kind, related_entity_id, geom,
                      start_time, detected_at, status, confidence, source, source_confidence, raw_payload
                    )
                    SELECT
                      'satellite_overflight',
                      'space',
                      'low',
                      'Satellite overflight window',
                      CONCAT(s.name, ' is overflying AOI ', a.name),
                      'satellite',
                      s.id,
                      'aoi',
                      a.id::text,
                      s.geom,
                      s.observed_at,
                      NOW(),
                      'open',
                      0.61,
                      'system',
                      0.61,
                      jsonb_build_object('aoi_name', a.name)
                    FROM satellites_current s
                    JOIN aois a
                      ON ST_DWithin(
                        s.geom::geography,
                        COALESCE(a.center_geom, ST_Centroid(a.geom))::geography,
                        GREATEST(COALESCE(a.radius_m, 250000.0), 250000.0)
                      )
                    WHERE NOT EXISTS (
                      SELECT 1
                      FROM events e
                      WHERE e.event_type = 'satellite_overflight'
                        AND e.entity_id = s.id
                        AND e.related_entity_id = a.id::text
                        AND e.start_time > NOW() - interval '90 minutes'
                    )
                    """
                )
            ).rowcount or 0
            conn.execute(
                text(
                    """
                    INSERT INTO relationships (
                      source_kind, source_id, target_kind, target_id, relationship_type,
                      strength, context_event_id, source, source_confidence, observed_at, raw_payload
                    )
                    SELECT
                      COALESCE(e.entity_kind, 'unknown'),
                      COALESCE(e.entity_id, e.id::text),
                      COALESCE(e.related_entity_kind, 'event'),
                      COALESCE(e.related_entity_id, e.id::text),
                      e.event_type,
                      e.confidence,
                      e.id,
                      'system',
                      e.source_confidence,
                      e.detected_at,
                      e.raw_payload
                    FROM events e
                    WHERE e.detected_at > NOW() - interval '5 minutes'
                      AND e.entity_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1
                        FROM relationships r
                        WHERE r.context_event_id = e.id
                      )
                    """
                )
            )
        if emitted:
            LOGGER.info("Event engine inserted %s new events", emitted)
            await publish("events", {"inserted": emitted})
            await publish("view.invalidate", {"scope": "events"})
        import asyncio

        await asyncio.sleep(60)
