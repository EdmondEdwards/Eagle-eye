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


def list_vessels_current(bbox: str | None, limit: int) -> list[dict[str, Any]]:
    bbox_clause, bbox_params = _build_envelope_clause(bbox)
    return fetch_all(
        f"""
        SELECT
          id,
          mmsi,
          imo,
          vessel_name,
          vessel_type,
          flag,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          heading_deg,
          speed_kts,
          source,
          source_confidence,
          observed_at,
          raw_reference
        FROM vessels_current
        WHERE 1 = 1
        {bbox_clause}
        ORDER BY observed_at DESC
        LIMIT :limit
        """,
        {**bbox_params, "limit": limit},
    )


def list_satellites_current(bbox: str | None, limit: int) -> list[dict[str, Any]]:
    bbox_clause, bbox_params = _build_envelope_clause(bbox)
    return fetch_all(
        f"""
        SELECT
          id,
          catalog_number,
          satellite_name,
          international_designator,
          group_name,
          orbit_class,
          ST_Y(geom) AS lat,
          ST_X(geom) AS lon,
          altitude_m,
          velocity_kts,
          tle_epoch,
          source,
          source_confidence,
          observed_at,
          raw_reference
        FROM satellites_current
        WHERE 1 = 1
        {bbox_clause}
        ORDER BY observed_at DESC, satellite_name ASC
        LIMIT :limit
        """,
        {**bbox_params, "limit": limit},
    )


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


def vessel_history(since: datetime, until: datetime, bbox: str | None, entity_id: str | None, limit: int) -> dict[str, Any]:
    return _history_query("vessels_history", "vessel", since, until, bbox, entity_id, limit)


def satellite_history(since: datetime, until: datetime, bbox: str | None, entity_id: str | None, limit: int) -> dict[str, Any]:
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
          velocity_kts,
          satellite_name,
          catalog_number
        FROM satellites_history
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
        label = row.get("satellite_name") or row.get("catalog_number") or row["entity_id"]
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
                "altitude_m": row.get("altitude_m"),
                "velocity_kts": row.get("velocity_kts"),
            }
        )

    return {
        "window": {"from": since, "to": until},
        "tracks": list(tracks.values()),
    }


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
            SELECT id, satellite_name AS label, source, observed_at, ST_Y(geom) AS lat, ST_X(geom) AS lon
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
            SELECT 'vessel' AS kind, id, COALESCE(NULLIF(TRIM(vessel_name), ''), mmsi) AS label, mmsi AS subtitle, source, observed_at,
            json_build_object('lat', ST_Y(geom), 'lon', ST_X(geom)) AS location
            FROM vessels_current
            WHERE LOWER(COALESCE(vessel_name, '')) LIKE :like OR LOWER(mmsi) LIKE :like OR LOWER(COALESCE(imo, '')) LIKE :like
            ORDER BY observed_at DESC
            LIMIT 10
            """,
            {"like": like},
        )
    )
    results.extend(
        fetch_all(
            """
            SELECT 'satellite' AS kind, id, satellite_name AS label,
            COALESCE(group_name, catalog_number) AS subtitle, source, observed_at,
            json_build_object('lat', ST_Y(geom), 'lon', ST_X(geom)) AS location
            FROM satellites_current
            WHERE LOWER(satellite_name) LIKE :like
               OR LOWER(catalog_number) LIKE :like
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
