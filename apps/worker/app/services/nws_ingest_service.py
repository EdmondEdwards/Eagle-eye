from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..providers.nws_adapter import NWSAdapter, NWSAlertPayload
from .hazard_event_normalizer import json_dumps, normalize_nws_alert


@dataclass(slots=True)
class NWSIngestResult:
    fetched: int
    normalized: int
    status: str


class NWSIngestService:
    def __init__(self, engine: Engine, adapter: NWSAdapter) -> None:
        self.engine = engine
        self.adapter = adapter

    async def run_once(self) -> NWSIngestResult:
        rows = await self.adapter.fetch_active_alerts()
        normalized = 0
        with self.engine.begin() as conn:
            for row in rows:
                self._upsert_native(conn, row)
                normalized += self._upsert_normalized(conn, row)
            _upsert_health(conn, item_count=len(rows), status="healthy", details={"alerts_only": True})
        return NWSIngestResult(fetched=len(rows), normalized=normalized, status="healthy")

    def _upsert_native(self, conn: Any, row: NWSAlertPayload) -> None:
        conn.execute(
            text(
                """
                INSERT INTO nws_alerts (
                  nws_alert_id, event, severity, certainty, urgency, status, sent, effective, onset, expires,
                  headline, description, instruction, area_desc, parameters_json, raw_alert_json, geometry, updated_at
                )
                VALUES (
                  :alert_id, :event, :severity, :certainty, :urgency, :status, :sent, :effective, :onset, :expires,
                  :headline, :description, :instruction, :area_desc, CAST(:parameters_json AS jsonb), CAST(:raw_alert_json AS jsonb),
                  CASE WHEN :geometry_geojson IS NULL THEN NULL ELSE ST_SetSRID(ST_GeomFromGeoJSON(:geometry_geojson), 4326) END,
                  NOW()
                )
                ON CONFLICT (nws_alert_id) DO UPDATE
                SET event = EXCLUDED.event,
                    severity = EXCLUDED.severity,
                    certainty = EXCLUDED.certainty,
                    urgency = EXCLUDED.urgency,
                    status = EXCLUDED.status,
                    sent = EXCLUDED.sent,
                    effective = EXCLUDED.effective,
                    onset = EXCLUDED.onset,
                    expires = EXCLUDED.expires,
                    headline = EXCLUDED.headline,
                    description = EXCLUDED.description,
                    instruction = EXCLUDED.instruction,
                    area_desc = EXCLUDED.area_desc,
                    parameters_json = EXCLUDED.parameters_json,
                    raw_alert_json = EXCLUDED.raw_alert_json,
                    geometry = EXCLUDED.geometry,
                    updated_at = NOW()
                """
            ),
            {
                "alert_id": row.alert_id,
                "event": row.event,
                "severity": row.severity,
                "certainty": row.certainty,
                "urgency": row.urgency,
                "status": row.status,
                "sent": row.sent,
                "effective": row.effective,
                "onset": row.onset,
                "expires": row.expires,
                "headline": row.headline,
                "description": row.description,
                "instruction": row.instruction,
                "area_desc": row.area_desc,
                "parameters_json": json_dumps(row.parameters),
                "raw_alert_json": json_dumps(row.raw),
                "geometry_geojson": json_dumps(row.geometry) if row.geometry else None,
            },
        )

    def _upsert_normalized(self, conn: Any, row: NWSAlertPayload) -> int:
        normalized = normalize_nws_alert(
            alert_id=row.alert_id,
            event=row.event,
            status=row.status,
            severity=row.severity,
            certainty=row.certainty,
            urgency=row.urgency,
            headline=row.headline,
            description=row.description,
            instruction=row.instruction,
            area_desc=row.area_desc,
            parameters=row.parameters,
            effective=row.effective,
            onset=row.onset,
            expires=row.expires,
            sent=row.sent,
            geometry_geojson=row.geometry,
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


def _upsert_health(conn: Any, *, item_count: int, status: str, details: dict[str, Any]) -> None:
    conn.execute(
        text(
            """
            INSERT INTO hazard_source_health (
              source_key, label, source_type, enabled, status, last_success_at, item_count, details_json, updated_at
            )
            VALUES ('nws', 'NOAA / NWS', 'alert', TRUE, :status, NOW(), :item_count, CAST(:details_json AS jsonb), NOW())
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
        {"status": status, "item_count": item_count, "details_json": json_dumps(details)},
    )

