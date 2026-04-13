from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx

from .canonical import VesselPresenceOverlayRecord
from .maritime_provider import MaritimeProvider

LOGGER = logging.getLogger(__name__)


class GlobalFishingWatchProvider(MaritimeProvider):
    provider_name = "global_fishing_watch"
    ingest_mode = "batch"
    BASE_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"

    def __init__(self, *, enabled: bool, api_token: str | None, poll_interval_seconds: int = 3600) -> None:
        super().__init__(enabled=enabled and bool(api_token), priority=20, description="Delayed AIS-derived vessel presence enrichment")
        self.api_token = api_token
        self.poll_interval_seconds = max(900, poll_interval_seconds)

    async def poll_presence_overlay(self) -> list[VesselPresenceOverlayRecord]:
        if not self.enabled or not self.api_token:
            return []

        self.mark_attempt()
        observed_to = datetime.now(timezone.utc)
        observed_from = observed_to - timedelta(days=1)
        params = {
            "datasets[0]": "public-global-presence:latest",
            "date-range": f"{observed_from.date().isoformat()},{observed_to.date().isoformat()}",
            "format": "JSON",
            "spatial-resolution": "LOW",
            "temporal-resolution": "DAY",
            "spatial-aggregation": "true",
        }
        payload = {
            "region": {
                "geojson": {
                    "type": "Polygon",
                    "coordinates": [[[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]],
                }
            }
        }

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.post(
                    self.BASE_URL,
                    params=params,
                    json=payload,
                    timeout=90.0,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                )
                response.raise_for_status()
            overlays = self._parse_report(response.json(), observed_from=observed_from, observed_to=observed_to, raw_reference=str(response.url))
            self.mark_success(valid_messages=len(overlays))
            return overlays
        except Exception as exc:  # pragma: no cover - network recovery path
            self.mark_error(f"GFW presence fetch failed: {exc}")
            LOGGER.warning("GFW presence fetch failed: %s", exc)
            return []

    def _parse_report(
        self,
        payload: dict[str, Any],
        *,
        observed_from: datetime,
        observed_to: datetime,
        raw_reference: str,
    ) -> list[VesselPresenceOverlayRecord]:
        overlays: list[VesselPresenceOverlayRecord] = []
        rows = payload.get("entries") or payload.get("data") or payload.get("features") or []
        if not isinstance(rows, list):
            return overlays

        for row in rows:
            if not isinstance(row, dict):
                continue
            geometry = row.get("geometry")
            if not geometry and isinstance(row.get("region"), dict):
                geometry = row["region"].get("geometry")
            if not isinstance(geometry, dict):
                continue

            density = row.get("value") or row.get("presence") or row.get("metric")
            try:
                density_value = float(density) if density is not None else None
            except (TypeError, ValueError):
                density_value = None

            overlays.append(
                VesselPresenceOverlayRecord(
                    overlay_id=f"gfw:{uuid4()}",
                    provider=self.provider_name,
                    dataset="public-global-presence:latest",
                    label="Global Fishing Watch vessel presence",
                    category="vessel_presence",
                    geometry=geometry,
                    density=density_value,
                    observed_from=observed_from,
                    observed_to=observed_to,
                    source_confidence=0.52,
                    raw_reference=raw_reference,
                    raw_payload=row,
                )
            )
        return overlays
