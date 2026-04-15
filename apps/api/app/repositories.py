from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from uuid import UUID

from eagle_eye_simulation import (
    compute_satellite_footprint,
    compute_visibility_passes,
    next_clock_state,
    normalize_time_state,
    predict_aircraft_track,
    predict_vessel_track,
)

from .db import as_json, execute, execute_many, fetch_all, fetch_one
from .schemas import (
    AoiCreate,
    AoiUpdate,
    CaseCreate,
    CaseUpdate,
    EntityTimelineResponse,
    GlobeViewState,
    InvestigationBundle,
    NoteCreate,
    NoteUpdate,
    TagCreate,
    TagAssignmentCreate,
    TimeStateUpdate,
    WatchlistCreate,
    WatchlistEntityCreate,
    WatchlistUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)

LOGGER = logging.getLogger(__name__)
LIVE_TRACK_STALE_MINUTES = 10


def _utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _live_track_interval_sql() -> str:
    return f"interval '{LIVE_TRACK_STALE_MINUTES} minutes'"


def _table_exists(table_name: str) -> bool:
    row = fetch_one("SELECT to_regclass(:table_name) AS relation_name", {"table_name": f"public.{table_name}"})
    return bool(row and row.get("relation_name"))


def get_time_state() -> dict[str, Any]:
    execute(
        """
        CREATE TABLE IF NOT EXISTS time_state (
          singleton BOOLEAN PRIMARY KEY DEFAULT TRUE,
          mode TEXT NOT NULL DEFAULT 'live',
          status TEXT NOT NULL DEFAULT 'playing',
          "current_timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          playback_speed DOUBLE PRECISION NOT NULL DEFAULT 1.0,
          step_seconds INTEGER NOT NULL DEFAULT 60,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CHECK (singleton = TRUE),
          CHECK (mode IN ('live', 'paused', 'replay', 'simulate')),
          CHECK (status IN ('playing', 'paused'))
        )
        """
    )
    execute(
        """
        INSERT INTO time_state (singleton, mode, status, "current_timestamp", playback_speed, step_seconds, updated_at)
        VALUES (TRUE, 'live', 'playing', NOW(), 1.0, 60, NOW())
        ON CONFLICT (singleton) DO NOTHING
        """
    )
    record = fetch_one(
        """
        SELECT mode, status, "current_timestamp", playback_speed, step_seconds, updated_at
        FROM time_state
        WHERE singleton = TRUE
        """
    )
    state = normalize_time_state(record or {})
    computed = next_clock_state(state)
    execute(
        """
        UPDATE time_state
        SET mode = :mode,
            status = :status,
            "current_timestamp" = :current_timestamp,
            playback_speed = :playback_speed,
            step_seconds = :step_seconds,
            updated_at = :updated_at
        WHERE singleton = TRUE
        """,
        computed,
    )
    return computed


def set_time_state(payload: TimeStateUpdate) -> dict[str, Any]:
    current = get_time_state()
    updated = {**current}
    incoming = payload.model_dump(exclude_none=True)
    action = incoming.pop("action", None)
    updated.update(incoming)
    if action == "play":
        updated["status"] = "playing"
    elif action == "pause":
        updated["status"] = "paused"
    elif action == "step_forward":
        updated["status"] = "paused"
        updated["current_timestamp"] = _utc(updated["current_timestamp"]) + timedelta(seconds=int(updated["step_seconds"]))
    elif action == "step_back":
        updated["status"] = "paused"
        updated["current_timestamp"] = _utc(updated["current_timestamp"]) - timedelta(seconds=int(updated["step_seconds"]))
    elif action == "jump":
        updated["status"] = "paused"
    updated = normalize_time_state(updated)
    execute(
        """
        UPDATE time_state
        SET mode = :mode,
            status = :status,
            "current_timestamp" = :current_timestamp,
            playback_speed = :playback_speed,
            step_seconds = :step_seconds,
            updated_at = NOW()
        WHERE singleton = TRUE
        """,
        updated,
    )
    return get_time_state()


def _bbox_params(view: GlobeViewState) -> dict[str, float]:
    return {
        "west": view.west,
        "south": view.south,
        "east": view.east,
        "north": view.north,
    }


def _bbox_sql() -> str:
    return """
    (
      (:west <= :east AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326))
      OR
      (
        :west > :east
        AND (
          geom && ST_MakeEnvelope(:west, :south, 180, :north, 4326)
          OR geom && ST_MakeEnvelope(-180, :south, :east, :north, 4326)
        )
      )
    )
    """


def _cluster_query(table: str, entity_kind: str, timestamp: datetime, view: GlobeViewState) -> list[dict[str, Any]]:
    if table == "satellites_current" or (table == "satellites_history" and view.mode != "live"):
        id_column = "norad_cat_id"
    elif table.startswith("vessels"):
        id_column = "mmsi"
    else:
        id_column = "icao24"
    cell_size = 10.0 if view.camera_height > 12_000_000 else 4.0 if view.camera_height > 4_000_000 else 1.25
    if view.mode == "live" and table.endswith("_current"):
        time_clause = f"observed_at >= (:timestamp - {_live_track_interval_sql()})"
        params = {**_bbox_params(view), "timestamp": timestamp, "cell_size": cell_size}
        from_clause = table
    else:
        time_clause = "observed_at <= :timestamp"
        params = {**_bbox_params(view), "timestamp": timestamp, "cell_size": cell_size}
        from_clause = f"(SELECT DISTINCT ON (entity_id) * FROM {table} WHERE observed_at <= :timestamp ORDER BY entity_id, observed_at DESC) latest"
        id_column = "entity_id"
    return fetch_all(
        f"""
        SELECT
          CONCAT(:entity_kind, ':cluster:', ROUND(ST_Y(geom)::numeric / :cell_size, 0), ':', ROUND(ST_X(geom)::numeric / :cell_size, 0)) AS id,
          AVG(ST_Y(geom)) AS lat,
          AVG(ST_X(geom)) AS lon,
          COUNT(*)::int AS count,
          ARRAY_AGG({id_column} ORDER BY observed_at DESC)[1:6] AS sample_ids
        FROM {from_clause}
        WHERE {_bbox_sql()}
          AND {time_clause}
        GROUP BY ROUND(ST_Y(geom)::numeric / :cell_size, 0), ROUND(ST_X(geom)::numeric / :cell_size, 0)
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 300
        """,
        {**params, "entity_kind": entity_kind},
    )


def _prediction(record: dict[str, Any], entity_kind: str) -> list[dict[str, Any]]:
    if entity_kind == "aircraft":
        return predict_aircraft_track(
            lat=record["lat"],
            lon=record["lon"],
            heading_deg=record.get("heading_deg"),
            speed_kts=record.get("velocity_kts"),
            observed_at=record.get("observed_at"),
            minutes_ahead=30,
            step_seconds=120,
            altitude_m=record.get("altitude_m"),
        )
    if entity_kind == "vessel":
        return predict_vessel_track(
            lat=record["lat"],
            lon=record["lon"],
            heading_deg=record.get("course_deg") or record.get("heading_deg"),
            speed_kts=record.get("speed_kts"),
            observed_at=record.get("observed_at"),
            minutes_ahead=90,
            step_seconds=300,
            altitude_m=0,
        )
    if entity_kind == "satellite":
        base_lat = float(record["lat"])
        base_lon = float(record["lon"])
        observed_at = _utc(record.get("observed_at"))
        points = []
        for minute in range(0, 120, 5):
            points.append(
                {
                    "lat": max(min(base_lat + 18 * __import__("math").sin(minute / 12), 82), -82),
                    "lon": ((base_lon + minute * 3.8) + 540) % 360 - 180,
                    "observed_at": (observed_at + timedelta(minutes=minute)).isoformat(),
                    "altitude_m": (record.get("altitude_m") or 500000),
                    "confidence": max(0.25, 0.95 - minute / 180),
                }
            )
        return points
    return []


def _entity_rows(table: str, entity_kind: str, timestamp: datetime, view: GlobeViewState, *, limit: int) -> list[dict[str, Any]]:
    if entity_kind == "satellite":
        label = "name"
        lat_col = "computed_lat"
        lon_col = "computed_lon"
        alt_col = "computed_alt_km"
        speed_col = "computed_velocity_kms"
    else:
        label = "COALESCE(callsign, vessel_name, name, icao24, mmsi, norad_cat_id, id)"
        lat_col = "ST_Y(geom)"
        lon_col = "ST_X(geom)"
        alt_col = "altitude_m"
        speed_col = "COALESCE(velocity_kts, speed_kts)"

    if view.mode == "live" and table.endswith("_current"):
        rows = fetch_all(
            f"""
            SELECT *,
                   {lat_col} AS lat,
                   {lon_col} AS lon,
                   {alt_col} AS altitude_value,
                   {speed_col} AS speed_value,
                   {label} AS label
            FROM {table}
            WHERE {_bbox_sql()}
              AND observed_at >= (:timestamp - {_live_track_interval_sql()})
            ORDER BY observed_at DESC
            LIMIT :limit
            """,
            {**_bbox_params(view), "timestamp": timestamp, "limit": limit},
        )
    else:
        rows = fetch_all(
            f"""
            SELECT *,
                   {lat_col} AS lat,
                   {lon_col} AS lon,
                   {alt_col} AS altitude_value,
                   {speed_col} AS speed_value,
                   {label} AS label
            FROM (
              SELECT DISTINCT ON (entity_id) *
              FROM {table}
              WHERE observed_at <= :timestamp
              ORDER BY entity_id, observed_at DESC
            ) latest
            WHERE {_bbox_sql()}
            ORDER BY observed_at DESC
            LIMIT :limit
            """,
            {**_bbox_params(view), "timestamp": timestamp, "limit": limit},
        )
    return rows


def _map_entity(row: dict[str, Any], entity_kind: str) -> dict[str, Any]:
    label = row.get("label") or row.get("name") or row.get("icao24") or row.get("mmsi") or row.get("norad_cat_id") or row["id"]
    if entity_kind == "satellite":
        geometry = {"type": "Point", "coordinates": [row["computed_lon"], row["computed_lat"]]}
    elif row.get("geom"):
        geometry = {"type": "Point", "coordinates": [row["lon"], row["lat"]]}
    else:
        geometry = {"type": "Point", "coordinates": [row["lon"], row["lat"]]}
    return {
        "id": row["id"],
        "entity_kind": entity_kind,
        "label": label,
        "geometry": geometry,
        "properties": {
            key: value
            for key, value in row.items()
            if key
            not in {"geom", "label", "lat", "lon"}
        },
        "observed_at": row["observed_at"],
        "predicted_path": _prediction(
            {
                "lat": row["computed_lat"] if entity_kind == "satellite" else row["lat"],
                "lon": row["computed_lon"] if entity_kind == "satellite" else row["lon"],
                "heading_deg": row.get("heading_deg"),
                "course_deg": row.get("course_deg"),
                "velocity_kts": row.get("velocity_kts"),
                "speed_kts": row.get("speed_kts"),
                "altitude_m": row.get("altitude_m"),
                "observed_at": row["observed_at"],
            },
            entity_kind,
        ),
    }


def _query_domain(table: str, entity_kind: str, timestamp: datetime, view: GlobeViewState) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cluster_only = view.camera_height > 7_500_000 and entity_kind in {"aircraft", "vessel", "satellite"}
    clusters = _cluster_query(table, entity_kind, timestamp, view) if cluster_only else []
    limit = 600 if view.camera_height < 2_000_000 else 250 if not cluster_only else 90
    should_render_entities = (not cluster_only) or not clusters
    entities = (
        [_map_entity(row, entity_kind) for row in _entity_rows(table, entity_kind, timestamp, view, limit=limit)]
        if should_render_entities
        else []
    )
    return entities, [
        {
            "id": row["id"],
            "entity_kind": entity_kind,
            "count": row["count"],
            "lat": row["lat"],
            "lon": row["lon"],
            "sample_ids": list(row.get("sample_ids") or []),
        }
        for row in clusters
    ]


def _count_live_rows(table: str, timestamp: datetime, view: GlobeViewState) -> dict[str, int]:
    total_row = fetch_one(f"SELECT COUNT(*)::int AS count FROM {table}") or {"count": 0}
    if table == "satellites_current":
        geom_clause = _bbox_sql()
    else:
        geom_clause = _bbox_sql()
    fresh_row = fetch_one(
        f"""
        SELECT COUNT(*)::int AS count
        FROM {table}
        WHERE observed_at >= (:timestamp - {_live_track_interval_sql()})
        """,
        {"timestamp": timestamp},
    ) or {"count": 0}
    bbox_row = fetch_one(
        f"""
        SELECT COUNT(*)::int AS count
        FROM {table}
        WHERE observed_at >= (:timestamp - {_live_track_interval_sql()})
          AND {geom_clause}
        """,
        {**_bbox_params(view), "timestamp": timestamp},
    ) or {"count": 0}
    return {
        "total_rows": int(total_row.get("count") or 0),
        "fresh_rows": int(fresh_row.get("count") or 0),
        "bbox_rows": int(bbox_row.get("count") or 0),
    }


def list_events(*, view: GlobeViewState | None = None, entity_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    if not _table_exists("events"):
        return []
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if view is not None:
        clauses.append("geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)")
        clauses.append("start_time <= :timestamp")
        clauses.append("COALESCE(end_time, start_time + interval '12 hours') >= (:timestamp - interval '24 hours')")
        params.update(_bbox_params(view))
        params["timestamp"] = _utc(view.timestamp)
    if entity_id:
        clauses.append("(entity_id = :entity_id OR related_entity_id = :entity_id)")
        params["entity_id"] = entity_id
    return fetch_all(
        f"""
        SELECT
          id,
          event_type,
          category,
          severity,
          title,
          summary,
          entity_kind,
          entity_id,
          related_entity_kind,
          related_entity_id,
          CASE WHEN geom IS NULL THEN NULL ELSE ST_AsGeoJSON(geom)::json END AS geometry,
          start_time,
          end_time,
          detected_at,
          status,
          confidence,
          source,
          source_confidence,
          raw_reference
        FROM events
        WHERE 1 = 1
        {' '.join(f'AND {clause}' for clause in clauses)}
        ORDER BY start_time DESC
        LIMIT :limit
        """,
        params,
    )


def list_hazard_events(
    *,
    view: GlobeViewState | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sources: list[str] | None = None,
    categories: list[str] | None = None,
    statuses: list[str] | None = None,
    severities: list[str] | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    if not _table_exists("hazard_events_normalized"):
        return []
    params: dict[str, Any] = {"limit": limit}
    clauses = []
    if view is not None:
        bbox = (view.west, view.south, view.east, view.north)
        point_in_time = _utc(view.timestamp)
        clauses.append("start_time <= :point_in_time")
        clauses.append("COALESCE(end_time, start_time + interval '24 hours') >= (:point_in_time - interval '12 hours')")
        params["point_in_time"] = point_in_time
    if bbox is not None:
        clauses.append("geometry IS NOT NULL")
        clauses.append("geometry && ST_MakeEnvelope(:west, :south, :east, :north, 4326)")
        params.update({"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]})
    if start_time is not None:
        clauses.append("COALESCE(end_time, start_time) >= :start_time")
        params["start_time"] = _utc(start_time)
    if end_time is not None:
        clauses.append("start_time <= :end_time")
        params["end_time"] = _utc(end_time)
    if sources:
        clauses.append("LOWER(source) = ANY(:sources)")
        params["sources"] = [item.lower() for item in sources]
    if categories:
        clauses.append("LOWER(COALESCE(properties_json->>'category', type)) = ANY(:categories)")
        params["categories"] = [item.lower() for item in categories]
    if statuses:
        clauses.append("LOWER(status) = ANY(:statuses)")
        params["statuses"] = [item.lower() for item in statuses]
    if severities:
        clauses.append("LOWER(COALESCE(severity, '')) = ANY(:severities)")
        params["severities"] = [item.lower() for item in severities]
    rows = fetch_all(
        f"""
        SELECT
          id,
          source,
          source_record_id,
          type,
          title,
          status,
          severity,
          confidence,
          start_time,
          end_time,
          created_at,
          CASE WHEN geometry IS NULL THEN NULL ELSE ST_AsGeoJSON(geometry)::json END AS geometry,
          properties_json
        FROM hazard_events_normalized
        WHERE 1 = 1
        {' '.join(f'AND {clause}' for clause in clauses)}
        ORDER BY start_time DESC
        LIMIT :limit
        """,
        params,
    )
    return [_map_hazard_event_row(row) for row in rows]


def _map_hazard_event_row(row: dict[str, Any]) -> dict[str, Any]:
    properties = row.get("properties_json") or row.get("properties") or {}
    provenance = properties.get("provenance") or {}
    return {
        "id": row["id"],
        "event_type": row["type"],
        "category": properties.get("category") or row["type"],
        "severity": row.get("severity") or "medium",
        "title": row["title"],
        "summary": properties.get("description") or properties.get("instruction") or properties.get("area_desc"),
        "entity_kind": "hazard",
        "entity_id": str(row["id"]),
        "related_entity_kind": None,
        "related_entity_id": None,
        "geometry": row.get("geometry"),
        "start_time": row["start_time"],
        "end_time": row.get("end_time"),
        "detected_at": row.get("created_at") or row["start_time"],
        "status": row["status"],
        "confidence": float(row.get("confidence") or 0.7),
        "source": row["source"],
        "source_confidence": float(row.get("confidence") or 0.7),
        "raw_reference": properties.get("link"),
        "source_record_id": row.get("source_record_id"),
        "properties": properties,
        "provenance": provenance,
    }


def list_relationships(*, selected_ids: list[str] | None = None, limit: int = 200) -> list[dict[str, Any]]:
    if not _table_exists("relationships"):
        return []
    params: dict[str, Any] = {"limit": limit}
    clause = ""
    if selected_ids:
        params["selected_ids"] = selected_ids
        clause = """
        AND (
          source_id = ANY(:selected_ids)
          OR target_id = ANY(:selected_ids)
        )
        """
    return fetch_all(
        f"""
        SELECT
          id,
          source_kind,
          source_id,
          target_kind,
          target_id,
          relationship_type,
          strength,
          context_event_id,
          context_case_id,
          source,
          source_confidence,
          observed_at,
          raw_payload
        FROM relationships
        WHERE 1 = 1
        {clause}
        ORDER BY observed_at DESC
        LIMIT :limit
        """,
        params,
    )


def list_aois(limit: int = 200) -> list[dict[str, Any]]:
    if not _table_exists("aois"):
        return []
    return fetch_all(
        """
        SELECT
          id,
          name,
          description,
          geometry_type,
          ST_AsGeoJSON(geom)::json AS geometry,
          CASE WHEN center_geom IS NULL THEN NULL ELSE ST_AsGeoJSON(center_geom)::json END AS center,
          radius_m,
          tags,
          source,
          source_confidence,
          observed_at,
          updated_at
        FROM aois
        ORDER BY updated_at DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )


def create_aoi(payload: AoiCreate) -> dict[str, Any]:
    execute(
        """
        INSERT INTO aois (
          name, description, geometry_type, geom, center_geom, radius_m, tags, raw_payload
        )
        VALUES (
          :name,
          :description,
          :geometry_type,
          ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326),
          CASE
            WHEN :center IS NULL THEN NULL
            ELSE ST_SetSRID(ST_GeomFromGeoJSON(:center), 4326)
          END,
          :radius_m,
          :tags,
          :raw_payload
        )
        """,
        {
            "name": payload.name,
            "description": payload.description,
            "geometry_type": payload.geometry_type,
            "geometry": as_json(payload.geometry.model_dump()),
            "center": as_json({"type": "Point", "coordinates": [payload.center["lon"], payload.center["lat"]]}) if payload.center else None,
            "radius_m": payload.radius_m,
            "tags": payload.tags,
            "raw_payload": as_json(payload.model_dump(mode="json")),
        },
    )
    return list_aois(limit=1)[0]


def update_aoi(aoi_id: UUID, payload: AoiUpdate) -> dict[str, Any] | None:
    current = fetch_one(
        """
        SELECT id, name, description, geometry_type, radius_m, tags
        FROM aois
        WHERE id = :aoi_id
        """,
        {"aoi_id": aoi_id},
    )
    if not current:
        return None
    merged = {**current, **payload.model_dump(exclude_none=True)}
    execute(
        """
        UPDATE aois
        SET name = :name,
            description = :description,
            radius_m = :radius_m,
            tags = :tags,
            updated_at = NOW()
        WHERE id = :aoi_id
        """,
        {
            "aoi_id": aoi_id,
            "name": merged["name"],
            "description": merged.get("description"),
            "radius_m": merged.get("radius_m"),
            "tags": merged.get("tags") or [],
        },
    )
    return next((row for row in list_aois() if str(row["id"]) == str(aoi_id)), None)


def events_for_aoi(aoi_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    native_rows = fetch_all(
        """
        SELECT
          e.id,
          e.event_type,
          e.category,
          e.severity,
          e.title,
          e.summary,
          e.entity_kind,
          e.entity_id,
          e.related_entity_kind,
          e.related_entity_id,
          CASE WHEN e.geom IS NULL THEN NULL ELSE ST_AsGeoJSON(e.geom)::json END AS geometry,
          e.start_time,
          e.end_time,
          e.detected_at,
          e.status,
          e.confidence,
          e.source,
          e.source_confidence,
          e.raw_reference
        FROM events e
        JOIN aois a ON a.id = :aoi_id
        WHERE e.geom IS NOT NULL
          AND ST_Intersects(e.geom, a.geom)
        ORDER BY e.start_time DESC
        LIMIT :limit
        """,
        {"aoi_id": aoi_id, "limit": limit},
    )
    hazard_rows = []
    if _table_exists("hazard_events_normalized"):
        hazard_rows = fetch_all(
            """
            SELECT
              h.id,
              h.source,
              h.source_record_id,
              h.type,
              h.title,
              h.status,
              h.severity,
              h.confidence,
              h.start_time,
              h.end_time,
              h.created_at,
              ST_AsGeoJSON(h.geometry)::json AS geometry,
              h.properties_json
            FROM hazard_events_normalized h
            JOIN aois a ON a.id = :aoi_id
            WHERE h.geometry IS NOT NULL
              AND ST_Intersects(h.geometry, a.geom)
            ORDER BY h.start_time DESC
            LIMIT :limit
            """,
            {"aoi_id": aoi_id, "limit": limit},
        )
    return native_rows + [_map_hazard_event_row(row) for row in hazard_rows]


def satellite_passes(satellite_id: str, *, target_lat: float, target_lon: float, threshold_km: float = 550.0) -> list[dict[str, Any]]:
    sat = fetch_one(
        """
        SELECT norad_cat_id, name, computed_lat, computed_lon, computed_alt_km, observed_at
        FROM satellites_current
        WHERE norad_cat_id = :satellite_id OR id = :satellite_id
        ORDER BY observed_at DESC
        LIMIT 1
        """,
        {"satellite_id": satellite_id},
    )
    if not sat:
        return []
    base_time = _utc(sat["observed_at"])
    track = []
    period_minutes = 95
    for minute in range(0, 12 * 60, 5):
        lon = ((float(sat["computed_lon"]) + (minute / period_minutes) * 360.0) + 540.0) % 360.0 - 180.0
        lat = max(min(float(sat["computed_lat"]) + 22.0 * __import__("math").sin(minute / 15.0), 82.0), -82.0)
        track.append(
            {
                "lat": lat,
                "lon": lon,
                "observed_at": (base_time + timedelta(minutes=minute)).isoformat(),
            }
        )
    return compute_visibility_passes(track, target_lat=target_lat, target_lon=target_lon, threshold_km=threshold_km)


def passes_for_aoi(aoi_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
    aoi = fetch_one(
        """
        SELECT
          id,
          name,
          ST_Y(COALESCE(center_geom, ST_Centroid(geom))) AS lat,
          ST_X(COALESCE(center_geom, ST_Centroid(geom))) AS lon,
          COALESCE(radius_m, 500000.0) / 1000.0 AS radius_km
        FROM aois
        WHERE id = :aoi_id
        """,
        {"aoi_id": aoi_id},
    )
    if not aoi:
        return []
    satellites = fetch_all(
        """
        SELECT norad_cat_id, name
        FROM satellites_current
        ORDER BY observed_at DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )
    results = []
    for satellite in satellites:
        passes = satellite_passes(
            satellite["norad_cat_id"],
            target_lat=aoi["lat"],
            target_lon=aoi["lon"],
            threshold_km=max(float(aoi["radius_km"]) * 1.5, 250.0),
        )
        if passes:
            results.append({"satellite_id": satellite["norad_cat_id"], "name": satellite["name"], "passes": passes})
    return results


def satellite_fov(satellite_id: str, at: datetime | None = None) -> dict[str, Any] | None:
    row = fetch_one(
        """
        SELECT norad_cat_id, name, computed_lat, computed_lon, computed_alt_km, observed_at
        FROM satellites_current
        WHERE norad_cat_id = :satellite_id OR id = :satellite_id
        ORDER BY observed_at DESC
        LIMIT 1
        """,
        {"satellite_id": satellite_id},
    )
    if not row:
        return None
    timestamp = _utc(at or row["observed_at"])
    footprint = compute_satellite_footprint(
        lat=float(row["computed_lat"]),
        lon=float(row["computed_lon"]),
        altitude_km=float(row.get("computed_alt_km") or 500.0),
        half_angle_deg=20.0,
    )
    return {
        "satellite_id": row["norad_cat_id"],
        "timestamp": timestamp,
        "footprint": footprint,
        "cone": {
            "apex": {"lat": row["computed_lat"], "lon": row["computed_lon"], "altitude_km": row.get("computed_alt_km")},
            "half_angle_deg": 20.0,
        },
        "swath_km": footprint["properties"]["radius_km"] * 2,
    }


def query_view(view: GlobeViewState) -> dict[str, Any]:
    timestamp = _utc() if view.mode == "live" else _utc(view.timestamp)
    entities: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    try:
        if "aircraft" in view.enabled_layers and _table_exists("aircraft_current" if view.mode == "live" else "aircraft_history"):
            rows, groupings = _query_domain("aircraft_current" if view.mode == "live" else "aircraft_history", "aircraft", timestamp, view)
            entities.extend(rows)
            clusters.extend(groupings)
    except Exception:
        LOGGER.exception("Aircraft view query failed")
    try:
        if "vessels" in view.enabled_layers and _table_exists("vessels_current" if view.mode == "live" else "vessels_history"):
            rows, groupings = _query_domain("vessels_current" if view.mode == "live" else "vessels_history", "vessel", timestamp, view)
            entities.extend(rows)
            clusters.extend(groupings)
    except Exception:
        LOGGER.exception("Vessel view query failed")
    try:
        if "satellites" in view.enabled_layers and _table_exists("satellites_current" if view.mode == "live" else "satellites_history"):
            rows, groupings = _query_domain("satellites_current" if view.mode == "live" else "satellites_history", "satellite", timestamp, view)
            entities.extend(rows)
            clusters.extend(groupings)
    except Exception:
        LOGGER.exception("Satellite view query failed")
    try:
        if "airspace" in view.enabled_layers and _table_exists("airspace_overlays"):
            airspace = fetch_all(
                f"""
                SELECT
                  id,
                  name,
                  category,
                  ST_AsGeoJSON(geom)::json AS geometry,
                  observed_at,
                  active_from,
                  active_to,
                  source,
                  source_confidence
                FROM airspace_overlays
                WHERE geom IS NOT NULL
                  AND {_bbox_sql()}
                  AND COALESCE(active_to, :timestamp + interval '24 hours') >= :timestamp
                  AND COALESCE(active_from, :timestamp - interval '24 hours') <= :timestamp
                ORDER BY observed_at DESC
                LIMIT 200
                """,
                {**_bbox_params(view), "timestamp": timestamp},
            )
            entities.extend(
                [
                    {
                        "id": row["id"],
                        "entity_kind": "airspace",
                        "label": row["name"],
                        "geometry": row["geometry"],
                        "properties": row,
                        "observed_at": row["observed_at"],
                        "predicted_path": [],
                    }
                    for row in airspace
                ]
            )
    except Exception:
        LOGGER.exception("Airspace view query failed")
    try:
        if "aois" in view.enabled_layers and _table_exists("aois"):
            aois = fetch_all(
                f"""
                SELECT id, name, ST_AsGeoJSON(geom)::json AS geometry, observed_at, updated_at, tags
                FROM aois
                WHERE {_bbox_sql()}
                ORDER BY updated_at DESC
                LIMIT 100
                """,
                _bbox_params(view),
            )
            entities.extend(
                [
                    {
                        "id": str(row["id"]),
                        "entity_kind": "aoi",
                        "label": row["name"],
                        "geometry": row["geometry"],
                        "properties": {"tags": row.get("tags") or [], "updated_at": row["updated_at"]},
                        "observed_at": row["observed_at"],
                        "predicted_path": [],
                    }
                    for row in aois
                ]
            )
    except Exception:
        LOGGER.exception("AOI view query failed")
    try:
        event_rows = list_events(view=view, limit=150) if "events" in view.enabled_layers else []
    except Exception:
        LOGGER.exception("Event view query failed")
        event_rows = []
    try:
        hazard_layers = [layer for layer in view.enabled_layers if layer in {"eonet", "firms", "nws"}]
        hazard_rows = list_hazard_events(view=view, sources=hazard_layers, limit=200) if hazard_layers else []
        event_rows.extend(hazard_rows)
        event_rows = sorted(event_rows, key=lambda row: row["start_time"], reverse=True)[:250]
    except Exception:
        LOGGER.exception("Hazard view query failed")
    try:
        relationship_rows = list_relationships(selected_ids=view.selected_entities, limit=150)
    except Exception:
        LOGGER.exception("Relationship view query failed")
        relationship_rows = []
    return {
        "view": view.model_dump(),
        "entities": entities,
        "clusters": clusters,
        "events": event_rows,
        "relationships": relationship_rows,
        "stats": {
            "entities": len(entities),
            "clusters": len(clusters),
            "events": len(event_rows),
            "relationships": len(relationship_rows),
        },
    }


def diagnose_view(view: GlobeViewState) -> dict[str, Any]:
    timestamp = _utc() if view.mode == "live" else _utc(view.timestamp)
    layers: list[dict[str, Any]] = []
    total_entities = 0
    total_clusters = 0

    for key, table, kind in (
        ("aircraft", "aircraft_current" if view.mode == "live" else "aircraft_history", "aircraft"),
        ("vessels", "vessels_current" if view.mode == "live" else "vessels_history", "vessel"),
        ("satellites", "satellites_current" if view.mode == "live" else "satellites_history", "satellite"),
    ):
        if key not in view.enabled_layers:
            continue
        exists = _table_exists(table)
        cluster_only = view.camera_height > 7_500_000 and kind in {"aircraft", "vessel", "satellite"}
        counts = {"total_rows": 0, "fresh_rows": 0, "bbox_rows": 0}
        rows: list[dict[str, Any]] = []
        clusters: list[dict[str, Any]] = []
        if exists:
            if view.mode == "live":
                counts = _count_live_rows(table, timestamp, view)
            try:
                rows, clusters = _query_domain(table, kind, timestamp, view)
            except Exception:
                LOGGER.exception("View diagnostics query failed for %s", key)
        total_entities += len(rows)
        total_clusters += len(clusters)
        layers.append(
            {
                "key": key,
                "table": table,
                "table_exists": exists,
                "cluster_only": cluster_only,
                "total_rows": counts["total_rows"],
                "fresh_rows": counts["fresh_rows"],
                "bbox_rows": counts["bbox_rows"],
                "query_entities": len(rows),
                "query_clusters": len(clusters),
            }
        )

    result = {
        "view": view.model_dump(),
        "effective_timestamp": timestamp,
        "live_track_stale_minutes": LIVE_TRACK_STALE_MINUTES,
        "layers": layers,
        "stats": {
            "layers": len(layers),
            "entities": total_entities,
            "clusters": total_clusters,
        },
    }
    LOGGER.info(
        "View diagnostics mode=%s camera_height=%.0f layers=%s entities=%s clusters=%s",
        view.mode,
        view.camera_height,
        ",".join(layer["key"] for layer in layers),
        total_entities,
        total_clusters,
    )
    return result


def list_entities(view: GlobeViewState) -> list[dict[str, Any]]:
    return query_view(view)["entities"]


def list_satellites_in_view(view: GlobeViewState) -> list[dict[str, Any]]:
    if not _table_exists("satellites_current" if view.mode == "live" else "satellites_history"):
        return []
    rows, _ = _query_domain("satellites_current" if view.mode == "live" else "satellites_history", "satellite", _utc(view.timestamp), view)
    return rows


def list_cases() -> list[dict[str, Any]]:
    cases = fetch_all(
        """
        SELECT id, title, summary, status, priority, source, created_at, updated_at
        FROM cases
        ORDER BY updated_at DESC
        """
    )
    for case in cases:
        case["entities"] = fetch_all(
            """
            SELECT entity_kind, entity_id, role
            FROM case_entities
            WHERE case_id = :case_id
            ORDER BY created_at ASC
            """,
            {"case_id": case["id"]},
        )
    return cases


def create_case(payload: CaseCreate) -> dict[str, Any]:
    execute(
        """
        INSERT INTO cases (title, summary, status, priority, source)
        VALUES (:title, :summary, :status, :priority, :source)
        """,
        payload.model_dump(exclude={"entities"}),
    )
    created = fetch_one("SELECT id FROM cases ORDER BY created_at DESC LIMIT 1")
    execute_many(
        """
        INSERT INTO case_entities (case_id, entity_kind, entity_id, role)
        VALUES (:case_id, :entity_kind, :entity_id, :role)
        """,
        [{"case_id": created["id"], **entity.model_dump()} for entity in payload.entities],
    )
    return list_cases()[0]


def update_case(case_id: UUID, payload: CaseUpdate) -> dict[str, Any] | None:
    current = fetch_one(
        """
        SELECT id, title, summary, status, priority, source, created_at, updated_at
        FROM cases
        WHERE id = :case_id
        """,
        {"case_id": case_id},
    )
    if not current:
        return None
    merged = {**current, **payload.model_dump(exclude_none=True, exclude={"entities"})}
    execute(
        """
        UPDATE cases
        SET title = :title,
            summary = :summary,
            status = :status,
            priority = :priority,
            updated_at = NOW()
        WHERE id = :case_id
        """,
        {"case_id": case_id, **merged},
    )
    if payload.entities is not None:
        execute("DELETE FROM case_entities WHERE case_id = :case_id", {"case_id": case_id})
        execute_many(
            """
            INSERT INTO case_entities (case_id, entity_kind, entity_id, role)
            VALUES (:case_id, :entity_kind, :entity_id, :role)
            """,
            [{"case_id": case_id, **entity.model_dump()} for entity in payload.entities],
        )
    return next((row for row in list_cases() if str(row["id"]) == str(case_id)), None)


def list_notes(limit: int = 200) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, case_id, entity_kind, entity_id, body, author, source, created_at, updated_at
        FROM notes
        ORDER BY updated_at DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )


def create_note(payload: NoteCreate) -> dict[str, Any]:
    execute(
        """
        INSERT INTO notes (case_id, entity_kind, entity_id, body, author, source)
        VALUES (:case_id, :entity_kind, :entity_id, :body, :author, :source)
        """,
        payload.model_dump(),
    )
    return list_notes(limit=1)[0]


def update_note(note_id: UUID, payload: NoteUpdate) -> dict[str, Any] | None:
    current = fetch_one(
        """
        SELECT id, case_id, entity_kind, entity_id, body, author, source, created_at, updated_at
        FROM notes
        WHERE id = :note_id
        """,
        {"note_id": note_id},
    )
    if not current:
        return None
    merged = {**current, **payload.model_dump(exclude_none=True)}
    execute(
        """
        UPDATE notes
        SET case_id = :case_id,
            body = :body,
            updated_at = NOW()
        WHERE id = :note_id
        """,
        {"note_id": note_id, "case_id": merged.get("case_id"), "body": merged["body"]},
    )
    return fetch_one(
        """
        SELECT id, case_id, entity_kind, entity_id, body, author, source, created_at, updated_at
        FROM notes
        WHERE id = :note_id
        """,
        {"note_id": note_id},
    )


def list_watchlists() -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT id, name, description, color, source, created_at, updated_at
        FROM watchlists
        ORDER BY updated_at DESC
        """
    )
    for row in rows:
        row["entities"] = fetch_all(
            """
            SELECT id, entity_kind, entity_id, label, created_at
            FROM watchlist_entities
            WHERE watchlist_id = :watchlist_id
            ORDER BY created_at DESC
            """,
            {"watchlist_id": row["id"]},
        )
    return rows


def create_watchlist(payload: WatchlistCreate) -> dict[str, Any]:
    execute(
        """
        INSERT INTO watchlists (name, description, color, source)
        VALUES (:name, :description, :color, :source)
        """,
        payload.model_dump(),
    )
    return list_watchlists()[0]


def update_watchlist(watchlist_id: UUID, payload: WatchlistUpdate) -> dict[str, Any] | None:
    current = fetch_one(
        """
        SELECT id, name, description, color, source, created_at, updated_at
        FROM watchlists
        WHERE id = :watchlist_id
        """,
        {"watchlist_id": watchlist_id},
    )
    if not current:
        return None
    merged = {**current, **payload.model_dump(exclude_none=True)}
    execute(
        """
        UPDATE watchlists
        SET name = :name,
            description = :description,
            color = :color,
            updated_at = NOW()
        WHERE id = :watchlist_id
        """,
        {"watchlist_id": watchlist_id, **merged},
    )
    return next((row for row in list_watchlists() if str(row["id"]) == str(watchlist_id)), None)


def add_watchlist_entity(watchlist_id: UUID, payload: WatchlistEntityCreate) -> dict[str, Any]:
    execute(
        """
        INSERT INTO watchlist_entities (watchlist_id, entity_kind, entity_id, label)
        VALUES (:watchlist_id, :entity_kind, :entity_id, :label)
        """,
        {"watchlist_id": watchlist_id, **payload.model_dump()},
    )
    return next(row for row in list_watchlists() if str(row["id"]) == str(watchlist_id))


def remove_watchlist_entity(watchlist_id: UUID, entity_id: str) -> dict[str, Any] | None:
    execute(
        """
        DELETE FROM watchlist_entities
        WHERE watchlist_id = :watchlist_id
          AND entity_id = :entity_id
        """,
        {"watchlist_id": watchlist_id, "entity_id": entity_id},
    )
    return next((row for row in list_watchlists() if str(row["id"]) == str(watchlist_id)), None)


def list_tags() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, name, color, source, created_at, updated_at
        FROM tags
        ORDER BY updated_at DESC
        """
    )


def create_tag(payload: TagCreate) -> dict[str, Any]:
    execute(
        """
        INSERT INTO tags (name, color, source)
        VALUES (:name, :color, :source)
        ON CONFLICT (name) DO UPDATE SET color = EXCLUDED.color, updated_at = NOW()
        """,
        payload.model_dump(),
    )
    return fetch_one("SELECT id, name, color, source, created_at, updated_at FROM tags WHERE name = :name", {"name": payload.name})


def assign_tag(payload: TagAssignmentCreate) -> dict[str, Any]:
    tag = fetch_one("SELECT id, name, color, source, created_at, updated_at FROM tags WHERE name = :name", {"name": payload.tag_name})
    if not tag:
        tag = create_tag(TagCreate(name=payload.tag_name))
    execute(
        """
        INSERT INTO entity_tags (tag_id, case_id, entity_kind, entity_id)
        VALUES (:tag_id, :case_id, :entity_kind, :entity_id)
        ON CONFLICT DO NOTHING
        """,
        {
            "tag_id": tag["id"],
            "case_id": payload.case_id,
            "entity_kind": payload.entity_kind,
            "entity_id": payload.entity_id,
        },
    )
    return tag


def list_workspaces() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, name, description, camera, time_context, layers, selected_entities, selected_aois, source, created_at, updated_at
        FROM workspaces
        ORDER BY updated_at DESC
        """
    )


def create_workspace(payload: WorkspaceCreate) -> dict[str, Any]:
    execute(
        """
        INSERT INTO workspaces (name, description, camera, time_context, layers, selected_entities, selected_aois, source)
        VALUES (:name, :description, CAST(:camera AS jsonb), CAST(:time_context AS jsonb), CAST(:layers AS jsonb), CAST(:selected_entities AS jsonb), CAST(:selected_aois AS jsonb), :source)
        """,
        {
            "name": payload.name,
            "description": payload.description,
            "camera": as_json(payload.camera),
            "time_context": as_json(payload.time_context),
            "layers": as_json(payload.layers),
            "selected_entities": as_json(payload.selected_entities),
            "selected_aois": as_json(payload.selected_aois),
            "source": payload.source,
        },
    )
    return list_workspaces()[0]


def update_workspace(workspace_id: UUID, payload: WorkspaceUpdate) -> dict[str, Any] | None:
    current = fetch_one(
        """
        SELECT id, name, description, camera, time_context, layers, selected_entities, selected_aois, source, created_at, updated_at
        FROM workspaces
        WHERE id = :workspace_id
        """,
        {"workspace_id": workspace_id},
    )
    if not current:
        return None
    merged = {**current, **payload.model_dump(exclude_none=True)}
    execute(
        """
        UPDATE workspaces
        SET name = :name,
            description = :description,
            camera = CAST(:camera AS jsonb),
            time_context = CAST(:time_context AS jsonb),
            layers = CAST(:layers AS jsonb),
            selected_entities = CAST(:selected_entities AS jsonb),
            selected_aois = CAST(:selected_aois AS jsonb),
            updated_at = NOW()
        WHERE id = :workspace_id
        """,
        {
            "workspace_id": workspace_id,
            "name": merged["name"],
            "description": merged.get("description"),
            "camera": as_json(merged.get("camera") or {}),
            "time_context": as_json(merged.get("time_context") or {}),
            "layers": as_json(merged.get("layers") or {}),
            "selected_entities": as_json(merged.get("selected_entities") or []),
            "selected_aois": as_json(merged.get("selected_aois") or []),
        },
    )
    return fetch_one(
        """
        SELECT id, name, description, camera, time_context, layers, selected_entities, selected_aois, source, created_at, updated_at
        FROM workspaces
        WHERE id = :workspace_id
        """,
        {"workspace_id": workspace_id},
    )


def entity_timeline(entity_id: str, *, timestamp: datetime | None = None, history_hours: int = 12, future_minutes: int = 120) -> dict[str, Any]:
    reference = _utc(timestamp)
    history_start = reference - timedelta(hours=history_hours)
    entity_kind = "unknown"
    history: list[dict[str, Any]] = []
    predicted: list[dict[str, Any]] = []

    aircraft = fetch_all(
        """
        SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon, altitude_m, observed_at
        FROM aircraft_history
        WHERE entity_id = :entity_id
          AND observed_at BETWEEN :history_start AND :reference
        ORDER BY observed_at ASC
        LIMIT 500
        """,
        {"entity_id": entity_id, "history_start": history_start, "reference": reference},
    )
    if aircraft:
        entity_kind = "aircraft"
        history = aircraft
        current = fetch_one(
            """
            SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon, altitude_m, heading_deg, velocity_kts, observed_at
            FROM aircraft_current
            WHERE id = :entity_id
            """,
            {"entity_id": entity_id},
        )
        if current:
            predicted = predict_aircraft_track(
                lat=current["lat"],
                lon=current["lon"],
                heading_deg=current.get("heading_deg"),
                speed_kts=current.get("velocity_kts"),
                observed_at=current.get("observed_at"),
                minutes_ahead=future_minutes,
                step_seconds=120,
                altitude_m=current.get("altitude_m"),
            )

    if not history:
        vessels = fetch_all(
            """
            SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon, 0::double precision AS altitude_m, observed_at
            FROM vessels_history
            WHERE entity_id = :entity_id
              AND observed_at BETWEEN :history_start AND :reference
            ORDER BY observed_at ASC
            LIMIT 500
            """,
            {"entity_id": entity_id, "history_start": history_start, "reference": reference},
        )
        if vessels:
            entity_kind = "vessel"
            history = vessels
            current = fetch_one(
                """
                SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon, course_deg, heading_deg, speed_kts, observed_at
                FROM vessels_current
                WHERE id = :entity_id
                """,
                {"entity_id": entity_id},
            )
            if current:
                predicted = predict_vessel_track(
                    lat=current["lat"],
                    lon=current["lon"],
                    heading_deg=current.get("course_deg") or current.get("heading_deg"),
                    speed_kts=current.get("speed_kts"),
                    observed_at=current.get("observed_at"),
                    minutes_ahead=future_minutes,
                    step_seconds=300,
                    altitude_m=0,
                )

    if not history:
        satellites = fetch_all(
            """
            SELECT computed_lat AS lat, computed_lon AS lon, computed_alt_km * 1000.0 AS altitude_m, observed_at
            FROM satellites_history
            WHERE (entity_id = :entity_id OR norad_cat_id = REPLACE(:entity_id, 'satellite:', ''))
              AND observed_at BETWEEN :history_start AND :reference
            ORDER BY observed_at ASC
            LIMIT 500
            """,
            {"entity_id": entity_id, "history_start": history_start, "reference": reference},
        )
        if satellites:
            entity_kind = "satellite"
            history = satellites
            current = fetch_one(
                """
                SELECT computed_lat AS lat, computed_lon AS lon, computed_alt_km * 1000.0 AS altitude_m, observed_at
                FROM satellites_current
                WHERE id = :entity_id OR norad_cat_id = REPLACE(:entity_id, 'satellite:', '')
                ORDER BY observed_at DESC
                LIMIT 1
                """,
                {"entity_id": entity_id},
            )
            if current:
                predicted = _prediction(
                    {
                        "lat": current["lat"],
                        "lon": current["lon"],
                        "altitude_m": current.get("altitude_m"),
                        "observed_at": current.get("observed_at"),
                    },
                    "satellite",
                )

    return {
        "entity_id": entity_id,
        "entity_kind": entity_kind,
        "history": history,
        "predicted": predicted,
        "window": {"from": history_start, "to": reference + timedelta(minutes=future_minutes)},
    }


def list_source_status() -> list[dict[str, Any]]:
    aircraft = fetch_one(
        """
        SELECT MAX(observed_at) AS last_observed_at, COUNT(*)::int AS item_count
        FROM aircraft_current
        """
    ) if _table_exists("aircraft_current") else {}
    aircraft = aircraft or {}
    vessels = fetch_all(
        """
        SELECT provider_name, health_state, last_success, valid_message_count, error_count
        FROM vessel_source_health
        ORDER BY priority DESC, provider_name ASC
        """
    ) if _table_exists("vessel_source_health") else []
    satellites = fetch_one(
        """
        SELECT MAX(observed_at) AS last_observed_at, COUNT(*)::int AS item_count
        FROM satellites_current
        """
    ) if _table_exists("satellites_current") else {}
    satellites = satellites or {}
    airspace = fetch_one(
        """
        SELECT MAX(observed_at) AS last_observed_at, COUNT(*)::int AS item_count
        FROM airspace_overlays
        """
    ) if _table_exists("airspace_overlays") else {}
    airspace = airspace or {}
    events = fetch_one(
        """
        SELECT MAX(detected_at) AS last_observed_at, COUNT(*)::int AS item_count
        FROM events
        WHERE detected_at > NOW() - interval '24 hours'
        """
    ) if _table_exists("events") else {}
    events = events or {}
    rows = [
        {
            "key": "opensky",
            "label": "OpenSky",
            "domain": "air",
            "status": "healthy" if aircraft.get("item_count", 0) > 0 else "idle",
            "last_observed_at": aircraft.get("last_observed_at"),
            "item_count": aircraft.get("item_count", 0),
            "details": {"table": "aircraft_current"},
        },
        {
            "key": "celestrak",
            "label": "CelesTrak",
            "domain": "space",
            "status": "healthy" if satellites.get("item_count", 0) > 0 else "idle",
            "last_observed_at": satellites.get("last_observed_at"),
            "item_count": satellites.get("item_count", 0),
            "details": {"table": "satellites_current"},
        },
        {
            "key": "faa_tfr",
            "label": "FAA TFR",
            "domain": "airspace",
            "status": "healthy" if airspace.get("item_count", 0) > 0 else "idle",
            "last_observed_at": airspace.get("last_observed_at"),
            "item_count": airspace.get("item_count", 0),
            "details": {"table": "airspace_overlays"},
        },
        {
            "key": "events",
            "label": "Event Engine",
            "domain": "analytics",
            "status": "healthy",
            "last_observed_at": events.get("last_observed_at"),
            "item_count": events.get("item_count", 0),
            "details": {"window": "24h"},
        },
    ]
    for vessel in vessels:
        rows.append(
            {
                "key": f"maritime:{vessel['provider_name']}",
                "label": vessel["provider_name"],
                "domain": "maritime",
                "status": vessel["health_state"],
                "last_observed_at": vessel.get("last_success"),
                "item_count": vessel.get("valid_message_count", 0),
                "details": {"errors": vessel.get("error_count", 0)},
            }
        )
    if _table_exists("hazard_source_health"):
        for hazard in fetch_all(
            """
            SELECT source_key, label, source_type, status, last_success_at, item_count, details_json
            FROM hazard_source_health
            ORDER BY label ASC
            """
        ):
            rows.append(
                {
                    "key": hazard["source_key"],
                    "label": hazard["label"],
                    "domain": "hazard",
                    "status": hazard["status"],
                    "last_observed_at": hazard.get("last_success_at"),
                    "item_count": hazard.get("item_count", 0),
                    "details": hazard.get("details_json") or {"source_type": hazard.get("source_type")},
                }
            )
    return rows


def list_hazard_categories() -> list[dict[str, Any]]:
    if not _table_exists("hazard_events_normalized"):
        return []
    return fetch_all(
        """
        SELECT
          LOWER(COALESCE(properties_json->>'category', type)) AS key,
          COALESCE(properties_json->>'category', type) AS label,
          COUNT(*)::int AS item_count
        FROM hazard_events_normalized
        GROUP BY LOWER(COALESCE(properties_json->>'category', type)), COALESCE(properties_json->>'category', type)
        ORDER BY item_count DESC, label ASC
        """
    )


def get_hazard_event_detail(event_id: UUID) -> dict[str, Any] | None:
    row = fetch_one(
        """
        SELECT
          id,
          source,
          source_record_id,
          type,
          title,
          status,
          severity,
          confidence,
          start_time,
          end_time,
          created_at,
          CASE WHEN geometry IS NULL THEN NULL ELSE ST_AsGeoJSON(geometry)::json END AS geometry,
          properties_json
        FROM hazard_events_normalized
        WHERE id = :event_id
        """,
        {"event_id": event_id},
    )
    if not row:
        return None
    event = _map_hazard_event_row(row)
    source_payload = _hazard_source_payload(source=row["source"], source_record_id=row["source_record_id"])
    linked_cases = fetch_all(
        """
        SELECT c.id, c.title, c.summary, c.status, c.priority, c.source, c.created_at, c.updated_at
        FROM cases c
        JOIN case_entities ce ON ce.case_id = c.id
        WHERE ce.entity_kind = 'hazard'
          AND ce.entity_id = :event_id
        ORDER BY c.updated_at DESC
        """,
        {"event_id": str(event_id)},
    ) if _table_exists("case_entities") else []
    linked_aois = fetch_all(
        """
        SELECT
          a.id,
          a.name,
          a.description,
          a.geometry_type,
          ST_AsGeoJSON(a.geom)::json AS geometry,
          CASE WHEN a.center_geom IS NULL THEN NULL ELSE ST_AsGeoJSON(a.center_geom)::json END AS center,
          a.radius_m,
          a.tags,
          a.source,
          a.source_confidence,
          a.observed_at,
          a.updated_at
        FROM aois a
        JOIN hazard_events_normalized h ON h.id = :event_id
        WHERE h.geometry IS NOT NULL
          AND ST_Intersects(a.geom, h.geometry)
        ORDER BY a.updated_at DESC
        LIMIT 12
        """,
        {"event_id": event_id},
    ) if row.get("geometry") is not None and _table_exists("aois") else []
    nearby = _hazard_nearby(event_id)
    links = [value for value in [event.get("raw_reference"), (event.get("properties") or {}).get("link")] if value]
    return {
        "event": event,
        "source_payload": source_payload or {},
        "linked_cases": linked_cases,
        "linked_aois": linked_aois,
        "nearby": nearby,
        "links": links,
    }


def _hazard_source_payload(*, source: str, source_record_id: str) -> dict[str, Any] | None:
    if source == "eonet" and _table_exists("eonet_events"):
        row = fetch_one(
            """
            SELECT raw_event_json AS payload
            FROM eonet_events
            WHERE eonet_event_id = :source_record_id
            """,
            {"source_record_id": source_record_id},
        )
        return row.get("payload") if row else None
    if source == "firms" and _table_exists("firms_detections") and source_record_id.startswith("firms:"):
        row = fetch_one(
            """
            SELECT raw_detection_json AS payload
            FROM firms_detections
            WHERE firms_detection_id = :source_record_id
            """,
            {"source_record_id": source_record_id},
        )
        return row.get("payload") if row else None
    if source == "nws" and _table_exists("nws_alerts"):
        row = fetch_one(
            """
            SELECT raw_alert_json AS payload
            FROM nws_alerts
            WHERE nws_alert_id = :source_record_id
            """,
            {"source_record_id": source_record_id},
        )
        return row.get("payload") if row else None
    return None


def _hazard_nearby(event_id: UUID) -> dict[str, list[dict[str, Any]]]:
    if not _table_exists("hazard_events_normalized"):
        return {}
    nearby: dict[str, list[dict[str, Any]]] = {}
    queries = {
        "aircraft": (
            "aircraft_current",
            """
            SELECT id, COALESCE(callsign, icao24, id) AS label, observed_at,
                   ST_Distance(geom::geography, h.geometry::geography) AS distance_m
            FROM aircraft_current, hazard_events_normalized h
            WHERE h.id = :event_id AND h.geometry IS NOT NULL
              AND ST_DWithin(geom::geography, h.geometry::geography, 250000)
            ORDER BY distance_m ASC
            LIMIT 8
            """,
        ),
        "vessels": (
            "vessels_current",
            """
            SELECT id, COALESCE(vessel_name, mmsi, id) AS label, observed_at,
                   ST_Distance(geom::geography, h.geometry::geography) AS distance_m
            FROM vessels_current, hazard_events_normalized h
            WHERE h.id = :event_id AND h.geometry IS NOT NULL
              AND ST_DWithin(geom::geography, h.geometry::geography, 250000)
            ORDER BY distance_m ASC
            LIMIT 8
            """,
        ),
        "satellites": (
            "satellites_current",
            """
            SELECT id, COALESCE(name, norad_cat_id, id) AS label, observed_at,
                   ST_Distance(geom::geography, h.geometry::geography) AS distance_m
            FROM satellites_current, hazard_events_normalized h
            WHERE h.id = :event_id AND h.geometry IS NOT NULL
              AND ST_DWithin(geom::geography, h.geometry::geography, 750000)
            ORDER BY distance_m ASC
            LIMIT 8
            """,
        ),
        "webcams": (
            "webcams",
            """
            SELECT id, name AS label, created_at AS observed_at,
                   ST_Distance(geom::geography, h.geometry::geography) AS distance_m
            FROM webcams, hazard_events_normalized h
            WHERE h.id = :event_id AND h.geometry IS NOT NULL
              AND ST_DWithin(geom::geography, h.geometry::geography, 250000)
            ORDER BY distance_m ASC
            LIMIT 8
            """,
        ),
    }
    for key, (table_name, query) in queries.items():
        if _table_exists(table_name):
            nearby[key] = fetch_all(query, {"event_id": event_id})
    return nearby


def investigation_bundle(entity_id: str) -> dict[str, Any]:
    entity = next(
        (
            row
            for row in fetch_all(
                """
                SELECT id, 'aircraft' AS entity_kind, COALESCE(callsign, icao24, id) AS label,
                       json_build_object('type', 'Point', 'coordinates', json_build_array(ST_X(geom), ST_Y(geom))) AS geometry,
                       observed_at,
                       jsonb_build_object(
                         'icao24', icao24,
                         'callsign', callsign,
                         'altitude_m', altitude_m,
                         'heading_deg', heading_deg,
                         'velocity_kts', velocity_kts
                       ) AS properties
                FROM aircraft_current
                WHERE id = :entity_id
                UNION ALL
                SELECT id, 'vessel' AS entity_kind, COALESCE(vessel_name, callsign, mmsi, id) AS label,
                       json_build_object('type', 'Point', 'coordinates', json_build_array(ST_X(geom), ST_Y(geom))) AS geometry,
                       observed_at,
                       jsonb_build_object(
                         'mmsi', mmsi,
                         'vessel_name', vessel_name,
                         'course_deg', course_deg,
                         'speed_kts', speed_kts
                       ) AS properties
                FROM vessels_current
                WHERE id = :entity_id
                UNION ALL
                SELECT id, 'satellite' AS entity_kind, name AS label,
                       json_build_object('type', 'Point', 'coordinates', json_build_array(computed_lon, computed_lat)) AS geometry,
                       observed_at,
                       jsonb_build_object(
                         'norad_cat_id', norad_cat_id,
                         'name', name,
                         'computed_alt_km', computed_alt_km
                       ) AS properties
                FROM satellites_current
                WHERE id = :entity_id OR norad_cat_id = REPLACE(:entity_id, 'satellite:', '')
                UNION ALL
                SELECT id::text AS id, 'aoi' AS entity_kind, name AS label,
                       ST_AsGeoJSON(geom)::json AS geometry,
                       observed_at,
                       jsonb_build_object(
                         'geometry_type', geometry_type,
                         'radius_m', radius_m
                       ) AS properties
                FROM aois
                WHERE id::text = :entity_id
                """,
                {"entity_id": entity_id},
            )
        ),
        None,
    )
    if not entity:
        return {
            "entity": None,
            "events": [],
            "relationships": [],
            "notes": [],
            "aois": [],
            "watchlists": [],
            "satellite_fov": None,
            "satellite_passes": [],
            "timeline": None,
            "aoi_events": [],
            "aoi_passes": [],
        }
    events = list_events(entity_id=entity_id, limit=50)
    relationships = list_relationships(selected_ids=[entity_id], limit=50)
    notes = fetch_all(
        """
        SELECT id, case_id, entity_kind, entity_id, body, author, source, created_at, updated_at
        FROM notes
        WHERE entity_id = :entity_id
        ORDER BY updated_at DESC
        LIMIT 50
        """,
        {"entity_id": entity_id},
    )
    watchlists = fetch_all(
        """
        SELECT w.id, w.name, w.description, w.color, w.source, w.created_at, w.updated_at
        FROM watchlists w
        JOIN watchlist_entities we ON we.watchlist_id = w.id
        WHERE we.entity_id = :entity_id
        ORDER BY w.updated_at DESC
        """,
        {"entity_id": entity_id},
    )
    if entity["entity_kind"] == "aoi":
        aois = [row for row in list_aois() if str(row["id"]) == str(entity_id)]
    else:
        point = entity["geometry"]
        aois = fetch_all(
            """
            SELECT
              id,
              name,
              description,
              geometry_type,
              ST_AsGeoJSON(geom)::json AS geometry,
              CASE WHEN center_geom IS NULL THEN NULL ELSE ST_AsGeoJSON(center_geom)::json END AS center,
              radius_m,
              tags,
              source,
              source_confidence,
              observed_at,
              updated_at
            FROM aois
            WHERE ST_Intersects(
              geom,
              ST_SetSRID(ST_GeomFromGeoJSON(:entity_geometry), 4326)
            )
               OR ST_DWithin(
                 COALESCE(center_geom, ST_Centroid(geom))::geography,
                 ST_SetSRID(ST_GeomFromGeoJSON(:entity_geometry), 4326)::geography,
                 GREATEST(COALESCE(radius_m, 150000.0), 150000.0)
               )
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            {"entity_geometry": as_json(pointFromGeometry)},
        )
    satellite_fov_row = satellite_fov(entity_id) if entity["entity_kind"] == "satellite" else None
    satellite_passes_rows = []
    timeline = entity_timeline(entity_id)
    aoi_events_rows: list[dict[str, Any]] = []
    aoi_passes_rows: list[dict[str, Any]] = []
    if entity["entity_kind"] == "satellite":
        for aoi in aois[:3]:
            satellite_passes_rows.extend(
                [
                    {
                        "aoi_id": aoi["id"],
                        "aoi_name": aoi["name"],
                        "passes": item["passes"],
                    }
                    for item in passes_for_aoi(UUID(str(aoi["id"])))
                    if item["satellite_id"] in {entity_id, entity["properties"].get("norad_cat_id"), entity["id"]}
                ]
            )
    if entity["entity_kind"] == "aoi":
        aoi_uuid = UUID(str(entity_id))
        aoi_events_rows = events_for_aoi(aoi_uuid, limit=100)
        aoi_passes_rows = passes_for_aoi(aoi_uuid, limit=20)
    return {
        "entity": entity,
        "events": events,
        "relationships": relationships,
        "notes": notes,
        "aois": aois,
        "watchlists": [{**watchlist, "entities": []} for watchlist in watchlists],
        "satellite_fov": satellite_fov_row,
        "satellite_passes": satellite_passes_rows,
        "timeline": timeline,
        "aoi_events": aoi_events_rows,
        "aoi_passes": aoi_passes_rows,
    }
