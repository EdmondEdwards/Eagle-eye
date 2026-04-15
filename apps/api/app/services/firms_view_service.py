from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import fetch_all


def query_firms_records(
    *,
    bbox: tuple[float, float, float, float] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sensors: list[str] | None = None,
    limit: int = 500,
    clustered: bool = False,
) -> list[dict[str, Any]]:
    if clustered:
        return query_firms_clusters(bbox=bbox, start_time=start_time, end_time=end_time, limit=limit)
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if bbox:
        clauses.append("geometry && ST_MakeEnvelope(:west, :south, :east, :north, 4326)")
        params.update({"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]})
    if start_time:
        clauses.append("acquisition_time >= :start_time")
        params["start_time"] = _utc(start_time)
    if end_time:
        clauses.append("acquisition_time <= :end_time")
        params["end_time"] = _utc(end_time)
    if sensors:
        clauses.append("LOWER(source_sensor) = ANY(:sensors)")
        params["sensors"] = [item.lower() for item in sensors]
    return fetch_all(
        f"""
        SELECT
          firms_detection_id,
          source_sensor,
          acquisition_time,
          brightness,
          confidence,
          frp,
          daynight,
          satellite,
          ST_AsGeoJSON(geometry)::json AS geometry,
          raw_detection_json
        FROM firms_detections
        WHERE 1 = 1
        {' '.join(f'AND {clause}' for clause in clauses)}
        ORDER BY acquisition_time DESC
        LIMIT :limit
        """,
        params,
    )


def query_firms_clusters(
    *,
    bbox: tuple[float, float, float, float] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 250,
) -> list[dict[str, Any]]:
    clauses = ["source = 'firms'"]
    params: dict[str, Any] = {"limit": limit}
    if bbox:
        clauses.append("geometry && ST_MakeEnvelope(:west, :south, :east, :north, 4326)")
        params.update({"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]})
    if start_time:
        clauses.append("COALESCE(end_time, start_time) >= :start_time")
        params["start_time"] = _utc(start_time)
    if end_time:
        clauses.append("start_time <= :end_time")
        params["end_time"] = _utc(end_time)
    return fetch_all(
        f"""
        SELECT
          id,
          source_record_id,
          type,
          title,
          status,
          severity,
          confidence,
          start_time,
          end_time,
          ST_AsGeoJSON(geometry)::json AS geometry,
          properties_json
        FROM hazard_events_normalized
        WHERE {' AND '.join(clauses)}
        ORDER BY start_time DESC
        LIMIT :limit
        """,
        params,
    )


def default_firms_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    return end - timedelta(days=days), end


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

