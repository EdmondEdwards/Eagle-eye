from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .db import execute, fetch_all, fetch_one
from .schemas import (
    CaseCreate,
    CaseEntity,
    CaseUpdate,
    NoteCreate,
    NoteUpdate,
    SavedViewCreate,
    SavedViewUpdate,
    TagAssignmentCreate,
    TagCreate,
    TagUpdate,
    WatchlistCreate,
    WatchlistEntityCreate,
    WatchlistUpdate,
)
from .services.satellite_propagation_service import orbit_path_from_row, playback_from_rows

COORDINATE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$")


def _build_envelope_clause(bbox: str | None) -> tuple[str, dict[str, Any]]:
    if not bbox:
        return "", {}
    min_lon, min_lat, max_lon, max_lat = [float(value) for value in bbox.split(",")]
    return (
        """
        AND geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
        """,
        {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat,
        },
    )


def list_aircraft_current(bbox: str | None, limit: int) -> list[dict[str, Any]]:
    bbox_clause, bbox_params = _build_envelope_clause(bbox)
    return fetch_all(
        f"""
        SELECT
          id,
          icao24,
          callsign,
          registration,
          operator,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          altitude_m,
          heading_deg,
          velocity_kts,
          vertical_rate,
          source,
          source_confidence,
          observed_at,
          raw_reference
        FROM aircraft_current
        WHERE 1 = 1
        {bbox_clause}
        ORDER BY observed_at DESC
        LIMIT :limit
        """,
        {**bbox_params, "limit": limit},
    )


def list_vessels_current(
    bbox: str | None,
    limit: int,
    *,
    mmsi: str | None = None,
    imo: str | None = None,
    vessel_name: str | None = None,
    source: str | None = None,
    vessel_type: str | None = None,
    flag: str | None = None,
) -> list[dict[str, Any]]:
    where_clause, params = _build_vessel_filters(
        bbox,
        mmsi=mmsi,
        imo=imo,
        vessel_name=vessel_name,
        source=source,
        vessel_type=vessel_type,
        flag=flag,
    )
    return fetch_all(
        f"""
        SELECT
          id,
          mmsi,
          imo,
          vessel_name,
          callsign,
          vessel_type,
          flag,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          heading_deg,
          course_deg,
          speed_kts,
          nav_status,
          destination,
          draught_m,
          source,
          source_record_id,
          source_confidence,
          merged_confidence,
          observed_at,
          last_ingested_at,
          stale,
          raw_reference
        FROM vessels_current
        WHERE 1 = 1
        {where_clause}
        ORDER BY observed_at DESC
        LIMIT :limit
        """,
        {**params, "limit": limit},
    )


def _build_vessel_filters(
    bbox: str | None,
    *,
    mmsi: str | None = None,
    imo: str | None = None,
    vessel_name: str | None = None,
    source: str | None = None,
    vessel_type: str | None = None,
    flag: str | None = None,
) -> tuple[str, dict[str, Any]]:
    bbox_clause, bbox_params = _build_envelope_clause(bbox)
    clauses = [bbox_clause]
    params: dict[str, Any] = {**bbox_params}
    if mmsi:
        clauses.append("AND mmsi = :mmsi")
        params["mmsi"] = mmsi
    if imo:
        clauses.append("AND imo = :imo")
        params["imo"] = imo
    if vessel_name:
        clauses.append("AND LOWER(COALESCE(vessel_name, '')) LIKE :vessel_name")
        params["vessel_name"] = f"%{vessel_name.lower()}%"
    if source:
        clauses.append("AND LOWER(source) = :source")
        params["source"] = source.lower()
    if vessel_type:
        clauses.append("AND LOWER(COALESCE(vessel_type, '')) = :vessel_type")
        params["vessel_type"] = vessel_type.lower()
    if flag:
        clauses.append("AND LOWER(COALESCE(flag, '')) = :flag")
        params["flag"] = flag.lower()
    return "\n".join(filter(None, clauses)), params


def _build_satellite_filters(
    bbox: str | None,
    *,
    norad_cat_id: str | None = None,
    name: str | None = None,
    group: str | None = None,
) -> tuple[str, dict[str, Any]]:
    bbox_clause, bbox_params = _build_envelope_clause(bbox)
    clauses = [bbox_clause]
    params: dict[str, Any] = {**bbox_params}
    if norad_cat_id:
        clauses.append("AND norad_cat_id = :norad_cat_id")
        params["norad_cat_id"] = norad_cat_id
    if name:
        clauses.append("AND LOWER(name) LIKE :name")
        params["name"] = f"%{name.lower()}%"
    if group:
        clauses.append("AND LOWER(COALESCE(group_name, '')) = :group_name")
        params["group_name"] = group.lower()
    return "\n".join(filter(None, clauses)), params


def list_satellites_current(
    bbox: str | None,
    limit: int,
    *,
    norad_cat_id: str | None = None,
    name: str | None = None,
    group: str | None = None,
) -> list[dict[str, Any]]:
    where_clause, params = _build_satellite_filters(bbox, norad_cat_id=norad_cat_id, name=name, group=group)
    return fetch_all(
        f"""
        SELECT
          id,
          norad_cat_id,
          international_designator,
          name,
          object_type,
          group_name,
          orbit_class,
          tle_line1,
          tle_line2,
          epoch,
          inclination_deg,
          eccentricity,
          mean_motion,
          raan_deg,
          arg_perigee_deg,
          mean_anomaly_deg,
          bstar,
          computed_lat,
          computed_lon,
          computed_alt_km,
          computed_velocity_kms,
          source,
          source_confidence,
          observed_at,
          raw_reference
        FROM satellites_current
        WHERE 1 = 1
        {where_clause}
        ORDER BY observed_at DESC, name ASC
        LIMIT :limit
        """,
        {**params, "limit": limit},
    )


def list_satellites_catalog(
    *,
    limit: int,
    norad_cat_id: str | None = None,
    name: str | None = None,
    group: str | None = None,
    object_type: str | None = None,
    orbit_class: str | None = None,
) -> list[dict[str, Any]]:
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if norad_cat_id:
        clauses.append("AND norad_cat_id = :norad_cat_id")
        params["norad_cat_id"] = norad_cat_id
    if name:
        clauses.append("AND LOWER(name) LIKE :name")
        params["name"] = f"%{name.lower()}%"
    if group:
        clauses.append("AND LOWER(COALESCE(group_name, '')) = :group_name")
        params["group_name"] = group.lower()
    if object_type:
        clauses.append("AND LOWER(COALESCE(object_type, '')) = :object_type")
        params["object_type"] = object_type.lower()
    if orbit_class:
        clauses.append("AND LOWER(COALESCE(orbit_class, '')) = :orbit_class")
        params["orbit_class"] = orbit_class.lower()

    return fetch_all(
        f"""
        SELECT
          id,
          norad_cat_id,
          international_designator,
          name,
          object_type,
          group_name,
          orbit_class,
          source,
          tle_line1,
          tle_line2,
          epoch,
          inclination_deg,
          eccentricity,
          mean_motion,
          raan_deg,
          arg_perigee_deg,
          mean_anomaly_deg,
          bstar,
          source_confidence,
          observed_at,
          raw_reference
        FROM satellites_catalog
        WHERE 1 = 1
        {' '.join(clauses)}
        ORDER BY observed_at DESC, name ASC
        LIMIT :limit
        """,
        params,
    )


def get_satellite(norad_cat_id: str) -> dict[str, Any] | None:
    record = fetch_one(
        """
        SELECT
          c.id,
          c.norad_cat_id,
          c.international_designator,
          c.name,
          c.object_type,
          c.group_name,
          COALESCE(cur.orbit_class, c.orbit_class) AS orbit_class,
          COALESCE(cur.source, c.source) AS source,
          c.tle_line1,
          c.tle_line2,
          c.epoch,
          c.inclination_deg,
          c.eccentricity,
          c.mean_motion,
          c.raan_deg,
          c.arg_perigee_deg,
          c.mean_anomaly_deg,
          c.bstar,
          COALESCE(cur.source_confidence, c.source_confidence) AS source_confidence,
          COALESCE(cur.observed_at, c.observed_at) AS observed_at,
          cur.computed_lat,
          cur.computed_lon,
          cur.computed_alt_km,
          cur.computed_velocity_kms,
          COALESCE(cur.raw_reference, c.raw_reference) AS raw_reference
        FROM satellites_catalog c
        LEFT JOIN satellites_current cur ON cur.norad_cat_id = c.norad_cat_id
        WHERE c.norad_cat_id = :norad_cat_id
        """,
        {"norad_cat_id": norad_cat_id},
    )
    if not record:
        return None
    if record.get("computed_lat") is None or record.get("computed_lon") is None:
        current_path = orbit_path_from_row(
            record,
            start=datetime.now(timezone.utc),
            minutes_ahead=5,
            step_seconds=300,
        )
        if current_path:
            first_point = current_path[0].to_dict()
            record["computed_lat"] = first_point["lat"]
            record["computed_lon"] = first_point["lon"]
            record["computed_alt_km"] = first_point.get("alt_km")
            record["computed_velocity_kms"] = first_point.get("velocity_kms")
    return record


def list_airspace_current(at: datetime | None) -> list[dict[str, Any]]:
    reference_time = at or datetime.now(timezone.utc)
    return fetch_all(
        """
        SELECT
          id,
          source_id,
          name,
          category,
          CASE WHEN geom IS NULL THEN NULL ELSE ST_AsGeoJSON(geom)::json END AS geometry,
          active_from,
          active_to,
          source,
          source_confidence,
          observed_at,
          raw_reference
        FROM airspace_overlays
        WHERE COALESCE(active_to, NOW() + interval '1 day') >= :reference_time
          AND COALESCE(active_from, NOW() - interval '1 day') <= :reference_time
        ORDER BY active_from NULLS LAST, name ASC
        """,
        {"reference_time": reference_time.isoformat()},
    )


def _history_query(table_name: str, entity_kind: str, since: datetime, until: datetime, bbox: str | None, entity_id: str | None, limit: int) -> dict[str, Any]:
    bbox_clause, bbox_params = _build_envelope_clause(bbox)
    entity_clause = "AND entity_id = :entity_id" if entity_id else ""
    params: dict[str, Any] = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "limit": limit,
        **bbox_params,
    }
    if entity_id:
        params["entity_id"] = entity_id

    rows = fetch_all(
        f"""
        SELECT
          entity_id,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          observed_at,
          altitude_m,
          heading_deg,
          velocity_kts,
          speed_kts,
          callsign,
          icao24,
          vessel_name,
          mmsi
        FROM {table_name}
        WHERE observed_at BETWEEN :since AND :until
        {entity_clause}
        {bbox_clause}
        ORDER BY entity_id, observed_at ASC
        LIMIT :limit
        """,
        params,
    )

    tracks: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = row.get("callsign") or row.get("icao24") or row.get("vessel_name") or row.get("mmsi") or row["entity_id"]
        track = tracks.setdefault(
            row["entity_id"],
            {
                "entity_id": row["entity_id"],
                "label": label,
                "entity_kind": entity_kind,
                "points": [],
            },
        )
        track["points"].append(
            {
                "lat": row["lat"],
                "lon": row["lon"],
                "observed_at": row["observed_at"],
                "altitude_m": row.get("altitude_m"),
                "heading_deg": row.get("heading_deg"),
                "velocity_kts": row.get("velocity_kts"),
                "speed_kts": row.get("speed_kts"),
            }
        )

    return {
        "window": {"from": since, "to": until},
        "tracks": list(tracks.values()),
    }


def aircraft_history(since: datetime, until: datetime, bbox: str | None, entity_id: str | None, limit: int) -> dict[str, Any]:
    return _history_query("aircraft_history", "aircraft", since, until, bbox, entity_id, limit)


def vessel_history(
    since: datetime,
    until: datetime,
    bbox: str | None,
    entity_id: str | None,
    limit: int,
    *,
    mmsi: str | None = None,
    imo: str | None = None,
    vessel_name: str | None = None,
    source: str | None = None,
    vessel_type: str | None = None,
    flag: str | None = None,
) -> dict[str, Any]:
    bbox_clause, bbox_params = _build_vessel_filters(
        bbox,
        mmsi=mmsi or (entity_id.replace("vessel:", "", 1) if entity_id and entity_id.startswith("vessel:") else None),
        imo=imo,
        vessel_name=vessel_name,
        source=source,
        vessel_type=vessel_type,
        flag=flag,
    )
    entity_clause = "AND entity_id = :entity_id" if entity_id else ""
    params: dict[str, Any] = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "limit": limit,
        **bbox_params,
    }
    if entity_id:
        params["entity_id"] = entity_id

    rows = fetch_all(
        f"""
        SELECT
          entity_id,
          mmsi,
          imo,
          vessel_name,
          callsign,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          observed_at,
          heading_deg,
          course_deg,
          speed_kts,
          nav_status,
          source,
          stale
        FROM vessels_history
        WHERE observed_at BETWEEN :since AND :until
        {entity_clause}
        {bbox_clause}
        ORDER BY entity_id, observed_at ASC
        LIMIT :limit
        """,
        params,
    )

    tracks: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = row.get("vessel_name") or row.get("callsign") or row.get("mmsi") or row["entity_id"]
        track = tracks.setdefault(
            row["entity_id"],
            {
                "entity_id": row["entity_id"],
                "label": label,
                "entity_kind": "vessel",
                "points": [],
            },
        )
        track["points"].append(
            {
                "lat": row["lat"],
                "lon": row["lon"],
                "observed_at": row["observed_at"],
                "heading_deg": row.get("heading_deg"),
                "speed_kts": row.get("speed_kts"),
                "confidence": None if row.get("stale") is None else (0.35 if row.get("stale") else 0.9),
            }
        )

    return {"window": {"from": since, "to": until}, "tracks": list(tracks.values())}


def get_vessel(mmsi: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT
          id,
          mmsi,
          imo,
          vessel_name,
          callsign,
          vessel_type,
          flag,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          heading_deg,
          course_deg,
          speed_kts,
          nav_status,
          destination,
          draught_m,
          source,
          source_record_id,
          source_confidence,
          merged_confidence,
          observed_at,
          last_ingested_at,
          stale,
          raw_reference
        FROM vessels_current
        WHERE mmsi = :mmsi
        """,
        {"mmsi": mmsi},
    )


def search_vessels(
    *,
    q: str | None = None,
    bbox: str | None = None,
    limit: int = 25,
    source: str | None = None,
    vessel_type: str | None = None,
    flag: str | None = None,
) -> list[dict[str, Any]]:
    where_clause, params = _build_vessel_filters(
        bbox,
        source=source,
        vessel_type=vessel_type,
        flag=flag,
    )
    search_clause = ""
    if q:
        params["query"] = f"%{q.lower()}%"
        search_clause = """
        AND (
          LOWER(mmsi) LIKE :query
          OR LOWER(COALESCE(imo, '')) LIKE :query
          OR LOWER(COALESCE(vessel_name, '')) LIKE :query
          OR LOWER(COALESCE(callsign, '')) LIKE :query
        )
        """
    return fetch_all(
        f"""
        SELECT
          id,
          mmsi,
          imo,
          vessel_name,
          callsign,
          vessel_type,
          flag,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          heading_deg,
          course_deg,
          speed_kts,
          nav_status,
          destination,
          draught_m,
          source,
          source_record_id,
          source_confidence,
          merged_confidence,
          observed_at,
          last_ingested_at,
          stale,
          raw_reference
        FROM vessels_current
        WHERE 1 = 1
        {where_clause}
        {search_clause}
        ORDER BY observed_at DESC
        LIMIT :limit
        """,
        {**params, "limit": limit},
    )


def list_vessel_source_health() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT
          provider_name,
          ingest_mode,
          enabled,
          priority,
          health_state,
          last_success,
          last_attempt,
          valid_message_count,
          error_count,
          stall_threshold_seconds,
          last_error,
          updated_at
        FROM vessel_source_health
        ORDER BY priority DESC, provider_name ASC
        """
    )


def list_vessel_providers() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT
          provider_name,
          ingest_mode,
          priority,
          enabled,
          NULL::text AS description
        FROM vessel_source_health
        ORDER BY priority DESC, provider_name ASC
        """
    )


def vessel_presence_overlay(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    provider: str | None = None,
    limit: int = 250,
) -> list[dict[str, Any]]:
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if since:
        clauses.append("AND observed_to >= :since")
        params["since"] = since.isoformat()
    if until:
        clauses.append("AND observed_from <= :until")
        params["until"] = until.isoformat()
    if provider:
        clauses.append("AND LOWER(provider) = :provider")
        params["provider"] = provider.lower()

    return fetch_all(
        f"""
        SELECT
          overlay_id,
          provider,
          dataset,
          label,
          category,
          ST_AsGeoJSON(geom)::json AS geometry,
          density,
          observed_from,
          observed_to,
          source,
          source_confidence,
          observed_at,
          raw_reference
        FROM vessel_presence_overlays
        WHERE 1 = 1
        {' '.join(clauses)}
        ORDER BY observed_to DESC
        LIMIT :limit
        """,
        params,
    )


def satellite_history(
    since: datetime,
    until: datetime,
    bbox: str | None,
    entity_id: str | None,
    limit: int,
    *,
    norad_cat_id: str | None = None,
) -> dict[str, Any]:
    bbox_clause, bbox_params = _build_envelope_clause(bbox)
    norad_cat_id = norad_cat_id or (entity_id.replace("satellite:", "", 1) if entity_id and entity_id.startswith("satellite:") else None)
    clauses = [bbox_clause]
    params: dict[str, Any] = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "limit": limit,
        **bbox_params,
    }
    if entity_id:
        clauses.append("AND entity_id = :entity_id")
        params["entity_id"] = entity_id
    if norad_cat_id:
        clauses.append("AND norad_cat_id = :norad_cat_id")
        params["norad_cat_id"] = norad_cat_id

    rows = fetch_all(
        f"""
        SELECT
          entity_id,
          norad_cat_id,
          computed_lat AS lat,
          computed_lon AS lon,
          observed_at,
          computed_alt_km,
          computed_velocity_kms,
          playback_confidence,
          name
        FROM satellites_history
        WHERE observed_at BETWEEN :since AND :until
        {' '.join(filter(None, clauses))}
        ORDER BY entity_id, observed_at ASC
        LIMIT :limit
        """,
        params,
    )

    tracks: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = row.get("name") or row.get("norad_cat_id") or row["entity_id"]
        track = tracks.setdefault(
            row["entity_id"],
            {
                "entity_id": row["entity_id"],
                "label": label,
                "entity_kind": "satellite",
                "points": [],
            },
        )
        track["points"].append(
            {
                "lat": row["lat"],
                "lon": row["lon"],
                "observed_at": row["observed_at"],
                "alt_km": row.get("computed_alt_km"),
                "velocity_kms": row.get("computed_velocity_kms"),
                "confidence": row.get("playback_confidence"),
            }
        )

    if tracks:
        return {
            "window": {"from": since, "to": until},
            "tracks": list(tracks.values()),
        }

    if not norad_cat_id:
        return {
            "window": {"from": since, "to": until},
            "tracks": [],
        }

    snapshot_rows = fetch_all(
        """
        SELECT
          sc.id,
          sc.norad_cat_id,
          sc.international_designator,
          sc.name,
          sc.object_type,
          sc.group_name,
          sc.orbit_class,
          sc.source,
          sc.tle_line1,
          sc.tle_line2,
          sc.epoch,
          sc.inclination_deg,
          sc.eccentricity,
          sc.mean_motion,
          sc.raan_deg,
          sc.arg_perigee_deg,
          sc.mean_anomaly_deg,
          sc.bstar,
          sc.source_confidence,
          ss.observed_at,
          sc.raw_reference,
          COALESCE(ss.raw_payload, sc.raw_payload) AS raw_payload
        FROM satellites_catalog sc
        LEFT JOIN satellite_source_snapshots ss ON ss.norad_cat_id = sc.norad_cat_id
        WHERE sc.norad_cat_id = :norad_cat_id
        ORDER BY ss.observed_at DESC NULLS LAST
        LIMIT 4
        """,
        {"norad_cat_id": norad_cat_id},
    )
    if not snapshot_rows:
        return {
            "window": {"from": since, "to": until},
            "tracks": [],
        }

    playback_step_seconds = max(60, int((until - since).total_seconds() / 48) if until > since else 60)
    points = [
        point.to_dict()
        for point in playback_from_rows(snapshot_rows, since=since, until=until, step_seconds=playback_step_seconds)
    ]

    return {
        "window": {"from": since, "to": until},
        "tracks": [
            {
                "entity_id": f"satellite:{norad_cat_id}",
                "label": snapshot_rows[0]["name"],
                "entity_kind": "satellite",
                "points": points,
            }
        ],
    }


def satellite_orbit(norad_cat_id: str, *, start: datetime, minutes_ahead: int, step_seconds: int) -> dict[str, Any] | None:
    row = fetch_one(
        """
        SELECT
          id,
          norad_cat_id,
          international_designator,
          name,
          object_type,
          group_name,
          orbit_class,
          source,
          tle_line1,
          tle_line2,
          epoch,
          inclination_deg,
          eccentricity,
          mean_motion,
          raan_deg,
          arg_perigee_deg,
          mean_anomaly_deg,
          bstar,
          source_confidence,
          observed_at,
          raw_reference,
          raw_payload
        FROM satellites_catalog
        WHERE norad_cat_id = :norad_cat_id
        """,
        {"norad_cat_id": norad_cat_id},
    )
    if not row:
        return None

    return {
        "norad_cat_id": norad_cat_id,
        "source": row["source"],
        "epoch": row.get("epoch"),
        "points": [point.to_dict() for point in orbit_path_from_row(row, start=start, minutes_ahead=minutes_ahead, step_seconds=step_seconds)],
    }


def satellite_search(query: str, group: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    like = f"%{query.lower()}%"
    params: dict[str, Any] = {"like": like, "limit": limit}
    group_clause = ""
    if group:
        group_clause = "AND LOWER(COALESCE(group_name, '')) = :group_name"
        params["group_name"] = group.lower()
    return fetch_all(
        f"""
        SELECT
          'satellite' AS kind,
          id,
          name AS label,
          COALESCE(group_name, norad_cat_id) AS subtitle,
          source,
          observed_at,
          json_build_object('lat', computed_lat, 'lon', computed_lon) AS location
        FROM satellites_current
        WHERE (
          LOWER(name) LIKE :like
          OR LOWER(norad_cat_id) LIKE :like
          OR LOWER(COALESCE(international_designator, '')) LIKE :like
        )
        {group_clause}
        ORDER BY observed_at DESC
        LIMIT :limit
        """,
        params,
    )


def _group_entities(rows: list[dict[str, Any]], key_name: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key_name])].append(row)
    return grouped


def list_cases() -> list[dict[str, Any]]:
    cases = fetch_all("SELECT id, title, summary, status, priority, source, created_at, updated_at FROM cases ORDER BY updated_at DESC")
    entities = fetch_all("SELECT case_id, entity_kind, entity_id, role FROM case_entities ORDER BY created_at ASC")
    grouped = _group_entities(entities, "case_id")
    for item in cases:
        item["entities"] = grouped.get(str(item["id"]), [])
    return cases


def get_case(case_id: UUID) -> dict[str, Any] | None:
    records = [item for item in list_cases() if str(item["id"]) == str(case_id)]
    return records[0] if records else None


def create_case(payload: CaseCreate) -> dict[str, Any]:
    record = fetch_one(
        """
        INSERT INTO cases (title, summary, status, priority, source)
        VALUES (:title, :summary, :status, :priority, :source)
        RETURNING id, title, summary, status, priority, source, created_at, updated_at
        """,
        payload.model_dump(),
    )
    assert record is not None
    for entity in payload.entities:
        execute(
            """
            INSERT INTO case_entities (case_id, entity_kind, entity_id, role)
            VALUES (:case_id, :entity_kind, :entity_id, :role)
            """,
            {"case_id": record["id"], **entity.model_dump()},
        )
    return get_case(UUID(str(record["id"]))) or record


def update_case(case_id: UUID, payload: CaseUpdate) -> dict[str, Any] | None:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return get_case(case_id)
    entity_updates = updates.pop("entities", None)
    if updates:
        assignments = [f"{column} = :{column}" for column in updates]
        execute(
            f"UPDATE cases SET {', '.join(assignments)}, updated_at = NOW() WHERE id = :case_id",
            {**updates, "case_id": str(case_id)},
        )
    if entity_updates is not None:
        execute("DELETE FROM case_entities WHERE case_id = :case_id", {"case_id": str(case_id)})
        for entity in entity_updates:
            model = entity if isinstance(entity, CaseEntity) else CaseEntity.model_validate(entity)
            execute(
                """
                INSERT INTO case_entities (case_id, entity_kind, entity_id, role)
                VALUES (:case_id, :entity_kind, :entity_id, :role)
                """,
                {"case_id": str(case_id), **model.model_dump()},
            )
    return get_case(case_id)


def delete_case(case_id: UUID) -> None:
    execute("DELETE FROM cases WHERE id = :case_id", {"case_id": str(case_id)})


def list_notes() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, case_id, entity_kind, entity_id, body, author, source, created_at, updated_at
        FROM notes
        ORDER BY updated_at DESC
        """
    )


def create_note(payload: NoteCreate) -> dict[str, Any]:
    return fetch_one(
        """
        INSERT INTO notes (case_id, entity_kind, entity_id, body, author, source)
        VALUES (:case_id, :entity_kind, :entity_id, :body, :author, :source)
        RETURNING id, case_id, entity_kind, entity_id, body, author, source, created_at, updated_at
        """,
        payload.model_dump(),
    ) or {}


def update_note(note_id: UUID, payload: NoteUpdate) -> dict[str, Any] | None:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return fetch_one("SELECT * FROM notes WHERE id = :note_id", {"note_id": str(note_id)})
    assignments = [f"{column} = :{column}" for column in updates]
    execute(
        f"UPDATE notes SET {', '.join(assignments)}, updated_at = NOW() WHERE id = :note_id",
        {**updates, "note_id": str(note_id)},
    )
    return fetch_one(
        """
        SELECT id, case_id, entity_kind, entity_id, body, author, source, created_at, updated_at
        FROM notes
        WHERE id = :note_id
        """,
        {"note_id": str(note_id)},
    )


def delete_note(note_id: UUID) -> None:
    execute("DELETE FROM notes WHERE id = :note_id", {"note_id": str(note_id)})


def list_tags() -> list[dict[str, Any]]:
    return fetch_all("SELECT id, name, color, source, created_at, updated_at FROM tags ORDER BY name ASC")


def create_tag(payload: TagCreate) -> dict[str, Any]:
    return fetch_one(
        """
        INSERT INTO tags (name, color, source)
        VALUES (:name, :color, :source)
        RETURNING id, name, color, source, created_at, updated_at
        """,
        payload.model_dump(),
    ) or {}


def update_tag(tag_id: UUID, payload: TagUpdate) -> dict[str, Any] | None:
    updates = payload.model_dump(exclude_none=True)
    if updates:
        assignments = [f"{column} = :{column}" for column in updates]
        execute(
            f"UPDATE tags SET {', '.join(assignments)}, updated_at = NOW() WHERE id = :tag_id",
            {**updates, "tag_id": str(tag_id)},
        )
    return fetch_one("SELECT id, name, color, source, created_at, updated_at FROM tags WHERE id = :tag_id", {"tag_id": str(tag_id)})


def delete_tag(tag_id: UUID) -> None:
    execute("DELETE FROM tags WHERE id = :tag_id", {"tag_id": str(tag_id)})


def assign_tag(tag_id: UUID, payload: TagAssignmentCreate) -> dict[str, Any]:
    return fetch_one(
        """
        INSERT INTO entity_tags (tag_id, case_id, entity_kind, entity_id)
        VALUES (:tag_id, :case_id, :entity_kind, :entity_id)
        RETURNING id, tag_id, case_id, entity_kind, entity_id, created_at
        """,
        {"tag_id": str(tag_id), **payload.model_dump()},
    ) or {}


def unassign_tag(assignment_id: UUID) -> None:
    execute("DELETE FROM entity_tags WHERE id = :assignment_id", {"assignment_id": str(assignment_id)})


def list_watchlists() -> list[dict[str, Any]]:
    watchlists = fetch_all(
        "SELECT id, name, description, color, source, created_at, updated_at FROM watchlists ORDER BY updated_at DESC"
    )
    entities = fetch_all(
        "SELECT id, watchlist_id, entity_kind, entity_id, label, created_at FROM watchlist_entities ORDER BY created_at ASC"
    )
    grouped = _group_entities(entities, "watchlist_id")
    for item in watchlists:
        item["entities"] = grouped.get(str(item["id"]), [])
    return watchlists


def get_watchlist(watchlist_id: UUID) -> dict[str, Any] | None:
    records = [item for item in list_watchlists() if str(item["id"]) == str(watchlist_id)]
    return records[0] if records else None


def create_watchlist(payload: WatchlistCreate) -> dict[str, Any]:
    record = fetch_one(
        """
        INSERT INTO watchlists (name, description, color, source)
        VALUES (:name, :description, :color, :source)
        RETURNING id, name, description, color, source, created_at, updated_at
        """,
        payload.model_dump(),
    )
    assert record is not None
    record["entities"] = []
    return record


def update_watchlist(watchlist_id: UUID, payload: WatchlistUpdate) -> dict[str, Any] | None:
    updates = payload.model_dump(exclude_none=True)
    if updates:
        assignments = [f"{column} = :{column}" for column in updates]
        execute(
            f"UPDATE watchlists SET {', '.join(assignments)}, updated_at = NOW() WHERE id = :watchlist_id",
            {**updates, "watchlist_id": str(watchlist_id)},
        )
    return get_watchlist(watchlist_id)


def delete_watchlist(watchlist_id: UUID) -> None:
    execute("DELETE FROM watchlists WHERE id = :watchlist_id", {"watchlist_id": str(watchlist_id)})


def add_watchlist_entity(watchlist_id: UUID, payload: WatchlistEntityCreate) -> dict[str, Any]:
    return fetch_one(
        """
        INSERT INTO watchlist_entities (watchlist_id, entity_kind, entity_id, label)
        VALUES (:watchlist_id, :entity_kind, :entity_id, :label)
        RETURNING id, entity_kind, entity_id, label, created_at
        """,
        {"watchlist_id": str(watchlist_id), **payload.model_dump()},
    ) or {}


def remove_watchlist_entity(entity_row_id: UUID) -> None:
    execute("DELETE FROM watchlist_entities WHERE id = :entity_row_id", {"entity_row_id": str(entity_row_id)})


def list_saved_views() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, name, description, center_lat, center_lon, center_altitude, heading_deg, pitch_deg, roll_deg, layers, created_at, updated_at
        FROM saved_views
        ORDER BY updated_at DESC
        """
    )


def create_saved_view(payload: SavedViewCreate) -> dict[str, Any]:
    return fetch_one(
        """
        INSERT INTO saved_views (name, description, center_lat, center_lon, center_altitude, heading_deg, pitch_deg, roll_deg, layers)
        VALUES (:name, :description, :center_lat, :center_lon, :center_altitude, :heading_deg, :pitch_deg, :roll_deg, CAST(:layers AS jsonb))
        RETURNING id, name, description, center_lat, center_lon, center_altitude, heading_deg, pitch_deg, roll_deg, layers, created_at, updated_at
        """,
        {**payload.model_dump(), "layers": json.dumps(payload.layers)},
    ) or {}


def update_saved_view(view_id: UUID, payload: SavedViewUpdate) -> dict[str, Any] | None:
    updates = payload.model_dump(exclude_none=True)
    if "layers" in updates:
        updates["layers"] = json.dumps(updates["layers"])
        assignments = [f"{column} = CAST(:{column} AS jsonb)" if column == "layers" else f"{column} = :{column}" for column in updates]
    else:
        assignments = [f"{column} = :{column}" for column in updates]
    if updates:
        execute(
            f"UPDATE saved_views SET {', '.join(assignments)}, updated_at = NOW() WHERE id = :view_id",
            {**updates, "view_id": str(view_id)},
        )
    return fetch_one(
        """
        SELECT id, name, description, center_lat, center_lon, center_altitude, heading_deg, pitch_deg, roll_deg, layers, created_at, updated_at
        FROM saved_views
        WHERE id = :view_id
        """,
        {"view_id": str(view_id)},
    )


def delete_saved_view(view_id: UUID) -> None:
    execute("DELETE FROM saved_views WHERE id = :view_id", {"view_id": str(view_id)})


def search(query: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    coordinate_match = COORDINATE_RE.match(query)
    if coordinate_match:
        lat = float(coordinate_match.group(1))
        lon = float(coordinate_match.group(2))
        results.append(
            {
                "kind": "coordinate",
                "id": f"coord:{lat}:{lon}",
                "label": f"{lat:.4f}, {lon:.4f}",
                "subtitle": "Direct coordinate lookup",
                "location": {"lat": lat, "lon": lon},
            }
        )
        nearby = fetch_all(
            """
            SELECT id, callsign AS label, source, observed_at, ST_Y(geom) AS lat, ST_X(geom) AS lon
            FROM aircraft_current
            WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 75000)
            ORDER BY observed_at DESC
            LIMIT 5
            """,
            {"lat": lat, "lon": lon},
        )
        results.extend(
            {
                "kind": "aircraft",
                "id": row["id"],
                "label": row.get("label") or row["id"],
                "subtitle": "Aircraft near coordinate",
                "source": row.get("source"),
                "observed_at": row.get("observed_at"),
                "location": {"lat": row["lat"], "lon": row["lon"]},
            }
            for row in nearby
        )
        nearby_satellites = fetch_all(
            """
            SELECT id, name AS label, source, observed_at, computed_lat AS lat, computed_lon AS lon
            FROM satellites_current
            WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 175000)
            ORDER BY observed_at DESC
            LIMIT 5
            """,
            {"lat": lat, "lon": lon},
        )
        results.extend(
            {
                "kind": "satellite",
                "id": row["id"],
                "label": row.get("label") or row["id"],
                "subtitle": "Satellite near coordinate",
                "source": row.get("source"),
                "observed_at": row.get("observed_at"),
                "location": {"lat": row["lat"], "lon": row["lon"]},
            }
            for row in nearby_satellites
        )

    like = f"%{query.lower()}%"
    results.extend(
        fetch_all(
            """
            SELECT 'aircraft' AS kind, id, COALESCE(NULLIF(TRIM(callsign), ''), icao24) AS label, icao24 AS subtitle, source, observed_at,
            json_build_object('lat', ST_Y(geom), 'lon', ST_X(geom)) AS location
            FROM aircraft_current
            WHERE LOWER(COALESCE(callsign, '')) LIKE :like OR LOWER(icao24) LIKE :like
            ORDER BY observed_at DESC
            LIMIT 10
            """,
            {"like": like},
        )
    )
    results.extend(
        fetch_all(
            """
            SELECT 'vessel' AS kind, id, COALESCE(NULLIF(TRIM(vessel_name), ''), NULLIF(TRIM(callsign), ''), mmsi) AS label, mmsi AS subtitle, source, observed_at,
            json_build_object('lat', ST_Y(geom), 'lon', ST_X(geom)) AS location
            FROM vessels_current
            WHERE LOWER(COALESCE(vessel_name, '')) LIKE :like
               OR LOWER(mmsi) LIKE :like
               OR LOWER(COALESCE(imo, '')) LIKE :like
               OR LOWER(COALESCE(callsign, '')) LIKE :like
            ORDER BY observed_at DESC
            LIMIT 10
            """,
            {"like": like},
        )
    )
    results.extend(
        fetch_all(
            """
            SELECT 'satellite' AS kind, id, name AS label,
            COALESCE(group_name, norad_cat_id) AS subtitle, source, observed_at,
            json_build_object('lat', computed_lat, 'lon', computed_lon) AS location
            FROM satellites_current
            WHERE LOWER(name) LIKE :like
               OR LOWER(norad_cat_id) LIKE :like
               OR LOWER(COALESCE(international_designator, '')) LIKE :like
               OR LOWER(COALESCE(group_name, '')) LIKE :like
            ORDER BY observed_at DESC
            LIMIT 12
            """,
            {"like": like},
        )
    )
    results.extend(
        fetch_all(
            """
            SELECT 'airspace' AS kind, id, name AS label, category AS subtitle, source, observed_at, NULL AS location
            FROM airspace_overlays
            WHERE LOWER(name) LIKE :like OR LOWER(category) LIKE :like
            ORDER BY observed_at DESC
            LIMIT 10
            """,
            {"like": like},
        )
    )
    results.extend(
        fetch_all(
            """
            SELECT 'case' AS kind, id::text AS id, title AS label, summary AS subtitle, source, updated_at AS observed_at, NULL AS location
            FROM cases
            WHERE LOWER(title) LIKE :like OR LOWER(COALESCE(summary, '')) LIKE :like
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            {"like": like},
        )
    )
    results.extend(
        fetch_all(
            """
            SELECT 'watchlist' AS kind, id::text AS id, name AS label, description AS subtitle, source, updated_at AS observed_at, NULL AS location
            FROM watchlists
            WHERE LOWER(name) LIKE :like OR LOWER(COALESCE(description, '')) LIKE :like
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            {"like": like},
        )
    )

    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in results:
        key = (str(item["kind"]), str(item["id"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:25]
