from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from . import repositories as repo
from .schemas import (
    AirspaceOverlay,
    Aircraft,
    CaseRecord,
    CaseCreate,
    CaseUpdate,
    NoteCreate,
    NoteRecord,
    NoteUpdate,
    OrbitPathResponse,
    SavedViewCreate,
    SavedViewRecord,
    SavedViewUpdate,
    SearchResult,
    MaritimeProviderDescriptor,
    Satellite,
    SatelliteCatalogRecord,
    TagAssignment,
    TagAssignmentCreate,
    TagCreate,
    TagRecord,
    TagUpdate,
    TimelineResponse,
    Vessel,
    VesselPresenceOverlay,
    VesselSourceHealth,
    WatchlistCreate,
    WatchlistEntity,
    WatchlistEntityCreate,
    WatchlistRecord,
    WatchlistUpdate,
)

router = APIRouter()


def _default_since() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=1)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/api/aircraft/current", response_model=list[Aircraft])
def aircraft_current(bbox: str | None = Query(default=None), limit: int = Query(default=5000, le=10000)) -> list[dict]:
    return repo.list_aircraft_current(bbox, limit)


@router.get("/api/aircraft/history", response_model=TimelineResponse)
def aircraft_history(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    bbox: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=20000, le=100000),
) -> dict:
    since = since or _default_since()
    until = until or datetime.now(timezone.utc)
    return repo.aircraft_history(since, until, bbox, entity_id, limit)


@router.get("/api/vessels/current", response_model=list[Vessel])
def vessels_current(
    bbox: str | None = Query(default=None),
    limit: int = Query(default=5000, le=10000),
    mmsi: str | None = Query(default=None),
    imo: str | None = Query(default=None),
    vessel_name: str | None = Query(default=None),
    source: str | None = Query(default=None),
    vessel_type: str | None = Query(default=None),
    flag: str | None = Query(default=None),
) -> list[dict]:
    return repo.list_vessels_current(
        bbox,
        limit,
        mmsi=mmsi,
        imo=imo,
        vessel_name=vessel_name,
        source=source,
        vessel_type=vessel_type,
        flag=flag,
    )


@router.get("/api/vessels/history", response_model=TimelineResponse)
def vessels_history(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    bbox: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    mmsi: str | None = Query(default=None),
    imo: str | None = Query(default=None),
    vessel_name: str | None = Query(default=None),
    source: str | None = Query(default=None),
    vessel_type: str | None = Query(default=None),
    flag: str | None = Query(default=None),
    limit: int = Query(default=20000, le=100000),
) -> dict:
    since = since or _default_since()
    until = until or datetime.now(timezone.utc)
    return repo.vessel_history(
        since,
        until,
        bbox,
        entity_id,
        limit,
        mmsi=mmsi,
        imo=imo,
        vessel_name=vessel_name,
        source=source,
        vessel_type=vessel_type,
        flag=flag,
    )


@router.get("/api/vessels/search", response_model=list[Vessel])
def vessels_search(
    q: str | None = Query(default=None),
    bbox: str | None = Query(default=None),
    limit: int = Query(default=25, le=250),
    source: str | None = Query(default=None),
    vessel_type: str | None = Query(default=None),
    flag: str | None = Query(default=None),
) -> list[dict]:
    return repo.search_vessels(q=q, bbox=bbox, limit=limit, source=source, vessel_type=vessel_type, flag=flag)


@router.get("/api/vessels/source-health", response_model=list[VesselSourceHealth])
def vessels_source_health() -> list[dict]:
    return repo.list_vessel_source_health()


@router.get("/api/vessels/providers", response_model=list[MaritimeProviderDescriptor])
def vessels_providers() -> list[dict]:
    return repo.list_vessel_providers()


@router.get("/api/vessels/presence-overlay", response_model=list[VesselPresenceOverlay])
def vessels_presence_overlay(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    provider: str | None = Query(default=None),
    limit: int = Query(default=250, le=5000),
) -> list[dict]:
    return repo.vessel_presence_overlay(since=since, until=until, provider=provider, limit=limit)


@router.get("/api/vessels/{mmsi}", response_model=Vessel)
def get_vessel(mmsi: str) -> dict:
    record = repo.get_vessel(mmsi)
    if not record:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return record


@router.get("/api/satellites/current", response_model=list[Satellite])
def satellites_current(
    bbox: str | None = Query(default=None),
    limit: int = Query(default=2000, le=5000),
    norad_cat_id: str | None = Query(default=None),
    name: str | None = Query(default=None),
    group: str | None = Query(default=None),
) -> list[dict]:
    return repo.list_satellites_current(bbox, limit, norad_cat_id=norad_cat_id, name=name, group=group)


@router.get("/api/satellites/catalog", response_model=list[SatelliteCatalogRecord])
def satellites_catalog(
    limit: int = Query(default=500, le=5000),
    norad_cat_id: str | None = Query(default=None),
    name: str | None = Query(default=None),
    group: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    orbit_class: str | None = Query(default=None),
) -> list[dict]:
    return repo.list_satellites_catalog(
        limit=limit,
        norad_cat_id=norad_cat_id,
        name=name,
        group=group,
        object_type=object_type,
        orbit_class=orbit_class,
    )


@router.get("/api/satellites/history", response_model=TimelineResponse)
def satellites_history(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    bbox: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    norad_cat_id: str | None = Query(default=None),
    limit: int = Query(default=30000, le=120000),
) -> dict:
    since = since or _default_since()
    until = until or datetime.now(timezone.utc)
    return repo.satellite_history(since, until, bbox, entity_id, limit, norad_cat_id=norad_cat_id)


@router.get("/api/satellites/search", response_model=list[SearchResult])
def satellites_search(q: str = Query(..., min_length=1), group: str | None = Query(default=None), limit: int = Query(default=20, le=100)) -> list[dict]:
    return repo.satellite_search(q, group, limit)


@router.get("/api/satellites/{norad_cat_id}", response_model=Satellite)
def get_satellite(norad_cat_id: str) -> dict:
    record = repo.get_satellite(norad_cat_id)
    if not record:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return record


@router.get("/api/satellites/{norad_cat_id}/orbit", response_model=OrbitPathResponse)
def satellite_orbit(
    norad_cat_id: str,
    start: datetime | None = Query(default=None),
    minutes_ahead: int = Query(default=90, ge=15, le=24 * 60),
    step_seconds: int = Query(default=120, ge=15, le=3600),
) -> dict:
    record = repo.satellite_orbit(
        norad_cat_id,
        start=start or datetime.now(timezone.utc),
        minutes_ahead=minutes_ahead,
        step_seconds=step_seconds,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return record


@router.get("/api/airspace/current", response_model=list[AirspaceOverlay])
def airspace_current(at: datetime | None = Query(default=None)) -> list[dict]:
    return repo.list_airspace_current(at)


@router.get("/api/cases", response_model=list[CaseRecord])
def list_cases() -> list[dict]:
    return repo.list_cases()


@router.post("/api/cases", response_model=CaseRecord)
def create_case(payload: CaseCreate) -> dict:
    return repo.create_case(payload)


@router.get("/api/cases/{case_id}", response_model=CaseRecord)
def get_case(case_id: UUID) -> dict:
    record = repo.get_case(case_id)
    if not record:
        raise HTTPException(status_code=404, detail="Case not found")
    return record


@router.put("/api/cases/{case_id}", response_model=CaseRecord)
def update_case(case_id: UUID, payload: CaseUpdate) -> dict:
    record = repo.update_case(case_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="Case not found")
    return record


@router.delete("/api/cases/{case_id}", status_code=204, response_class=Response)
def delete_case(case_id: UUID) -> Response:
    repo.delete_case(case_id)
    return Response(status_code=204)


@router.get("/api/watchlists", response_model=list[WatchlistRecord])
def list_watchlists() -> list[dict]:
    return repo.list_watchlists()


@router.post("/api/watchlists", response_model=WatchlistRecord)
def create_watchlist(payload: WatchlistCreate) -> dict:
    return repo.create_watchlist(payload)


@router.put("/api/watchlists/{watchlist_id}", response_model=WatchlistRecord)
def update_watchlist(watchlist_id: UUID, payload: WatchlistUpdate) -> dict:
    record = repo.update_watchlist(watchlist_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return record


@router.delete("/api/watchlists/{watchlist_id}", status_code=204, response_class=Response)
def delete_watchlist(watchlist_id: UUID) -> Response:
    repo.delete_watchlist(watchlist_id)
    return Response(status_code=204)


@router.post("/api/watchlists/{watchlist_id}/entities", response_model=WatchlistEntity)
def add_watchlist_entity(watchlist_id: UUID, payload: WatchlistEntityCreate) -> dict:
    return repo.add_watchlist_entity(watchlist_id, payload)


@router.delete("/api/watchlists/entities/{entity_row_id}", status_code=204, response_class=Response)
def remove_watchlist_entity(entity_row_id: UUID) -> Response:
    repo.remove_watchlist_entity(entity_row_id)
    return Response(status_code=204)


@router.get("/api/notes", response_model=list[NoteRecord])
def list_notes() -> list[dict]:
    return repo.list_notes()


@router.post("/api/notes", response_model=NoteRecord)
def create_note(payload: NoteCreate) -> dict:
    return repo.create_note(payload)


@router.put("/api/notes/{note_id}", response_model=NoteRecord)
def update_note(note_id: UUID, payload: NoteUpdate) -> dict:
    record = repo.update_note(note_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="Note not found")
    return record


@router.delete("/api/notes/{note_id}", status_code=204, response_class=Response)
def delete_note(note_id: UUID) -> Response:
    repo.delete_note(note_id)
    return Response(status_code=204)


@router.get("/api/tags", response_model=list[TagRecord])
def list_tags() -> list[dict]:
    return repo.list_tags()


@router.post("/api/tags", response_model=TagRecord)
def create_tag(payload: TagCreate) -> dict:
    return repo.create_tag(payload)


@router.put("/api/tags/{tag_id}", response_model=TagRecord)
def update_tag(tag_id: UUID, payload: TagUpdate) -> dict:
    record = repo.update_tag(tag_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="Tag not found")
    return record


@router.delete("/api/tags/{tag_id}", status_code=204, response_class=Response)
def delete_tag(tag_id: UUID) -> Response:
    repo.delete_tag(tag_id)
    return Response(status_code=204)


@router.post("/api/tags/{tag_id}/assignments", response_model=TagAssignment)
def assign_tag(tag_id: UUID, payload: TagAssignmentCreate) -> dict:
    return repo.assign_tag(tag_id, payload)


@router.delete("/api/tags/assignments/{assignment_id}", status_code=204, response_class=Response)
def unassign_tag(assignment_id: UUID) -> Response:
    repo.unassign_tag(assignment_id)
    return Response(status_code=204)


@router.get("/api/saved-views", response_model=list[SavedViewRecord])
def list_saved_views() -> list[dict]:
    return repo.list_saved_views()


@router.post("/api/saved-views", response_model=SavedViewRecord)
def create_saved_view(payload: SavedViewCreate) -> dict:
    return repo.create_saved_view(payload)


@router.put("/api/saved-views/{view_id}", response_model=SavedViewRecord)
def update_saved_view(view_id: UUID, payload: SavedViewUpdate) -> dict:
    record = repo.update_saved_view(view_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return record


@router.delete("/api/saved-views/{view_id}", status_code=204, response_class=Response)
def delete_saved_view(view_id: UUID) -> Response:
    repo.delete_saved_view(view_id)
    return Response(status_code=204)


@router.get("/api/search", response_model=list[SearchResult])
def search(q: str = Query(min_length=1)) -> list[dict]:
    return repo.search(q)
