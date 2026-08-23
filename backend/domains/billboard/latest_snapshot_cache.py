"""Small cache-only Billboard preview shared with lightweight consumers."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import Any

_MAX_ENTRIES = 8
_lock = RLock()
_snapshots: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
_revision = 0
_key_revisions: dict[tuple[Any, ...], int] = {}


def snapshot_key(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
    merge_enabled=True,
) -> tuple[Any, ...]:
    return (
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
        merge_level,
        dynamic_threshold,
        max_merge_gap_minutes,
        include_compilations,
        merge_enabled,
    )


def store_latest_snapshot(key: tuple[Any, ...], payload: dict[str, Any]) -> None:
    global _revision
    weeks = payload.get("meta", {}).get("all_weeks_desc", [])
    selected = set(weeks[:2])
    snapshot = {
        "meta": {"all_weeks_desc": list(weeks[:2])},
        "weekly": [
            row for row in payload.get("weekly", []) if row.get("billboard_week") in selected
        ],
        "weekly_album": [
            row for row in payload.get("weekly_album", []) if row.get("billboard_week") in selected
        ],
        "weekly_artist": [
            row for row in payload.get("weekly_artist", []) if row.get("billboard_week") in selected
        ],
    }
    with _lock:
        _snapshots[key] = snapshot
        _revision += 1
        _key_revisions[key] = _key_revisions.get(key, 0) + 1
        _snapshots.move_to_end(key)
        while len(_snapshots) > _MAX_ENTRIES:
            _snapshots.popitem(last=False)


def store_latest_snapshot_for_args(args: tuple[Any, ...], payload: dict[str, Any]) -> None:
    store_latest_snapshot(snapshot_key(*args), payload)


def store_latest_snapshot_for_locals(
    values: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    names = (
        "min_ms",
        "music_only",
        "bb_top_n",
        "bb_album_top_n",
        "bb_artist_top_n",
        "bb_week_start_dow",
        "bb_week_start_hour",
        "year_start",
        "year_end",
        "merge_level",
        "dynamic_threshold",
        "max_merge_gap_minutes",
        "include_compilations",
        "merge_enabled",
    )
    store_latest_snapshot_for_args(tuple(values[name] for name in names), payload)
    return payload


def get_latest_snapshot_if_cached(key: tuple[Any, ...]) -> dict[str, Any] | None:
    """Return only an already-computed exact semantic key; never build charts."""
    with _lock:
        value = _snapshots.get(key)
        if value is None:
            return None
        _snapshots.move_to_end(key)
        return {
            "meta": {"all_weeks_desc": list(value["meta"]["all_weeks_desc"])},
            "weekly": [dict(row) for row in value["weekly"]],
            "weekly_album": [dict(row) for row in value["weekly_album"]],
            "weekly_artist": [dict(row) for row in value["weekly_artist"]],
        }


def clear_latest_snapshots() -> None:
    global _revision
    with _lock:
        _snapshots.clear()
        _key_revisions.clear()
        _revision += 1


def latest_snapshot_revision(key: tuple[Any, ...] | None = None) -> int:
    with _lock:
        return _revision if key is None else _key_revisions.get(key, 0)


clear_latest_snapshots.cache_clear = clear_latest_snapshots  # type: ignore[attr-defined]


from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("billboard", "latest_snapshot", clear_latest_snapshots)
