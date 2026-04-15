from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import fetch_all


def query_eonet_events(
    *,
    bbox: tuple[float, float, float, float] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    statuses: list[str] | None = None,
    categories: list[str] | None = None,
    sources: list[str] | None = None,
    limit: int = 200,
    simplify_tolerance: float = 0.0,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    clauses = []
    geom_clauses = []
    if statuses:
        clauses.append("LOWER(e.status) = ANY(:statuses)")
        params["statuses"] = [item.lower() for item in statuses]
    if categories:
        clauses.append(
            """
            EXISTS (
              SELECT 1
              FROM jsonb_array_elements(e.categories_json) AS category
              WHERE LOWER(COALESCE(category->>'title', category->>'id', '')) = ANY(:categories)
            )
            """
        )
        params["categories"] = [item.lower() for item in categories]
    if sources:
        clauses.append(
            """
            EXISTS (
              SELECT 1
              FROM jsonb_array_elements(e.sources_json) AS source
              WHERE LOWER(COALESCE(source->>'id', source->>'title', '')) = ANY(:sources)
            )
            """
        )
        params["sources"] = [item.lower() for item in sources]
    if start_time:
        geom_clauses.append("COALESCE(g.event_time, e.first_seen_at) >= :start_time")
        params["start_time"] = _utc(start_time)
    if end_time:
        geom_clauses.append("COALESCE(g.event_time, e.closed_at, e.last_seen_at) <= :end_time")
        params["end_time"] = _utc(end_time)
    if bbox:
        geom_clauses.append("g.geometry && ST_MakeEnvelope(:west, :south, :east, :north, 4326)")
        params.update({"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]})
    return fetch_all(
        f"""
        SELECT
          e.eonet_event_id,
          e.title,
          e.description,
          e.link,
          e.status,
          e.categories_json,
          e.sources_json,
          e.closed_at,
          e.first_seen_at,
          e.last_seen_at,
          COALESCE(g.event_time, e.last_seen_at) AS event_time,
          CASE
            WHEN g.geometry IS NULL THEN NULL
            WHEN :simplify_tolerance > 0 THEN ST_AsGeoJSON(ST_SimplifyPreserveTopology(g.geometry, :simplify_tolerance))::json
            ELSE ST_AsGeoJSON(g.geometry)::json
          END AS geometry
        FROM eonet_events e
        LEFT JOIN LATERAL (
          SELECT geometry, event_time
          FROM eonet_event_geometry
          WHERE eonet_event_id = e.eonet_event_id
          {' '.join(f'AND {clause}' for clause in geom_clauses)}
          ORDER BY event_time DESC NULLS LAST, id DESC
          LIMIT 1
        ) g ON TRUE
        WHERE 1 = 1
        {' '.join(f'AND {clause}' for clause in clauses)}
        ORDER BY COALESCE(g.event_time, e.last_seen_at) DESC
        LIMIT :limit
        """,
        {**params, "simplify_tolerance": simplify_tolerance},
    )


def default_eonet_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    return end - timedelta(days=days), end


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

