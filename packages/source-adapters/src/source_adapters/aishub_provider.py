from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4
from xml.etree import ElementTree

import httpx

from .canonical import VesselSnapshot, VesselSourceSnapshotRecord
from .maritime_provider import MaritimeProvider

LOGGER = logging.getLogger(__name__)


def _as_float(value: Any) -> float | None:
    if value in (None, "", "511", "360.0", "360"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_observed_at(value: Any) -> datetime:
    if value in (None, ""):
        return datetime.now(timezone.utc)
    text = str(value).strip()
    for candidate in (text.replace(" GMT", "+00:00"), text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromtimestamp(int(float(text)), tz=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


class AISHubProvider(MaritimeProvider):
    provider_name = "aishub"
    ingest_mode = "polling"
    BASE_URL = "https://data.aishub.net/ws.php"

    def __init__(
        self,
        *,
        enabled: bool,
        username: str | None,
        password: str | None,
        poll_interval_seconds: int = 60,
        bounding_boxes: list[list[list[float]]] | None = None,
        output_format: str = "json",
    ) -> None:
        super().__init__(enabled=enabled and bool(username) and bool(password), priority=70, description="Fallback AIS polling provider with one-minute minimum interval")
        self.username = username
        self.password = password
        self.poll_interval_seconds = max(60, poll_interval_seconds)
        self.bounding_boxes = bounding_boxes or [[[-90, -180], [90, 180]]]
        self.output_format = output_format.lower()

    async def poll_records(self) -> tuple[list[VesselSnapshot], list[VesselSourceSnapshotRecord]]:
        if not self.enabled or not self.username or not self.password:
            return [], []

        self.mark_attempt()
        params = self._build_params()
        url = f"{self.BASE_URL}?{urlencode(params)}"
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(self.BASE_URL, params=params, timeout=45.0, auth=(self.username, self.password))
                response.raise_for_status()
            records, snapshots = self._parse_response(response)
            self.mark_success(valid_messages=len(records))
            return records, snapshots
        except Exception as exc:  # pragma: no cover - network recovery path
            self.mark_error(f"AISHub poll failed: {exc}")
            LOGGER.warning("AISHub poll failed: %s", exc)
            return [], []

    def _build_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "username": self.username,
            "format": 1,
            "output": self.output_format,
            "compress": 0,
            "interval": 5,
        }
        first_box = self.bounding_boxes[0] if self.bounding_boxes else [[-90, -180], [90, 180]]
        south, west = first_box[0]
        north, east = first_box[1]
        params.update(
            {
                "latmin": south,
                "latmax": north,
                "lonmin": west,
                "lonmax": east,
            }
        )
        return params

    def _parse_response(self, response: httpx.Response) -> tuple[list[VesselSnapshot], list[VesselSourceSnapshotRecord]]:
        if self.output_format == "xml":
            rows = self._parse_xml(response.text)
        else:
            rows = self._parse_json(response.text)
        ingested_at = datetime.now(timezone.utc)
        vessels: list[VesselSnapshot] = []
        snapshots: list[VesselSourceSnapshotRecord] = []
        for row in rows:
            vessel, snapshot = self._normalize_row(row, ingested_at=ingested_at, source_url=str(response.url))
            snapshots.append(snapshot)
            if vessel:
                vessels.append(vessel)
        return vessels, snapshots

    @staticmethod
    def _parse_json(payload: str) -> list[dict[str, Any]]:
        parsed = json.loads(payload)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            vessels = parsed.get("vessels") or parsed.get("Vessels") or parsed.get("data")
            if isinstance(vessels, list):
                return [item for item in vessels if isinstance(item, dict)]
        return []

    @staticmethod
    def _parse_xml(payload: str) -> list[dict[str, Any]]:
        root = ElementTree.fromstring(payload)
        rows: list[dict[str, Any]] = []
        for element in root.findall(".//vessel"):
            rows.append({key.upper(): value for key, value in element.attrib.items()})
        return rows

    def _normalize_row(
        self,
        row: dict[str, Any],
        *,
        ingested_at: datetime,
        source_url: str,
    ) -> tuple[VesselSnapshot | None, VesselSourceSnapshotRecord]:
        mmsi = str(row.get("MMSI") or "").strip()
        observed_at = _parse_observed_at(row.get("TIME") or row.get("TSTAMP"))
        source_record_id = f"aishub:{mmsi or uuid4()}"
        snapshot = VesselSourceSnapshotRecord(
            snapshot_id=f"{source_record_id}:{uuid4()}",
            provider=self.provider_name,
            source_record_id=source_record_id,
            mmsi=mmsi or None,
            imo=str(row.get("IMO")) if row.get("IMO") not in (None, "", "0", 0) else None,
            vessel_name=row.get("NAME"),
            observed_at=observed_at,
            ingested_at=ingested_at,
            raw_reference=source_url,
            raw_payload=row,
        )
        lat = _as_float(row.get("LATITUDE"))
        lon = _as_float(row.get("LONGITUDE"))
        if not mmsi or lat is None or lon is None:
            snapshot.parse_error = "AISHub record missing MMSI or coordinates"
            return None, snapshot

        vessel = VesselSnapshot(
            id=f"vessel:{mmsi}",
            mmsi=mmsi,
            imo=str(row.get("IMO")) if row.get("IMO") not in (None, "", "0", 0) else None,
            vessel_name=row.get("NAME"),
            callsign=row.get("CALLSIGN"),
            vessel_type=str(row.get("TYPE")) if row.get("TYPE") not in (None, "") else None,
            flag=None,
            lat=lat,
            lon=lon,
            heading_deg=_as_float(row.get("HEADING")),
            course_deg=_as_float(row.get("COG")),
            speed_kts=_as_float(row.get("SOG")),
            nav_status=str(row.get("NAVSTAT")) if row.get("NAVSTAT") not in (None, "") else None,
            destination=row.get("DEST"),
            draught_m=_as_float(row.get("DRAUGHT")),
            source=self.provider_name,
            source_record_id=source_record_id,
            source_confidence=0.68,
            merged_confidence=0.68,
            observed_at=observed_at,
            last_ingested_at=ingested_at,
            raw_reference=source_url,
            raw_payload=row,
        )
        return vessel, snapshot
