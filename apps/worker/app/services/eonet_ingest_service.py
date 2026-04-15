from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..providers.eonet_adapter import EONETAdapter, EONETEventPayload
from .hazard_event_normalizer import json_dumps, normalize_eonet_event, utc


@dataclass(slots=True)
class EONETIngestResult:
    fetched: int
    normalized: int
    status: str


class EONETIngestService:
    def __init__(self, engine: Engine, adapter: EONETAdapter) -> None:
        self.engine = engine
        self.adapter = adapter

    async def run_once(
        self,
        *,
        default_status: str,
        default_days: int,
        historical_backfill_start: datetime | None = None,
    ) -> EONETIngestResult:
        rows = await self.adapter.fetch_events(
            status=default_status,
            days=default_days,
            start=historical_backfill_start,
        )
        normalized = 0
        with self.engine.begin() as conn:
            for event in rows:
                self._upsert_native(conn, event)
                normalized += self._upsert_normalized(conn, event)
            _upsert_health(
                conn,
                source_key="eonet",
                label="NASA EONET",
                source_type="event",
                status="healthy",
                item_count=len(rows),
                details={"default_status": default_status, "default_days": default_days},
            )
        return EONETIngestResult(fetched=len(rows), normalized=normalized, status="healthy")

    def _upsert_native(self, conn: Any, event: EONETEventPayload) -> None:
        conn.execute(
            text(
                """
                INSERT INTO eonet_events (
                  eonet_event_id, title, description, link, status, categories_json, sources_json,
                  closed_at, first_seen_at, last_seen_at, raw_event_json, updated_at
                )
                VALUES (
                  :event_id, :title, :description, :link, :status, CAST(:categories_json AS jsonb), CAST(:sources_json AS jsonb),
                  :closed_at, NOW(), NOW(), CAST(:raw_event_json AS jsonb), NOW()
                )
                ON CONFLICT (eonet_event_id) DO UPDATE
                SET title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    link = EXCLUDED.link,
                    status = EXCLUDED.status,
                    categories_json = EXCLUDED.categories_json,
                    sources_json = EXCLUDED.sources_json,
                    closed_at = EXCLUDED.closed_at,
                    last_seen_at = NOW(),
                    raw_event_json = EXCLUDED.raw_event_json,
                    updated_at = NOW()
                """
            ),
            {
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "link": event.link,
                "status": event.status.lower(),
                "categories_json": json_dumps(event.categories),
                "sources_json": json_dumps(event.sources),
                "closed_at": utc(event.closed_at),
                "raw_event_json": json_dumps(event.raw),
            },
        )
        for geometry in event.geometries:
            if not geometry.geometry:
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO eonet_event_geometry (eonet_event_id, geometry_type, event_time, geometry)
                    SELECT :event_id, :geometry_type, :event_time, ST_SetSRID(ST_GeomFromGeoJSON(:geometry_geojson), 4326)
                    WHERE NOT EXISTS (
                      SELECT 1
                      FROM eonet_event_geometry
                      WHERE eonet_event_id = :event_id
                        AND COALESCE(event_time, TIMESTAMPTZ 'epoch') = COALESCE(:event_time, TIMESTAMPTZ 'epoch')
                        AND geometry_type = :geometry_type
                        AND ST_Equals(geometry, ST_SetSRID(ST_GeomFromGeoJSON(:geometry_geojson), 4326))
                    )
                    """
                ),
                {
                    "event_id": event.event_id,
                    "geometry_type": geometry.geometry_type,
                    "event_time": utc(geometry.event_time),
                    "geometry_geojson": json_dumps(geometry.geometry),
                },
            )

    def _upsert_normalized(self, conn: Any, event: EONETEventPayload) -> int:
        latest = max(event.geometries, key=lambda item: utc(item.event_time) or datetime.min.replace(tzinfo=timezone.utc), default=None)
        normalized = normalize_eonet_event(
            event_id=event.event_id,
            title=event.title,
            status=event.status,
            categories=event.categories,
            sources=event.sources,
            link=event.link,
            description=event.description,
            closed_at=event.closed_at,
            geometry_geojson=latest.geometry if latest else None,
            geometry_time=latest.event_time if latest else None,
        )
        conn.execute(
            text(
                """
                INSERT INTO hazard_events_normalized (
                  source, source_record_id, type, title, status, severity, confidence, start_time, end_time, geometry, properties_json, updated_at
                )
                VALUES (
                  :source, :source_record_id, :type, :title, :status, :severity, :confidence, :start_time, :end_time,
                  CASE WHEN :geometry_geojson IS NULL THEN NULL ELSE ST_SetSRID(ST_GeomFromGeoJSON(:geometry_geojson), 4326) END,
                  CAST(:properties_json AS jsonb),
                  NOW()
                )
                ON CONFLICT (source, source_record_id) DO UPDATE
                SET type = EXCLUDED.type,
                    title = EXCLUDED.title,
                    status = EXCLUDED.status,
                    severity = EXCLUDED.severity,
                    confidence = EXCLUDED.confidence,
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    geometry = EXCLUDED.geometry,
                    properties_json = EXCLUDED.properties_json,
                    updated_at = NOW()
                """
            ),
            normalized,
        )
        return 1


def _upsert_health(
    conn: Any,
    *,
    source_key: str,
    label: str,
    source_type: str,
    status: str,
    item_count: int,
    details: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO hazard_source_health (
              source_key, label, source_type, enabled, status, last_success_at, item_count, details_json, updated_at
            )
            VALUES (
              :source_key, :label, :source_type, TRUE, :status, NOW(), :item_count, CAST(:details_json AS jsonb), NOW()
            )
            ON CONFLICT (source_key) DO UPDATE
            SET label = EXCLUDED.label,
                source_type = EXCLUDED.source_type,
                enabled = TRUE,
                status = EXCLUDED.status,
                last_success_at = NOW(),
                item_count = EXCLUDED.item_count,
                details_json = EXCLUDED.details_json,
                updated_at = NOW()
            """
        ),
        {
            "source_key": source_key,
            "label": label,
            "source_type": source_type,
            "status": status,
            "item_count": item_count,
            "details_json": json_dumps(details),
        },
    )

