from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOWED_CATEGORIES = {
    "airport",
    "port",
    "city",
    "traffic",
    "rail",
    "weather",
    "coast",
    "wildlife",
    "public_square",
    "infrastructure",
}

ALLOWED_ACCESS_MODES = {"embed", "preview_only", "link_only"}

REQUIRED_FIELDS = {
    "id",
    "name",
    "provider",
    "country",
    "region",
    "city",
    "lat",
    "lon",
    "category",
    "subcategory",
    "watch_url",
    "access_mode",
    "embed_allowed",
    "source_confidence",
    "tags",
    "priority",
    "metadata",
}


def load_seed_file(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() in {".yaml", ".yml"}:
        payload = _load_yaml_or_json_compatible(text)
    else:
        payload = json.loads(text)

    if isinstance(payload, list):
        return {"entries": payload}, payload
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise ValueError("Seed file must contain an 'entries' array or be a top-level array.")
        return payload, entries
    raise ValueError("Seed file must be a JSON/YAML object or array.")


def _load_yaml_or_json_compatible(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return json.loads(text)
    return yaml.safe_load(text)


def validate_entries(entries: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_provider_camera: set[tuple[str, str]] = set()
    seen_provider_watch: set[tuple[str, str]] = set()

    for index, entry in enumerate(entries):
        label = entry.get("id") or f"index={index}"
        missing = sorted(REQUIRED_FIELDS - set(entry))
        if missing:
            errors.append(f"{label}: missing required fields: {', '.join(missing)}")
            continue

        if not isinstance(entry["id"], str) or not entry["id"].strip():
            errors.append(f"{label}: id must be a non-empty string")
        elif entry["id"] in seen_ids:
            errors.append(f"{label}: duplicate id '{entry['id']}'")
        else:
            seen_ids.add(entry["id"])

        category = entry["category"]
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"{label}: invalid category '{category}'")

        access_mode = entry["access_mode"]
        if access_mode not in ALLOWED_ACCESS_MODES:
            errors.append(f"{label}: invalid access_mode '{access_mode}'")

        lat = entry["lat"]
        lon = entry["lon"]
        if not _is_number(lat) or not -90 <= float(lat) <= 90:
            errors.append(f"{label}: lat must be within -90..90")
        if not _is_number(lon) or not -180 <= float(lon) <= 180:
            errors.append(f"{label}: lon must be within -180..180")

        if not isinstance(entry["tags"], list) or not entry["tags"]:
            errors.append(f"{label}: tags must be a non-empty list")
        if entry["priority"] not in {1, 2, 3}:
            errors.append(f"{label}: priority must be 1, 2, or 3")
        if not isinstance(entry["metadata"], dict):
            errors.append(f"{label}: metadata must be an object")
        if not isinstance(entry["embed_allowed"], bool):
            errors.append(f"{label}: embed_allowed must be a boolean")

        if not isinstance(entry["watch_url"], str) or not entry["watch_url"].startswith("http"):
            errors.append(f"{label}: watch_url must be an http/https URL")

        provider = entry["provider"]
        provider_camera_id = entry.get("provider_camera_id")
        if provider_camera_id:
            provider_camera_key = (provider, str(provider_camera_id))
            if provider_camera_key in seen_provider_camera:
                errors.append(
                    f"{label}: duplicate provider + provider_camera_id '{provider}:{provider_camera_id}'"
                )
            else:
                seen_provider_camera.add(provider_camera_key)

        provider_watch_key = (provider, entry["watch_url"])
        if provider_watch_key in seen_provider_watch:
            errors.append(f"{label}: duplicate provider + watch_url '{provider}:{entry['watch_url']}'")
        else:
            seen_provider_watch.add(provider_watch_key)

    return errors


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
