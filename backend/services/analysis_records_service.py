"""Playback Records service — caching, period resolution, entity frame building, orchestration."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from functools import lru_cache

import pandas as pd

from backend.core.cache import singleflight
from backend.core.db import get_db, load_plays, load_plays_for_artists
from backend.domains.playback.counting import assign_logical_event_id
from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.domains.playback.records import (
    _add_cover_urls_to_records,
    _serialize_records,
    compute_playback_records,
)
from backend.domains.playback.records_duration_facts import RecordsDurationFacts
from backend.domains.playback.records_helpers import (
    attach_scoped_records_duration,
    records_duration_frame,
)
from backend.domains.playback.track_groups import load_track_group_keys
from backend.services.analysis_stats_service import PERIOD_LABELS, resolve_period_dates

logger = logging.getLogger(__name__)

# Bump this whenever record ranking/serialization semantics change so a
# long-lived process cannot serve a pre-fix payload from its LRU cache.
PLAYBACK_RECORDS_SORT_CONTRACT_VERSION = "2026-10-07-release-date-evidence-v8-source-selection"


def _load_reliable_album_release_dates(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load unambiguous full-precision Spotify release dates for local albums."""
    from backend.domains.metadata.release_dates import (
        compare_release_dates,
        parse_release_date,
        precision_expression,
    )

    columns = ["album_name", "artist_name", "source_album_release_date"]
    try:
        rows = conn.execute(f"""SELECT al.album_name, ar.artist_name,
                 sam.release_date, {precision_expression(conn, "spotify_album_meta", "sam")}
            FROM album_spotify_links asl JOIN albums al USING(album_id)
            JOIN artists ar ON ar.artist_id=al.artist_id
            JOIN spotify_album_meta sam USING(spotify_album_id)
            WHERE asl.confidence>=0.9 AND lower(COALESCE(sam.album_type,'')) IN ('album','ep')""").fetchall()
        from collections import defaultdict

        grouped = defaultdict(list)
        for row in rows:
            grouped[(row[0], row[1])].append(parse_release_date(row[2], row[3]))
        reliable = []
        for (album_name, artist_name), evidence in grouped.items():
            days = {item.exact_day for item in evidence if item.exact_day is not None}
            if len(days) != 1:
                continue
            selected = next(item for item in evidence if item.exact_day is not None)
            if any(
                compare_release_dates(selected, item) in {"conflict", "unknown"}
                for item in evidence
            ):
                continue
            reliable.append((album_name, artist_name, selected.raw))
        return pd.DataFrame(reliable, columns=columns)
    except Exception as exc:
        logger.warning("Reliable album release-date lookup failed: %s", exc)
        return pd.DataFrame(columns=columns)


def _canonical_records_track_frame(frame: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    """Return one owned frame; a successful merge already copies its input."""
    if frame.empty:
        return frame.copy()
    if not groups.empty:
        result = frame.merge(groups, on="track_id", how="left")
        result["canonical_track_id"] = result["track_agg_id"].fillna(result["track_id"])
        result["canonical_track_name"] = result["track_agg_name"].fillna(result["track_name"])
    else:
        result = frame.copy()
        result["canonical_track_id"] = result["track_id"]
        result["canonical_track_name"] = result["track_name"]
    return result


def _build_records_track_frame(
    event_frame: pd.DataFrame,
    duration_frame: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int,
) -> pd.DataFrame:
    tg = pd.DataFrame()
    if (not event_frame.empty or not duration_frame.empty) and merge_level >= 2:
        tg = load_track_group_keys(conn, merge_level)
        # Keep the played version's representative key for artist credits;
        # group representatives determine only the aggregation identity.
        if not tg.empty:
            tg = tg[["track_id", "track_agg_id", "track_agg_name"]]
    # Complete the event result before allocating the duration result. The
    # source frames stay read-only; copying before merge would duplicate the
    # wide buffers once more at its peak.
    track_frame = _canonical_records_track_frame(event_frame, tg)
    track_duration = _canonical_records_track_frame(duration_frame, tg)
    attach_listening_duration_frame(track_frame, track_duration)
    return track_frame


def _build_records_album_frame(
    frame: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int,
    include_compilations: bool,
    membership: pd.DataFrame | None,
    *,
    duration: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Build one owned projection; release join intermediates before the next one.

    The input remains read-only, including on a failed membership lookup/join.
    Successful canonicalization already makes its own copy, so no full-width
    copy is needed before entering it.
    """
    fallback_frame = frame
    if not frame.empty and merge_level >= 2:
        try:
            from backend.domains.playback.album_projects import (
                apply_canonical_song_keys,
                load_album_project_membership,
            )

            with_keys = apply_canonical_song_keys(frame, conn, merge_level)
            if membership is None:
                membership = load_album_project_membership(conn, merge_level, include_compilations)
            if not membership.empty and "canonical_song_key" in with_keys.columns:
                membership_join = membership[
                    [
                        "canonical_song_key",
                        "project_id",
                        "album_project_name",
                        "release_date",
                        "release_date_precision",
                    ]
                ].rename(
                    columns={
                        "project_id": "album_project_id",
                        "release_date": "album_project_release_date",
                        "release_date_precision": "album_project_release_date_precision",
                    }
                )
                result = with_keys.merge(membership_join, on="canonical_song_key", how="left")
                if duration:
                    # The previous duration path retained an already-expanded
                    # join if a subsequent fill failed; preserve that fallback.
                    fallback_frame = result
                result["album_project_id"] = result["album_project_id"].fillna(
                    result["album_name"].astype(str)
                )
                result["album_project_name"] = result["album_project_name"].fillna(
                    result["album_name"]
                )
                return result, membership
        except Exception as exc:
            if duration:
                logger.warning(
                    "Album duration project membership join failed, falling back to album_name: %s",
                    exc,
                )
            else:
                logger.warning(
                    "Album project membership join failed, falling back to album_name: %s", exc
                )
    result = fallback_frame.copy()
    if not result.empty:
        result["album_project_id"] = result["album_name"].astype(str)
        result["album_project_name"] = result["album_name"]
    return result, membership


def _build_entity_frames(
    event_frame: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int,
    include_compilations: bool = False,
    min_ms: int = 30000,
    music_only: bool = True,
    merge_enabled: bool = True,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    period_start: str | None = None,
    period_end: str | None = None,
    duration_facts: RecordsDurationFacts | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build track, album, and artist entity frames with canonicalization.

    Returns:
        track_frame: event_frame with canonical_track_id/name columns added
        album_frame: event_frame with album_project_id/name columns added
        artist_frame: fan-out frame with one row per contributing artist
    """
    # Establish logical identity before track/album membership expands rows.
    # Yearly Review also calls this builder directly on its history frame.
    # Existing identities can be read directly; entity projections own results.
    if "_logical_event_id" not in event_frame.columns:
        event_frame = assign_logical_event_id(event_frame)
    # Build artist history before allocating track/album projections so their
    # wide result frames do not overlap the artist reconstruction peak.
    try:
        artist_frame = load_plays_for_artists(
            conn,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        artist_frame = attach_scoped_records_duration(
            artist_frame,
            start_date=period_start,
            end_date=period_end,
            duration_facts=duration_facts,
        )
        if not artist_frame.empty and (period_start or period_end):
            dates = artist_frame["ts_date"].astype(str)
            mask = pd.Series(True, index=artist_frame.index)
            if period_start:
                mask &= dates >= period_start
            if period_end:
                mask &= dates <= period_end
            scoped_artist_duration = records_duration_frame(artist_frame)
            artist_frame = artist_frame.loc[mask].copy()
            attach_listening_duration_frame(artist_frame, scoped_artist_duration)
    except Exception as e:
        # Fallback: use primary artist from event_frame
        logger.warning("Artist fan-out failed, falling back to primary artist: %s", e)
        artist_frame = event_frame.copy()

    duration_frame = records_duration_frame(event_frame, copy=False)
    # Complete each album projection before allocating the track pair. Keep
    # full output columns for Records and Yearly Review, but let each join's
    # temporary wide frames die before constructing the next entity frame.
    album_frame, membership = _build_records_album_frame(
        event_frame, conn, merge_level, include_compilations, None
    )
    album_duration, _ = _build_records_album_frame(
        duration_frame, conn, merge_level, include_compilations, membership, duration=True
    )
    attach_listening_duration_frame(album_frame, album_duration)
    # The result owns these slices until its metadata contract releases them.
    del album_duration

    # Fastest album milestones use a trustworthy formal release date to discard
    # prerelease plays. Prefer the canonical album-project date; only use a
    # source-album fallback when one high-confidence Spotify date is unambiguous.
    if not album_frame.empty:
        if "album_project_release_date" not in album_frame.columns:
            album_frame["album_project_release_date"] = None
        from backend.domains.metadata.release_dates import parse_release_date

        precision = album_frame.get(
            "album_project_release_date_precision", pd.Series(None, index=album_frame.index)
        )
        album_frame["album_project_release_day"] = [
            evidence.exact_day.isoformat() if evidence.exact_day else None
            for evidence in (
                parse_release_date(raw, prec)
                for raw, prec in zip(album_frame["album_project_release_date"], precision)
            )
        ]
        # A derived Series also carries duration attrs; its last use is above.
        del precision
        release_dates = _load_reliable_album_release_dates(conn)
        if not release_dates.empty:
            # The loader emits one fallback per key; the album projection is
            # already owned, so only join keys need to enter this lookup.
            release_lookup = album_frame[["album_name", "artist_name"]].merge(
                release_dates,
                on=["album_name", "artist_name"],
                how="left",
                validate="many_to_one",
            )
            # Preserve the previous merge's index and metadata contract: its
            # cleared duration attrs determine subsequent Records consumption.
            album_frame.index = release_lookup.index
            album_frame.columns.name = release_lookup.columns.name
            album_frame.attrs.clear()
            # Preserve fillna's existing dtype inference explicitly. Its silent
            # object downcast warns on all-missing dates and caches this entire
            # source file through linecache during a high-memory Records build.
            release_day = album_frame["album_project_release_day"]
            album_frame["album_release_date"] = release_day.where(
                release_day.notna(), release_lookup["source_album_release_date"]
            ).infer_objects(copy=False)
            del release_day
            del release_lookup
        else:
            album_frame["album_release_date"] = album_frame["album_project_release_day"]

    track_frame = _build_records_track_frame(event_frame, duration_frame, conn, merge_level)
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
    *,
    preloaded_event_frame: pd.DataFrame | None = None,
    preloaded_entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
) -> dict:
    """Compute playback records (uncached inner function)."""

    # Yearly Review already owns a filtered play frame and canonical entity
    # frames. Reuse those when provided; the standalone records page keeps the
    # existing load/build path.
    event_frame = preloaded_event_frame
    if event_frame is None:
        event_frame = load_plays(
            conn,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )

    # Preserve full-history duplicate ordinals before narrowing the time range.
    # Existing IDs on Yearly Review's prepared frames remain unchanged.
    event_frame = assign_logical_event_id(event_frame)

    # Keep the complete standalone history for lifetime ordinal records before
    # applying the requested display period.  Yearly Review supplies an
    # already-scoped preloaded frame, so its existing annual semantics remain
    # unchanged and it does not opt into this standalone lifetime snapshot.
    lifetime_event_frame = None if preloaded_event_frame is not None else event_frame.copy()

    duration_facts = RecordsDurationFacts()

    # Period filtering
    period_start, period_end = resolve_period_dates(period, start_date, end_date)
    event_frame = attach_scoped_records_duration(
        event_frame,
        start_date=period_start,
        end_date=period_end,
        duration_facts=duration_facts,
    )
    scoped_duration = records_duration_frame(event_frame, copy=False)
    if period_start or period_end:
        if period_start:
            event_frame = event_frame[event_frame["ts_date"].astype(str) >= period_start]
        if period_end:
            event_frame = event_frame[event_frame["ts_date"].astype(str) <= period_end]
        event_frame = event_frame.copy()
        attach_listening_duration_frame(event_frame, scoped_duration)

    duration_frame = records_duration_frame(event_frame, copy=False)

    # Resolved period for response
    if period == "lifetime":
        range_source = event_frame if not event_frame.empty else duration_frame
        p_start = str(range_source["ts_date"].min()) if not range_source.empty else None
        p_end = str(range_source["ts_date"].max()) if not range_source.empty else None
        del range_source
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
    if event_frame.empty and duration_frame.empty:
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
    total_hours = round(float(duration_frame["ms_played"].sum()) / 3_600_000, 1)
    active_days = int(event_frame["ts_date"].nunique())

    meta = {
        "total_plays": total_plays,
        "total_hours": total_hours,
        "active_days": active_days,
        "merge_level": merge_level,
        "min_sample_plays": 10,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    # Build entity frames only for standalone callers. Preloaded frames are
    # already aligned to the same annual range by the Yearly Review orchestrator.
    if preloaded_entity_frames is None:
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
            period_start=period_start,
            period_end=period_end,
            duration_facts=duration_facts,
        )
    else:
        track_frame, album_frame, artist_frame = tuple(
            attach_scoped_records_duration(
                frame.copy(),
                start_date=period_start,
                end_date=period_end,
                duration_facts=duration_facts,
            )
            for frame in preloaded_entity_frames
        )

    # Geometry is no longer needed once every entity owns its scoped slices.
    del duration_facts

    # Compute records
    raw_records = compute_playback_records(
        event_frame=event_frame,
        track_frame=track_frame,
        album_frame=album_frame,
        artist_frame=artist_frame,
        merge_level=merge_level,
        conn=conn,
        milestone_event_frame=lifetime_event_frame,
    )

    # Calculation has consumed the history and entity projections. Keep only
    # record results while presentation resolves covers and serializes them.
    del event_frame, lifetime_event_frame, scoped_duration, duration_frame
    del track_frame, album_frame, artist_frame

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
            "late_night_trajectory": {
                "monthly": flat.get("time_late_night_trajectory_monthly", []),
                "quarterly": flat.get("time_late_night_trajectory_quarterly", []),
                "monthly_min_plays": flat.get("time_late_night_monthly_min_plays", 500),
                "quarterly_min_plays": flat.get("time_late_night_quarterly_min_plays", 1500),
            },
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
                "album": flat.get("discovery_feat_lover_album", []),
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


@singleflight
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
    sort_contract_version: str = PLAYBACK_RECORDS_SORT_CONTRACT_VERSION,
    track_credit_policy: str = "",
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
    max_merge_gap_minutes: int | None = 5,
    include_compilations: bool = False,
) -> dict:
    """Get all playback records for the analysis/records page."""
    from backend.domains.metadata.track_credits import TRACK_CREDIT_POLICY_VERSION

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
        sort_contract_version=PLAYBACK_RECORDS_SORT_CONTRACT_VERSION,
        track_credit_policy=TRACK_CREDIT_POLICY_VERSION,
    )


# Register cache for global invalidation (import, version merge, album project rebuild)
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("analysis", "records", _get_analysis_records_cached)
