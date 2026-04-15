from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..providers.firms_adapter import FIRMSAdapter, FIRMSDetectionPayload
from .hazard_event_normalizer import json_dumps, normalize_firms_cluster, normalize_firms_detection


@dataclass(slots=True)
class FIRMSIngestResult:
    fetched: int
    normalized: int
    queried_areas: int
    status: str


class FIRMSIngestService:
    def __init__(self, engine: Engine, adapter: FIRMSAdapter) -> None:
        self.engine = engine
        self.adapter = adapter

    async def run_once(
        self,
        *,
        sensors: list[str],
        lookback_days: int,
        enable_clustering: bool,
        configured_bboxes: list[tuple[float, float, float, float]],
        global_tile_step_degrees: float,
        max_tiles: int,
    ) -> FIRMSIngestResult:
        query_areas = configured_bboxes or self._resolve_areas(global_tile_step_degrees=global_tile_step_degrees, max_tiles=max_tiles)
        total_rows = 0
        with self.engine.begin() as conn:
            for bbox in query_areas:
                for sensor in sensors:
                    rows = await self.adapter.fetch_area(sensor=sensor, bbox=bbox, days=lookback_days)
                    total_rows += len(rows)
                    for row in rows:
                        self._insert_detection(conn, row)
            normalized = self._refresh_normalized(conn, lookback_days=lookback_days, enable_clustering=enable_clustering)
            _upsert_health(
                conn,
                item_count=total_rows,
                status="healthy",
                details={"areas": len(query_areas), "sensors": sensors, "lookback_days": lookback_days},
            )
        return FIRMSIngestResult(fetched=total_rows, normalized=normalized, queried_areas=len(query_areas), status="healthy")

    def _resolve_areas(self, *, global_tile_step_degrees: float, max_tiles: int) -> list[tuple[float, float, float, float]]:
        with self.engine.begin() as conn:
            aoi_boxes = conn.execute(
                text(
                    """
                    SELECT
                      ST_XMin(geom) AS west,
                      ST_YMin(geom) AS south,
                      ST_XMax(geom) AS east,
                      ST_YMax(geom) AS north
                    FROM aois
                    ORDER BY updated_at DESC
                    LIMIT 25
                    """
                )
            ).mappings().all()
        if aoi_boxes:
            return [(float(row["west"]), float(row["south"]), float(row["east"]), float(row["north"])) for row in aoi_boxes]
        areas: list[tuple[float, float, float, float]] = []
        lat = -80.0
        while lat < 80.0 and len(areas) < max_tiles:
            lon = -180.0
            while lon < 180.0 and len(areas) < max_tiles:
                areas.append((lon, lat, min(lon + global_tile_step_degrees, 180.0), min(lat + global_tile_step_degrees, 80.0)))
                lon += global_tile_step_degrees
            lat += global_tile_step_degrees
        return areas or [(-180.0, -80.0, 180.0, 80.0)]

    def _insert_detection(self, conn: Any, row: FIRMSDetectionPayload) -> None:
        conn.execute(
            text(
                """
                INSERT INTO firms_detections (
                  firms_detection_id, source_sensor, acquisition_time, latitude, longitude, brightness, confidence,
                  frp, daynight, satellite, raw_detection_json, geometry
                )
                VALUES (
                  :detection_id, :source_sensor, :acquisition_time, :latitude, :longitude, :brightness, :confidence,
                  :frp, :daynight, :satellite, CAST(:raw_detection_json AS jsonb),
                  ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)
                )
                ON CONFLICT (firms_detection_id) DO NOTHING
                """
            ),
            {
                "detection_id": row.detection_id,
                "source_sensor": row.source_sensor,
                "acquisition_time": row.acquisition_time,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "brightness": row.brightness,
                "confidence": row.confidence,
                "frp": row.frp,
                "daynight": row.daynight,
                "satellite": row.satellite,
                "raw_detection_json": json_dumps(row.raw),
            },
        )

    def _refresh_normalized(self, conn: Any, *, lookback_days: int, enable_clustering: bool) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        if enable_clustering:
            cluster_rows = conn.execute(
                text(
                    """
                    WITH recent AS (
                      SELECT
                        firms_detection_id,
                        source_sensor,
                        acquisition_time,
                        confidence,
                        brightness,
                        frp,
                        daynight,
                        satellite,
                        geometry,
                        ST_SnapToGrid(geometry, 0.25, 0.25) AS snapped_geom
                      FROM firms_detections
                      WHERE acquisition_time >= :cutoff
                    )
                    SELECT
                      CONCAT(
                        'cluster:',
                        source_sensor,
                        ':',
                        TO_CHAR(date_trunc('hour', MIN(acquisition_time)), 'YYYYMMDDHH24'),
                        ':',
                        md5(ST_AsText(snapped_geom))
                      ) AS cluster_id,
                      source_sensor,
                      MIN(acquisition_time) AS start_time,
                      MAX(acquisition_time) AS end_time,
                      COUNT(*)::int AS detection_count,
                      AVG(COALESCE(frp, 0)) AS avg_frp,
                      AVG(COALESCE(brightness, 0)) AS avg_brightness,
                      AVG(CASE LOWER(COALESCE(confidence, 'nominal'))
                            WHEN 'h' THEN 0.95
                            WHEN 'high' THEN 0.95
                            WHEN 'n' THEN 0.65
                            WHEN 'nominal' THEN 0.65
                            WHEN 'l' THEN 0.35
                            WHEN 'low' THEN 0.35
                            ELSE 0.6
                          END) AS confidence_score,
                      ARRAY_AGG(firms_detection_id ORDER BY acquisition_time DESC) AS detection_ids,
                      ST_AsGeoJSON(ST_ConvexHull(ST_Collect(geometry)))::json AS geometry
                    FROM recent
                    GROUP BY source_sensor, snapped_geom
                    HAVING COUNT(*) >= 2
                    """
                ),
                {"cutoff": cutoff},
            ).mappings().all()
            count = 0
            for row in cluster_rows:
                severity = "high" if float(row["avg_frp"] or 0) >= 25 or int(row["detection_count"]) >= 10 else "medium"
                normalized = normalize_firms_cluster(
                    cluster_id=str(row["cluster_id"]),
                    title=f"FIRMS fire cluster ({row['source_sensor']})",
                    severity=severity,
                    confidence=float(row["confidence_score"] or 0.7),
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    geometry_geojson=row["geometry"],
                    properties_json={
                        "sensor": row["source_sensor"],
                        "detection_count": row["detection_count"],
                        "avg_frp": float(row["avg_frp"] or 0),
                        "avg_brightness": float(row["avg_brightness"] or 0),
                        "detection_ids": list(row["detection_ids"] or []),
                    },
                )
                _upsert_normalized(conn, normalized)
                count += 1
            return count
        rows = conn.execute(
            text(
                """
                SELECT
                  firms_detection_id,
                  source_sensor,
                  acquisition_time,
                  brightness,
                  confidence,
                  frp,
                  daynight,
                  satellite,
                  ST_AsGeoJSON(geometry)::json AS geometry
                FROM firms_detections
                WHERE acquisition_time >= :cutoff
                """
            ),
            {"cutoff": cutoff},
        ).mappings().all()
        for row in rows:
            confidence = 0.9 if str(row["confidence"] or "").lower() in {"h", "high"} else 0.65
            severity = "high" if float(row["frp"] or 0) >= 20 else "medium"
            _upsert_normalized(
                conn,
                normalize_firms_detection(
                    detection_id=str(row["firms_detection_id"]),
                    title=f"FIRMS thermal anomaly ({row['source_sensor']})",
                    severity=severity,
                    confidence=confidence,
                    acquisition_time=row["acquisition_time"],
                    geometry_geojson=row["geometry"],
                    properties_json={
                        "sensor": row["source_sensor"],
                        "brightness": row["brightness"],
                        "frp": row["frp"],
                        "confidence_native": row["confidence"],
                        "daynight": row["daynight"],
                        "satellite": row["satellite"],
                    },
                ),
            )
        return len(rows)


def _upsert_normalized(conn: Any, normalized: dict[str, Any]) -> None:
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


def _upsert_health(conn: Any, *, item_count: int, status: str, details: dict[str, Any]) -> None:
    conn.execute(
        text(
            """
            INSERT INTO hazard_source_health (
              source_key, label, source_type, enabled, status, last_success_at, item_count, details_json, updated_at
            )
            VALUES ('firms', 'NASA FIRMS', 'detection', TRUE, :status, NOW(), :item_count, CAST(:details_json AS jsonb), NOW())
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

