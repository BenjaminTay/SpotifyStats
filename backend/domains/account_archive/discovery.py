"""Privacy-safe search bursts and a bounded discovery evidence funnel."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from bisect import bisect_right
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.domains.account_archive.overview import _database_path
from backend.domains.account_archive.source_data import (
    load_effective_archive_plays,
    load_saved_track_entities,
    load_track_group_map,
    load_track_preview_map,
)
from backend.models.account_archive import ArchiveFilterContext

ARCHIVE_DISCOVERY_CACHE_TTL_SECONDS = 300
DISCOVERY_BURST_GAP_MINUTES = 5
DISCOVERY_PLAY_WINDOW_MINUTES = 60
DISCOVERY_SAVE_WINDOW_DAYS = 30
DISCOVERY_TIMEZONE = "Asia/Shanghai"
DISCOVERY_NORMALIZATION_VERSION = "nfkc_casefold_ws_v1"
DISCOVERY_PREVIEW_LIMIT = 5


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def _timestamp(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z[UTC]", "Z")
    try:
        parsed = pd.Timestamp(cleaned)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _normalize_query(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def _search_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "search_queries"):
        return []
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(search_queries)")}
    required = {
        "id",
        "query_text",
        "search_time_utc",
        "platform",
        "interaction_uri",
    }
    if not required.issubset(columns):
        return []
    rows = conn.execute(
        """
        SELECT id, query_text, search_time_utc, platform, interaction_uri
        FROM search_queries
        ORDER BY search_time_utc, id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _search_revision_from_rows(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(f"discovery:{DISCOVERY_NORMALIZATION_VERSION}\n".encode())
    for row in rows:
        payload = [
            row.get("query_text") or "",
            row.get("search_time_utc") or "",
            row.get("platform") or "",
            row.get("interaction_uri") or "",
        ]
        digest.update(json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()[:20]


def _deduplicate_events(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    invalid_timestamps = 0
    for row in rows:
        event_at = _timestamp(row.get("search_time_utc"))
        if event_at is None:
            invalid_timestamps += 1
            continue
        normalized_query = _normalize_query(row.get("query_text"))
        signature = (
            normalized_query,
            _iso(event_at),
            str(row.get("platform") or "").strip(),
            str(row.get("interaction_uri") or "").strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        events.append(
            {
                "id": int(row.get("id") or 0),
                "normalized_query": normalized_query,
                "event_at": event_at,
                "interaction_uri": signature[3],
            }
        )
    events.sort(key=lambda event: (event["event_at"], event["id"]))
    return events, invalid_timestamps


def _assign_bursts(events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    bursts: list[list[dict[str, Any]]] = []
    previous_at: pd.Timestamp | None = None
    gap = pd.Timedelta(minutes=DISCOVERY_BURST_GAP_MINUTES)
    for event in events:
        event_at = event["event_at"]
        if previous_at is None or event_at - previous_at > gap:
            bursts.append([])
        event["burst_id"] = len(bursts) - 1
        bursts[-1].append(event)
        previous_at = event_at
    return bursts


def _interaction_type(uri: str) -> str:
    for kind in ("track", "artist", "album", "playlist", "show", "episode"):
        if uri.startswith(f"spotify:{kind}:"):
            return kind
    return "other"


def _track_uri_map(conn: sqlite3.Connection) -> dict[str, int]:
    if not _table_exists(conn, "tracks"):
        return {}
    rows = conn.execute(
        """
        SELECT spotify_track_uri, MIN(track_id)
        FROM tracks
        WHERE spotify_track_uri IS NOT NULL AND TRIM(spotify_track_uri) != ''
        GROUP BY spotify_track_uri
        """
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _play_times(frame: pd.DataFrame) -> dict[int, list[pd.Timestamp]]:
    if frame.empty:
        return {}
    result: dict[int, list[pd.Timestamp]] = {}
    for raw_track_id, group in frame.groupby("archive_track_id", sort=False):
        track_id: Any = raw_track_id
        result[int(track_id)] = sorted(group["event_at"].tolist())
    return result


def _first_play_in_window(
    times: list[pd.Timestamp], start: pd.Timestamp, end: pd.Timestamp
) -> pd.Timestamp | None:
    index = bisect_right(times, start)
    if index < len(times) and times[index] <= end:
        return times[index]
    return None


def _distribution(
    events: list[dict[str, Any]], bursts: list[list[dict[str, Any]]]
) -> tuple[list[dict[str, int]], list[dict[str, int]], int]:
    weekday_counts = {index: 0 for index in range(7)}
    hour_counts = {index: 0 for index in range(24)}
    for burst in bursts:
        local = burst[0]["event_at"].tz_convert(DISCOVERY_TIMEZONE)
        weekday_counts[int(local.weekday())] += 1
        hour_counts[int(local.hour)] += 1
    active_days = len(
        {event["event_at"].tz_convert(DISCOVERY_TIMEZONE).date().isoformat() for event in events}
    )
    return (
        [{"weekday": weekday, "bursts": weekday_counts[weekday]} for weekday in range(7)],
        [{"hour": hour, "bursts": hour_counts[hour]} for hour in range(24)],
        active_days,
    )


def _funnel(
    conn: sqlite3.Connection,
    events: list[dict[str, Any]],
    context: ArchiveFilterContext,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    track_events = [
        event for event in events if _interaction_type(event["interaction_uri"]) == "track"
    ]
    track_bursts = {int(event["burst_id"]) for event in track_events}
    if not track_events:
        return (
            {
                "display_status": "unavailable",
                "playback_window_minutes": DISCOVERY_PLAY_WINDOW_MINUTES,
                "save_window_days": DISCOVERY_SAVE_WINDOW_DAYS,
                "track_interaction_bursts": 0,
                "mapped_track_interaction_bursts": 0,
                "played_within_1h_bursts": 0,
                "currently_saved_within_30d_bursts": 0,
            },
            [],
        )

    uri_map = _track_uri_map(conn)
    group_map = load_track_group_map(conn, context.merge_level)
    play_frame = load_effective_archive_plays(conn, context)
    times_by_track = _play_times(play_frame)
    saved_entities, _ = load_saved_track_entities(conn, context)
    saved_at_by_track = {
        int(entity["archive_track_id"]): saved_at
        for entity in saved_entities
        if (saved_at := _timestamp(entity.get("added_date"))) is not None
    }

    mapped_bursts: set[int] = set()
    played_bursts: set[int] = set()
    saved_bursts: set[int] = set()
    saved_candidates: list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, int, int, int]] = []
    play_delta = pd.Timedelta(minutes=DISCOVERY_PLAY_WINDOW_MINUTES)
    save_delta = pd.Timedelta(days=DISCOVERY_SAVE_WINDOW_DAYS)
    for event in track_events:
        local_track_id = uri_map.get(event["interaction_uri"])
        if local_track_id is None:
            continue
        burst_id = int(event["burst_id"])
        archive_track_id = group_map.get(local_track_id, local_track_id)
        mapped_bursts.add(burst_id)
        event_at = event["event_at"]
        played_at = _first_play_in_window(
            times_by_track.get(archive_track_id, []), event_at, event_at + play_delta
        )
        if played_at is None:
            continue
        played_bursts.add(burst_id)
        saved_at = saved_at_by_track.get(archive_track_id)
        if saved_at is None or not (played_at <= saved_at <= event_at + save_delta):
            continue
        saved_bursts.add(burst_id)
        saved_candidates.append(
            (event_at, played_at, saved_at, local_track_id, archive_track_id, burst_id)
        )

    examples: list[dict[str, Any]] = []
    seen_tracks: set[int] = set()
    latest_candidates = sorted(
        saved_candidates,
        key=lambda item: (item[0], -item[4], -item[5]),
        reverse=True,
    )
    preview_map = load_track_preview_map(conn, {item[3] for item in latest_candidates})
    for event_at, played_at, saved_at, local_track_id, archive_track_id, _ in latest_candidates:
        if archive_track_id in seen_tracks:
            continue
        metadata = preview_map.get(local_track_id)
        if metadata is None:
            continue
        seen_tracks.add(archive_track_id)
        examples.append(
            {
                **metadata,
                "interaction_at": _iso(event_at),
                "played_at": _iso(played_at),
                "added_date": _iso(saved_at),
            }
        )
        if len(examples) >= DISCOVERY_PREVIEW_LIMIT:
            break

    return (
        {
            "display_status": "count_only",
            "playback_window_minutes": DISCOVERY_PLAY_WINDOW_MINUTES,
            "save_window_days": DISCOVERY_SAVE_WINDOW_DAYS,
            "track_interaction_bursts": len(track_bursts),
            "mapped_track_interaction_bursts": len(mapped_bursts),
            "played_within_1h_bursts": len(played_bursts),
            "currently_saved_within_30d_bursts": len(saved_bursts),
        },
        examples,
    )


def build_archive_discovery(
    conn: sqlite3.Connection,
    context: ArchiveFilterContext,
    search_revision: str | None = None,
) -> dict[str, Any]:
    rows = _search_rows(conn)
    revision = search_revision or _search_revision_from_rows(rows)
    data_revision = hashlib.sha256(f"{context.source_revision}:{revision}".encode()).hexdigest()[
        :20
    ]
    events, invalid_timestamps = _deduplicate_events(rows)
    bursts = _assign_bursts(events)
    interactions = [event for event in events if event["interaction_uri"]]
    interaction_types = {
        kind: sum(_interaction_type(event["interaction_uri"]) == kind for event in interactions)
        for kind in ("track", "artist", "album", "playlist", "show", "episode", "other")
    }
    weekday_distribution, hour_distribution, active_days = _distribution(events, bursts)
    funnel, examples = _funnel(conn, events, context)
    interaction_bursts = {int(event["burst_id"]) for event in interactions}

    if not rows:
        status = "unavailable"
    elif (
        invalid_timestamps
        or not interactions
        or funnel["mapped_track_interaction_bursts"] < funnel["track_interaction_bursts"]
    ):
        status = "partial"
    else:
        status = "available"

    return {
        "schema_version": "account_archive_discovery_v1",
        "content_version": "account_archive_discovery_v1_0",
        "data_revision": data_revision,
        "status": status,
        "filter_context": context.model_dump(mode="json"),
        "period": {
            "first_search_at": _iso(events[0]["event_at"]) if events else None,
            "latest_search_at": _iso(events[-1]["event_at"]) if events else None,
            "active_days": active_days,
        },
        "coverage": {
            "normalization_version": DISCOVERY_NORMALIZATION_VERSION,
            "burst_gap_minutes": DISCOVERY_BURST_GAP_MINUTES,
            "raw_search_rows": len(rows),
            "deduplicated_search_rows": len(events),
            "invalid_timestamp_rows": invalid_timestamps,
            "unique_normalized_queries": len(
                {event["normalized_query"] for event in events if event["normalized_query"]}
            ),
            "search_bursts": len(bursts),
            "interaction_records": len(interactions),
            "interaction_bursts": len(interaction_bursts),
        },
        "interaction_types": interaction_types,
        "funnel": funnel,
        "weekday_distribution": weekday_distribution,
        "hour_distribution": hour_distribution,
        "observed_saved_examples": examples,
    }


@ttl_cached(ARCHIVE_DISCOVERY_CACHE_TTL_SECONDS, namespace="account_archive")
def _get_archive_discovery_cached(
    db_path: str,
    context_json: str,
    search_revision: str,
    cache_key: str,
) -> dict[str, Any]:
    del cache_key
    context = ArchiveFilterContext.model_validate_json(context_json)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        return build_archive_discovery(conn, context, search_revision)
    finally:
        conn.close()


register_ttl("account_archive", "discovery", _get_archive_discovery_cached)


def get_archive_discovery(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> dict[str, Any]:
    search_revision = _search_revision_from_rows(_search_rows(conn))
    db_path = _database_path(conn)
    cache_key = f"discovery:{context.filter_fingerprint}:{search_revision}"
    if db_path and os.path.exists(db_path):
        return _get_archive_discovery_cached(
            db_path,
            context.model_dump_json(),
            search_revision,
            cache_key,
        )
    return build_archive_discovery(conn, context, search_revision)
