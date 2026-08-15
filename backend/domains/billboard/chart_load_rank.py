"""Shared Billboard load/rank cache used by full and staged chart APIs."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from backend.core.cache import singleflight
from backend.domains.billboard.chart_ranking import (
    _add_running_metrics,
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
)
from backend.domains.billboard.data_loader import (
    _try_load_from_agg,
    load_billboard_raw,
    load_billboard_raw_for_artists,
)
from backend.domains.billboard.version_merge import _normalize_album_column


def billboard_revision_state() -> tuple[int, int, int, int, str]:
    """Return the metadata generation that may change artist attribution.

    The active revisions are included separately so a pending rebuild cannot
    share an LRU entry with the ready aggregate generation.
    """
    from backend.core.db import get_db
    from backend.domains.metadata.artist_identity import get_identity_state
    from backend.domains.metadata.track_credits import get_track_credit_state

    conn = get_db()
    try:
        identity = get_identity_state(conn)
        credits = get_track_credit_state(conn)
        return (
            int(identity.get("current_revision", 0)),
            int(identity.get("active_aggregate_revision", 0)),
            int(credits.get("current_revision", 0)),
            int(credits.get("active_aggregate_revision", 0)),
            f"{identity.get('rebuild_status', 'ready')}:{credits.get('rebuild_status', 'ready')}",
        )
    finally:
        conn.close()


def call_with_billboard_revision_cache(cached_fn, args: tuple):
    """Call a revision-keyed LRU, bypassing storage while rebuilds are pending."""
    state = billboard_revision_state()
    ready = state[0] == state[1] and state[2] == state[3] and state[4] == "ready:ready"
    if not ready:
        return cached_fn.__wrapped__(*args, state)
    return cached_fn(*args, state)


@singleflight
@lru_cache(maxsize=8)
def _load_and_rank_cached_by_revision(
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
    _revision_state=(0, 0, 0, 0, "ready:ready"),
):
    return _load_and_rank_uncached(
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
    )


def _load_and_rank_cached(
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
):
    revision_state = billboard_revision_state()
    ready = (
        revision_state[0] == revision_state[1]
        and revision_state[2] == revision_state[3]
        and revision_state[4] == "ready:ready"
    )
    args = (
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
    )
    # Pending fallbacks are correct but deliberately short-lived: never let an
    # in-flight rebuild result become the stable ready-generation LRU value.
    if not ready:
        return _load_and_rank_uncached(*args)
    return _load_and_rank_cached_by_revision(*args, revision_state)


_load_and_rank_cached.cache_clear = _load_and_rank_cached_by_revision.cache_clear  # type: ignore[attr-defined]
_load_and_rank_cached.cache_info = _load_and_rank_cached_by_revision.cache_info  # type: ignore[attr-defined]


def _copy_load_and_rank_result(result):
    if len(result) == 7:
        (
            weekly,
            weekly_album,
            weekly_artist,
            all_weeks_asc,
            all_weeks_desc,
            df_filtered,
            album_total_map,
        ) = result
    else:
        weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered = result
        album_total_map = {}
    return (
        weekly.copy(),
        weekly_album.copy(),
        weekly_artist.copy(),
        list(all_weeks_asc),
        list(all_weeks_desc),
        df_filtered.copy(),
        album_total_map,
    )


def _load_and_rank_uncached(
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
):
    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    if _agg_tracks is not None:
        _agg_tracks = _filter_billboard_years(_agg_tracks, year_start, year_end)
        _agg_albums = _filter_billboard_years(_agg_albums, year_start, year_end)
        _agg_artists = _filter_billboard_years(_agg_artists, year_start, year_end)
        df_filtered = _agg_tracks.copy()
    else:
        df_raw = load_billboard_raw(
            min_ms,
            music_only,
            bb_week_start_dow,
            bb_week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        df_filtered = _filter_billboard_years(df_raw.copy(), year_start, year_end)

    coverage_source = _agg_albums if _agg_tracks is not None else df_filtered
    if (
        coverage_source is not None
        and not coverage_source.empty
        and "billboard_week" in coverage_source.columns
    ):
        date_column = next(
            (column for column in ("ts_date", "ts") if column in coverage_source.columns),
            None,
        )
        if date_column is not None:
            coverage_dates = pd.DataFrame(
                {
                    "year": pd.to_datetime(
                        coverage_source["billboard_week"],
                        errors="coerce",
                    ).dt.year,
                    "date": pd.to_datetime(
                        coverage_source[date_column],
                        errors="coerce",
                        utc=True,
                    ),
                }
            ).dropna()
            df_filtered.attrs["coverage_periods"] = {
                int(year): (group["date"].min(), group["date"].max())
                for year, group in coverage_dates.groupby("year", sort=False)
            }

    all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
    all_weeks_desc = sorted(all_weeks_asc, reverse=True)
    weekly = compute_weekly_rankings(
        df_filtered, bb_top_n, pre_agg=_agg_tracks, merge_level=merge_level
    )
    weekly_album = compute_album_weekly_rankings(
        df_filtered,
        bb_album_top_n,
        pre_agg=_agg_albums,
        merge_level=merge_level,
        include_compilations=include_compilations,
    )

    if _agg_artists is not None:
        weekly_artist = compute_artist_weekly_rankings(
            df_filtered, bb_artist_top_n, pre_agg=_agg_artists
        )
    else:
        df_artists = load_billboard_raw_for_artists(
            min_ms,
            music_only,
            bb_week_start_dow,
            bb_week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        df_artists = _filter_billboard_years(df_artists, year_start, year_end)
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

    weekly_album, weekly_artist = _attach_charting_entity_counts(
        weekly, weekly_album, weekly_artist, merge_level=merge_level
    )

    _artist_ac = (
        weekly_album.groupby(["billboard_week", "artist_name"])
        .agg(albums_count=("album_name", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.merge(
        _artist_ac, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["albums_count"] = weekly_artist["albums_count"].fillna(0).astype(int)

    weekly = _add_running_metrics(weekly, ["track_id"])
    weekly_album = _add_running_metrics(weekly_album, ["artist_name", "album_name"])
    weekly_artist = _add_running_metrics(weekly_artist, ["artist_name"])

    # Compute unfiltered total_plays for all album projects (no release-date filter)
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import compute_album_project_plays

    conn = get_db()
    try:
        album_total_plays = compute_album_project_plays(
            df_filtered,
            conn,
            merge_level=merge_level,
            include_compilations=include_compilations,
            billboard_mode=False,
        )
        album_total_map = {}
        if not album_total_plays.empty:
            for _, row in album_total_plays.iterrows():
                key = (row["album_project_name"], row["artist_name"])
                album_total_map[key] = int(row["play_count"])
    finally:
        conn.close()

    return (
        weekly,
        weekly_album,
        weekly_artist,
        all_weeks_asc,
        all_weeks_desc,
        df_filtered,
        album_total_map,
    )


def _charting_artist_track_counts(weekly: pd.DataFrame, merge_level: int) -> pd.DataFrame:
    """Count Top-N canonical tracks per effective canonical credited artist."""
    columns = ["billboard_week", "artist_name", "tracks_count"]
    if weekly.empty:
        return pd.DataFrame(columns=columns)

    from backend.core.db import get_db
    from backend.domains.metadata.track_credits import get_effective_track_credit_frame
    from backend.domains.playback.track_groups import load_track_group_keys

    chart_tracks = weekly[["billboard_week", "track_id"]].drop_duplicates().copy()
    chart_tracks["track_id"] = chart_tracks["track_id"].astype(int)
    canonical_ids = set(chart_tracks["track_id"].tolist())
    conn = get_db()
    try:
        member_to_canonical: dict[int, int] = {track_id: track_id for track_id in canonical_ids}
        if merge_level > 1:
            keys = load_track_group_keys(conn, merge_level)
            if not keys.empty:
                keys = keys[keys["track_agg_id"].isin(canonical_ids)]
                member_to_canonical.update(
                    {int(row.track_id): int(row.track_agg_id) for row in keys.itertuples()}
                )
        credits = get_effective_track_credit_frame(conn, member_to_canonical.keys())
    finally:
        conn.close()
    if credits.empty:
        return pd.DataFrame(columns=columns)
    credits = credits[["track_id", "artist_id", "artist_name"]].copy()
    credits["track_id"] = credits["track_id"].map(member_to_canonical)
    credits = credits[credits["track_id"].isin(canonical_ids)].drop_duplicates(
        ["track_id", "artist_id"]
    )
    expanded = chart_tracks.merge(credits, on="track_id", how="inner")
    return (
        expanded.drop_duplicates(["billboard_week", "artist_id", "track_id"])
        .groupby(["billboard_week", "artist_id", "artist_name"], as_index=False)
        .agg(tracks_count=("track_id", "nunique"))
        .drop(columns=["artist_id"])
    )


def _attach_charting_entity_counts(weekly, weekly_album, weekly_artist, *, merge_level=2):
    _album_tc = (
        weekly.groupby(["billboard_week", "album_name", "artist_name"])
        .agg(tracks_count=("track_id", "nunique"))
        .reset_index()
    )
    _album_tc = _normalize_album_column(
        _album_tc, dedup_cols=["billboard_week", "album_name", "artist_name"]
    )
    _album_tc = (
        _album_tc.groupby(["billboard_week", "album_name", "artist_name"])
        .agg(tracks_count=("tracks_count", "sum"))
        .reset_index()
    )
    weekly_album = weekly_album.drop(columns=["tracks_count"], errors="ignore").merge(
        _album_tc, on=["billboard_week", "album_name", "artist_name"], how="left"
    )
    weekly_album["tracks_count"] = weekly_album["tracks_count"].fillna(0).astype(int)

    _artist_tc = _charting_artist_track_counts(weekly, merge_level)
    weekly_artist = weekly_artist.drop(columns=["tracks_count"], errors="ignore").merge(
        _artist_tc, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["tracks_count"] = weekly_artist["tracks_count"].fillna(0).astype(int)
    return weekly_album, weekly_artist


# Compatibility alias retained for focused downstream tests/imports.
_attach_track_and_artist_counts_from_preagg = _attach_charting_entity_counts


def _filter_billboard_years(
    df: pd.DataFrame,
    year_start: int | None,
    year_end: int | None,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    years = pd.to_datetime(out["billboard_week"]).dt.year
    if year_start is not None:
        out = out[years >= year_start]
        years = years.loc[out.index]
    if year_end is not None:
        out = out[years <= year_end]
    from backend.domains.playback.logical_timeline import (
        attach_billboard_weighted_frame,
        get_billboard_weighted_frame,
    )

    weighted = get_billboard_weighted_frame(df)
    if weighted is not None and not weighted.empty:
        weighted_years = pd.to_datetime(weighted["billboard_week"]).dt.year
        weighted_out = weighted
        if year_start is not None:
            weighted_out = weighted_out[weighted_years >= year_start]
            weighted_years = weighted_years.loc[weighted_out.index]
        if year_end is not None:
            weighted_out = weighted_out[weighted_years <= year_end]
        attach_billboard_weighted_frame(out, weighted_out.copy())
    return out


def _filtered_record_count(df: pd.DataFrame) -> int:
    if "play_count" in df.columns:
        return int(pd.to_numeric(df["play_count"], errors="coerce").fillna(0).sum())
    return int(len(df))
