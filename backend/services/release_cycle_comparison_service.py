"""Reuse published chart facts while preparing one release comparison batch."""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.core.access_surface import (
    reset_public_readonly_db_guard,
    set_public_readonly_db_guard,
    snapshot_unavailable,
)
from backend.core.cache import singleflight
from backend.core.cache_manager import register_lru
from backend.core.db import base_filters, get_db, merge_consecutive_plays
from backend.domains.billboard import persistent_cache
from backend.domains.billboard.chart_staged_api import _resolve
from backend.domains.billboard.data_loader import _track_identity_sql
from backend.domains.metadata.artist_identity import get_artist_identity_map
from backend.domains.playback.counting import filter_effective_plays
from backend.domains.playback.logical_timeline import billboard_week_for_timestamps
from backend.services.versus_personal_stats_service import _load_target_timeline

RANK_COLUMNS = ("billboard_week", "artist_name", "album_name", "rank", "play_count")
PUBLISHED_RANK_COLUMNS = (*RANK_COLUMNS, "album_project_id")
PLAY_COLUMNS = (
    "artist_name",
    "album_name",
    "track_name",
    "track_id",
    "ms_played",
    "ts_date_dt",
    "ts_date",
    "billboard_week",
)
COUNT_FILTERS = (
    "min_ms",
    "music_only",
    "merge_enabled",
    "dynamic_threshold",
    "max_merge_gap_minutes",
    "bb_week_start_dow",
    "bb_week_start_hour",
)


def _artist_source_ids(conn, names):
    """Select Billboard primary-artist sources, without credit fan-out.

    Follow the same per-play L1 representative and canonical display names as
    the raw Billboard projection. Selected sources are then read for their
    entire timeline, including the predecessor context needed for merging.
    """
    mapping = get_artist_identity_map(conn)
    artist_ids = [
        int(artist_id)
        for artist_id, raw_name in conn.execute("SELECT artist_id,artist_name FROM artists")
        if (mapping[int(artist_id)].display_name if int(artist_id) in mapping else raw_name)
        in names
    ]
    if not artist_ids:
        return ()
    _, joins, _ = _track_identity_sql(conn)
    markers = ",".join("?" for _ in artist_ids)
    return tuple(
        int(row[0])
        for row in conn.execute(
            f"SELECT DISTINCT p.track_id FROM plays p {joins} "
            f"WHERE p.track_id IS NOT NULL AND t.artist_id IN ({markers}) ORDER BY p.track_id",
            artist_ids,
        )
    )


def _count_events(conn, params):
    """Reconstruct the global count timeline without unused listening tracks.

    Album/artist presentation cannot affect count continuity. Keep original
    L1 identity, import-stable ordering, source album boundaries and duration
    thresholds; never prune short fragments before logical reconstruction.
    """
    identity_columns, joins, spotify_id = _track_identity_sql(conn)
    where, values = base_filters(min_ms=0, music_only=params["music_only"])
    sql = f"""SELECT p.play_id,p.ts,p.ts_date,p.ms_played,p.source_album_id,
                     {identity_columns},stm.duration_ms
              FROM plays p {joins}
              LEFT JOIN spotify_track_meta stm ON {spotify_id}=stm.spotify_track_id
              {("WHERE " + where) if where else ""}
              ORDER BY p.ts,COALESCE(p.source_fingerprint,''),p.play_id"""
    events = pd.read_sql_query(sql, conn, params=values)
    if params["merge_enabled"]:
        events = merge_consecutive_plays(
            events,
            params["min_ms"],
            max_gap_minutes=params["max_merge_gap_minutes"],
            boundary_column="source_album_id",
            dynamic_threshold=params["dynamic_threshold"],
        )
    events = filter_effective_plays(
        events, min_ms=params["min_ms"], dynamic_threshold=params["dynamic_threshold"]
    )
    events["billboard_year"] = pd.to_datetime(
        billboard_week_for_timestamps(
            events["counted_at"] if "counted_at" in events else events["ts"],
            week_start_dow=params["bb_week_start_dow"],
            week_start_hour=params["bb_week_start_hour"],
        )
    ).dt.year
    return events


def _try_aggregate_daily_projection(conn, params, source_revision):
    """Reuse only a complete, current merge-enabled music aggregate proof.

    Source rows retain event dates and open coverage weeks. Sum their count
    weights directly: duration-only rows contribute zero, and dimension joins
    would unnecessarily discard events with absent presentation metadata.
    """
    if not params["merge_enabled"] or not params["music_only"]:
        return None
    from backend.core import db
    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import get_track_credit_revision
    from backend.domains.metadata.track_identity import get_track_identity_revision

    try:
        source_token = conn.execute("PRAGMA data_version").fetchone()[0]
        if (
            persistent_cache.build_cache_context("weekly", params)["source_revision"]
            != source_revision
        ):
            return None
        config = db._aggregation_config(conn)
        if config.get("builder_version") != db._BILLBOARD_AGGREGATION_BUILDER_VERSION:
            return None
        generation = db._active_playback_generation(conn)
        dataset = db._active_playback_dataset_digest(conn)
        if (
            not generation
            or not dataset
            or config.get("data_generation_id") != generation
            or config.get("source_dataset_digest") != dataset
        ):
            return None
        param_hash, dependencies = db.build_aggregation_semantic_proof(
            conn,
            min_ms=params["min_ms"],
            music_only=params["music_only"],
            week_start_dow=params["bb_week_start_dow"],
            week_start_hour=params["bb_week_start_hour"],
            dynamic_threshold=params["dynamic_threshold"],
            max_merge_gap_minutes=params["max_merge_gap_minutes"],
            identity_revision=get_identity_revision(conn),
            track_credit_revision=get_track_credit_revision(conn),
            track_identity_revision=get_track_identity_revision(conn),
        )
        # Project membership is applied when reading source aggregates; it is
        # not baked into their event counts (the same incremental reuse rule).
        # This global date baseline never consumes project attribution.
        if config.get("param_hash") != param_hash or any(
            config.get(key) != value
            for key, value in dependencies.items()
            if key != "album_project_revision"
        ):
            return None
        rows = tuple(
            (int(row[0]), str(row[1]), int(row[2]))
            for row in conn.execute(
                "SELECT CAST(substr(billboard_week,1,4) AS INTEGER),play_date,SUM(play_count) "
                "FROM agg_weekly_track_sources "
                "GROUP BY substr(billboard_week,1,4),play_date "
                "HAVING SUM(play_count)>0 ORDER BY 1,2"
            )
        )
        if (
            conn.execute("PRAGMA data_version").fetchone()[0] != source_token
            or persistent_cache.build_cache_context("weekly", params)["source_revision"]
            != source_revision
        ):
            return None
        return rows
    except (sqlite3.Error, KeyError, TypeError, ValueError):
        # This optional acceleration never repairs a missing/unreadable or
        # stale publication. The existing raw count path remains authoritative.
        return None


@singleflight
@lru_cache(maxsize=4)
def _daily_projection(params_json, source_revision):
    """Cache compact year/date/count tuples, with no global event frames."""
    conn = get_db(readonly=True)
    try:
        params = json.loads(params_json)
        projected = _try_aggregate_daily_projection(conn, params, source_revision)
        if projected is not None:
            return projected
        events = _count_events(conn, params)
        counts = events.groupby(["billboard_year", "ts_date"]).size()
        return tuple((int(year), str(day), int(count)) for (year, day), count in counts.items())
    finally:
        conn.close()


register_lru("billboard", "release_cycle_daily_projection", _daily_projection)


def _publication_state():
    path = Path(persistent_cache.BILLBOARD_CACHE_PATH)
    try:
        stat = path.stat()
    except OSError:
        return str(path.resolve()), None
    wal = path.with_name(path.name + "-wal")
    try:
        wal_stat = wal.stat()
    except FileNotFoundError:
        wal_state = None
    except OSError:
        return str(path.resolve()), None
    else:
        # Read-only SQLite connections can create/remove an empty WAL. It has
        # no publication content and must not split the singleflight key.
        wal_state = (
            (wal_stat.st_ino, wal_stat.st_mtime_ns, wal_stat.st_size)
            if wal_stat.st_size > 0
            else None
        )
    return str(path.resolve()), stat.st_ino, stat.st_size, stat.st_mtime_ns, wal_state


@singleflight
@lru_cache(maxsize=4)
def _weekly_projection(context_json, publication_state):
    """Retain only immutable rank tuples, never full JSON or source frames."""
    del publication_state
    context = json.loads(context_json)
    # Even private comparison reads must not create/repair a sidecar or delete
    # corrupt publications. This scoped guard does not change provider policy
    # in the subsequent existing release-cycle calculation.
    token = set_public_readonly_db_guard(True)
    try:
        payload = persistent_cache.load_persisted_snapshot(context, allow_lkg=False)
    finally:
        reset_public_readonly_db_guard(token)
    if payload is None:
        raise snapshot_unavailable("weekly", context["source_revision"])
    result = []
    for name in ("weekly_artist", "weekly_album"):
        rows = payload.get(name)
        if not isinstance(rows, list):
            raise snapshot_unavailable("weekly", context["source_revision"])
        try:
            result.append(
                tuple(
                    tuple(row.get(column) for column in PUBLISHED_RANK_COLUMNS)
                    for row in rows
                    if isinstance(row, dict)
                )
            )
        except (TypeError, ValueError):
            raise snapshot_unavailable("weekly", context["source_revision"]) from None
    return tuple(result)


register_lru("billboard", "release_cycle_weekly_projection", _weekly_projection)


def prepare_comparison_data(filters, artist_names, merge_level=2, include_compilations=False):
    """Prepare one shared date baseline and target-artist frame without ranking.

    Playback uses a scoped count timeline and compact global daily baseline.
    Weekly ranking comes only from the matching exact publication.
    No release metadata, metrics, alignment or endpoint input contract changes.
    """
    _, params = _resolve(
        (),
        {**vars(filters), "merge_level": merge_level, "include_compilations": include_compilations},
    )
    context = persistent_cache.build_cache_context("weekly", params)
    projection = _weekly_projection(json.dumps(context, sort_keys=True), _publication_state())
    count_params = {name: params[name] for name in COUNT_FILTERS}
    daily_rows = _daily_projection(
        json.dumps(count_params, sort_keys=True), context["source_revision"]
    )
    daily_frame = pd.DataFrame(daily_rows, columns=("year", "date", "play_count"))
    if filters.year_start is not None:
        daily_frame = daily_frame.loc[daily_frame["year"] >= filters.year_start]
    if filters.year_end is not None:
        daily_frame = daily_frame.loc[daily_frame["year"] <= filters.year_end]
    daily_frame["date"] = pd.to_datetime(daily_frame["date"])
    total_daily = daily_frame.groupby("date")["play_count"].sum()
    total_daily.name = "play_count"
    names = set(artist_names)
    conn = get_db(readonly=True)
    try:
        source_ids = _artist_source_ids(conn, names)
        frame, _ = _load_target_timeline(conn, source_ids, params, include_duration=False)
        if source_ids:
            frame = frame.loc[frame["source_track_id"].isin(source_ids)].copy()
            album_names = dict(conn.execute("SELECT album_id,album_name FROM albums").fetchall())
            frame["album_name"] = (
                frame["source_album_id"].map(album_names).fillna(frame["album_name"])
            )
            frame["billboard_week"] = billboard_week_for_timestamps(
                frame["counted_at"] if "counted_at" in frame else frame["ts"],
                week_start_dow=filters.bb_week_start_dow,
                week_start_hour=filters.bb_week_start_hour,
            )
        else:
            frame = pd.DataFrame(columns=PLAY_COLUMNS)
    finally:
        conn.close()
    if "ts_date_dt" not in frame.columns:
        frame["ts_date_dt"] = pd.to_datetime(frame["ts_date"])
    frame = pd.DataFrame(frame, copy=False).loc[:, list(PLAY_COLUMNS)]
    if filters.year_start is not None or filters.year_end is not None:
        years = pd.to_datetime(frame["billboard_week"]).dt.year
        mask = pd.Series(True, index=frame.index)
        if filters.year_start is not None:
            mask &= years >= filters.year_start
        if filters.year_end is not None:
            mask &= years <= filters.year_end
        frame = frame.loc[mask]
    selected = frame.loc[frame["artist_name"].isin(names)].copy()
    ranked = []
    for rows in projection:
        target = pd.DataFrame([row[:5] for row in rows if row[1] in names], columns=RANK_COLUMNS)
        target["billboard_week"] = pd.to_datetime(target["billboard_week"]).dt.date
        ranked.append(target)
    if persistent_cache.build_cache_context("weekly", params) != context:
        raise snapshot_unavailable("weekly")
    return selected, ranked[0], ranked[1], total_daily


def prepare_project_comparison_data(
    filters, items, merge_level=2, include_compilations=False, *, include_selections=False
):
    """Select project songs independently of the artist and source container.

    Artist timelines keep their existing primary-artist contract. Project
    timelines share the exact membership and logical-event reconstruction of
    personal comparisons, including collaboration sources and predecessor rows.
    """
    from backend.services.versus_personal_context import resolve_selection
    from backend.services.versus_personal_stats_service import _album_song_frames

    _, params = _resolve(
        (),
        {**vars(filters), "merge_level": merge_level, "include_compilations": include_compilations},
    )
    context = persistent_cache.build_cache_context("weekly", params)
    conn = get_db(readonly=True)
    try:
        selections = resolve_selection(
            conn, "album", items, merge_level, filters=params, allow_shared_album_project=True
        )
        artists = get_artist_identity_map(conn)
        names = [
            artists[item.artist_id].display_name if item.artist_id in artists else item.artist_name
            for item in selections
            if item.artist_name
        ]
        artist_frame, artist_ranks, _, total_daily = prepare_comparison_data(
            filters, names, merge_level, include_compilations
        )
        projection = _weekly_projection(json.dumps(context, sort_keys=True), _publication_state())
        if any(row[5] is None for row in projection[1]):
            raise snapshot_unavailable("weekly", context["source_revision"])
        sources = tuple(
            sorted({track for selection in selections for track in selection.track_ids})
        )
        events, _ = _load_target_timeline(conn, sources, params, include_duration=False)
        events = events.loc[events["source_track_id"].isin(sources)].copy()
        if not events.empty:
            events, _ = _album_song_frames(
                conn, events, pd.DataFrame(columns=["track_id", "track_name"]), merge_level
            )
            events["billboard_week"] = billboard_week_for_timestamps(
                events["counted_at"] if "counted_at" in events else events["ts"],
                week_start_dow=params["bb_week_start_dow"],
                week_start_hour=params["bb_week_start_hour"],
            )
            events["ts_date_dt"] = pd.to_datetime(events["ts_date"])
            years = pd.to_datetime(events["billboard_week"]).dt.year
            if filters.year_start is not None:
                events = events.loc[years >= filters.year_start]
            if filters.year_end is not None:
                events = events.loc[years <= filters.year_end]
        project_frames = []
        project_ranks = []
        for selection in selections:
            project_frames.append(
                events.loc[events["canonical_song_key"].isin(selection.song_keys)].copy()
                if not events.empty
                else pd.DataFrame(columns=PLAY_COLUMNS)
            )
            rows = [row for row in projection[1] if row[5] == selection.project_id]
            ranks = pd.DataFrame(rows, columns=PUBLISHED_RANK_COLUMNS)
            ranks["billboard_week"] = pd.to_datetime(ranks["billboard_week"]).dt.date
            project_ranks.append(ranks)
    finally:
        conn.close()
    if persistent_cache.build_cache_context("weekly", params) != context:
        raise snapshot_unavailable("weekly")
    result = (artist_frame, artist_ranks, total_daily, project_frames, project_ranks)
    return (*result, selections) if include_selections else result
