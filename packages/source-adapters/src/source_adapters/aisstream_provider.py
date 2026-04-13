from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import websockets

from .canonical import VesselSnapshot, VesselSourceSnapshotRecord
from .maritime_provider import MaritimeProvider

LOGGER = logging.getLogger(__name__)


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_iso8601(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class AISStreamProvider(MaritimeProvider):
    provider_name = "aisstream"
    ingest_mode = "websocket"
    STREAM_URL = "wss://stream.aisstream.io/v0/stream"

    def __init__(
        self,
        *,
        api_key: str | None,
        enabled: bool,
        priority: int = 100,
        bounding_boxes: list[list[list[float]]] | None = None,
        filter_message_types: list[str] | None = None,
        stall_threshold_seconds: int = 90,
        log_raw_messages: bool = False,
    ) -> None:
        super().__init__(enabled=enabled and bool(api_key), priority=priority, description="Primary real-time AIS WebSocket feed")
        self.api_key = api_key
        self.bounding_boxes = bounding_boxes or [[[-90, -180], [90, 180]]]
        self.filter_message_types = filter_message_types or [
            "PositionReport",
            "StandardClassBPositionReport",
            "ShipStaticData",
        ]
        self.log_raw_messages = log_raw_messages
        self._ship_cache: dict[str, dict[str, Any]] = {}
        self._stall_threshold_seconds = max(30, stall_threshold_seconds)
        self.health_snapshot().stall_threshold_seconds = self._stall_threshold_seconds
        self._health.stall_threshold_seconds = self._stall_threshold_seconds

    def _subscription_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "APIKey": self.api_key,
            "BoundingBoxes": self.bounding_boxes,
        }
        if self.filter_message_types:
            payload["FilterMessageTypes"] = self.filter_message_types
        return payload

    async def stream_records(self) -> AsyncIterator[tuple[VesselSnapshot | None, VesselSourceSnapshotRecord | None]]:
        if not self.enabled or not self.api_key:
            LOGGER.warning("AISStream disabled or API key missing; maritime live ingest will rely on fallback providers.")
            while True:
                await asyncio.sleep(60)

        backoff = 2
        last_valid_message_at = datetime.now(timezone.utc)

        while True:
            self.mark_attempt()
            try:
                async with websockets.connect(self.STREAM_URL, ping_interval=20, ping_timeout=20, max_size=2**22) as socket:
                    await socket.send(json.dumps(self._subscription_payload()))
                    self.mark_success()
                    backoff = 2

                    async for raw_message in socket:
                        if self.log_raw_messages:
                            LOGGER.info("AISStream raw payload=%s", raw_message[:1000])

                        payload = json.loads(raw_message)
                        record, snapshot = self._parse_payload(payload)
                        if snapshot is not None:
                            LOGGER.debug("AISStream source snapshot %s", snapshot.snapshot_id)
                        if record is None:
                            if (datetime.now(timezone.utc) - last_valid_message_at).total_seconds() >= self._stall_threshold_seconds:
                                self.mark_stalled("AISStream connected but no valid vessel updates were parsed within the stall threshold.")
                            yield None, snapshot
                            continue

                        last_valid_message_at = datetime.now(timezone.utc)
                        self.mark_success(valid_messages=1)
                        yield record, snapshot
            except Exception as exc:  # pragma: no cover - network recovery path
                self.mark_error(f"AISStream connection dropped: {exc}")
                LOGGER.warning("AISStream connection dropped: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _parse_payload(self, payload: dict[str, Any]) -> tuple[VesselSnapshot | None, VesselSourceSnapshotRecord | None]:
        metadata = payload.get("MetaData", {}) or {}
        message = payload.get("Message", {}) or {}
        message_type = payload.get("MessageType")
        observed_at = _parse_iso8601(metadata.get("time_utc"))
        ingested_at = datetime.now(timezone.utc)
        source_record_id = self.extract_record_id(payload, "MessageId", "message_id")
        if source_record_id is None:
            source_record_id = f"aisstream:{metadata.get('MMSI') or metadata.get('ShipName') or ingested_at.timestamp()}"

        if message_type == "ShipStaticData":
            static_data = message.get("ShipStaticData", {})
            mmsi = str(static_data.get("UserID") or metadata.get("MMSI") or "").strip()
            if mmsi:
                self._ship_cache[mmsi] = static_data
            snapshot = VesselSourceSnapshotRecord(
                snapshot_id=f"{source_record_id}:static",
                provider=self.provider_name,
                source_record_id=source_record_id,
                mmsi=mmsi or None,
                imo=str(static_data.get("ImoNumber")) if static_data.get("ImoNumber") else None,
                vessel_name=static_data.get("Name"),
                observed_at=observed_at,
                ingested_at=ingested_at,
                raw_reference=self.STREAM_URL,
                raw_payload=payload,
            )
            return None, snapshot

        position = message.get("PositionReport") or message.get("StandardClassBPositionReport")
        if not position:
            return None, None

        mmsi = str(position.get("UserID") or metadata.get("MMSI") or "").strip()
        lat = _as_float(position.get("Latitude"))
        lon = _as_float(position.get("Longitude"))
        if not mmsi or lat is None or lon is None:
            snapshot = VesselSourceSnapshotRecord(
                snapshot_id=f"{source_record_id}:parse-error",
                provider=self.provider_name,
                source_record_id=source_record_id,
                mmsi=mmsi or None,
                imo=None,
                vessel_name=None,
                observed_at=observed_at,
                ingested_at=ingested_at,
                raw_reference=self.STREAM_URL,
                raw_payload=payload,
                parse_error="Missing MMSI or coordinates in AISStream position report",
            )
            return None, snapshot

        cached = self._ship_cache.get(mmsi, {})
        record = VesselSnapshot(
            id=f"vessel:{mmsi}",
            mmsi=mmsi,
            imo=str(cached.get("ImoNumber")) if cached.get("ImoNumber") else None,
            vessel_name=cached.get("Name") or metadata.get("ShipName"),
            callsign=cached.get("CallSign"),
            vessel_type=str(cached.get("Type")) if cached.get("Type") else None,
            flag=metadata.get("Flag"),
            lat=lat,
            lon=lon,
            heading_deg=_as_float(position.get("TrueHeading")),
            course_deg=_as_float(position.get("Cog")),
            speed_kts=_as_float(position.get("Sog")),
            nav_status=str(position.get("NavigationalStatus")) if position.get("NavigationalStatus") is not None else None,
            destination=cached.get("Destination"),
            draught_m=_as_float(cached.get("MaximumStaticDraught")),
            source=self.provider_name,
            source_record_id=source_record_id,
            source_confidence=0.86,
            merged_confidence=0.86,
            observed_at=observed_at,
            last_ingested_at=ingested_at,
            raw_reference=self.STREAM_URL,
            raw_payload=payload,
        )
        snapshot = VesselSourceSnapshotRecord(
            snapshot_id=f"{source_record_id}:position",
            provider=self.provider_name,
            source_record_id=source_record_id,
            mmsi=mmsi,
            imo=record.imo,
            vessel_name=record.vessel_name,
            observed_at=observed_at,
            ingested_at=ingested_at,
            raw_reference=self.STREAM_URL,
            raw_payload=payload,
        )
        return record, snapshot
