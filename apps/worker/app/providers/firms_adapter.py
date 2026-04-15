from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any

import httpx


@dataclass(slots=True)
class FIRMSDetectionPayload:
    detection_id: str
    source_sensor: str
    acquisition_time: datetime
    latitude: float
    longitude: float
    brightness: float | None
    confidence: str | None
    frp: float | None
    daynight: str | None
    satellite: str | None
    raw: dict[str, Any]


class FIRMSAdapter:
    def __init__(
        self,
        *,
        map_key: str,
        base_url: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv",
        app_name: str = "Eagle Eye",
        timeout_seconds: float = 45.0,
    ) -> None:
        self.map_key = map_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={
                "Accept": "text/csv,application/json",
                "User-Agent": f"{app_name} hazard-ingest",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_area(
        self,
        *,
        sensor: str,
        bbox: tuple[float, float, float, float],
        days: int,
    ) -> list[FIRMSDetectionPayload]:
        bbox_text = ",".join(f"{value:.6f}" for value in bbox)
        url = f"{self.base_url}/{self.map_key}/{sensor}/{bbox_text}/{days}"
        response = await self._client.get(url)
        response.raise_for_status()
        return _parse_csv(sensor, response.text)


def _parse_csv(sensor: str, payload: str) -> list[FIRMSDetectionPayload]:
    reader = csv.DictReader(io.StringIO(payload))
    rows: list[FIRMSDetectionPayload] = []
    for row in reader:
        latitude = _to_float(row.get("latitude"))
        longitude = _to_float(row.get("longitude"))
        acq_date = (row.get("acq_date") or row.get("acquisition_date") or "").strip()
        acq_time = (row.get("acq_time") or row.get("acquisition_time") or "").strip()
        acquisition_time = _parse_acquisition_time(acq_date, acq_time)
        if latitude is None or longitude is None or acquisition_time is None:
            continue
        raw = dict(row)
        detection_id = row.get("firms_detection_id") or _derive_detection_id(sensor, latitude, longitude, acquisition_time, raw)
        rows.append(
            FIRMSDetectionPayload(
                detection_id=detection_id,
                source_sensor=(row.get("instrument") or row.get("sensor") or sensor).strip() or sensor,
                acquisition_time=acquisition_time,
                latitude=latitude,
                longitude=longitude,
                brightness=_first_float(row, "brightness", "bright_ti4", "brightness_value"),
                confidence=(row.get("confidence") or row.get("confidence_level") or None),
                frp=_first_float(row, "frp"),
                daynight=(row.get("daynight") or row.get("day_night") or None),
                satellite=(row.get("satellite") or row.get("platform") or None),
                raw=raw,
            )
        )
    return rows


def _parse_acquisition_time(acq_date: str, acq_time: str) -> datetime | None:
    if not acq_date:
        return None
    time_text = acq_time.zfill(4) if acq_time else "0000"
    try:
        return datetime.strptime(f"{acq_date} {time_text}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(acq_date.replace("Z", "+00:00"))
        except ValueError:
            return None


def _derive_detection_id(sensor: str, latitude: float, longitude: float, acquisition_time: datetime, raw: dict[str, Any]) -> str:
    digest = sha1(
        "|".join(
            [
                sensor,
                f"{latitude:.5f}",
                f"{longitude:.5f}",
                acquisition_time.isoformat(),
                str(raw.get("brightness") or raw.get("bright_ti4") or ""),
                str(raw.get("satellite") or raw.get("platform") or ""),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return f"firms:{digest}"


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_float(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None

