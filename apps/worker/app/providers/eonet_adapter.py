from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


@dataclass(slots=True)
class EONETGeometry:
    geometry_type: str
    event_time: datetime | None
    geometry: dict[str, Any]
    raw: dict[str, Any]


@dataclass(slots=True)
class EONETEventPayload:
    event_id: str
    title: str
    description: str | None
    link: str | None
    status: str
    categories: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    closed_at: datetime | None
    geometries: list[EONETGeometry]
    raw: dict[str, Any]


class EONETAdapter:
    def __init__(
        self,
        *,
        base_url: str = "https://eonet.gsfc.nasa.gov/api/v3",
        app_name: str = "Eagle Eye",
        use_geojson: bool = True,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.use_geojson = use_geojson
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": f"{app_name} hazard-ingest",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_events(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        source: str | None = None,
        days: int | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[EONETEventPayload]:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if category:
            params["category"] = category
        if source:
            params["source"] = source
        if days is not None:
            params["days"] = days
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        if bbox:
            params["bbox"] = ",".join(str(value) for value in bbox)
        path = "/events/geojson" if self.use_geojson else "/events"
        response = await self._client.get(f"{self.base_url}{path}", params=params)
        response.raise_for_status()
        payload = response.json()
        return self._parse_geojson(payload) if self.use_geojson else self._parse_json(payload)

    def _parse_json(self, payload: dict[str, Any]) -> list[EONETEventPayload]:
        events = payload.get("events", [])
        rows: list[EONETEventPayload] = []
        for event in events:
            rows.append(
                EONETEventPayload(
                    event_id=str(event["id"]),
                    title=event.get("title") or str(event["id"]),
                    description=event.get("description"),
                    link=event.get("link"),
                    status=(event.get("closed") and "closed") or event.get("status") or "open",
                    categories=list(event.get("categories") or []),
                    sources=list(event.get("sources") or []),
                    closed_at=_parse_datetime(event.get("closed")),
                    geometries=[
                        EONETGeometry(
                            geometry_type=str(item.get("type") or item.get("geometry", {}).get("type") or "Unknown"),
                            event_time=_parse_datetime(item.get("date")),
                            geometry=item.get("coordinates")
                            and {"type": item.get("type", "Point"), "coordinates": item.get("coordinates")}
                            or item.get("geometry")
                            or {},
                            raw=item,
                        )
                        for item in (event.get("geometry") or [])
                        if item.get("geometry") or item.get("coordinates")
                    ],
                    raw=event,
                )
            )
        return rows

    def _parse_geojson(self, payload: dict[str, Any]) -> list[EONETEventPayload]:
        rows: list[EONETEventPayload] = []
        for feature in payload.get("features", []):
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            rows.append(
                EONETEventPayload(
                    event_id=str(properties.get("id") or feature.get("id")),
                    title=properties.get("title") or str(properties.get("id") or feature.get("id")),
                    description=properties.get("description"),
                    link=properties.get("link"),
                    status=(properties.get("closed") and "closed") or properties.get("status") or "open",
                    categories=list(properties.get("categories") or []),
                    sources=list(properties.get("sources") or []),
                    closed_at=_parse_datetime(properties.get("closed")),
                    geometries=[
                        EONETGeometry(
                            geometry_type=str(geometry.get("type") or "Unknown"),
                            event_time=_parse_datetime(properties.get("geometry_date") or properties.get("date")),
                            geometry=geometry,
                            raw={"geometry": geometry, "properties": properties},
                        )
                    ]
                    if geometry
                    else [],
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
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None

