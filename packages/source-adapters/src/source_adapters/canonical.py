from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


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
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        payload["active_from"] = self.active_from.isoformat() if self.active_from else None
        payload["active_to"] = self.active_to.isoformat() if self.active_to else None
        return payload


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

