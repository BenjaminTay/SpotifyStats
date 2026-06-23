"""Playback Records service — caching, period resolution, entity frame building, orchestration."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from functools import lru_cache

import pandas as pd

from backend.core.cache import singleflight
from backend.core.db import get_db, load_plays, load_plays_for_artists
from backend.domains.playback.records import (
    _add_cover_urls_to_records,
    _serialize_records,
    compute_playback_records,
)
from backend.domains.playback.track_groups import load_track_group_keys
from backend.services.analysis_stats_service import PERIOD_LABELS, resolve_period_dates

logger = logging.getLogger(__name__)


def _build_entity_frames(
    event_frame: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int,
    include_compilations: bool = False,
    min_ms: int = 30000,
    music_only: bool = True,
    merge_enabled: bool = True,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build track, album, and artist entity frames with canonicalization.

    Returns:
        track_frame: event_frame with canonical_track_id/name columns added
        album_frame: event_frame with album_project_id/name columns added
        artist_frame: fan-out frame with one row per contributing artist
    """
    track_frame = event_frame.copy() if not event_frame.empty else event_frame
    album_frame = event_frame.copy() if not event_frame.empty else event_frame

    # ── Track canonicalization ──
    if not track_frame.empty and merge_level >= 2:
        tg = load_track_group_keys(conn, merge_level)
        if not tg.empty:
            track_frame = track_frame.merge(tg, on="track_id", how="left")
            track_frame["canonical_track_id"] = track_frame["track_agg_id"].fillna(
                track_frame["track_id"]
            )
            track_frame["canonical_track_name"] = track_frame["track_agg_name"].fillna(
                track_frame["track_name"]
            )
        else:
            track_frame["canonical_track_id"] = track_frame["track_id"]
            track_frame["canonical_track_name"] = track_frame["track_name"]
    elif not track_frame.empty:
        track_frame["canonical_track_id"] = track_frame["track_id"]
        track_frame["canonical_track_name"] = track_frame["track_name"]

    # ── Album canonicalization via album project membership ──
    if not album_frame.empty and merge_level >= 2:
        try:
            from backend.domains.playback.album_projects import (
                apply_canonical_song_keys,
                load_album_project_membership,
            )

            # Apply canonical song keys first (required for membership join)
            events_with_keys = apply_canonical_song_keys(album_frame, conn, merge_level)
            membership = load_album_project_membership(conn, merge_level, include_compilations)

            if not membership.empty and "canonical_song_key" in events_with_keys.columns:
                # Join each play event to its album project via canonical song key
                merged = events_with_keys.merge(
                    membership[["canonical_song_key", "album_project_id", "album_project_name"]],
                    on="canonical_song_key",
                    how="left",
                )
                # Fall back to album_name for tracks not in any project
                merged["album_project_id"] = merged["album_project_id"].fillna(
                    merged["album_name"].astype(str)
                )
                merged["album_project_name"] = merged["album_project_name"].fillna(
                    merged["album_name"]
                )
                album_frame = merged
            else:
                album_frame["album_project_id"] = album_frame["album_name"].astype(str)
                album_frame["album_project_name"] = album_frame["album_name"]
        except Exception as e:
            logger.warning(
                "Album project membership join failed, falling back to album_name: %s", e
            )
            album_frame["album_project_id"] = album_frame["album_name"].astype(str)
            album_frame["album_project_name"] = album_frame["album_name"]
    elif not album_frame.empty:
        album_frame["album_project_id"] = album_frame["album_name"].astype(str)
        album_frame["album_project_name"] = album_frame["album_name"]

    # ── Artist fan-out with same filtering as event_frame ──
    try:
        artist_frame = load_plays_for_artists(
            conn,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        # Filter to same date range as event_frame
        if not artist_frame.empty and not event_frame.empty:
            min_date = event_frame["ts_date"].min()
            max_date = event_frame["ts_date"].max()
            artist_frame = artist_frame[
                (artist_frame["ts_date"] >= min_date) & (artist_frame["ts_date"] <= max_date)
            ]
    except Exception as e:
        # Fallback: use primary artist from event_frame
        logger.warning("Artist fan-out failed, falling back to primary artist: %s", e)
        artist_frame = event_frame.copy() if not event_frame.empty else event_frame

    return track_frame, album_frame, artist_frame


def _get_analysis_records_uncached(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str,
    start_date: str | None,
    end_date: str | None,
    merge_level: int,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    include_compilations: bool,
) -> dict:
    """Compute playback records (uncached inner function)."""

    # Load plays
    event_frame = load_plays(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    # Period filtering
    period_start, period_end = resolve_period_dates(period, start_date, end_date)
    if period_start or period_end:
        if period_start:
            event_frame = event_frame[event_frame["ts_date"].astype(str) >= period_start]
        if period_end:
            event_frame = event_frame[event_frame["ts_date"].astype(str) <= period_end]

    # Resolved period for response
    if period == "lifetime":
        p_start = str(event_frame["ts_date"].min()) if not event_frame.empty else None
        p_end = str(event_frame["ts_date"].max()) if not event_frame.empty else None
    else:
        p_start = period_start
        p_end = period_end

    resolved_period = {
        "period": period,
        "label": PERIOD_LABELS.get(period, "全部时间"),
        "start_date": p_start,
        "end_date": p_end,
    }

    # Summary meta
    if event_frame.empty:
        meta = {
            "total_plays": 0,
            "total_hours": 0.0,
            "active_days": 0,
            "merge_level": merge_level,
            "min_sample_plays": 10,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        return {
            "period": resolved_period,
            "meta": meta,
            "records": {},
        }

    total_plays = len(event_frame)
    total_hours = round(float(event_frame["ms_played"].sum()) / 3_600_000, 1)
    active_days = int(event_frame["ts_date"].nunique())

    meta = {
        "total_plays": total_plays,
        "total_hours": total_hours,
        "active_days": active_days,
        "merge_level": merge_level,
        "min_sample_plays": 10,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    # Build entity frames
    track_frame, album_frame, artist_frame = _build_entity_frames(
        event_frame,
        conn,
        merge_level,
        include_compilations,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    # Compute records
    raw_records = compute_playback_records(
        event_frame=event_frame,
        track_frame=track_frame,
        album_frame=album_frame,
        artist_frame=artist_frame,
        merge_level=merge_level,
        conn=conn,
    )

    # Add cover URLs
    _add_cover_urls_to_records(raw_records)

    # Serialize
    serialized = _serialize_records(raw_records)

    # Assemble into nested structure expected by PlaybackRecordsResponse
    nested = _assemble_nested_records(serialized)

    return {
        "period": resolved_period,
        "meta": meta,
        "records": nested,
    }


def _assemble_nested_records(flat: dict) -> dict:
    """Assemble flat serialized records into the nested structure expected by the response model.

    Flat keys like 'obsession_daily_binge_track' → nested path obsession.daily_binge.track
    """

    def _triple(prefix):
        """Extract {track, album, artist} triple for a given flat key prefix."""
        return {
            "track": flat.get(f"{prefix}_track", []),
            "album": flat.get(f"{prefix}_album", []),
            "artist": flat.get(f"{prefix}_artist", []),
        }

    return {
        "obsession": {
            "daily_binge": _triple("obsession_daily_binge"),
            "daily_duration": _triple("obsession_daily_duration"),
            "consecutive_marathon": _triple("obsession_consecutive_marathon"),
            "daily_total_record": flat.get("obsession_daily_total", []),
        },
        "time_patterns": {
            "hourly_dominance": _triple("time_hourly_dominance"),
            "monthly_peak": _triple("time_monthly_peak"),
            "yearly_peak": _triple("time_yearly_peak"),
            "late_night_peak_day": flat.get("time_late_night_peak_day", []),
            "weekday_preference": flat.get("time_weekday_preference", []),
            "new_year_eve": flat.get("time_new_year_eve", []),
        },
        "reigns": {
            "daily_champion": _triple("reign_daily_champion"),
            "monthly_reign": _triple("reign_monthly_reign"),
            "yearly_reign": _triple("reign_yearly_reign"),
            "fastest_milestone": _triple("reign_fastest_milestone"),
            "consecutive_champion_days": _triple("reign_consecutive_champion"),
        },
        "longevity": {
            "longest_streak_days": _triple("longevity_streak"),
            "longest_span": _triple("longevity_span"),
            "comeback_after_sleep": _triple("longevity_comeback"),
            "most_active_months": _triple("longevity_active_months"),
            "user_active_streak": flat.get("longevity_user_streak", []),
        },
        "discovery": {
            "discovery_day": _triple("discovery_day"),
            "longest_no_repeat": _triple("discovery_no_repeat"),
            "album_completionist": {
                "track": [],
                "album": flat.get("discovery_album_completionist", []),
                "artist": [],
            },
            "same_name_diff_artist": flat.get("discovery_same_name_diff_artist", []),
            "feat_lover": {
                "track": flat.get("discovery_feat_lover_track", []),
                "album": [],
                "artist": flat.get("discovery_feat_lover_artist", []),
            },
        },
        "behavior": {
            "skip_storm": _triple("behavior_skip_storm"),
            "shuffle_peak": flat.get("behavior_shuffle_peak", []),
            "platform_reign": flat.get("behavior_platform_reign", []),
            "platform_switch_day": flat.get("behavior_platform_switch_day", []),
            "playback_milestones": flat.get("behavior_playback_milestones", []),
        },
    }


@lru_cache(maxsize=64)
def _get_analysis_records_cached(
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str,
    start_date: str | None,
    end_date: str | None,
    merge_level: int,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    include_compilations: bool,
) -> dict:
    """Cached wrapper for playback records computation."""
    conn = get_db()
    try:
        return _get_analysis_records_uncached(
            conn=conn,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            period=period,
            start_date=start_date,
            end_date=end_date,
            merge_level=merge_level,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            include_compilations=include_compilations,
        )
    finally:
        conn.close()


@singleflight
def get_analysis_records(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    merge_level: int = 2,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
    include_compilations: bool = False,
) -> dict:
    """Get all playback records for the analysis/records page."""
    return _get_analysis_records_cached(
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        merge_level=merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
    )


# Register cache for global invalidation (import, version merge, album project rebuild)
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("analysis", "records", _get_analysis_records_cached)
