from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable

from .canonical import VesselSnapshot


PROVIDER_PREFERENCE = {
    "aisstream": 3,
    "aishub": 2,
    "global_fishing_watch": 1,
}


def _provider_rank(source: str) -> int:
    return PROVIDER_PREFERENCE.get(source, 0)


def _same_target(left: VesselSnapshot, right: VesselSnapshot) -> bool:
    if left.mmsi and right.mmsi and left.mmsi == right.mmsi:
        return True
    if left.imo and right.imo and left.imo == right.imo:
        return True
    if left.vessel_name and right.vessel_name and left.vessel_name.strip().upper() == right.vessel_name.strip().upper():
        return True
    return False


def merge_vessel_records(records: Iterable[VesselSnapshot], *, now: datetime | None = None, stale_after_seconds: int = 300) -> list[VesselSnapshot]:
    current_time = now or datetime.now(timezone.utc)
    merged: list[VesselSnapshot] = []

    for record in records:
        existing_index = next((index for index, candidate in enumerate(merged) if _same_target(candidate, record)), None)
        if existing_index is None:
            merged.append(record)
            continue

        current = merged[existing_index]
        winner = current
        if _provider_rank(record.source) > _provider_rank(current.source):
            winner = record
        elif record.observed_at > current.observed_at:
            winner = record
        elif (record.source_confidence or 0) > (current.source_confidence or 0):
            winner = record

        merged[existing_index] = VesselSnapshot(
            id=winner.id,
            mmsi=winner.mmsi or current.mmsi,
            imo=winner.imo or current.imo,
            vessel_name=winner.vessel_name or current.vessel_name,
            callsign=winner.callsign or current.callsign,
            vessel_type=winner.vessel_type or current.vessel_type,
            flag=winner.flag or current.flag,
            lat=winner.lat,
            lon=winner.lon,
            heading_deg=winner.heading_deg if winner.heading_deg is not None else current.heading_deg,
            course_deg=winner.course_deg if winner.course_deg is not None else current.course_deg,
            speed_kts=winner.speed_kts if winner.speed_kts is not None else current.speed_kts,
            nav_status=winner.nav_status or current.nav_status,
            destination=winner.destination or current.destination,
            draught_m=winner.draught_m if winner.draught_m is not None else current.draught_m,
            source=winner.source,
            source_record_id=winner.source_record_id or current.source_record_id,
            source_confidence=max(winner.source_confidence, current.source_confidence),
            merged_confidence=max(
                winner.merged_confidence or winner.source_confidence,
                current.merged_confidence or current.source_confidence,
            ),
            observed_at=max(winner.observed_at, current.observed_at),
            last_ingested_at=max(winner.last_ingested_at, current.last_ingested_at),
            raw_reference=winner.raw_reference or current.raw_reference,
            raw_payload=winner.raw_payload or current.raw_payload,
            stale=False,
        )

    return [
        replace(
            record,
            stale=(current_time - record.observed_at).total_seconds() > stale_after_seconds,
            merged_confidence=record.merged_confidence or max(record.source_confidence, 0.0),
        )
        for record in merged
    ]
