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
    load_billboard_raw_for_artists,
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
):
    """Load raw data and compute all three weekly rankings. Returns a 5-tuple."""
    df_raw = load_billboard_raw(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
    df_raw = df_raw.copy()
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        df_raw = df_raw[df_raw["_year"] >= year_start]
    if year_end is not None:
        df_raw = df_raw[df_raw["_year"] <= year_end]

    all_weeks = sorted(df_raw["billboard_week"].unique().tolist())

    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms, music_only, bb_week_start_dow, bb_week_start_hour
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
        df_artists = load_billboard_raw_for_artists(
            min_ms,
            music_only,
            bb_week_start_dow,
            bb_week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

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
