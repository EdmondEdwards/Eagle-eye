from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from source_adapters.canonical import OrbitSample, SatelliteCatalogRecord
from source_adapters.satellite_propagation_service import SatellitePropagationService as CoreSatellitePropagationService

_service = CoreSatellitePropagationService()


def _as_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def catalog_record_from_row(row: dict[str, Any]) -> SatelliteCatalogRecord:
    return SatelliteCatalogRecord(
        id=row.get("id") or f"satellite:{row['norad_cat_id']}",
        norad_cat_id=str(row["norad_cat_id"]),
        international_designator=row.get("international_designator"),
        name=row["name"],
        object_type=row.get("object_type"),
        orbit_class=row.get("orbit_class"),
        source=row.get("source") or "celestrak",
        tle_line1=row.get("tle_line1"),
        tle_line2=row.get("tle_line2"),
        epoch=_as_datetime(row.get("epoch")),
        inclination_deg=row.get("inclination_deg"),
        eccentricity=row.get("eccentricity"),
        mean_motion=row.get("mean_motion"),
        raan_deg=row.get("raan_deg"),
        arg_perigee_deg=row.get("arg_perigee_deg"),
        mean_anomaly_deg=row.get("mean_anomaly_deg"),
        bstar=row.get("bstar"),
        source_confidence=row.get("source_confidence") or 0.74,
        observed_at=_as_datetime(row.get("observed_at")) or datetime.now(timezone.utc),
        group_name=row.get("group_name"),
        raw_reference=row.get("raw_reference"),
        raw_payload=row.get("raw_payload") or {},
    )


def orbit_path_from_row(
    row: dict[str, Any],
    *,
    start: datetime,
    minutes_ahead: int,
    step_seconds: int,
) -> list[OrbitSample]:
    record = catalog_record_from_row(row)
    return _service.generate_orbit_path(record, start=start, minutes_ahead=minutes_ahead, step_seconds=step_seconds)


def playback_from_rows(
    rows: list[dict[str, Any]],
    *,
    since: datetime,
    until: datetime,
    step_seconds: int,
) -> list[OrbitSample]:
    snapshots = [
        (
            catalog_record_from_row(row),
            _as_datetime(row.get("observed_at")) or since,
            row.get("source_confidence"),
        )
        for row in rows
    ]
    return _service.generate_playback_points(snapshots, since=since, until=until, step_seconds=step_seconds)
