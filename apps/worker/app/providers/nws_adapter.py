from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


@dataclass(slots=True)
class NWSAlertPayload:
    alert_id: str
    event: str
    severity: str | None
    certainty: str | None
    urgency: str | None
    status: str
    sent: datetime | None
    effective: datetime | None
    onset: datetime | None
    expires: datetime | None
    headline: str | None
    description: str | None
    instruction: str | None
    area_desc: str | None
    parameters: dict[str, Any]
    geometry: dict[str, Any] | None
    raw: dict[str, Any]


class NWSAdapter:
    def __init__(
        self,
        *,
        base_url: str = "https://api.weather.gov",
        app_name: str = "Eagle Eye",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={
                "Accept": "application/geo+json,application/json",
                "User-Agent": f"{app_name} (hazard-ingest)",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_active_alerts(self) -> list[NWSAlertPayload]:
        response = await self._client.get(f"{self.base_url}/alerts/active")
        response.raise_for_status()
        payload = response.json()
        rows: list[NWSAlertPayload] = []
        for feature in payload.get("features", []):
            properties = feature.get("properties") or {}
            rows.append(
                NWSAlertPayload(
                    alert_id=str(properties.get("id") or feature.get("id")),
                    event=properties.get("event") or "Alert",
                    severity=properties.get("severity"),
                    certainty=properties.get("certainty"),
                    urgency=properties.get("urgency"),
                    status=properties.get("status") or "Actual",
                    sent=_parse_datetime(properties.get("sent")),
                    effective=_parse_datetime(properties.get("effective")),
                    onset=_parse_datetime(properties.get("onset")),
                    expires=_parse_datetime(properties.get("expires")),
                    headline=properties.get("headline"),
                    description=properties.get("description"),
                    instruction=properties.get("instruction"),
                    area_desc=properties.get("areaDesc"),
                    parameters=dict(properties.get("parameters") or {}),
                    geometry=feature.get("geometry"),
                    raw=feature,
                )
            )
        return rows


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None

