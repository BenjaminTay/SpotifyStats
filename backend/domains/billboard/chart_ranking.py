"""Weekly ranking computation and running metrics."""

import pandas as pd

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
        # After canonicalization, re-aggregate: sum play_count/total_ms per group.
        # album_name is kept as the first (alphabetical) representative.
        weekly = (
            weekly.groupby(
                ["billboard_week", "track_id", "track_name", "artist_name", "album_name"]
            )
            .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
            .reset_index()
        )
    else:
        df = _df.copy()
        _apply_track_groups(df, merge_level=merge_level)
        weekly = (
            df.groupby(["billboard_week", "track_id", "track_name", "artist_name", "album_name"])
            .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
            .reset_index()
        )

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
        key_map = keys.set_index("track_id")
        df["_track_agg_id"] = df["track_id"].map(key_map["track_agg_id"])
        df["_track_agg_name"] = df["track_id"].map(key_map["track_agg_name"])
        mask = df["_track_agg_id"].notna()
        df.loc[mask, "track_id"] = df.loc[mask, "_track_agg_id"].astype(int)
        df.loc[mask, "track_name"] = df.loc[mask, "_track_agg_name"]
        df.drop(columns=["_track_agg_id", "_track_agg_name"], inplace=True)
    finally:
        conn.close()


def compute_album_weekly_rankings(_df, top_n, pre_agg=None, merge_level: int = 2):
    """Aggregate per-week album rankings from ALL plays (not just charting tracks).

    If pre_agg DataFrame is provided (from agg_weekly_albums), skips the
    expensive groupby step.

    Release groups are applied to merge different album versions (deluxe,
    acoustic, etc.) into canonical names before ranking.
    merge_level=1: no merge, 2: scope='release' (default), 3: scope='composition'.
    """
    if pre_agg is not None and not pre_agg.empty:
        weekly_album = pre_agg.copy()
        # pre_agg already has: billboard_week, album_id, album_name,
        # artist_name, play_count, total_ms
        # Estimate tracks_count from the album-tracks relationship
        weekly_album["tracks_count"] = 0
    else:
        df = _df.copy()
        df = df.dropna(subset=["album_name"])
        weekly_album = (
            df.groupby(["billboard_week", "album_name", "artist_name"])
            .agg(
                play_count=("ms_played", "count"),
                total_ms=("ms_played", "sum"),
                tracks_count=("track_id", "nunique"),
            )
            .reset_index()
        )

    # 应用发行版本合并：将组内成员的 album_name 替换为 canonical_name 并重新聚合
    weekly_album = _apply_album_release_groups(weekly_album, merge_level=merge_level)

    weekly_album = weekly_album.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    # 排除 single 类型 + 排除专辑发行前的周数
    album_meta = _load_album_metadata()
    weekly_album = weekly_album.merge(
        album_meta["type"], on=["album_name", "artist_name"], how="left"
    )
    weekly_album = weekly_album[weekly_album["album_type"] != "single"]
    weekly_album = weekly_album.merge(
        album_meta["release_date"], on=["album_name", "artist_name"], how="left"
    )
    if not weekly_album.empty:
        weekly_album["_bb_week"] = pd.to_datetime(weekly_album["billboard_week"])
        weekly_album["_rel_date"] = pd.to_datetime(weekly_album["release_date"], errors="coerce")
        weekly_album = weekly_album[
            weekly_album["_rel_date"].isna()
            | (weekly_album["_bb_week"] + pd.Timedelta(days=6) >= weekly_album["_rel_date"])
        ].drop(columns=["_bb_week", "_rel_date"])

    weekly_album["rank"] = weekly_album.groupby("billboard_week").cumcount() + 1
    weekly_album = weekly_album[weekly_album["rank"] <= top_n]
    return weekly_album


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
    df = df.sort_values(cols + ["billboard_week"]).reset_index(drop=True)

    running = []
    for _, grp in df.groupby(cols):
        grp = grp.copy()
        grp["running_peak"] = grp["rank"].cummin()
        grp["running_wks"] = range(1, len(grp) + 1)
        pk_idx = grp["rank"].idxmin()
        pk_wk = pd.to_datetime(grp.loc[pk_idx, "billboard_week"])
        grp["running_peak_wks"] = (pd.to_datetime(grp["billboard_week"]) - pk_wk).dt.days // 7 + 1
        running.append(grp)
    return pd.concat(running, ignore_index=True)
