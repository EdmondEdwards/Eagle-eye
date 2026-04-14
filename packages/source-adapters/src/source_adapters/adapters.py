from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urljoin

import httpx
import websockets
from bs4 import BeautifulSoup

from .canonical import AirspaceOverlayRecord, AircraftSnapshot, VesselSnapshot, WebcamCatalogEntry

LOGGER = logging.getLogger(__name__)


class OpenSkyAdapter:
    TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    STATES_URL = "https://opensky-network.org/api/states/all"

    def __init__(self, client_id: str | None, client_secret: str | None) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _ensure_token(self, client: httpx.AsyncClient) -> str | None:
        if not self.client_id or not self.client_secret:
            return None
        if self._access_token and self._token_expires_at > asyncio.get_running_loop().time() + 30:
            return self._access_token

        response = await client.post(
            self.TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload.get("access_token")
        self._token_expires_at = asyncio.get_running_loop().time() + float(payload.get("expires_in", 300))
        return self._access_token

    async def poll(self) -> list[AircraftSnapshot]:
        if not self.client_id or not self.client_secret:
            LOGGER.warning("OpenSky credentials are not configured; aircraft ingest is idle.")
            return []

        async with httpx.AsyncClient(follow_redirects=True) as client:
            token = await self._ensure_token(client)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            response = await client.get(self.STATES_URL, headers=headers, timeout=30.0)
            response.raise_for_status()
            payload = response.json()

        snapshots: list[AircraftSnapshot] = []
        observed_at = datetime.now(timezone.utc)
        for state in payload.get("states", []):
            if len(state) < 17 or state[5] is None or state[6] is None:
                continue

            icao24 = str(state[0]).strip()
            velocity_ms = state[9]
            vertical_rate_ms = state[11]
            snapshots.append(
                AircraftSnapshot(
                    id=f"aircraft:{icao24}",
                    icao24=icao24,
                    callsign=state[1].strip() if state[1] else None,
                    registration=None,
                    operator=state[2] if state[2] else None,
                    lon=float(state[5]),
                    lat=float(state[6]),
                    altitude_m=float(state[13] if state[13] is not None else state[7]) if state[13] is not None or state[7] is not None else None,
                    heading_deg=float(state[10]) if state[10] is not None else None,
                    velocity_kts=float(velocity_ms) * 1.94384 if velocity_ms is not None else None,
                    vertical_rate=float(vertical_rate_ms) if vertical_rate_ms is not None else None,
                    observed_at=datetime.fromtimestamp(state[4], tz=timezone.utc) if state[4] else observed_at,
                    raw_reference=self.STATES_URL,
                    raw_payload={
                        "state_vector": state,
                        "time": payload.get("time"),
                    },
                )
            )

        return snapshots


class AISStreamAdapter:
    STREAM_URL = "wss://stream.aisstream.io/v0/stream"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key
        self._vessel_cache: dict[str, dict[str, Any]] = {}

    async def stream(self) -> AsyncIterator[VesselSnapshot]:
        if not self.api_key:
            LOGGER.warning("AISStream API key is not configured; vessel ingest is idle.")
            while True:
                await asyncio.sleep(60)
            return

        subscription = {
            "APIKey": self.api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FilterMessageTypes": [
                "PositionReport",
                "StandardClassBPositionReport",
                "ShipStaticData",
            ],
        }

        backoff = 2
        while True:
            try:
                async with websockets.connect(self.STREAM_URL, ping_interval=20, ping_timeout=20, max_size=2**22) as socket:
                    await socket.send(json.dumps(subscription))
                    backoff = 2
                    async for raw_message in socket:
                        payload = json.loads(raw_message)
                        message_type = payload.get("MessageType")
                        metadata = payload.get("MetaData", {})
                        message = payload.get("Message", {})
                        if message_type == "ShipStaticData":
                            ship_data = message.get("ShipStaticData", {})
                            mmsi = str(ship_data.get("UserID") or metadata.get("MMSI") or "")
                            if mmsi:
                                self._vessel_cache[mmsi] = ship_data
                            continue

                        candidate = message.get("PositionReport") or message.get("StandardClassBPositionReport")
                        if not candidate:
                            continue

                        mmsi = str(candidate.get("UserID") or metadata.get("MMSI") or "")
                        cached = self._vessel_cache.get(mmsi, {})
                        lat = candidate.get("Latitude")
                        lon = candidate.get("Longitude")
                        if lat is None or lon is None or not mmsi:
                            continue

                        observed_at = metadata.get("time_utc")
                        yield VesselSnapshot(
                            id=f"vessel:{mmsi}",
                            mmsi=mmsi,
                            imo=str(cached.get("ImoNumber")) if cached.get("ImoNumber") else None,
                            vessel_name=cached.get("Name"),
                            vessel_type=str(cached.get("Type")) if cached.get("Type") else None,
                            flag=cached.get("CallSign"),
                            lat=float(lat),
                            lon=float(lon),
                            heading_deg=float(candidate.get("TrueHeading")) if candidate.get("TrueHeading") is not None else None,
                            speed_kts=float(candidate.get("Sog")) if candidate.get("Sog") is not None else None,
                            observed_at=datetime.fromisoformat(observed_at.replace("Z", "+00:00")) if observed_at else datetime.now(timezone.utc),
                            raw_reference=self.STREAM_URL,
                            raw_payload=payload,
                        )
            except Exception as exc:  # pragma: no cover - network recovery path
                LOGGER.warning("AISStream connection dropped: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)


class FAAAirspaceAdapter:
    LIST_URL = "https://tfr.faa.gov/tfr2/list.html"
    DETAIL_LINK_RE = re.compile(r"detail_\d+\.html")
    DECIMAL_COORD_RE = re.compile(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)")
    RADIUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(NM|nautical miles?)", re.IGNORECASE)

    async def fetch_active(self) -> list[AirspaceOverlayRecord]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            listing_response = await client.get(self.LIST_URL, timeout=30.0)
            listing_response.raise_for_status()
            soup = BeautifulSoup(listing_response.text, "html.parser")
            detail_urls = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if self.DETAIL_LINK_RE.search(href):
                    detail_urls.append(urljoin(self.LIST_URL, href))

            overlays: list[AirspaceOverlayRecord] = []
            for detail_url in list(dict.fromkeys(detail_urls))[:150]:
                try:
                    detail_response = await client.get(detail_url, timeout=30.0)
                    detail_response.raise_for_status()
                    overlay = self._parse_detail(detail_url, detail_response.text)
                    if overlay:
                        overlays.append(overlay)
                except Exception as exc:  # pragma: no cover - best effort parser
                    LOGGER.warning("FAA detail parse failed for %s: %s", detail_url, exc)
            return overlays

    def _parse_detail(self, detail_url: str, html: str) -> AirspaceOverlayRecord | None:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        identifier = detail_url.rsplit("/", 1)[-1].replace(".html", "")
        title = soup.title.string.strip() if soup.title and soup.title.string else identifier

        coords = [(float(match.group(2)), float(match.group(1))) for match in self.DECIMAL_COORD_RE.finditer(text)]
        geometry: dict[str, Any] | None = None
        if len(coords) >= 3:
            ring = [[lon, lat] for lon, lat in coords[:80]]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            geometry = {"type": "Polygon", "coordinates": [ring]}
        else:
            center = coords[0] if coords else None
            radius_match = self.RADIUS_RE.search(text)
            if center and radius_match:
                radius_nm = float(radius_match.group(1))
                geometry = self._circle_polygon(center[0], center[1], radius_nm)

        active_from = None
        active_to = None
        iso_candidates = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text)
        if iso_candidates:
            active_from = datetime.fromisoformat(iso_candidates[0].replace("Z", "+00:00"))
            active_to = datetime.fromisoformat(iso_candidates[-1].replace("Z", "+00:00"))

        return AirspaceOverlayRecord(
            id=f"airspace:{identifier}",
            source_id=identifier,
            name=title,
            category="tfr",
            geometry=geometry,
            active_from=active_from,
            active_to=active_to,
            raw_reference=detail_url,
            raw_payload={"html_excerpt": text[:1500]},
        )

    def _circle_polygon(self, lat: float, lon: float, radius_nm: float) -> dict[str, Any]:
        points: list[list[float]] = []
        radius_deg_lat = radius_nm / 60.0
        radius_deg_lon = radius_nm / max(60.0 * math.cos(math.radians(lat)), 0.1)
        for index in range(0, 36):
            theta = (index / 36.0) * (2 * math.pi)
            points.append([lon + math.cos(theta) * radius_deg_lon, lat + math.sin(theta) * radius_deg_lat])
        points.append(points[0])
        return {"type": "Polygon", "coordinates": [points]}


class WebcamCatalogAdapter:
    def catalog(self) -> list[WebcamCatalogEntry]:
        seed_path = Path(__file__).resolve().parents[4] / "data" / "webcams" / "approved_webcams_seed.json"
        if not seed_path.exists():
            LOGGER.warning("Approved webcam seed not found at %s", seed_path)
            return []

        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        entries = payload.get("entries", payload if isinstance(payload, list) else [])
        catalog: list[WebcamCatalogEntry] = []
        for entry in entries:
            catalog.append(
                WebcamCatalogEntry(
                    id=entry["id"],
                    name=entry["name"],
                    provider=entry["provider"],
                    provider_camera_id=entry.get("provider_camera_id"),
                    country=entry["country"],
                    region=entry["region"],
                    city=entry["city"],
                    lat=float(entry["lat"]),
                    lon=float(entry["lon"]),
                    category=entry["category"],
                    subcategory=entry["subcategory"],
                    watch_url=entry["watch_url"],
                    embed_url=entry.get("embed_url"),
                    preview_image_url=entry.get("preview_image_url"),
                    access_mode=entry["access_mode"],
                    embed_allowed=bool(entry["embed_allowed"]),
                    source_confidence=float(entry["source_confidence"]),
                    tags=list(entry.get("tags", [])),
                    priority=int(entry.get("priority", 2)),
                    metadata=dict(entry.get("metadata", {})),
                )
            )
        return catalog
