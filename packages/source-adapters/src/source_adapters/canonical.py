from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(payload: dict[str, Any], *date_keys: str) -> dict[str, Any]:
    for key in date_keys:
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


@dataclass(slots=True)
class AircraftSnapshot:
    id: str
    icao24: str
    callsign: str | None
    registration: str | None
    operator: str | None
    lat: float
    lon: float
    altitude_m: float | None
    heading_deg: float | None
    velocity_kts: float | None
    vertical_rate: float | None
    source: str = "opensky"
    source_confidence: float = 0.82
    observed_at: datetime = field(default_factory=utc_now)
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "observed_at")


@dataclass(slots=True)
class VesselSnapshot:
    id: str
    mmsi: str
    imo: str | None
    vessel_name: str | None
    callsign: str | None
    vessel_type: str | None
    flag: str | None
    lat: float
    lon: float
    heading_deg: float | None
    course_deg: float | None
    speed_kts: float | None
    nav_status: str | None
    destination: str | None
    draught_m: float | None
    source: str
    source_record_id: str | None = None
    source_confidence: float = 0.75
    merged_confidence: float | None = None
    observed_at: datetime = field(default_factory=utc_now)
    last_ingested_at: datetime = field(default_factory=utc_now)
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "observed_at", "last_ingested_at")


@dataclass(slots=True)
class VesselSourceSnapshotRecord:
    snapshot_id: str
    provider: str
    source_record_id: str | None
    mmsi: str | None
    imo: str | None
    vessel_name: str | None
    observed_at: datetime
    ingested_at: datetime = field(default_factory=utc_now)
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "observed_at", "ingested_at")


@dataclass(slots=True)
class VesselSourceHealthRecord:
    provider_name: str
    ingest_mode: Literal["websocket", "polling", "batch"]
    enabled: bool
    priority: int
    health_state: Literal["healthy", "degraded", "unhealthy", "disabled"]
    last_success: datetime | None = None
    last_attempt: datetime | None = None
    valid_message_count: int = 0
    error_count: int = 0
    stall_threshold_seconds: int | None = None
    last_error: str | None = None
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "last_success", "last_attempt", "updated_at")


@dataclass(slots=True)
class VesselPresenceOverlayRecord:
    overlay_id: str
    provider: str
    dataset: str
    label: str
    category: str
    geometry: dict[str, Any]
    density: float | None
    observed_from: datetime
    observed_to: datetime
    source_confidence: float = 0.58
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "observed_from", "observed_to")


@dataclass(slots=True)
class MaritimeProviderDescriptor:
    provider_name: str
    ingest_mode: Literal["websocket", "polling", "batch"]
    priority: int
    enabled: bool
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SatelliteCatalogRecord:
    id: str
    norad_cat_id: str
    international_designator: str | None
    name: str
    object_type: str | None
    orbit_class: str | None
    source: str
    tle_line1: str | None
    tle_line2: str | None
    epoch: datetime | None
    inclination_deg: float | None
    eccentricity: float | None
    mean_motion: float | None
    raan_deg: float | None
    arg_perigee_deg: float | None
    mean_anomaly_deg: float | None
    bstar: float | None
    source_confidence: float = 0.74
    observed_at: datetime = field(default_factory=utc_now)
    group_name: str | None = None
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "epoch", "observed_at")


@dataclass(slots=True)
class SatelliteSourceSnapshotRecord:
    snapshot_id: str
    satellite_id: str
    norad_cat_id: str
    provider: str
    group_name: str | None
    payload_format: str
    epoch: datetime | None
    observed_at: datetime = field(default_factory=utc_now)
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "epoch", "observed_at")


@dataclass(slots=True)
class SatelliteSnapshot:
    id: str
    norad_cat_id: str
    international_designator: str | None
    name: str
    object_type: str | None
    orbit_class: str | None
    source: str
    tle_line1: str | None
    tle_line2: str | None
    epoch: datetime | None
    inclination_deg: float | None
    eccentricity: float | None
    mean_motion: float | None
    raan_deg: float | None
    arg_perigee_deg: float | None
    mean_anomaly_deg: float | None
    bstar: float | None
    source_confidence: float
    observed_at: datetime
    computed_lat: float
    computed_lon: float
    computed_alt_km: float | None
    computed_velocity_kms: float | None
    group_name: str | None = None
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    playback_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "epoch", "observed_at")


@dataclass(slots=True)
class OrbitSample:
    observed_at: datetime
    lat: float
    lon: float
    alt_km: float | None
    velocity_kms: float | None

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "observed_at")


@dataclass(slots=True)
class SatelliteIngestResult:
    provider: str
    catalog_records: list[SatelliteCatalogRecord]
    source_snapshots: list[SatelliteSourceSnapshotRecord]
    observed_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


@dataclass(slots=True)
class AirspaceOverlayRecord:
    id: str
    source_id: str
    name: str
    category: str
    geometry: dict[str, Any] | None
    active_from: datetime | None
    active_to: datetime | None
    source: str = "faa_tfr"
    source_confidence: float = 0.68
    observed_at: datetime = field(default_factory=utc_now)
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "active_from", "active_to", "observed_at")


@dataclass(slots=True)
class WebcamCatalogEntry:
    id: str
    name: str
    provider: str
    lat: float
    lon: float
    status: str = "planned"
    source: str = "webcam_catalog_placeholder"
    observed_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class LiveEnvelope:
    topic: str
    action: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"topic": self.topic, "action": self.action, "payload": self.payload}
