"""Community feed — Data loading for community feed generation."""

import pandas as pd

from backend.domains.billboard.chart_ranking import (
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
)
from backend.domains.billboard.data_loader import (
    _try_load_from_agg,
    load_billboard_raw,
)

# ──────────────────────────────────────────────


def _load_chart_data(
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    merge_level=2,
    include_compilations=False,
    merge_enabled=True,
):
    """Load raw data and compute all three weekly rankings. Returns a 5-tuple."""
    df_raw = _load_compact_raw(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_enabled=merge_enabled,
    )
    from backend.domains.billboard.week_coverage import (
        current_open_billboard_week,
        keep_complete_billboard_weeks,
    )

    df_raw = keep_complete_billboard_weeks(
        df_raw,
        open_week=current_open_billboard_week(
            week_start_dow=bb_week_start_dow, week_start_hour=bb_week_start_hour
        ),
    )
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        df_raw = df_raw[df_raw["_year"] >= year_start]
    if year_end is not None:
        df_raw = df_raw[df_raw["_year"] <= year_end]

    all_weeks = sorted(df_raw["billboard_week"].unique().tolist())

    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_enabled=merge_enabled,
    )
    if _agg_tracks is not None:
        _agg_tracks = _agg_tracks[
            pd.to_datetime(_agg_tracks["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_albums = _agg_albums[
            pd.to_datetime(_agg_albums["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_artists = _agg_artists[
            pd.to_datetime(_agg_artists["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]

    weekly = compute_weekly_rankings(df_raw, bb_top_n, pre_agg=_agg_tracks, merge_level=merge_level)
    weekly_album = compute_album_weekly_rankings(
        df_raw,
        bb_album_top_n,
        pre_agg=_agg_albums,
        merge_level=merge_level,
        include_compilations=include_compilations,
    )
    if _agg_artists is not None:
        weekly_artist = compute_artist_weekly_rankings(
            df_raw, bb_artist_top_n, pre_agg=_agg_artists
        )
    else:
        df_artists = _artist_frame_from_raw(df_raw)
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

    # No raw frames survive a maintenance invocation via the old loader LRU.
    for frame in (weekly, weekly_album, weekly_artist):
        frame.attrs = {}
    df_raw.attrs = {}
    return df_raw, weekly, weekly_album, weekly_artist, all_weeks


def _compute_personal_weekly(df_raw) -> dict:
    """Compute per-week personal playback stats from raw plays data.

    Returns dict: {week_val: {plays, ms, track_ids: set, artist_names: set,
                               top_artist, top_artist_plays}}
    """
    personal = {}
    for week_val, grp in df_raw.groupby("billboard_week"):
        artist_counts = grp.groupby("artist_name").size()
        top_artist = artist_counts.idxmax() if len(artist_counts) > 0 else ""
        top_artist_plays = int(artist_counts.max()) if len(artist_counts) > 0 else 0

        personal[week_val] = {
            "plays": len(grp),
            "ms": int(grp["ms_played"].sum()),
            "track_ids": set(grp["track_id"].unique()),
            "artist_names": set(grp["artist_name"].unique()),
            "top_artist": top_artist,
            "top_artist_plays": top_artist_plays,
        }
    return personal


def _load_collection_data(conn) -> dict:
    """Load saved tracks data for collection-related posts."""
    try:
        rows = conn.execute(
            "SELECT track_name, artist_name, added_date FROM saved_tracks ORDER BY added_date"
        ).fetchall()
        saved = [{"track_name": r[0], "artist_name": r[1], "added_date": r[2]} for r in rows]

        total_saved = len(saved)
        first_save = saved[0] if saved else None

        # Count forgotten tracks: saved but never played (check against plays table)
        forgotten_rows = conn.execute("""
            SELECT st.track_name, st.artist_name, st.added_date
            FROM saved_tracks st
            WHERE st.track_name NOT IN (
                SELECT DISTINCT p.track_name FROM plays p WHERE p.track_name IS NOT NULL
            )
            ORDER BY st.added_date
        """).fetchall()
        forgotten = [
            {"track_name": r[0], "artist_name": r[1], "added_date": r[2]} for r in forgotten_rows
        ]

        return {
            "total_saved": total_saved,
            "first_save": first_save,
            "forgotten": forgotten,
            "forgotten_count": len(forgotten),
        }
    except Exception:
        return {"total_saved": 0, "first_save": None, "forgotten": [], "forgotten_count": 0}


# ──────────────── post generators (per type) ────────────────


def _artist_frame_from_raw(raw):
    """Fan effective credits out from the same count/duration contribution rows.

    Each input row has a local identity; duplicate canonical credits collapse
    within that row, never across logical events or duration slices.
    """
    from backend.core.db import get_db
    from backend.domains.metadata.artist_identity import canonicalize_artist_frame
    from backend.domains.metadata.track_credits import get_effective_track_credit_frame
    from backend.domains.playback.logical_timeline import (
        attach_billboard_weighted_frame,
        get_billboard_weighted_frame,
    )

    conn = get_db(readonly=True)
    try:
        credits = get_effective_track_credit_frame(conn).rename(
            columns={"track_id": "representative_track_id"}
        )

        def fan(frame):
            # Avoid copying interval objects and nested attrs into every credited row.
            columns = [
                c
                for c in frame.columns
                if c
                not in {
                    "artist_name",
                    "artist_id",
                    "raw_artist_id",
                    "raw_artist_name",
                    "_logical_event_id",
                    "_artist_event_id",
                    "_listening_intervals_ns",
                }
            ]
            source = frame.loc[:, columns].copy()
            source.attrs = {}
            source["_logical_event_id"] = range(len(source))
            result = source.merge(
                credits[["representative_track_id", "raw_artist_id", "artist_name"]],
                on="representative_track_id",
                how="inner",
            )
            result["artist_id"] = result.pop("raw_artist_id")
            return canonicalize_artist_frame(result, conn)

        result = fan(raw)
        weighted = get_billboard_weighted_frame(raw)
        if weighted is not None:
            attach_billboard_weighted_frame(result, fan(weighted))
        return result
    finally:
        conn.close()


def _load_compact_raw(*args, **kwargs):
    from backend.domains.billboard.build_context import BillboardBuildContext
    from backend.services.billboard_snapshot_service import configured_billboard_filters

    # Reuse the existing owned-frame projection; it preserves independent
    # duration weights and releases reconstruction objects before ranking.
    with BillboardBuildContext(configured_billboard_filters()) as invocation:
        return invocation.load_raw(load_billboard_raw, *args, **kwargs)
