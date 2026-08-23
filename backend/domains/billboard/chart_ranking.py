"""Weekly ranking computation and running metrics."""

import unicodedata

import pandas as pd

from backend.domains.billboard.album_display import choose_representative_album
from backend.domains.billboard.data_loader import _load_album_metadata
from backend.domains.billboard.version_merge import _apply_album_release_groups
from backend.domains.playback.logical_timeline import get_billboard_weighted_frame

BILLBOARD_RANKING_VERSION = "billboard_ranking_v2"


def _normalised_text_key(value: object) -> str:
    if pd.isna(value):
        return ""
    return unicodedata.normalize("NFKC", str(value)).casefold()


def _stable_weekly_sort(
    frame: pd.DataFrame,
    *,
    id_columns: tuple[str, ...],
    text_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Sort weekly candidates with an explicit, input-order-independent tie key."""
    result = frame.copy()
    sort_columns = ["billboard_week", "play_count", "total_ms"]
    ascending = [True, False, False]
    stable_columns = [column for column in id_columns if column in result.columns]
    sort_columns.extend(stable_columns)
    ascending.extend([True] * len(stable_columns))
    # Text keys remain a deterministic fallback for rows whose stable ID is
    # absent, and a harmless final discriminator when an ID is present.
    temporary_columns: list[str] = []
    for index, column in enumerate(text_columns):
        if column not in result.columns:
            continue
        normalised_key = f"_stable_text_key_{index}"
        original_key = f"_stable_text_original_{index}"
        result[normalised_key] = result[column].map(_normalised_text_key)
        result[original_key] = result[column].fillna("").astype(str)
        temporary_columns.extend((normalised_key, original_key))
    sort_columns.extend(temporary_columns)
    ascending.extend([True] * len(temporary_columns))
    result = result.sort_values(sort_columns, ascending=ascending, kind="stable")
    return result.drop(columns=[column for column in result if column.startswith("_stable_text_")])


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
        weighted = get_billboard_weighted_frame(_df)
        df = weighted.copy() if weighted is not None else _df.copy()
        _apply_track_groups(df, merge_level=merge_level)
        group_cols = ["billboard_week", "track_id", "track_name", "artist_name"]
        album_choice = choose_representative_album(df, group_cols)
        if {"play_count", "total_ms"} <= set(df.columns):
            weekly = (
                df.groupby(group_cols)
                .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
                .reset_index()
            )
        else:
            weekly = (
                df.groupby(group_cols)
                .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
                .reset_index()
            )
        weekly = weekly.merge(album_choice, on=group_cols, how="left")

    weekly = weekly[weekly["play_count"] > 0]
    # Tiebreaker: sort by play_count DESC, then total_ms DESC
    weekly = _stable_weekly_sort(
        weekly,
        id_columns=("track_id",),
        text_columns=("artist_name", "track_name"),
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
    primary_ids = df.loc[mask, "_track_agg_id"].dropna().astype(int).unique()
    if len(primary_ids) == 0:
        return

    placeholders = ",".join("?" for _ in primary_ids)
    rows = conn.execute(
        f"""SELECT tg.primary_track_id, a.album_name
            FROM track_groups tg
            JOIN tracks t ON tg.primary_track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE tg.primary_track_id IN ({placeholders})""",
        tuple(int(g) for g in primary_ids),
    ).fetchall()

    album_map = {row[0]: row[1] for row in rows}
    # _track_agg_id is the primary_track_id; map to canonical album_name
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
        weighted = get_billboard_weighted_frame(_df)
        df = weighted.copy() if weighted is not None else _df.copy()

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
    ranked = ranked[ranked["play_count"] > 0]
    if ranked.empty:
        return pd.DataFrame()

    weekly_album = ranked.rename(
        columns={
            "album_project_name": "album_name",
            "unique_canonical_songs": "tracks_count",
        }
    )
    weekly_album = _stable_weekly_sort(
        weekly_album,
        id_columns=("album_project_id", "album_id"),
        text_columns=("artist_name", "album_name"),
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
    weekly_album = _stable_weekly_sort(
        weekly_album,
        id_columns=("album_project_id", "album_id"),
        text_columns=("artist_name", "album_name"),
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
        weighted = get_billboard_weighted_frame(_df)
        df = weighted.copy() if weighted is not None else _df.copy()
        df = df.dropna(subset=["artist_name"])
        if {"play_count", "total_ms"} <= set(df.columns):
            weekly_artist = (
                df.groupby(["billboard_week", "artist_name"])
                .agg(
                    play_count=("play_count", "sum"),
                    total_ms=("total_ms", "sum"),
                    tracks_count=("track_id", "nunique"),
                )
                .reset_index()
            )
        else:
            weekly_artist = (
                df.groupby(["billboard_week", "artist_name"])
                .agg(
                    play_count=("ms_played", "count"),
                    total_ms=("ms_played", "sum"),
                    tracks_count=("track_id", "nunique"),
                )
                .reset_index()
            )

    weekly_artist = weekly_artist[weekly_artist["play_count"] > 0]
    weekly_artist = _stable_weekly_sort(
        weekly_artist,
        id_columns=("artist_id",),
        text_columns=("artist_name",),
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
