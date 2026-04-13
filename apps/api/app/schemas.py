from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Aircraft(BaseModel):
    id: str
    icao24: str
    callsign: str | None = None
    registration: str | None = None
    operator: str | None = None
    lat: float
    lon: float
    altitude_m: float | None = None
    heading_deg: float | None = None
    velocity_kts: float | None = None
    vertical_rate: float | None = None
    source: str
    source_confidence: float
    observed_at: datetime
    raw_reference: str | None = None


class Vessel(BaseModel):
    id: str
    mmsi: str
    imo: str | None = None
    vessel_name: str | None = None
    callsign: str | None = None
    vessel_type: str | None = None
    flag: str | None = None
    lat: float
    lon: float
    heading_deg: float | None = None
    course_deg: float | None = None
    speed_kts: float | None = None
    nav_status: str | None = None
    destination: str | None = None
    draught_m: float | None = None
    source: str
    source_record_id: str | None = None
    source_confidence: float
    merged_confidence: float | None = None
    observed_at: datetime
    last_ingested_at: datetime | None = None
    stale: bool = False
    raw_reference: str | None = None


class VesselSourceHealth(BaseModel):
    provider_name: str
    ingest_mode: Literal["websocket", "polling", "batch"]
    enabled: bool
    priority: int
    health_state: Literal["healthy", "degraded", "unhealthy", "disabled"]
    last_success: datetime | None = None
    last_attempt: datetime | None = None
    valid_message_count: int
    error_count: int
    stall_threshold_seconds: int | None = None
    last_error: str | None = None
    updated_at: datetime


class MaritimeProviderDescriptor(BaseModel):
    provider_name: str
    ingest_mode: Literal["websocket", "polling", "batch"]
    priority: int
    enabled: bool
    description: str | None = None


class VesselPresenceOverlay(BaseModel):
    overlay_id: str
    provider: str
    dataset: str
    label: str
    category: str
    geometry: dict[str, Any]
    density: float | None = None
    observed_from: datetime
    observed_to: datetime
    source: str
    source_confidence: float
    observed_at: datetime
    raw_reference: str | None = None


class Satellite(BaseModel):
    id: str
    norad_cat_id: str
    international_designator: str | None = None
    name: str
    object_type: str | None = None
    group_name: str | None = None
    orbit_class: str | None = None
    tle_line1: str | None = None
    tle_line2: str | None = None
    epoch: datetime | None = None
    inclination_deg: float | None = None
    eccentricity: float | None = None
    mean_motion: float | None = None
    raan_deg: float | None = None
    arg_perigee_deg: float | None = None
    mean_anomaly_deg: float | None = None
    bstar: float | None = None
    computed_lat: float
    computed_lon: float
    computed_alt_km: float | None = None
    computed_velocity_kms: float | None = None
    source: str
    source_confidence: float
    observed_at: datetime
    playback_confidence: float | None = None
    raw_reference: str | None = None


class SatelliteCatalogRecord(BaseModel):
    id: str
    norad_cat_id: str
    international_designator: str | None = None
    name: str
    object_type: str | None = None
    group_name: str | None = None
    orbit_class: str | None = None
    tle_line1: str | None = None
    tle_line2: str | None = None
    epoch: datetime | None = None
    inclination_deg: float | None = None
    eccentricity: float | None = None
    mean_motion: float | None = None
    raan_deg: float | None = None
    arg_perigee_deg: float | None = None
    mean_anomaly_deg: float | None = None
    bstar: float | None = None
    source: str
    source_confidence: float
    observed_at: datetime
    raw_reference: str | None = None


class AirspaceOverlay(BaseModel):
    id: str
    source_id: str
    name: str
    category: str
    geometry: dict[str, Any] | None = None
    active_from: datetime | None = None
    active_to: datetime | None = None
    source: str
    source_confidence: float
    observed_at: datetime
    raw_reference: str | None = None


class TimelinePoint(BaseModel):
    lat: float
    lon: float
    observed_at: datetime
    altitude_m: float | None = None
    alt_km: float | None = None
    heading_deg: float | None = None
    velocity_kts: float | None = None
    velocity_kms: float | None = None
    speed_kts: float | None = None
    confidence: float | None = None


class TimelineTrack(BaseModel):
    entity_id: str
    label: str
    entity_kind: Literal["aircraft", "vessel", "satellite"]
    points: list[TimelinePoint]


class TimelineResponse(BaseModel):
    window: dict[str, datetime]
    tracks: list[TimelineTrack]


class OrbitPathResponse(BaseModel):
    norad_cat_id: str
    source: str
    epoch: datetime | None = None
    points: list[TimelinePoint]


class CaseEntity(BaseModel):
    entity_kind: Literal["aircraft", "vessel", "satellite", "airspace"]
    entity_id: str
    role: str | None = None


class CaseRecord(BaseModel):
    id: UUID
    title: str
    summary: str | None = None
    status: str
    priority: str
    source: str
    created_at: datetime
    updated_at: datetime
    entities: list[CaseEntity] = Field(default_factory=list)


class CaseCreate(BaseModel):
    title: str
    summary: str | None = None
    status: str = "active"
    priority: str = "medium"
    source: str = "user"
    entities: list[CaseEntity] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    priority: str | None = None
    entities: list[CaseEntity] | None = None


class NoteRecord(BaseModel):
    id: UUID
    case_id: UUID | None = None
    entity_kind: str | None = None
    entity_id: str | None = None
    body: str
    author: str
    source: str
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    case_id: UUID | None = None
    entity_kind: str | None = None
    entity_id: str | None = None
    body: str
    author: str = "local-analyst"
    source: str = "user"

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("body must not be empty")
        return cleaned


class NoteUpdate(BaseModel):
    body: str | None = None


class TagRecord(BaseModel):
    id: UUID
    name: str
    color: str
    source: str
    created_at: datetime
    updated_at: datetime


class TagCreate(BaseModel):
    name: str
    color: str = "#6ee7ff"
    source: str = "user"


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagAssignment(BaseModel):
    id: UUID
    tag_id: UUID
    case_id: UUID | None = None
    entity_kind: str | None = None
    entity_id: str | None = None
    created_at: datetime


class TagAssignmentCreate(BaseModel):
    tag_id: UUID
    case_id: UUID | None = None
    entity_kind: str | None = None
    entity_id: str | None = None


class WatchlistEntity(BaseModel):
    id: UUID
    entity_kind: Literal["aircraft", "vessel", "satellite"]
    entity_id: str
    label: str | None = None
    created_at: datetime


class WatchlistRecord(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    color: str
    source: str
    created_at: datetime
    updated_at: datetime
    entities: list[WatchlistEntity] = Field(default_factory=list)


class WatchlistCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#4ade80"
    source: str = "user"


class WatchlistUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class WatchlistEntityCreate(BaseModel):
    entity_kind: Literal["aircraft", "vessel", "satellite"]
    entity_id: str
    label: str | None = None


class SavedViewRecord(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    center_lat: float
    center_lon: float
    center_altitude: float
    heading_deg: float
    pitch_deg: float
    roll_deg: float
    layers: dict[str, bool]
    created_at: datetime
    updated_at: datetime


class SavedViewCreate(BaseModel):
    name: str
    description: str | None = None
    center_lat: float
    center_lon: float
    center_altitude: float
    heading_deg: float
    pitch_deg: float
    roll_deg: float
    layers: dict[str, bool] = Field(default_factory=dict)


class SavedViewUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    center_altitude: float | None = None
    heading_deg: float | None = None
    pitch_deg: float | None = None
    roll_deg: float | None = None
    layers: dict[str, bool] | None = None


class SearchResult(BaseModel):
    kind: str
    id: str
    label: str
    subtitle: str | None = None
    source: str | None = None
    observed_at: datetime | None = None
    location: dict[str, float] | None = None
