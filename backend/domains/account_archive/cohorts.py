"""Censored collection relationship metrics and aligned playback windows."""

from __future__ import annotations

import os
import sqlite3
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.domains.account_archive.overview import _database_path, _pct
from backend.domains.account_archive.source_data import (
    load_effective_archive_plays,
    load_saved_track_entities,
    load_track_preview_map,
)
from backend.models.account_archive import ArchiveFilterContext

ARCHIVE_COHORTS_CACHE_TTL_SECONDS = 300
RETURN_HORIZONS = (7, 30, 90, 365)
ALIGNED_WEEK_RANGE = range(-4, 13)
MIN_STABLE_RATE_SAMPLE = 30
RECENT_WINDOW_DAYS = 90
FREQUENT_UNSAVED_MIN_PLAYS = 5


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


def _play_times(frame: pd.DataFrame) -> dict[int, list[pd.Timestamp]]:
    if frame.empty:
        return {}
    return {
        int(track_id): sorted(group["event_at"].tolist())
        for track_id, group in frame.groupby("archive_track_id", sort=False)
    }


def _count_after(times: list[pd.Timestamp], start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Count events in the non-overlapping interval (start, end]."""
    return max(bisect_right(times, end) - bisect_right(times, start), 0)


def _count_before(times: list[pd.Timestamp], start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Count events in [start, end), used for pre-save windows."""
    return max(bisect_left(times, end) - bisect_left(times, start), 0)


def _saved_preview(
    entity: dict[str, Any],
    times: list[pd.Timestamp],
    effective_plays: int | None = None,
    days_to_save: int | None = None,
) -> dict[str, Any]:
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
        "first_play_at": times[0].isoformat().replace("+00:00", "Z") if times else None,
        "last_play_at": times[-1].isoformat().replace("+00:00", "Z") if times else None,
        "effective_plays": len(times) if effective_plays is None else effective_plays,
        "days_to_save": days_to_save,
    }


def _encounter_to_save(
    entities: list[dict[str, Any]],
    times_by_track: dict[int, list[pd.Timestamp]],
    first_observation: pd.Timestamp | None,
) -> tuple[dict[str, Any], int]:
    keys = ("same_day", "days_1_7", "days_8_30", "days_31_90", "days_90_plus")
    counts = {key: 0 for key in keys}
    eligible: list[tuple[int, dict[str, Any], list[pd.Timestamp]]] = []
    no_pre_save = 0
    invalid_dates = 0
    shanghai = "Asia/Shanghai"
    for entity in entities:
        saved_at = _timestamp(entity.get("added_date"))
        if saved_at is None:
            if entity.get("added_date"):
                invalid_dates += 1
            continue
        times = times_by_track.get(int(entity["archive_track_id"]), [])
        if (
            not times
            or times[0] > saved_at
            or first_observation is None
            or saved_at < first_observation
        ):
            no_pre_save += 1
            continue
        day_gap = (saved_at.tz_convert(shanghai).date() - times[0].tz_convert(shanghai).date()).days
        if day_gap == 0:
            key = "same_day"
        elif day_gap <= 7:
            key = "days_1_7"
        elif day_gap <= 30:
            key = "days_8_30"
        elif day_gap <= 90:
            key = "days_31_90"
        else:
            key = "days_90_plus"
        counts[key] += 1
        eligible.append((day_gap, entity, times))

    total = len(eligible)
    bins = [
        {"key": key, "entities": counts[key], "share_pct": _pct(counts[key], total)} for key in keys
    ]
    examples = [
        _saved_preview(entity, times, days_to_save=day_gap)
        for day_gap, entity, times in sorted(eligible, key=lambda item: item[0], reverse=True)[:5]
    ]
    return (
        {
            "eligible_entities": total,
            "no_observed_pre_save_play": no_pre_save,
            "bins": bins,
            "examples": examples,
        },
        invalid_dates,
    )


def _symmetric_window(
    entities: list[dict[str, Any]],
    times_by_track: dict[int, list[pd.Timestamp]],
    first_observation: pd.Timestamp | None,
    latest_observation: pd.Timestamp | None,
) -> dict[str, Any]:
    result = {
        "window_days": 30,
        "eligible_entities": 0,
        "before_events": 0,
        "after_events": 0,
        "more_before": 0,
        "equal": 0,
        "more_after": 0,
    }
    if first_observation is None or latest_observation is None:
        return result
    delta = pd.Timedelta(days=30)
    for entity in entities:
        saved_at = _timestamp(entity.get("added_date"))
        if (
            saved_at is None
            or saved_at - delta < first_observation
            or saved_at + delta > latest_observation
        ):
            continue
        times = times_by_track.get(int(entity["archive_track_id"]), [])
        before = _count_before(times, saved_at - delta, saved_at)
        after = _count_after(times, saved_at, saved_at + delta)
        result["eligible_entities"] += 1
        result["before_events"] += before
        result["after_events"] += after
        if before > after:
            result["more_before"] += 1
        elif after > before:
            result["more_after"] += 1
        else:
            result["equal"] += 1
    return result


def _return_windows(
    entities: list[dict[str, Any]],
    times_by_track: dict[int, list[pd.Timestamp]],
    first_observation: pd.Timestamp | None,
    latest_observation: pd.Timestamp | None,
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for horizon in RETURN_HORIZONS:
        eligible = 0
        returned = 0
        if first_observation is not None and latest_observation is not None:
            delta = pd.Timedelta(days=horizon)
            for entity in entities:
                saved_at = _timestamp(entity.get("added_date"))
                if (
                    saved_at is None
                    or saved_at < first_observation
                    or saved_at + delta > latest_observation
                ):
                    continue
                eligible += 1
                times = times_by_track.get(int(entity["archive_track_id"]), [])
                if _count_after(times, saved_at, saved_at + delta) > 0:
                    returned += 1
        if eligible == 0:
            display_status = "unavailable"
            rate = None
        elif eligible < MIN_STABLE_RATE_SAMPLE:
            display_status = "count_only"
            rate = None
        else:
            display_status = "stable_rate"
            rate = _pct(returned, eligible)
        windows.append(
            {
                "horizon_days": horizon,
                "eligible_entities": eligible,
                "returned_entities": returned,
                "return_rate_pct": rate,
                "display_status": display_status,
            }
        )
    return windows


def _vitality_metrics(
    entities: list[dict[str, Any]],
    times_by_track: dict[int, list[pd.Timestamp]],
    first_observation: pd.Timestamp | None,
    latest_observation: pd.Timestamp | None,
) -> list[dict[str, Any]]:
    definitions: tuple[tuple[str, int, int | None], ...] = (
        ("within_7d", 0, 7),
        ("days_8_30", 7, 30),
        ("after_180d", 180, None),
        ("after_365d", 365, None),
    )
    metrics: list[dict[str, Any]] = []
    for key, start_day, end_day in definitions:
        eligible = 0
        returned = 0
        if first_observation is not None and latest_observation is not None:
            for entity in entities:
                saved_at = _timestamp(entity.get("added_date"))
                if saved_at is None or saved_at < first_observation:
                    continue
                start = saved_at + pd.Timedelta(days=start_day)
                end = (
                    saved_at + pd.Timedelta(days=end_day)
                    if end_day is not None
                    else latest_observation
                )
                if start > latest_observation or end > latest_observation:
                    continue
                eligible += 1
                times = times_by_track.get(int(entity["archive_track_id"]), [])
                if _count_after(times, start, end) > 0:
                    returned += 1
        if eligible == 0:
            display_status = "unavailable"
            rate = None
        elif eligible < MIN_STABLE_RATE_SAMPLE:
            display_status = "count_only"
            rate = None
        else:
            display_status = "stable_rate"
            rate = _pct(returned, eligible)
        metrics.append(
            {
                "key": key,
                "start_day": start_day,
                "end_day": end_day,
                "eligible_entities": eligible,
                "returned_entities": returned,
                "return_rate_pct": rate,
                "display_status": display_status,
            }
        )
    return metrics


def _aligned_weeks(
    entities: list[dict[str, Any]],
    times_by_track: dict[int, list[pd.Timestamp]],
    first_observation: pd.Timestamp | None,
    latest_observation: pd.Timestamp | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for week_index in ALIGNED_WEEK_RANGE:
        eligible = 0
        with_play = 0
        events = 0
        if first_observation is not None and latest_observation is not None:
            for entity in entities:
                saved_at = _timestamp(entity.get("added_date"))
                if saved_at is None:
                    continue
                start = saved_at + pd.Timedelta(days=week_index * 7)
                end = start + pd.Timedelta(days=7)
                if start < first_observation or end > latest_observation:
                    continue
                eligible += 1
                times = times_by_track.get(int(entity["archive_track_id"]), [])
                count = (
                    _count_before(times, start, end)
                    if week_index < 0
                    else _count_after(times, start, end)
                )
                events += count
                with_play += int(count > 0)
        rows.append(
            {
                "week_index": week_index,
                "eligible_entities": eligible,
                "entities_with_play": with_play,
                "effective_play_events": events,
                "events_per_eligible": round(events / eligible, 2) if eligible else 0.0,
            }
        )
    return rows


def _relationship_matrix(
    conn: sqlite3.Connection,
    entities: list[dict[str, Any]],
    play_frame: pd.DataFrame,
    times_by_track: dict[int, list[pd.Timestamp]],
    latest_observation: pd.Timestamp | None,
    unmatched_saved_tracks: int,
) -> dict[str, Any]:
    active: list[tuple[pd.Timestamp, dict[str, Any], list[pd.Timestamp], int]] = []
    sleeping: list[tuple[pd.Timestamp | None, dict[str, Any], list[pd.Timestamp]]] = []
    recently_saved = 0
    without_date = 0
    saved_ids = {int(entity["archive_track_id"]) for entity in entities}
    recent_start = (
        latest_observation - pd.Timedelta(days=RECENT_WINDOW_DAYS)
        if latest_observation is not None
        else None
    )

    for entity in entities:
        saved_at = _timestamp(entity.get("added_date"))
        times = times_by_track.get(int(entity["archive_track_id"]), [])
        if recent_start is None or latest_observation is None:
            without_date += int(saved_at is None)
            continue
        recent_count = _count_after(times, recent_start, latest_observation)
        if recent_count:
            active.append((times[-1], entity, times, recent_count))
        elif saved_at is None:
            without_date += 1
        elif saved_at <= recent_start:
            sleeping.append((times[-1] if times else None, entity, times))
        else:
            recently_saved += 1

    frequent_unsaved_counts: list[tuple[int, int]] = []
    if recent_start is not None and latest_observation is not None and not play_frame.empty:
        recent = play_frame[
            (play_frame["event_at"] > recent_start) & (play_frame["event_at"] <= latest_observation)
        ]
        counts = recent.groupby("archive_track_id").size()
        frequent_unsaved_counts = sorted(
            (
                (int(track_id), int(count))
                for track_id, count in counts.items()
                if int(track_id) not in saved_ids and int(count) >= FREQUENT_UNSAVED_MIN_PLAYS
            ),
            key=lambda item: (-item[1], item[0]),
        )
    preview_map = load_track_preview_map(
        conn, {track_id for track_id, _ in frequent_unsaved_counts[:5]}
    )
    unsaved_examples = []
    for track_id, count in frequent_unsaved_counts[:5]:
        metadata = preview_map.get(track_id)
        if metadata is None:
            continue
        times = times_by_track.get(track_id, [])
        unsaved_examples.append(
            {
                **metadata,
                "added_date": None,
                "first_play_at": times[0].isoformat().replace("+00:00", "Z") if times else None,
                "last_play_at": times[-1].isoformat().replace("+00:00", "Z") if times else None,
                "effective_plays": count,
            }
        )

    active_examples = [
        _saved_preview(entity, times, recent_count)
        for _, entity, times, recent_count in sorted(
            active, key=lambda item: item[0], reverse=True
        )[:5]
    ]
    sleeping_examples = [
        _saved_preview(entity, times)
        for _, entity, times in sorted(
            sleeping,
            key=lambda item: (item[0] is not None, item[0] or pd.Timestamp.min.tz_localize("UTC")),
        )[:5]
    ]
    return {
        "recent_window_days": RECENT_WINDOW_DAYS,
        "frequent_unsaved_min_plays": FREQUENT_UNSAVED_MIN_PLAYS,
        "counts": {
            "recent_active_saved": len(active),
            "sleeping_saved": len(sleeping),
            "recently_saved_without_recent_play": recently_saved,
            "saved_without_date": without_date,
            "frequent_unsaved": len(frequent_unsaved_counts),
            "unmatched_saved_tracks": unmatched_saved_tracks,
        },
        "recent_active_examples": active_examples,
        "sleeping_examples": sleeping_examples,
        "frequent_unsaved_examples": unsaved_examples,
    }


def build_collection_cohorts(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> dict[str, Any]:
    entities, source_coverage = load_saved_track_entities(conn, context)
    play_frame = load_effective_archive_plays(conn, context)
    times_by_track = _play_times(play_frame)
    first_observation = _timestamp(context.first_play_at)
    latest_observation = _timestamp(context.latest_play_at)
    dated = sum(1 for entity in entities if _timestamp(entity.get("added_date")) is not None)
    encounter, invalid_dates = _encounter_to_save(entities, times_by_track, first_observation)
    if not source_coverage["saved_tracks"]:
        status = "unavailable"
    elif source_coverage["unmatched_saved_tracks"] or dated < len(entities) or play_frame.empty:
        status = "partial"
    else:
        status = "available"

    return {
        "schema_version": "account_archive_cohorts_v2",
        "content_version": "account_archive_cohorts_v2_0",
        "data_revision": context.source_revision,
        "status": status,
        "filter_context": context.model_dump(mode="json"),
        "coverage": {
            **source_coverage,
            "dated_canonical_entities": dated,
            "invalid_added_dates": invalid_dates,
            "effective_play_events": len(play_frame),
        },
        "encounter_to_save": encounter,
        "symmetric_30_day_window": _symmetric_window(
            entities,
            times_by_track,
            first_observation,
            latest_observation,
        ),
        "return_windows": _return_windows(
            entities,
            times_by_track,
            first_observation,
            latest_observation,
        ),
        "vitality_metrics": _vitality_metrics(
            entities,
            times_by_track,
            first_observation,
            latest_observation,
        ),
        "aligned_weeks": _aligned_weeks(
            entities,
            times_by_track,
            first_observation,
            latest_observation,
        ),
        "relationship_matrix": _relationship_matrix(
            conn,
            entities,
            play_frame,
            times_by_track,
            latest_observation,
            source_coverage["unmatched_saved_tracks"],
        ),
    }


@ttl_cached(ARCHIVE_COHORTS_CACHE_TTL_SECONDS, namespace="account_archive")
def _get_collection_cohorts_cached(
    db_path: str, context_json: str, cache_key: str
) -> dict[str, Any]:
    del cache_key
    context = ArchiveFilterContext.model_validate_json(context_json)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        return build_collection_cohorts(conn, context)
    finally:
        conn.close()


register_ttl("account_archive", "collection_cohorts", _get_collection_cohorts_cached)


def get_collection_cohorts(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> dict[str, Any]:
    db_path = _database_path(conn)
    cache_key = f"cohorts:{context.filter_fingerprint}"
    if db_path and os.path.exists(db_path):
        return _get_collection_cohorts_cached(db_path, context.model_dump_json(), cache_key)
    return build_collection_cohorts(conn, context)
