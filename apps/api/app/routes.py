from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from . import repositories as repo
from .services.eonet_view_service import query_eonet_events
from .services.firms_view_service import query_firms_records
from .services.nws_view_service import query_nws_alerts
from .schemas import (
    AoiCreate,
    AoiRecord,
    AoiUpdate,
    CaseCreate,
    CaseRecord,
    CaseUpdate,
    EventRecord,
    HazardEventDetail,
    HazardViewQuery,
    HazardViewResponse,
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
    TagAssignmentCreate,
    TagRecord,
    TimeState,
    TimeStateUpdate,
    ViewDiagnosticsResponse,
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


def _csv_list(value: str | None) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()] if value else []


def _view_mode(mode: str) -> str:
    if mode == "simulate":
        return "simulate"
    if mode in {"replay", "paused"}:
        return "replay"
    return "live"


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


@router.post("/api/view/diagnostics", response_model=ViewDiagnosticsResponse)
def diagnose_view(payload: GlobeViewState) -> dict:
    return repo.diagnose_view(payload)


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
        mode=_view_mode(state["mode"]),
        enabled_layers=["events", "eonet", "firms", "nws"],
    )
    rows = repo.list_events(view=view, limit=limit)
    rows.extend(repo.list_hazard_events(view=view, limit=limit))
    return sorted(rows, key=lambda row: row["start_time"], reverse=True)[:limit]


@router.post("/api/hazards/view-query", response_model=HazardViewResponse)
def hazards_view_query(payload: HazardViewQuery) -> dict:
    events = repo.list_hazard_events(
        bbox=(payload.west, payload.south, payload.east, payload.north),
        start_time=payload.start_time,
        end_time=payload.end_time,
        sources=payload.sources,
        categories=payload.categories,
        statuses=payload.statuses,
        severities=payload.severities,
        limit=payload.limit,
    )
    return {
        "events": events,
        "stats": {
            "events": len(events),
            "sources": len({row["source"] for row in events}),
        },
    }


@router.get("/api/hazards/events", response_model=list[EventRecord])
def list_hazard_events(
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    source: str | None = None,
    category: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=200, le=500),
) -> list[dict]:
    bbox = (west, south, east, north) if None not in {west, south, east, north} else None
    return repo.list_hazard_events(
        bbox=bbox if bbox is not None else None,
        start_time=start_time,
        end_time=end_time,
        sources=_csv_list(source),
        categories=_csv_list(category),
        statuses=_csv_list(status),
        severities=_csv_list(severity),
        limit=limit,
    )


@router.get("/api/hazards/events/{event_id}", response_model=HazardEventDetail)
def hazard_event_detail(event_id: UUID) -> dict:
    row = repo.get_hazard_event_detail(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="Hazard event not found")
    return row


@router.get("/api/hazards/eonet")
def list_eonet_events(
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    status: str | None = None,
    category: str | None = None,
    source: str | None = None,
    limit: int = Query(default=200, le=500),
) -> list[dict]:
    bbox = (west, south, east, north) if None not in {west, south, east, north} else None
    simplify = 0.5 if bbox is None else max((bbox[2] - bbox[0]) / 1800.0, 0.0)
    return query_eonet_events(
        bbox=bbox if bbox is not None else None,
        start_time=start,
        end_time=end,
        statuses=_csv_list(status),
        categories=_csv_list(category),
        sources=_csv_list(source),
        limit=limit,
        simplify_tolerance=simplify,
    )


@router.get("/api/hazards/firms")
def list_firms_detections(
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    sensor: str | None = None,
    clustered: bool = Query(default=False),
    limit: int = Query(default=400, le=2000),
) -> list[dict]:
    bbox = (west, south, east, north) if None not in {west, south, east, north} else None
    return query_firms_records(
        bbox=bbox if bbox is not None else None,
        start_time=start,
        end_time=end,
        sensors=_csv_list(sensor),
        clustered=clustered,
        limit=limit,
    )


@router.get("/api/hazards/nws")
def list_nws_alerts(
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=200, le=500),
) -> list[dict]:
    bbox = (west, south, east, north) if None not in {west, south, east, north} else None
    simplify = 0.75 if bbox is None else max((bbox[2] - bbox[0]) / 1200.0, 0.0)
    return query_nws_alerts(
        bbox=bbox if bbox is not None else None,
        start_time=start,
        end_time=end,
        statuses=_csv_list(status),
        severities=_csv_list(severity),
        limit=limit,
        simplify_tolerance=simplify,
    )


@router.get("/api/hazards/categories")
def hazard_categories() -> list[dict]:
    return repo.list_hazard_categories()


@router.get("/api/hazards/source-health", response_model=list[SourceStatusRecord])
def hazard_source_health() -> list[dict]:
    return [row for row in repo.list_source_status() if row["domain"] == "hazard"]


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


@router.post("/api/tags/assign", response_model=TagRecord)
def assign_tag(payload: TagAssignmentCreate) -> dict:
    return repo.assign_tag(payload)


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
