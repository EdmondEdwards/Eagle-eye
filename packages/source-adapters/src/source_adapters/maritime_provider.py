from __future__ import annotations

from abc import ABC
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Literal

from .canonical import MaritimeProviderDescriptor, VesselPresenceOverlayRecord, VesselSnapshot, VesselSourceHealthRecord, VesselSourceSnapshotRecord


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MaritimeProvider(ABC):
    provider_name: str
    ingest_mode: Literal["websocket", "polling", "batch"]
    priority: int
    enabled: bool

    def __init__(self, *, enabled: bool, priority: int, description: str | None = None) -> None:
        self.enabled = enabled
        self.priority = priority
        self.description = description
        self._health = VesselSourceHealthRecord(
            provider_name=self.provider_name,
            ingest_mode=self.ingest_mode,
            enabled=enabled,
            priority=priority,
            health_state="disabled" if not enabled else "healthy",
        )

    def descriptor(self) -> MaritimeProviderDescriptor:
        return MaritimeProviderDescriptor(
            provider_name=self.provider_name,
            ingest_mode=self.ingest_mode,
            priority=self.priority,
            enabled=self.enabled,
            description=self.description,
        )

    def health_snapshot(self) -> VesselSourceHealthRecord:
        return replace(self._health)

    def mark_attempt(self) -> None:
        self._health.last_attempt = utc_now()
        self._health.updated_at = utc_now()

    def mark_success(self, *, valid_messages: int = 0) -> None:
        now = utc_now()
        self._health.health_state = "healthy" if self.enabled else "disabled"
        self._health.last_success = now
        self._health.last_attempt = now
        self._health.valid_message_count += max(valid_messages, 0)
        self._health.last_error = None
        self._health.updated_at = now

    def mark_error(self, message: str, *, degraded: bool = True) -> None:
        now = utc_now()
        self._health.last_attempt = now
        self._health.error_count += 1
        self._health.last_error = message[:500]
        self._health.health_state = "degraded" if degraded and self.enabled else "unhealthy"
        self._health.updated_at = now

    def mark_stalled(self, message: str) -> None:
        self._health.health_state = "degraded" if self.enabled else "disabled"
        self._health.last_error = message[:500]
        self._health.updated_at = utc_now()

    async def stream_records(self) -> AsyncIterator[tuple[VesselSnapshot | None, VesselSourceSnapshotRecord | None]]:
        if False:
            yield None, None

    async def poll_records(self) -> tuple[list[VesselSnapshot], list[VesselSourceSnapshotRecord]]:
        return [], []

    async def poll_presence_overlay(self) -> list[VesselPresenceOverlayRecord]:
        return []

    @staticmethod
    def extract_record_id(payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return str(value)
        return None
