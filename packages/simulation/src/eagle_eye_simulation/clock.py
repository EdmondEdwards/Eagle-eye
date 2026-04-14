from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _utc(dt: datetime | str | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_time_state(payload: dict[str, Any]) -> dict[str, Any]:
    current = _utc(payload.get("current_timestamp"))
    mode = str(payload.get("mode", "live")).lower()
    if mode not in {"live", "paused", "replay", "simulate"}:
        mode = "live"
    status = str(payload.get("status", "playing")).lower()
    if status not in {"playing", "paused"}:
        status = "playing"
    return {
        "mode": mode,
        "status": status,
        "current_timestamp": current,
        "playback_speed": float(payload.get("playback_speed", 1.0) or 1.0),
        "step_seconds": max(int(payload.get("step_seconds", 60) or 60), 1),
        "updated_at": _utc(payload.get("updated_at")),
    }


def next_clock_state(payload: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    state = normalize_time_state(payload)
    reference = _utc(now)
    if state["status"] == "paused":
        state["updated_at"] = reference
        return state

    if state["mode"] == "live":
        state["current_timestamp"] = reference
        state["updated_at"] = reference
        return state

    elapsed = max((reference - state["updated_at"]).total_seconds(), 0.0)
    advance = elapsed * state["playback_speed"]
    state["current_timestamp"] = state["current_timestamp"] + timedelta(seconds=advance)
    state["updated_at"] = reference
    return state
