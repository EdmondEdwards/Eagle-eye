from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from . import repositories as repo
from .schemas import (
    AoiCreate,
    AoiRecord,
    AoiUpdate,
    CaseCreate,
    CaseRecord,
    CaseUpdate,
    EventRecord,
    EntityTimelineResponse,
    GlobeViewState,
    InvestigationBundle,
    NoteCreate,
    NoteRecord,
    NoteUpdate,
    RelationshipRecord,
    SatelliteFovResponse,
    SatellitePassResponse,
    SourceStatusRecord,
    TagCreate,
    TagRecord,
    TimeState,
    TimeStateUpdate,
    ViewQueryResponse,
    WatchlistCreate,
    WatchlistEntityCreate,
    WatchlistRecord,
    WatchlistUpdate,
    WorkspaceCreate,
    WorkspaceRecord,
    WorkspaceUpdate,
)

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/api/time/state", response_model=TimeState)
def get_time_state() -> dict:
    return repo.get_time_state()


@router.post("/api/time/set", response_model=TimeState)
def set_time_state(payload: TimeStateUpdate) -> dict:
    return repo.set_time_state(payload)


@router.post("/api/view/query", response_model=ViewQueryResponse)
def query_view(payload: GlobeViewState) -> dict:
    return repo.query_view(payload)


@router.get("/api/view/entities")
def view_entities(
    west: float,
    south: float,
    east: float,
    north: float,
    camera_height: float,
    timestamp: datetime,
    mode: str = Query(default="live"),
    enabled_layers: str = Query(default="aircraft,vessels,satellites,airspace,aois"),
) -> list[dict]:
    view = GlobeViewState(
        west=west,
        south=south,
        east=east,
        north=north,
        camera_height=camera_height,
        timestamp=timestamp,
        mode=mode,
        enabled_layers=[item.strip() for item in enabled_layers.split(",") if item.strip()],
    )
    return repo.list_entities(view)


@router.get("/api/view/events", response_model=list[EventRecord])
def view_events(
    west: float,
    south: float,
    east: float,
    north: float,
    camera_height: float,
    timestamp: datetime,
    mode: str = Query(default="live"),
) -> list[dict]:
    view = GlobeViewState(
        west=west,
        south=south,
        east=east,
        north=north,
        camera_height=camera_height,
        timestamp=timestamp,
        mode=mode,
        enabled_layers=["events"],
    )
    return repo.list_events(view=view)


@router.get("/api/view/satellites")
def view_satellites(
    west: float,
    south: float,
    east: float,
    north: float,
    camera_height: float,
    timestamp: datetime,
    mode: str = Query(default="live"),
) -> list[dict]:
    view = GlobeViewState(
        west=west,
        south=south,
        east=east,
        north=north,
        camera_height=camera_height,
        timestamp=timestamp,
        mode=mode,
        enabled_layers=["satellites"],
    )
    return repo.list_satellites_in_view(view)


@router.get("/api/events", response_model=list[EventRecord])
def list_events(entity_id: str | None = None, limit: int = Query(default=200, le=500)) -> list[dict]:
    return repo.list_events(entity_id=entity_id, limit=limit)


@router.get("/api/events/live", response_model=list[EventRecord])
def list_live_events(limit: int = Query(default=50, le=200)) -> list[dict]:
    state = repo.get_time_state()
    view = GlobeViewState(
        west=-180,
        south=-85,
        east=180,
        north=85,
        camera_height=36_000_000,
        timestamp=state["current_timestamp"],
        mode=state["mode"],
        enabled_layers=["events"],
    )
    return repo.list_events(view=view, limit=limit)


@router.get("/api/relationships", response_model=list[RelationshipRecord])
def list_relationships(selected_ids: str | None = None, limit: int = Query(default=200, le=500)) -> list[dict]:
    ids = [item.strip() for item in selected_ids.split(",")] if selected_ids else None
    return repo.list_relationships(selected_ids=ids, limit=limit)


@router.get("/api/sources/status", response_model=list[SourceStatusRecord])
def sources_status() -> list[dict]:
    return repo.list_source_status()


@router.get("/api/investigate/{entity_id}", response_model=InvestigationBundle)
def investigate_entity(entity_id: str) -> dict:
    return repo.investigation_bundle(entity_id)


@router.get("/api/entities/{entity_id}/timeline", response_model=EntityTimelineResponse)
def get_entity_timeline(
    entity_id: str,
    timestamp: datetime | None = None,
    history_hours: int = Query(default=12, ge=1, le=72),
    future_minutes: int = Query(default=120, ge=15, le=24 * 60),
) -> dict:
    return repo.entity_timeline(entity_id, timestamp=timestamp, history_hours=history_hours, future_minutes=future_minutes)


@router.get("/api/cases", response_model=list[CaseRecord])
def list_cases() -> list[dict]:
    return repo.list_cases()


@router.post("/api/cases", response_model=CaseRecord)
def create_case(payload: CaseCreate) -> dict:
    return repo.create_case(payload)


@router.put("/api/cases/{case_id}", response_model=CaseRecord)
def update_case(case_id: UUID, payload: CaseUpdate) -> dict:
    row = repo.update_case(case_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return row


@router.get("/api/workspaces", response_model=list[WorkspaceRecord])
def list_workspaces() -> list[dict]:
    return repo.list_workspaces()


@router.post("/api/workspaces", response_model=WorkspaceRecord)
def create_workspace(payload: WorkspaceCreate) -> dict:
    return repo.create_workspace(payload)


@router.put("/api/workspaces/{workspace_id}", response_model=WorkspaceRecord)
def update_workspace(workspace_id: UUID, payload: WorkspaceUpdate) -> dict:
    row = repo.update_workspace(workspace_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return row


@router.get("/api/watchlists", response_model=list[WatchlistRecord])
def list_watchlists() -> list[dict]:
    return repo.list_watchlists()


@router.post("/api/watchlists", response_model=WatchlistRecord)
def create_watchlist(payload: WatchlistCreate) -> dict:
    return repo.create_watchlist(payload)


@router.put("/api/watchlists/{watchlist_id}", response_model=WatchlistRecord)
def update_watchlist(watchlist_id: UUID, payload: WatchlistUpdate) -> dict:
    row = repo.update_watchlist(watchlist_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return row


@router.post("/api/watchlists/{watchlist_id}/entities", response_model=WatchlistRecord)
def add_watchlist_entity(watchlist_id: UUID, payload: WatchlistEntityCreate) -> dict:
    return repo.add_watchlist_entity(watchlist_id, payload)


@router.delete("/api/watchlists/{watchlist_id}/entities", response_model=WatchlistRecord)
def remove_watchlist_entity(watchlist_id: UUID, entity_id: str = Query(...)) -> dict:
    row = repo.remove_watchlist_entity(watchlist_id, entity_id)
    if not row:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return row


@router.get("/api/notes", response_model=list[NoteRecord])
def list_notes(limit: int = Query(default=200, le=500)) -> list[dict]:
    return repo.list_notes(limit)


@router.post("/api/notes", response_model=NoteRecord)
def create_note(payload: NoteCreate) -> dict:
    return repo.create_note(payload)


@router.put("/api/notes/{note_id}", response_model=NoteRecord)
def update_note(note_id: UUID, payload: NoteUpdate) -> dict:
    row = repo.update_note(note_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    return row


@router.get("/api/tags", response_model=list[TagRecord])
def list_tags() -> list[dict]:
    return repo.list_tags()


@router.post("/api/tags", response_model=TagRecord)
def create_tag(payload: TagCreate) -> dict:
    return repo.create_tag(payload)


@router.get("/api/aois", response_model=list[AoiRecord])
def list_aois() -> list[dict]:
    return repo.list_aois()


@router.post("/api/aois", response_model=AoiRecord)
def create_aoi(payload: AoiCreate) -> dict:
    return repo.create_aoi(payload)


@router.put("/api/aois/{aoi_id}", response_model=AoiRecord)
def update_aoi(aoi_id: UUID, payload: AoiUpdate) -> dict:
    row = repo.update_aoi(aoi_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="AOI not found")
    return row


@router.get("/api/aois/{aoi_id}/events", response_model=list[EventRecord])
def aoi_events(aoi_id: UUID) -> list[dict]:
    return repo.events_for_aoi(aoi_id)


@router.get("/api/aois/{aoi_id}/passes")
def aoi_passes(aoi_id: UUID) -> list[dict]:
    return repo.passes_for_aoi(aoi_id)


@router.get("/api/satellites/{satellite_id}/fov", response_model=SatelliteFovResponse)
def satellite_fov(satellite_id: str, at: datetime | None = None) -> dict:
    row = repo.satellite_fov(satellite_id, at=at)
    if not row:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return row


@router.get("/api/satellites/{satellite_id}/passes", response_model=SatellitePassResponse)
def satellite_passes(
    satellite_id: str,
    lat: float | None = None,
    lon: float | None = None,
    aoi_id: UUID | None = None,
    threshold_km: float = 550.0,
) -> dict:
    if aoi_id:
        aoi_passes = repo.passes_for_aoi(aoi_id)
        target = next((item for item in aoi_passes if item["satellite_id"] == satellite_id), None)
        return {"satellite_id": satellite_id, "target": {"aoi_id": str(aoi_id)}, "passes": [] if not target else target["passes"]}
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="lat/lon or aoi_id is required")
    return {
        "satellite_id": satellite_id,
        "target": {"lat": lat, "lon": lon, "threshold_km": threshold_km},
        "passes": repo.satellite_passes(satellite_id, target_lat=lat, target_lon=lon, threshold_km=threshold_km),
    }
