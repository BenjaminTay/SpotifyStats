"""Return episodes and currently sleeping relationships for the music archive."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.domains.account_archive.overview import _database_path
from backend.domains.account_archive.source_data import (
    load_effective_archive_plays,
    load_saved_track_entities,
)
from backend.models.account_archive import ArchiveFilterContext

ARCHIVE_RETURNS_CACHE_TTL_SECONDS = 300
RETURN_GAP_DAYS = 90
RETURN_PREVIEW_LIMIT = 5


def _timestamp(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _play_times(frame: pd.DataFrame) -> dict[int, list[pd.Timestamp]]:
    if frame.empty:
        return {}
    result: dict[int, list[pd.Timestamp]] = {}
    for raw_track_id, group in frame.groupby("archive_track_id", sort=False):
        track_id: Any = raw_track_id
        result[int(track_id)] = sorted(group["event_at"].tolist())
    return result


def _entity_metadata(entity: dict[str, Any]) -> dict[str, Any]:
    cover_url = None
    if entity.get("local_album_id") is not None and (
        entity.get("image_path") or entity.get("image_url")
    ):
        cover_url = f"/covers/albums/{int(entity['local_album_id'])}.jpg"
    return {
        "track_name": entity.get("track_name") or "",
        "artist_name": entity.get("artist_name") or "",
        "album_name": entity.get("album_name"),
        "cover_url": cover_url,
        "deep_link": entity.get("deep_link"),
        "added_date": entity.get("added_date"),
    }


def _elapsed_days(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return max(int((end - start).total_seconds() // 86_400), 0)


def _return_story(
    entity: dict[str, Any],
    episode: tuple[pd.Timestamp, pd.Timestamp],
    return_count: int,
) -> dict[str, Any]:
    previous, returned = episode
    return {
        **_entity_metadata(entity),
        "previous_play_at": _iso(previous),
        "returned_at": _iso(returned),
        "dormant_days": _elapsed_days(previous, returned),
        "return_count": return_count,
    }


def _build_return_metrics(
    entities: list[dict[str, Any]],
    times_by_track: dict[int, list[pd.Timestamp]],
    latest_observation: pd.Timestamp | None,
) -> dict[str, Any]:
    threshold = pd.Timedelta(days=RETURN_GAP_DAYS)
    returned: list[
        tuple[
            dict[str, Any],
            list[pd.Timestamp],
            list[tuple[pd.Timestamp, pd.Timestamp]],
        ]
    ] = []
    eligible = 0
    sleeping: list[tuple[int, dict[str, Any], list[pd.Timestamp]]] = []

    for entity in entities:
        saved_at = _timestamp(entity.get("added_date"))
        if saved_at is None:
            continue
        times = times_by_track.get(int(entity["archive_track_id"]), [])
        post_save_pairs = [
            (previous, current) for previous, current in zip(times, times[1:]) if current > saved_at
        ]
        eligible += int(bool(post_save_pairs))
        episodes = [
            (previous, current)
            for previous, current in post_save_pairs
            if current - previous >= threshold
        ]
        if episodes:
            returned.append((entity, times, episodes))

        if latest_observation is None:
            continue
        recent_start = latest_observation - threshold
        if saved_at > recent_start:
            continue
        recent_play = any(recent_start < item <= latest_observation for item in times)
        if recent_play:
            continue
        observed_times = [item for item in times if item <= latest_observation]
        last_play = observed_times[-1] if observed_times else None
        inactive_since = max(saved_at, last_play) if last_play is not None else saved_at
        dormant_days = _elapsed_days(inactive_since, latest_observation)
        if dormant_days >= RETURN_GAP_DAYS:
            sleeping.append((dormant_days, entity, observed_times))

    latest_rows = sorted(
        returned,
        key=lambda item: (
            max(episode[1] for episode in item[2]),
            -int(item[0]["archive_track_id"]),
        ),
        reverse=True,
    )
    latest_returns = [
        _return_story(entity, max(episodes, key=lambda episode: episode[1]), len(episodes))
        for entity, _, episodes in latest_rows[:RETURN_PREVIEW_LIMIT]
    ]
    longest_rows = sorted(
        returned,
        key=lambda item: (
            max(episode[1] - episode[0] for episode in item[2]),
            -int(item[0]["archive_track_id"]),
        ),
        reverse=True,
    )
    longest_returns = [
        _return_story(
            entity,
            max(episodes, key=lambda episode: episode[1] - episode[0]),
            len(episodes),
        )
        for entity, _, episodes in longest_rows[:RETURN_PREVIEW_LIMIT]
    ]
    sleeping_recommendations = [
        {
            **_entity_metadata(entity),
            "last_play_at": _iso(times[-1]) if times else None,
            "dormant_days": dormant_days,
            "effective_plays": len(times),
        }
        for dormant_days, entity, times in sorted(
            sleeping,
            key=lambda item: (-item[0], int(item[1]["archive_track_id"])),
        )[:RETURN_PREVIEW_LIMIT]
    ]

    recent_30 = 0
    recent_90 = 0
    if latest_observation is not None:
        start_30 = latest_observation - pd.Timedelta(days=30)
        start_90 = latest_observation - threshold
        for _, _, episodes in returned:
            last_return = max(episode[1] for episode in episodes)
            recent_30 += int(start_30 < last_return <= latest_observation)
            recent_90 += int(start_90 < last_return <= latest_observation)

    return {
        "return_eligible_entities": eligible,
        "summary": {
            "gap_threshold_days": RETURN_GAP_DAYS,
            "return_episodes": sum(len(episodes) for _, _, episodes in returned),
            "returned_entities": len(returned),
            "multiple_return_entities": sum(1 for _, _, episodes in returned if len(episodes) > 1),
            "recent_30_day_return_entities": recent_30,
            "recent_90_day_return_entities": recent_90,
            "current_sleeping_entities": len(sleeping),
        },
        "latest_returns": latest_returns,
        "longest_returns": longest_returns,
        "sleeping_recommendations": sleeping_recommendations,
    }


def build_archive_returns(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> dict[str, Any]:
    entities, source_coverage = load_saved_track_entities(conn, context)
    play_frame = load_effective_archive_plays(conn, context)
    times_by_track = _play_times(play_frame)
    latest_observation = _timestamp(context.latest_play_at)
    dated = sum(1 for entity in entities if _timestamp(entity.get("added_date")) is not None)
    invalid_dates = sum(
        1
        for entity in entities
        if entity.get("added_date") and _timestamp(entity.get("added_date")) is None
    )
    metrics = _build_return_metrics(entities, times_by_track, latest_observation)

    if not source_coverage["saved_tracks"]:
        status = "unavailable"
    elif source_coverage["unmatched_saved_tracks"] or dated < len(entities) or play_frame.empty:
        status = "partial"
    else:
        status = "available"

    return {
        "schema_version": "account_archive_returns_v1",
        "content_version": "account_archive_returns_v1_0",
        "data_revision": context.source_revision,
        "status": status,
        "filter_context": context.model_dump(mode="json"),
        "coverage": {
            **source_coverage,
            "dated_canonical_entities": dated,
            "invalid_added_dates": invalid_dates,
            "entities_with_effective_history": sum(
                1 for entity in entities if times_by_track.get(int(entity["archive_track_id"]))
            ),
            "return_eligible_entities": metrics["return_eligible_entities"],
            "effective_play_events": len(play_frame),
        },
        "summary": metrics["summary"],
        "latest_returns": metrics["latest_returns"],
        "longest_returns": metrics["longest_returns"],
        "sleeping_recommendations": metrics["sleeping_recommendations"],
    }


@ttl_cached(ARCHIVE_RETURNS_CACHE_TTL_SECONDS, namespace="account_archive")
def _get_archive_returns_cached(db_path: str, context_json: str, cache_key: str) -> dict[str, Any]:
    del cache_key
    context = ArchiveFilterContext.model_validate_json(context_json)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        return build_archive_returns(conn, context)
    finally:
        conn.close()


register_ttl("account_archive", "returns", _get_archive_returns_cached)


def get_archive_returns(conn: sqlite3.Connection, context: ArchiveFilterContext) -> dict[str, Any]:
    db_path = _database_path(conn)
    cache_key = f"returns:{context.filter_fingerprint}"
    if db_path and os.path.exists(db_path):
        return _get_archive_returns_cached(db_path, context.model_dump_json(), cache_key)
    return build_archive_returns(conn, context)
