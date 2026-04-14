from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


EARTH_RADIUS_KM = 6371.0


def _utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _wrap_lon(lon: float) -> float:
    return ((lon + 540.0) % 360.0) - 180.0


def _step_position(lat: float, lon: float, heading_deg: float, distance_km: float) -> tuple[float, float]:
    if distance_km == 0:
        return lat, lon
    heading = math.radians(heading_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    angular = distance_km / EARTH_RADIUS_KM
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular)
        + math.cos(lat1) * math.sin(angular) * math.cos(heading)
    )
    lon2 = lon1 + math.atan2(
        math.sin(heading) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), _wrap_lon(math.degrees(lon2))


def _predict_track(
    *,
    lat: float,
    lon: float,
    heading_deg: float | None,
    speed_kts: float | None,
    observed_at: datetime | None,
    minutes_ahead: int,
    step_seconds: int,
    altitude_m: float | None = None,
) -> list[dict[str, float | str | None]]:
    start = _utc(observed_at)
    heading = float(heading_deg or 0.0)
    speed = max(float(speed_kts or 0.0), 0.0)
    speed_kmh = speed * 1.852
    points: list[dict[str, float | str | None]] = []
    current_lat = lat
    current_lon = lon
    for offset in range(0, max(minutes_ahead * 60, step_seconds) + 1, step_seconds):
        if offset > 0:
            distance_km = speed_kmh * (step_seconds / 3600.0)
            current_lat, current_lon = _step_position(current_lat, current_lon, heading, distance_km)
        points.append(
            {
                "lat": current_lat,
                "lon": current_lon,
                "altitude_m": altitude_m,
                "observed_at": (start + timedelta(seconds=offset)).isoformat(),
                "confidence": max(0.15, 1.0 - (offset / max(minutes_ahead * 60, 1)) * 0.6),
            }
        )
    return points


def predict_aircraft_track(**kwargs: float | int | datetime | None) -> list[dict[str, float | str | None]]:
    return _predict_track(**kwargs)


def predict_vessel_track(**kwargs: float | int | datetime | None) -> list[dict[str, float | str | None]]:
    return _predict_track(**kwargs)


def compute_satellite_footprint(lat: float, lon: float, altitude_km: float, half_angle_deg: float = 20.0, segments: int = 48) -> dict[str, object]:
    altitude = max(altitude_km, 1.0)
    radius_km = math.tan(math.radians(half_angle_deg)) * altitude
    lat_radius = radius_km / 111.32
    lon_radius = radius_km / max(111.32 * math.cos(math.radians(max(min(lat, 89.0), -89.0))), 0.25)
    ring: list[list[float]] = []
    for index in range(segments):
        theta = (2 * math.pi * index) / segments
        ring.append([_wrap_lon(lon + math.cos(theta) * lon_radius), lat + math.sin(theta) * lat_radius])
    ring.append(ring[0])
    return {
        "type": "Polygon",
        "coordinates": [ring],
        "properties": {
          "center": {"lat": lat, "lon": lon},
          "radius_km": radius_km,
          "half_angle_deg": half_angle_deg,
        },
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def compute_visibility_passes(
    track: list[dict[str, float | str | None]],
    target_lat: float,
    target_lon: float,
    threshold_km: float,
) -> list[dict[str, object]]:
    passes: list[dict[str, object]] = []
    active: dict[str, object] | None = None
    for point in track:
        lat = float(point["lat"])
        lon = float(point["lon"])
        timestamp = str(point["observed_at"])
        distance = _haversine_km(lat, lon, target_lat, target_lon)
        if distance <= threshold_km:
            if active is None:
                active = {
                    "start_time": timestamp,
                    "min_distance_km": distance,
                    "closest_point": {"lat": lat, "lon": lon, "observed_at": timestamp},
                }
            else:
                active["min_distance_km"] = min(float(active["min_distance_km"]), distance)
                if distance <= float(active["min_distance_km"]):
                    active["closest_point"] = {"lat": lat, "lon": lon, "observed_at": timestamp}
            active["end_time"] = timestamp
        elif active is not None:
            passes.append(active)
            active = None
    if active is not None:
        passes.append(active)
    return passes
