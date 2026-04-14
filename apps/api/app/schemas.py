from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class GlobeViewState(BaseModel):
    west: float
    south: float
    east: float
    north: float
    camera_height: float
    heading: float = 0
    pitch: float = -90
    roll: float = 0
    timestamp: datetime
    mode: Literal["live", "replay", "simulate"] = "live"
    enabled_layers: list[str] = Field(default_factory=list)
    selected_entities: list[str] = Field(default_factory=list)
    selected_aois: list[str] = Field(default_factory=list)

    @field_validator("enabled_layers", mode="before")
    @classmethod
    def _default_layers(cls, value: Any) -> list[str]:
        if not value:
            return ["aircraft", "vessels", "satellites", "airspace", "events", "aois"]
        return list(value)


class ClusterRecord(BaseModel):
    id: str
    entity_kind: Literal["aircraft", "vessel", "satellite", "event"]
    count: int
    lat: float
    lon: float
    sample_ids: list[str] = Field(default_factory=list)


class EntityRecord(BaseModel):
    id: str
    entity_kind: Literal["aircraft", "vessel", "satellite", "airspace", "aoi"]
    label: str
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime
    predicted_path: list[dict[str, Any]] = Field(default_factory=list)


class EventRecord(BaseModel):
    id: UUID
    event_type: str
    category: str
    severity: str
    title: str
    summary: str | None = None
    entity_kind: str | None = None
    entity_id: str | None = None
    related_entity_kind: str | None = None
    related_entity_id: str | None = None
    geometry: dict[str, Any] | None = None
    start_time: datetime
    end_time: datetime | None = None
    detected_at: datetime
    status: str
    confidence: float
    source: str
    source_confidence: float
    raw_reference: str | None = None


class RelationshipRecord(BaseModel):
    id: UUID
    source_kind: str
    source_id: str
    target_kind: str
    target_id: str
    relationship_type: str
    strength: float
    context_event_id: UUID | None = None
    context_case_id: UUID | None = None
    source: str
    source_confidence: float
    observed_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ViewQueryResponse(BaseModel):
    view: GlobeViewState
    entities: list[EntityRecord]
    clusters: list[ClusterRecord]
    events: list[EventRecord]
    relationships: list[RelationshipRecord]
    stats: dict[str, int]


class TimeState(BaseModel):
    mode: Literal["live", "paused", "replay", "simulate"]
    status: Literal["playing", "paused"]
    current_timestamp: datetime
    playback_speed: float = 1.0
    step_seconds: int = 60
    updated_at: datetime


class TimeStateUpdate(BaseModel):
    mode: Literal["live", "paused", "replay", "simulate"] | None = None
    status: Literal["playing", "paused"] | None = None
    current_timestamp: datetime | None = None
    playback_speed: float | None = None
    step_seconds: int | None = None
    action: Literal["play", "pause", "step_forward", "step_back", "jump"] | None = None


class GeoJsonGeometry(BaseModel):
    type: str
    coordinates: Any | None = None


class AoiRecord(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    geometry_type: Literal["polygon", "rectangle", "circle"]
    geometry: dict[str, Any]
    center: dict[str, Any] | None = None
    radius_m: float | None = None
    tags: list[str] = Field(default_factory=list)
    source: str
    source_confidence: float
    observed_at: datetime
    updated_at: datetime


class AoiCreate(BaseModel):
    name: str
    description: str | None = None
    geometry_type: Literal["polygon", "rectangle", "circle"]
    geometry: GeoJsonGeometry
    center: dict[str, float] | None = None
    radius_m: float | None = None
    tags: list[str] = Field(default_factory=list)


class WorkspaceRecord(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    camera: dict[str, Any]
    time_context: dict[str, Any]
    layers: dict[str, Any]
    selected_entities: list[str]
    selected_aois: list[str]
    source: str
    created_at: datetime
    updated_at: datetime


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None
    camera: dict[str, Any]
    time_context: dict[str, Any]
    layers: dict[str, Any]
    selected_entities: list[str] = Field(default_factory=list)
    selected_aois: list[str] = Field(default_factory=list)
    source: str = "user"


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    camera: dict[str, Any] | None = None
    time_context: dict[str, Any] | None = None
    layers: dict[str, Any] | None = None
    selected_entities: list[str] | None = None
    selected_aois: list[str] | None = None


class CaseEntity(BaseModel):
    entity_kind: str
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


class WatchlistEntityRecord(BaseModel):
    id: UUID
    entity_kind: str
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
    entities: list[WatchlistEntityRecord] = Field(default_factory=list)


class WatchlistCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#6ee7ff"
    source: str = "user"


class WatchlistEntityCreate(BaseModel):
    entity_kind: str
    entity_id: str
    label: str | None = None


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


class SatelliteFovResponse(BaseModel):
    satellite_id: str
    timestamp: datetime
    footprint: dict[str, Any]
    cone: dict[str, Any]
    swath_km: float


class SatellitePassResponse(BaseModel):
    satellite_id: str
    target: dict[str, Any]
    passes: list[dict[str, Any]]
