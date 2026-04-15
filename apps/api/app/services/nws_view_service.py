from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import fetch_all


def query_nws_alerts(
    *,
    bbox: tuple[float, float, float, float] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    statuses: list[str] | None = None,
    severities: list[str] | None = None,
    limit: int = 200,
    simplify_tolerance: float = 0.0,
) -> list[dict[str, Any]]:
    clauses = []
    params: dict[str, Any] = {"limit": limit, "simplify_tolerance": simplify_tolerance}
    if bbox:
        clauses.append("geometry && ST_MakeEnvelope(:west, :south, :east, :north, 4326)")
        params.update({"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]})
    if start_time:
        clauses.append("COALESCE(expires, effective, sent) >= :start_time")
        params["start_time"] = _utc(start_time)
    if end_time:
        clauses.append("COALESCE(onset, effective, sent) <= :end_time")
        params["end_time"] = _utc(end_time)
    if statuses:
        clauses.append("LOWER(status) = ANY(:statuses)")
        params["statuses"] = [item.lower() for item in statuses]
    if severities:
        clauses.append("LOWER(COALESCE(severity, '')) = ANY(:severities)")
        params["severities"] = [item.lower() for item in severities]
    return fetch_all(
        f"""
        SELECT
          nws_alert_id,
          event,
          severity,
          certainty,
          urgency,
          status,
          sent,
          effective,
          onset,
          expires,
          headline,
          description,
          instruction,
          area_desc,
          parameters_json,
          CASE
            WHEN geometry IS NULL THEN NULL
            WHEN :simplify_tolerance > 0 THEN ST_AsGeoJSON(ST_SimplifyPreserveTopology(geometry, :simplify_tolerance))::json
            ELSE ST_AsGeoJSON(geometry)::json
          END AS geometry
        FROM nws_alerts
        WHERE 1 = 1
        {' '.join(f'AND {clause}' for clause in clauses)}
        ORDER BY COALESCE(effective, sent) DESC
        LIMIT :limit
        """,
        params,
    )


def default_nws_window(hours: int = 48) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    return end - timedelta(hours=hours), end


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
