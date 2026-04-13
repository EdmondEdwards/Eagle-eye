from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from skyfield.api import EarthSatellite, load, wgs84

from .canonical import OrbitSample, SatelliteCatalogRecord, SatelliteSnapshot


class SatellitePropagationService:
    def __init__(self) -> None:
        self._timescale = load.timescale(builtin=True)

    def propagate_one(
        self,
        record: SatelliteCatalogRecord,
        at: datetime,
        *,
        observed_at: datetime | None = None,
        playback_confidence: float | None = None,
    ) -> SatelliteSnapshot:
        target_time = at.astimezone(timezone.utc)
        geocentric = self._build_satellite(record).at(self._timescale.from_datetime(target_time))
        latitude, longitude = wgs84.latlon_of(geocentric)
        altitude_km = float(wgs84.height_of(geocentric).km)
        velocity = geocentric.velocity.km_per_s
        velocity_kms = math.sqrt(sum(float(component) ** 2 for component in velocity))
        return SatelliteSnapshot(
            id=record.id,
            norad_cat_id=record.norad_cat_id,
            international_designator=record.international_designator,
            name=record.name,
            object_type=record.object_type,
            orbit_class=record.orbit_class or self.classify_orbit(altitude_km),
            source=record.source,
            tle_line1=record.tle_line1,
            tle_line2=record.tle_line2,
            epoch=record.epoch,
            inclination_deg=record.inclination_deg,
            eccentricity=record.eccentricity,
            mean_motion=record.mean_motion,
            raan_deg=record.raan_deg,
            arg_perigee_deg=record.arg_perigee_deg,
            mean_anomaly_deg=record.mean_anomaly_deg,
            bstar=record.bstar,
            source_confidence=record.source_confidence,
            observed_at=observed_at or target_time,
            computed_lat=float(latitude.degrees),
            computed_lon=float(longitude.degrees),
            computed_alt_km=altitude_km,
            computed_velocity_kms=velocity_kms,
            group_name=record.group_name,
            raw_reference=record.raw_reference,
            raw_payload=record.raw_payload,
            playback_confidence=playback_confidence,
        )

    def propagate_many(
        self,
        records: Sequence[SatelliteCatalogRecord],
        at: datetime,
        *,
        observed_at: datetime | None = None,
        playback_confidence: float | None = None,
    ) -> list[SatelliteSnapshot]:
        return [
            self.propagate_one(record, at, observed_at=observed_at, playback_confidence=playback_confidence)
            for record in records
        ]

    def generate_orbit_path(
        self,
        record: SatelliteCatalogRecord,
        *,
        start: datetime,
        minutes_ahead: int = 90,
        step_seconds: int = 120,
    ) -> list[OrbitSample]:
        total_steps = max(2, int((minutes_ahead * 60) / max(step_seconds, 15)))
        points: list[OrbitSample] = []
        for step in range(total_steps + 1):
            sample_at = start + timedelta(seconds=step * step_seconds)
            snapshot = self.propagate_one(record, sample_at, observed_at=sample_at)
            points.append(
                OrbitSample(
                    observed_at=sample_at,
                    lat=snapshot.computed_lat,
                    lon=snapshot.computed_lon,
                    alt_km=snapshot.computed_alt_km,
                    velocity_kms=snapshot.computed_velocity_kms,
                )
            )
        return points

    def generate_playback_points(
        self,
        records: Iterable[tuple[SatelliteCatalogRecord, datetime, float | None]],
        *,
        since: datetime,
        until: datetime,
        step_seconds: int = 300,
    ) -> list[OrbitSample]:
        samples: list[OrbitSample] = []
        snapshot_records = list(records)
        if until <= since:
            return samples
        if not snapshot_records:
            return samples
        current = since
        while current <= until:
            best = min(
                snapshot_records,
                key=lambda item: abs((item[1] - current).total_seconds()),
            )
            snapshot = self.propagate_one(best[0], current, observed_at=current, playback_confidence=best[2])
            samples.append(
                OrbitSample(
                    observed_at=current,
                    lat=snapshot.computed_lat,
                    lon=snapshot.computed_lon,
                    alt_km=snapshot.computed_alt_km,
                    velocity_kms=snapshot.computed_velocity_kms,
                )
            )
            current += timedelta(seconds=max(step_seconds, 30))
        return samples

    def _build_satellite(self, record: SatelliteCatalogRecord) -> EarthSatellite:
        if record.tle_line1 and record.tle_line2:
            return EarthSatellite(record.tle_line1, record.tle_line2, record.name, self._timescale)
        return EarthSatellite.from_omm(self._timescale, record.raw_payload)

    @staticmethod
    def classify_orbit(altitude_km: float | None) -> str | None:
        if altitude_km is None:
            return None
        if altitude_km >= 35_000:
            return "GEO"
        if altitude_km >= 20_000:
            return "MEO"
        if altitude_km >= 2_000:
            return "HEO"
        return "LEO"
