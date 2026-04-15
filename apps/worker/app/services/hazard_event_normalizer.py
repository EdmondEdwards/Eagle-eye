from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)


def normalize_eonet_event(
    *,
    event_id: str,
    title: str,
    status: str,
    categories: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    link: str | None,
    description: str | None,
    closed_at: datetime | None,
    geometry_geojson: dict[str, Any] | None,
    geometry_time: datetime | None,
) -> dict[str, Any]:
    category_titles = [str(item.get("title") or item.get("id") or "").strip() for item in categories if item]
    primary_category = next((item for item in category_titles if item), "Natural Event")
    return {
        "source": "eonet",
        "source_record_id": event_id,
        "type": "natural_event",
        "title": title,
        "status": status.lower(),
        "severity": infer_eonet_severity(category_titles),
        "confidence": 0.8,
        "start_time": utc(geometry_time) or utc(closed_at) or datetime.now(timezone.utc),
        "end_time": utc(closed_at),
        "geometry_geojson": geometry_geojson,
        "properties_json": {
            "category": primary_category,
            "categories": categories,
            "sources": sources,
            "description": description,
            "link": link,
            "provenance": {"native_table": "eonet_events", "native_id": event_id},
        },
    }


def normalize_firms_cluster(
    *,
    cluster_id: str,
    title: str,
    severity: str,
    confidence: float,
    start_time: datetime,
    end_time: datetime,
    geometry_geojson: dict[str, Any] | None,
    properties_json: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source": "firms",
        "source_record_id": cluster_id,
        "type": "fire_cluster_event",
        "title": title,
        "status": "active",
        "severity": severity,
        "confidence": confidence,
        "start_time": utc(start_time) or datetime.now(timezone.utc),
        "end_time": utc(end_time),
        "geometry_geojson": geometry_geojson,
        "properties_json": {
            **properties_json,
            "category": "Wildfires",
            "provenance": {"native_table": "firms_detections", "cluster_id": cluster_id},
        },
    }


def normalize_firms_detection(
    *,
    detection_id: str,
    title: str,
    severity: str,
    confidence: float,
    acquisition_time: datetime,
    geometry_geojson: dict[str, Any],
    properties_json: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source": "firms",
        "source_record_id": detection_id,
        "type": "fire_detection",
        "title": title,
        "status": "active",
        "severity": severity,
        "confidence": confidence,
        "start_time": utc(acquisition_time) or datetime.now(timezone.utc),
        "end_time": utc(acquisition_time),
        "geometry_geojson": geometry_geojson,
        "properties_json": {
            **properties_json,
            "category": "Wildfires",
            "provenance": {"native_table": "firms_detections", "native_id": detection_id},
        },
    }


def normalize_nws_alert(
    *,
    alert_id: str,
    event: str,
    status: str,
    severity: str | None,
    certainty: str | None,
    urgency: str | None,
    headline: str | None,
    description: str | None,
    instruction: str | None,
    area_desc: str | None,
    parameters: dict[str, Any],
    effective: datetime | None,
    onset: datetime | None,
    expires: datetime | None,
    sent: datetime | None,
    geometry_geojson: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source": "nws",
        "source_record_id": alert_id,
        "type": "weather_alert",
        "title": headline or event,
        "status": status.lower(),
        "severity": normalize_nws_severity(severity),
        "confidence": infer_nws_confidence(certainty),
        "start_time": utc(onset) or utc(effective) or utc(sent) or datetime.now(timezone.utc),
        "end_time": utc(expires),
        "geometry_geojson": geometry_geojson,
        "properties_json": {
            "category": event,
            "event": event,
            "certainty": certainty,
            "urgency": urgency,
            "description": description,
            "instruction": instruction,
            "area_desc": area_desc,
            "parameters": parameters,
            "provenance": {"native_table": "nws_alerts", "native_id": alert_id},
        },
    }


def infer_eonet_severity(categories: list[str]) -> str:
    lowered = {item.lower() for item in categories}
    if {"wildfires", "volcanoes", "severe storms"} & lowered:
        return "high"
    if {"earthquakes", "floods", "landslides"} & lowered:
        return "medium"
    return "low"


def normalize_nws_severity(value: str | None) -> str:
    if not value:
        return "medium"
    lowered = value.strip().lower()
    if lowered in {"extreme", "severe"}:
        return "high"
    if lowered in {"moderate"}:
        return "medium"
    return "low"


def infer_nws_confidence(certainty: str | None) -> float:
    mapping = {
        "observed": 0.95,
        "likely": 0.82,
        "possible": 0.62,
        "unlikely": 0.35,
    }
    if not certainty:
        return 0.72
    return mapping.get(certainty.strip().lower(), 0.72)

