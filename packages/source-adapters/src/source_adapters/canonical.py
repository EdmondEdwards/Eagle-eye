from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


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
    vessel_type: str | None
    flag: str | None
    lat: float
    lon: float
    heading_deg: float | None
    speed_kts: float | None
    source: str = "aisstream"
    source_confidence: float = 0.78
    observed_at: datetime = field(default_factory=utc_now)
    raw_reference: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self), "observed_at")


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
