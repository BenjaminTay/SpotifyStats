"""Weekly ranking computation and running metrics."""

import pandas as pd

from backend.domains.billboard.album_display import choose_representative_album
from backend.domains.billboard.data_loader import _load_album_metadata
from backend.domains.billboard.version_merge import _apply_album_release_groups


def compute_weekly_rankings(_df, top_n, pre_agg=None, merge_level: int = 2):
    """Aggregate per-week rankings with tiebreaker (play_count > total_ms).

    If pre_agg DataFrame is provided (from agg_weekly_tracks), skips the
    expensive groupby step and directly ranks the pre-aggregated data.

    Track version groups are applied at merge_level >= 2 to merge remasters
    and alternate versions before ranking.
    """
    if pre_agg is not None and not pre_agg.empty:
        weekly = pre_agg.copy()
        _apply_track_groups(weekly, merge_level=merge_level)
        group_cols = ["billboard_week", "track_id", "track_name", "artist_name"]
        album_choice = choose_representative_album(weekly, group_cols)
        # After canonicalization, re-aggregate: sum play_count/total_ms per group.
        weekly = (
            weekly.groupby(group_cols)
            .agg(
                play_count=("play_count", "sum"),
                total_ms=("total_ms", "sum"),
            )
            .reset_index()
        )
        weekly = weekly.merge(album_choice, on=group_cols, how="left")
    else:
        df = _df.copy()
        _apply_track_groups(df, merge_level=merge_level)
        group_cols = ["billboard_week", "track_id", "track_name", "artist_name"]
        album_choice = choose_representative_album(df, group_cols)
        weekly = (
            df.groupby(group_cols)
            .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
            .reset_index()
        )
        weekly = weekly.merge(album_choice, on=group_cols, how="left")

    # Tiebreaker: sort by play_count DESC, then total_ms DESC
    weekly = weekly.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    weekly["rank"] = weekly.groupby("billboard_week").cumcount() + 1
    weekly = weekly[weekly["rank"] <= top_n]

    return weekly


def _apply_track_groups(df: pd.DataFrame, merge_level: int = 2) -> None:
    """Apply track version group canonicalization in-place on df.

    Maps track_id → canonical track_id/name for rows in a track group.
    Also canonicalizes album_name to the primary track's album so that
    downstream groupby (without album_name) still produces consistent results.
    """
    if merge_level <= 1 or df.empty:
        return

    from backend.core.db import get_db
    from backend.domains.playback.track_groups import load_track_group_keys

    conn = get_db()
    try:
        keys = load_track_group_keys(conn, merge_level=merge_level)
        if keys.empty:
            return
        keys = keys.copy()
        keys["_scope_rank"] = keys["track_group_scope"].map(
            {"composition": 0, "recording": 1} if merge_level >= 3 else {"recording": 0}
        )
        keys = keys.sort_values(["track_id", "_scope_rank", "track_agg_id"]).drop_duplicates(
            "track_id"
        )
        key_map = keys.set_index("track_id")
        df["_track_agg_id"] = df["track_id"].map(key_map["track_agg_id"])
        df["_track_agg_name"] = df["track_id"].map(key_map["track_agg_name"])
        mask = df["_track_agg_id"].notna()
        df["track_id"] = df["track_id"].astype("int64", copy=False)
        df.loc[mask, "track_id"] = df.loc[mask, "_track_agg_id"].astype(int)
        df.loc[mask, "track_name"] = df.loc[mask, "_track_agg_name"]

        # Canonicalize album_name to primary track's album for merged rows.
        # This prevents cross-album splits in downstream groupby aggregations.
        if "album_name" in df.columns:
            _canonicalize_album_name(df, mask, conn)

        df.drop(columns=["_track_agg_id", "_track_agg_name"], inplace=True)
    finally:
        conn.close()


def _canonicalize_album_name(df, mask, conn):
    """For rows mapped to a track group, set album_name to the
    primary track's album so all versions share the same album.
    """
    group_ids = df.loc[mask, "_track_agg_id"].dropna().astype(int).unique()
    if len(group_ids) == 0:
        return

    placeholders = ",".join("?" for _ in group_ids)
    rows = conn.execute(
        f"""SELECT tg.group_id, a.album_name
            FROM track_groups tg
            JOIN tracks t ON tg.primary_track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE tg.group_id IN ({placeholders})""",
        tuple(int(g) for g in group_ids),
    ).fetchall()

    album_map = {row[0]: row[1] for row in rows}
    # _track_agg_id is the group_id; map to canonical album_name
    df.loc[mask, "album_name"] = (
        df.loc[mask, "_track_agg_id"].map(album_map).fillna(df.loc[mask, "album_name"])
    )


def compute_album_weekly_rankings(
    _df, top_n, pre_agg=None, merge_level: int = 2, include_compilations: bool = False
):
    """Aggregate per-week album project rankings from all valid plays."""
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import compute_album_project_weekly_plays

    if pre_agg is not None and not pre_agg.empty and "track_id" in pre_agg.columns:
        df = pre_agg.copy()
    elif pre_agg is not None and not pre_agg.empty:
        return _legacy_album_weekly_rankings_from_album_preagg(
            pre_agg,
            top_n=top_n,
            merge_level=merge_level,
            include_compilations=include_compilations,
        )
    else:
        df = _df.copy()

    if df.empty:
        return pd.DataFrame()
    if "billboard_week" not in df.columns:
        df["billboard_week"] = df["ts_date"] if "ts_date" in df.columns else df["ts"]

    # L2/L3 album project membership may be bootstrapped lazily on cold DBs.
    conn = get_db(readonly=merge_level <= 1)
    try:
        ranked = compute_album_project_weekly_plays(
            df,
            conn,
            merge_level=merge_level,
            include_compilations=include_compilations,
            billboard_mode=True,
        )
    finally:
        conn.close()

    if ranked.empty:
        return pd.DataFrame()

    weekly_album = ranked.rename(
        columns={
            "album_project_name": "album_name",
            "unique_canonical_songs": "tracks_count",
        }
    )
    weekly_album = weekly_album.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    weekly_album["rank"] = weekly_album.groupby("billboard_week").cumcount() + 1
    return weekly_album[weekly_album["rank"] <= top_n]


def _legacy_album_weekly_rankings_from_album_preagg(
    pre_agg: pd.DataFrame,
    top_n: int,
    merge_level: int,
    include_compilations: bool,
) -> pd.DataFrame:
    """Compatibility path for old agg_weekly_albums until track-source preagg is built."""
    weekly_album = pre_agg.copy()
    weekly_album["tracks_count"] = 0
    weekly_album = _apply_album_release_groups(weekly_album, merge_level=merge_level)
    weekly_album = weekly_album.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    album_meta = _load_album_metadata()
    weekly_album = weekly_album.merge(
        album_meta["type"], on=["album_name", "artist_name"], how="left"
    )
    from backend.domains.playback.album_type import classify_album

    weekly_album["_category"] = weekly_album.apply(
        lambda r: classify_album(
            r["album_type"] if pd.notna(r["album_type"]) else None,
            total_tracks=int(r["total_tracks"]) if pd.notna(r.get("total_tracks")) else None,
        ),
        axis=1,
    )
    weekly_album = weekly_album[weekly_album["_category"] != "single"]
    if not include_compilations:
        weekly_album = weekly_album[weekly_album["_category"] != "compilation"]
    weekly_album = weekly_album.drop(columns=["_category"])
    weekly_album["rank"] = weekly_album.groupby("billboard_week").cumcount() + 1
    return weekly_album[weekly_album["rank"] <= top_n]


def _expand_track_source_preagg(pre_agg: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in pre_agg.itertuples(index=False):
        play_count = int(getattr(r, "play_count"))
        total_ms = int(getattr(r, "total_ms"))
        per_play_ms = total_ms // play_count if play_count else 0
        for _ in range(play_count):
            rows.append(
                {
                    "billboard_week": getattr(r, "billboard_week"),
                    "track_id": getattr(r, "track_id"),
                    "track_name": getattr(r, "track_name", ""),
                    "artist_name": getattr(r, "artist_name", ""),
                    "album_name": getattr(r, "album_name", ""),
                    "source_album_id": getattr(r, "source_album_id", None),
                    "ms_played": per_play_ms,
                    "ts": getattr(r, "ts", getattr(r, "play_date", None)),
                    "ts_date": getattr(r, "play_date", getattr(r, "ts", None)),
                }
            )
    return pd.DataFrame(rows)


def compute_artist_weekly_rankings(_df, top_n, pre_agg=None):
    """Aggregate per-week artist rankings from ALL plays (not just charting tracks).

    If pre_agg DataFrame is provided (from agg_weekly_artists), skips the
    expensive groupby step.
    """
    if pre_agg is not None and not pre_agg.empty:
        weekly_artist = pre_agg.copy()
        # pre_agg already has: billboard_week, artist_id, artist_name,
        # play_count, total_ms
        weekly_artist["tracks_count"] = 0
    else:
        df = _df.copy()
        df = df.dropna(subset=["artist_name"])
        weekly_artist = (
            df.groupby(["billboard_week", "artist_name"])
            .agg(
                play_count=("ms_played", "count"),
                total_ms=("ms_played", "sum"),
                tracks_count=("track_id", "nunique"),
            )
            .reset_index()
        )

    weekly_artist = weekly_artist.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    weekly_artist["rank"] = weekly_artist.groupby("billboard_week").cumcount() + 1
    weekly_artist = weekly_artist[weekly_artist["rank"] <= top_n]
    return weekly_artist


def _add_running_metrics(df, group_cols):
    """Add running rank/peak/weeks columns for each group in weekly data."""
    cols = list(group_cols)
    if df.empty:
        return df.copy()

    df = df.sort_values(cols + ["billboard_week"]).reset_index(drop=True)

    groups = df.groupby(cols, sort=False)
    df["running_peak"] = groups["rank"].cummin()
    df["running_wks"] = groups.cumcount() + 1

    # running_peak_wks: cumulative count of weeks at the running peak (cummin).
    # Accumulates across non-consecutive returns to the same peak level;
    # resets only when a new (better) peak is achieved.
    # Non-peak weeks carry the last accumulated count forward so the counter
    # is always visible.  This is a real-time metric — it doesn't know
    # about future peaks.
    results = []
    for _, g in df.groupby(cols, sort=False):
        at_run = g["rank"] == g["running_peak"]
        rp_id = g["running_peak"].ne(g["running_peak"].shift()).cumsum()
        result = pd.Series(pd.NA, index=g.index, dtype="Int64")
        mask = at_run.values
        if mask.any():
            result.loc[mask] = (
                g.loc[mask].groupby(rp_id.loc[mask], sort=False).cumcount() + 1
            ).astype("Int64")
        # Forward-fill accumulated count across non-peak weeks within each rp_id
        result = result.groupby(rp_id, sort=False).ffill().fillna(0).astype(int)
        results.append(result)
    df["running_peak_wks"] = pd.concat(results).astype(int)
    return df
