from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from .canonical import SatelliteCatalogRecord, SatelliteIngestResult, SatelliteSourceSnapshotRecord
from .satellite_provider import SatelliteProvider

LOGGER = logging.getLogger(__name__)


def _as_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_tle_payload(text: str) -> dict[str, tuple[str | None, str, str]]:
    mapping: dict[str, tuple[str | None, str, str]] = {}
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    index = 0
    while index < len(lines):
        name: str | None = None
        first = lines[index]
        if first.startswith("1 ") and index + 1 < len(lines):
            line1 = first
            line2 = lines[index + 1]
            index += 2
        elif index + 2 < len(lines):
            name = first.strip()
            line1 = lines[index + 1]
            line2 = lines[index + 2]
            index += 3
        else:
            break
        if not line1.startswith("1 ") or not line2.startswith("2 "):
            continue
        catalog_number = line1[2:7].strip()
        mapping[catalog_number] = (name, line1, line2)
    return mapping


class CelesTrakSatelliteAdapter(SatelliteProvider):
    provider_name = "celestrak"
    BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"

    def __init__(self, groups: tuple[str, ...] | None = None) -> None:
        self.groups = groups or ("active",)

    async def fetch_catalog(self) -> SatelliteIngestResult:
        observed_at = datetime.now(timezone.utc)
        catalog_by_norad: dict[str, SatelliteCatalogRecord] = {}
        snapshots: list[SatelliteSourceSnapshotRecord] = []

        async with httpx.AsyncClient(follow_redirects=True) as client:
            for group in self.groups:
                params_json = {"GROUP": group, "FORMAT": "json"}
                params_tle = {"GROUP": group, "FORMAT": "tle"}
                json_response, tle_response = await asyncio.gather(
                    client.get(self.BASE_URL, params=params_json, timeout=45.0),
                    client.get(self.BASE_URL, params=params_tle, timeout=45.0),
                )
                json_response.raise_for_status()
                tle_response.raise_for_status()
                tle_map = _parse_tle_payload(tle_response.text)
                source_url = str(json_response.url)

                for fields in json_response.json():
                    norad_cat_id = str(fields.get("NORAD_CAT_ID") or "").strip()
                    if not norad_cat_id:
                        continue

                    tle_name, tle_line1, tle_line2 = tle_map.get(norad_cat_id, (None, None, None))
                    name = str(fields.get("OBJECT_NAME") or tle_name or norad_cat_id).strip()
                    epoch = _as_datetime(fields.get("EPOCH"))
                    record = SatelliteCatalogRecord(
                        id=f"satellite:{norad_cat_id}",
                        norad_cat_id=norad_cat_id,
                        international_designator=str(fields.get("OBJECT_ID") or "").strip() or None,
                        name=name,
                        object_type=str(fields.get("OBJECT_TYPE") or "").strip() or None,
                        orbit_class=None,
                        source=self.provider_name,
                        tle_line1=tle_line1,
                        tle_line2=tle_line2,
                        epoch=epoch,
                        inclination_deg=_as_float(fields.get("INCLINATION")),
                        eccentricity=_as_float(fields.get("ECCENTRICITY")),
                        mean_motion=_as_float(fields.get("MEAN_MOTION")),
                        raan_deg=_as_float(fields.get("RA_OF_ASC_NODE")),
                        arg_perigee_deg=_as_float(fields.get("ARG_OF_PERICENTER")),
                        mean_anomaly_deg=_as_float(fields.get("MEAN_ANOMALY")),
                        bstar=_as_float(fields.get("BSTAR")),
                        source_confidence=0.78,
                        observed_at=observed_at,
                        group_name=group.upper(),
                        raw_reference=source_url,
                        raw_payload=fields,
                    )
                    catalog_by_norad[norad_cat_id] = record
                    snapshots.append(
                        SatelliteSourceSnapshotRecord(
                            snapshot_id=str(uuid4()),
                            satellite_id=record.id,
                            norad_cat_id=norad_cat_id,
                            provider=self.provider_name,
                            group_name=group.upper(),
                            payload_format="omm-json",
                            epoch=epoch,
                            observed_at=observed_at,
                            raw_reference=source_url,
                            raw_payload=fields,
                        )
                    )

        LOGGER.info("CelesTrak fetched %s catalog records across groups=%s", len(catalog_by_norad), ",".join(self.groups))
        return SatelliteIngestResult(
            provider=self.provider_name,
            catalog_records=sorted(catalog_by_norad.values(), key=lambda record: record.norad_cat_id),
            source_snapshots=snapshots,
            observed_at=observed_at,
        )
