"""Billboard computation service — extracted from app/pages/billboard/shared.py."""

import html as _html
from urllib.parse import quote as _url_quote
import numpy as np
import pandas as pd
from functools import lru_cache

from backend.core.db import get_db, base_filters, merge_consecutive_plays
from backend.core.json_helpers import py_val as _py_val, df_to_json as _df_to_json

# Weekday labels
DOW_NAMES = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
DOW_SHORT = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


# ═══════════════════════════════════════════════════════════════════════════
# HTML Table Renderer (Vinyl Archive styled, with clickable <a> links)
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════
# Data loading (cached)
# ═══════════════════════════════════════════════════════════════════════

def _try_load_from_agg(min_ms, music_only, week_start_dow, week_start_hour):
    """Try to load pre-aggregated weekly data from agg tables.

    Returns (tracks_df, albums_df, artists_df) if valid agg data exists,
    or (None, None, None) if parameters don't match or tables are empty.
    Each DataFrame is pre-grouped (play_count + total_ms) but NOT ranked.
    """
    from backend.core.db import _agg_param_hash, check_agg_valid, \
        load_agg_weekly_tracks, load_agg_weekly_albums, load_agg_weekly_artists

    param_hash = _agg_param_hash(min_ms, music_only, week_start_dow, week_start_hour)
    conn = get_db()
    if not check_agg_valid(conn, param_hash):
        conn.close()
        return None, None, None

    try:
        tracks = load_agg_weekly_tracks(conn)
        albums = load_agg_weekly_albums(conn)
        artists = load_agg_weekly_artists(conn)
        conn.close()
        if len(tracks) == 0:
            return None, None, None
        return tracks, albums, artists
    except Exception:
        conn.close()
        return None, None, None


@lru_cache(maxsize=1)
def load_billboard_raw(min_ms, music_only, week_start_dow, week_start_hour):
    """Load filtered plays and compute billboard_week with configurable boundary."""
    conn = get_db()
    _f, _fp = base_filters(
        min_ms=min_ms, music_only=music_only
    )
    _w = f"WHERE {_f}" if _f else ""
    df = pd.read_sql_query(
        f"""SELECT p.ts, p.ts_date, p.ts_dow, p.ts_hour, p.ms_played, p.track_id,
                   t.track_name, a.artist_name, al.album_name, stm.duration_ms
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            LEFT JOIN spotify_track_meta stm
              ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
            {_w}
            ORDER BY p.ts""",
        conn,
        params=_fp,
    )
    conn.close()

    # Billboard week: configurable boundary
    df["days_back"] = (df["ts_dow"] - week_start_dow) % 7
    mask_before = (df["ts_dow"] == week_start_dow) & (df["ts_hour"] < week_start_hour)
    df.loc[mask_before, "days_back"] = 7
    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (
        df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")
    ).dt.date

    # Merge consecutive same-track plays into logical play counts
    df = merge_consecutive_plays(df, min_ms)

    return df


@lru_cache(maxsize=1)
def load_track_album_map():
    """Get all album names for each track_id (including track_albums junction)."""
    conn = get_db()
    rows = conn.execute(
        """SELECT t.track_id, al.album_name
           FROM tracks t
           JOIN albums al ON t.album_id = al.album_id
           UNION
           SELECT ta.track_id, al.album_name
           FROM track_albums ta
           JOIN albums al ON ta.album_id = al.album_id"""
    ).fetchall()
    conn.close()

    data = {}
    for tid, album in rows:
        data.setdefault(tid, []).append(album)

    # Build DataFrame: track_id → list of album names
    records = []
    for tid, albums in data.items():
        records.append({"track_id": tid, "album_list": sorted(set(albums))})
    return pd.DataFrame(records)


@lru_cache(maxsize=1)
def _load_album_metadata():
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT DISTINCT al.album_name, a.artist_name, sam.album_type, sam.release_date
           FROM track_albums ta
           JOIN albums al ON ta.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           JOIN tracks t ON ta.track_id = t.track_id
           JOIN spotify_track_meta stm
             ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
           JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id""",
        conn,
    )

    base = df[["album_name", "artist_name", "album_type"]].copy()
    priority = {"album": 0, "compilation": 1, "single": 2}
    base["_pri"] = base["album_type"].map(priority)
    type_df = base.sort_values("_pri").drop_duplicates(
        subset=["album_name", "artist_name"], keep="first"
    ).drop(columns=["_pri"])

    date_df = df.dropna(subset=["release_date"])
    date_df = date_df.groupby(["album_name", "artist_name"], as_index=False)["release_date"].min()

    # 补充 release group canonical name 的元数据行
    _add_canonical_metadata(type_df, date_df, conn)

    conn.close()
    return {"type": type_df, "release_date": date_df}


def _add_canonical_metadata(type_df, date_df, conn):
    """为 release group 的 canonical_name 补充 album_type 和 release_date 行。

    将 canonical_name 映射到 primary_album 的 album_name，然后从现有 metadata
    中复制对应行。这样 release_date 过滤和 album_type 过滤能正确作用于合并后的名称。
    """
    mapping = pd.read_sql_query(
        """SELECT al.album_name, a.artist_name, rg.canonical_name,
                  rg.primary_album_id, pa.album_name AS primary_album_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id""",
        conn,
    )
    if mapping.empty:
        return

    # album_type: 从 primary_album 的 metadata 复制
    primary_types = type_df.merge(
        mapping[["primary_album_name", "artist_name", "canonical_name"]].drop_duplicates(),
        left_on=["album_name", "artist_name"],
        right_on=["primary_album_name", "artist_name"],
        how="inner",
    )[["canonical_name", "artist_name", "album_type"]].rename(
        columns={"canonical_name": "album_name"}
    )
    if not primary_types.empty:
        existing = set(zip(type_df["album_name"], type_df["artist_name"]))
        for _, row in primary_types.iterrows():
            key = (row["album_name"], row["artist_name"])
            if key not in existing:
                type_df.loc[len(type_df)] = row

    # release_date: 取 primary_album 的最早发行日期
    primary_dates = date_df.merge(
        mapping[["primary_album_name", "artist_name", "canonical_name"]].drop_duplicates(),
        left_on=["album_name", "artist_name"],
        right_on=["primary_album_name", "artist_name"],
        how="inner",
    ).groupby(["canonical_name", "artist_name"], as_index=False)["release_date"].min().rename(
        columns={"canonical_name": "album_name"}
    )
    if not primary_dates.empty:
        existing = set(zip(date_df["album_name"], date_df["artist_name"]))
        for _, row in primary_dates.iterrows():
            key = (row["album_name"], row["artist_name"])
            if key not in existing:
                date_df.loc[len(date_df)] = row


def _get_album_canonical_map():
    """获取所有 release group 成员的 (album_name, artist_name) → canonical_name 映射。"""
    conn = get_db()
    mapping = pd.read_sql_query(
        """SELECT al.album_name, a.artist_name, rg.canonical_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id""",
        conn,
    )
    conn.close()
    return mapping


def _normalize_album_column(df, album_col="album_name", artist_col="artist_name",
                            dedup_cols=None):
    """将 DataFrame 中的 album_name 替换为 canonical_name，可选去重。

    dedup_cols: 替换后按这些列去重（如 ["track_id", "album_name", "artist_name"]）。
    """
    mapping = _get_album_canonical_map()
    if mapping.empty:
        return df

    # 去重（同一 album 不应属于多个 group，但防御）
    mapping = mapping.drop_duplicates(subset=["album_name", "artist_name"])

    # 重命名右表列避免合并时后缀冲突
    mapping = mapping.rename(columns={
        "album_name": "_rg_album",
        "artist_name": "_rg_artist",
    })
    df = df.merge(mapping, left_on=[album_col, artist_col],
                  right_on=["_rg_album", "_rg_artist"], how="left")
    mask = df["canonical_name"].notna()
    df.loc[mask, album_col] = df.loc[mask, "canonical_name"]
    df = df.drop(columns=["canonical_name", "_rg_album", "_rg_artist"], errors="ignore")
    if dedup_cols:
        df = df.drop_duplicates(subset=dedup_cols)
    return df


def _resolve_album_members(album_name, artist_name):
    """返回 release group 所有成员的 album_name 列表（含自身）。

    如果 album_name 不在任何 group 中，返回 [album_name]。
    同时返回 canonical_name。
    """
    conn = get_db()
    row = conn.execute(
        """SELECT rg.canonical_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE al.album_name = ? AND a.artist_name = ?
           LIMIT 1""",
        [album_name, artist_name],
    ).fetchone()

    if not row:
        conn.close()
        return [album_name], album_name

    canonical = row[0]
    members = conn.execute(
        """SELECT al.album_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE rg.canonical_name = ? AND a.artist_name = ?""",
        [canonical, artist_name],
    ).fetchall()
    conn.close()
    return [m[0] for m in members], canonical


def _apply_album_release_groups(df):
    """将 release_group 成员的 album_name 替换为 canonical_name 并重新聚合。

    多版本专辑（豪华版、Acoustic版等）的周播放量被合并到 canonical name 下，
    使榜单排名反映合并后的成绩。
    """
    mapping = _get_album_canonical_map()
    if mapping.empty:
        return df

    df = df.merge(mapping, on=["album_name", "artist_name"], how="left")
    mask = df["canonical_name"].notna()
    df.loc[mask, "album_name"] = df.loc[mask, "canonical_name"]
    df = df.drop(columns=["canonical_name"])

    agg_cols = {"play_count": "sum", "total_ms": "sum", "tracks_count": "sum"}
    if "album_id" in df.columns:
        agg_cols["album_id"] = "min"

    df = df.groupby(
        ["billboard_week", "album_name", "artist_name"], as_index=False
    ).agg(agg_cols)

    return df


def compute_weekly_rankings(_df, top_n, pre_agg=None):
    """Aggregate per-week rankings with tiebreaker (play_count > total_ms).

    If pre_agg DataFrame is provided (from agg_weekly_tracks), skips the
    expensive groupby step and directly ranks the pre-aggregated data.
    """
    if pre_agg is not None and not pre_agg.empty:
        weekly = pre_agg.copy()
        # pre_agg already has: billboard_week, track_id, track_name,
        # artist_name, album_name, play_count, total_ms
    else:
        df = _df.copy()
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


def compute_album_weekly_rankings(_df, top_n, pre_agg=None):
    """Aggregate per-week album rankings from ALL plays (not just charting tracks).

    If pre_agg DataFrame is provided (from agg_weekly_albums), skips the
    expensive groupby step.

    Release groups are applied to merge different album versions (deluxe,
    acoustic, etc.) into canonical names before ranking.
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
    weekly_album = _apply_album_release_groups(weekly_album)

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


def compute_power_scores(weekly, N):
    """Compute Power Score for each track — composite ranking metric.

    Power Score = Σ(weekly_base_points × play_intensity_weight)
                  + peak_bonus + top5_bonus + top10_bonus

    Base points are normalized to rank/N so scores are comparable
    regardless of chart size N.
    """
    tier1_count = int(N * 0.1)
    tier2_count = int(N * 0.2)

    # Week median plays (competition baseline)
    week_medians = weekly.groupby("billboard_week")["play_count"].median().to_dict()

    scores = []
    for (track_id, track_name, artist_name), group in weekly.groupby(
        ["track_id", "track_name", "artist_name"]
    ):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top5 = int((group["rank"] <= 5).sum())
        weeks_top10 = int((group["rank"] <= 10).sum())
        weeks_at_no1 = int((group["rank"] == 1).sum())

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)

            # 1. Base points (normalized by rank/N)
            r_norm = rank / N if N > 0 else 0
            if rank == 1:
                base = 200
            elif r_norm <= 0.1:
                base = int(200 * (0.75 - 2.5 * r_norm))
            elif r_norm <= 0.2:
                rank_in_tier = rank - tier1_count
                base = max(1, int(85 * (0.85 ** rank_in_tier)))
            else:
                start_val = int(85 * 0.85 ** (tier2_count - tier1_count))
                base = max(1, int(start_val * (1 - (r_norm - 0.2) / 0.8)))

            # 2. Play intensity weight: log₂ ratio to week median
            if median > 0 and plays > 0:
                weight = 1 + min(3.0, max(0.0, np.log2(plays / median)))
            else:
                weight = 1.0

            total += base * weight

        # 3. Bonuses
        peak_bonus = {1: 100, 2: 50, 3: 30}.get(peak, 0)
        top5_bonus = weeks_top5 * 20
        top10_bonus = weeks_top10 * 5

        power_score = round(total + peak_bonus + top5_bonus + top10_bonus)

        scores.append(
            {
                "track_id": track_id,
                "track_name": track_name,
                "artist_name": artist_name,
                "power_score": power_score,
                "peak_position": peak,
                "weeks_on_chart": weeks_total,
                "weeks_top5": weeks_top5,
                "weeks_top10": weeks_top10,
                "weeks_at_no1": weeks_at_no1,
            }
        )

    return pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)


def compute_album_power_scores(weekly_album, N):
    """Compute Power Score for each album — composite ranking metric."""
    tier1_count = int(N * 0.1)
    tier2_count = int(N * 0.2)

    week_medians = weekly_album.groupby("billboard_week")["play_count"].median().to_dict()

    scores = []
    for (album_name, artist_name), group in weekly_album.groupby(["album_name", "artist_name"]):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top1 = int((group["rank"] == 1).sum())

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)

            r_norm = rank / N if N > 0 else 0
            if rank == 1:
                base = 200
            elif r_norm <= 0.1:
                base = int(200 * (0.75 - 2.5 * r_norm))
            elif r_norm <= 0.2:
                rank_in_tier = rank - tier1_count
                base = max(1, int(85 * (0.85 ** rank_in_tier)))
            else:
                start_val = int(85 * 0.85 ** (tier2_count - tier1_count))
                base = max(1, int(start_val * (1 - (r_norm - 0.2) / 0.8)))

            if median > 0 and plays > 0:
                weight = 1 + min(3.0, max(0.0, np.log2(plays / median)))
            else:
                weight = 1.0

            total += base * weight

        peak_bonus = {1: 100, 2: 50, 3: 30}.get(peak, 0)
        top1_bonus = weeks_top1 * 20

        power_score = round(total + peak_bonus + top1_bonus)

        scores.append({
            "album_name": album_name,
            "artist_name": artist_name,
            "power_score": power_score,
            "peak_position": peak,
            "weeks_on_chart": weeks_total,
            "weeks_top1": weeks_top1,
        })

    return pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)


def compute_artist_power_scores(weekly_artist, N):
    """Compute Power Score for each artist — composite ranking metric."""
    tier1_count = int(N * 0.1)
    tier2_count = int(N * 0.2)

    week_medians = weekly_artist.groupby("billboard_week")["play_count"].median().to_dict()

    scores = []
    for artist_name, group in weekly_artist.groupby("artist_name"):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top1 = int((group["rank"] == 1).sum())

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)

            r_norm = rank / N if N > 0 else 0
            if rank == 1:
                base = 200
            elif r_norm <= 0.1:
                base = int(200 * (0.75 - 2.5 * r_norm))
            elif r_norm <= 0.2:
                rank_in_tier = rank - tier1_count
                base = max(1, int(85 * (0.85 ** rank_in_tier)))
            else:
                start_val = int(85 * 0.85 ** (tier2_count - tier1_count))
                base = max(1, int(start_val * (1 - (r_norm - 0.2) / 0.8)))

            if median > 0 and plays > 0:
                weight = 1 + min(3.0, max(0.0, np.log2(plays / median)))
            else:
                weight = 1.0

            total += base * weight

        peak_bonus = {1: 100, 2: 50, 3: 30}.get(peak, 0)
        top1_bonus = weeks_top1 * 20

        power_score = round(total + peak_bonus + top1_bonus)

        scores.append({
            "artist_name": artist_name,
            "power_score": power_score,
            "peak_position": peak,
            "weeks_on_chart": weeks_total,
            "weeks_top1": weeks_top1,
        })

    return pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)


def compute_records(weekly, track_summary, top_n, weekly_album=None, weekly_artist=None):
    """Compute all-time Billboard records from weekly rankings.

    Returns a dict of record DataFrames and highlight values for the 榜单记录 tab.
    """
    records = {}

    # ── 1. Most simultaneous chart entries by artist (full chart) ──────
    artist_weekly = (
        weekly.groupby(["billboard_week", "artist_name"])
        .size()
        .reset_index(name="track_count")
    )
    if not artist_weekly.empty:
        best_full = artist_weekly.sort_values("track_count", ascending=False).iloc[0]
        records["artist_simul"] = {
            "artist": best_full["artist_name"],
            "week": best_full["billboard_week"],
            "count": int(best_full["track_count"]),
        }
        records["artist_simul_list"] = artist_weekly.sort_values(
            "track_count", ascending=False
        ).head(15)

    # ── 3. Most #1 songs by artist ─────────────────────────────────────
    no1_tracks = (
        weekly[weekly["rank"] == 1][["track_id", "artist_name"]]
        .drop_duplicates()
    )
    artist_no1 = (
        no1_tracks.groupby("artist_name")
        .size()
        .sort_values(ascending=False)
        .reset_index(name="冠单数")
    )
    records["artist_most_no1"] = artist_no1.head(15)

    # ── 4. Return to #1 ────────────────────────────────────────────────
    no1_weeks = (
        weekly[weekly["rank"] == 1][
            ["track_id", "track_name", "artist_name", "billboard_week"]
        ]
        .drop_duplicates()
        .sort_values(["track_id", "billboard_week"])
    )
    returns = []
    for tid, grp in no1_weeks.groupby("track_id"):
        if len(grp) >= 2:
            wks = grp["billboard_week"].tolist()
            for i in range(1, len(wks)):
                gap = (wks[i] - wks[i - 1]).days
                if gap > 8:  # More than one week apart → returned to #1
                    returns.append(
                        {
                            "track_id": tid,
                            "track_name": grp.iloc[i]["track_name"],
                            "artist_name": grp.iloc[i]["artist_name"],
                            "首次冠单": wks[i - 1],
                            "回冠日期": wks[i],
                            "间隔周数": gap // 7,
                        }
                    )
    records["return_to_no1"] = (
        pd.DataFrame(returns).sort_values("间隔周数", ascending=False)
        if returns
        else pd.DataFrame()
    )

    # ── 5. Debut at #1 ─────────────────────────────────────────────────
    debut = track_summary[
        (track_summary["peak_position"] == 1)
        & (track_summary["first_week"] == track_summary["first_peak_week"])
    ].copy()
    records["debut_no1"] = debut.sort_values("first_week")[
        ["track_id", "track_name", "artist_name", "first_week", "weeks_on_chart"]
    ]

    # ── 6. Longest charting songs ──────────────────────────────────────
    records["longest_charting"] = track_summary.sort_values(
        "weeks_on_chart", ascending=False
    ).head(20)[
        ["track_id", "track_name", "artist_name", "weeks_on_chart", "peak_position", "weeks_at_no1"]
    ]

    # ── 7. Longest charting without Top 10 ─────────────────────────────
    no_top10 = track_summary[track_summary["peak_position"] > 10].sort_values(
        "weeks_on_chart", ascending=False
    ).head(20)[
        ["track_id", "track_name", "artist_name", "weeks_on_chart", "peak_position"]
    ]
    records["longest_no_top10"] = no_top10

    # ── 8. Longest consecutive streak ─────────────────────────────────
    streaks = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby(
        "track_id"
    ):
        wks = grp["billboard_week"].tolist()
        max_run = 1
        cur_run = 1
        run_start = wks[0]
        run_end = wks[0]
        best_start = wks[0]
        best_end = wks[0]

        for i in range(1, len(wks)):
            if (wks[i] - wks[i - 1]).days <= 8:
                cur_run += 1
                run_end = wks[i]
            else:
                if cur_run > max_run:
                    max_run = cur_run
                    best_start = run_start
                    best_end = run_end
                cur_run = 1
                run_start = wks[i]
                run_end = wks[i]

        if cur_run > max_run:
            max_run = cur_run
            best_start = run_start
            best_end = run_end

        streaks.append(
            {
                "track_id": tid,
                "track_name": grp.iloc[0]["track_name"],
                "artist_name": grp.iloc[0]["artist_name"],
                "连续周数": max_run,
                "起始周": best_start,
                "结束周": best_end,
            }
        )
    records["longest_streak"] = (
        pd.DataFrame(streaks)
        .sort_values("连续周数", ascending=False)
        .head(20)
    )

    # ── 9. Biggest Jump / Drop ─────────────────────────────────────────
    changes = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby(
        "track_id"
    ):
        grp = grp.sort_values("billboard_week")
        rows = grp.to_dict("records")
        for i in range(1, len(rows)):
            prev, curr = rows[i - 1], rows[i]
            if (curr["billboard_week"] - prev["billboard_week"]).days <= 8:
                change = prev["rank"] - curr["rank"]  # positive = rise
                changes.append(
                    {
                        "track_id": tid,
                        "track_name": curr["track_name"],
                        "artist_name": curr["artist_name"],
                        "日期": curr["billboard_week"],
                        "上周排名": prev["rank"],
                        "本周排名": curr["rank"],
                        "变化": change,
                    }
                )
    if changes:
        ch_df = pd.DataFrame(changes)
        records["biggest_jump"] = ch_df.nlargest(15, "变化")
        records["biggest_drop"] = ch_df.nsmallest(15, "变化")
    else:
        records["biggest_jump"] = pd.DataFrame()
        records["biggest_drop"] = pd.DataFrame()

    # ── 10. Same album most simultaneous entries ───────────────────────
    _weekly_norm = _normalize_album_column(weekly.copy())
    album_weekly = (
        _weekly_norm.groupby(["billboard_week", "artist_name", "album_name"])
        .size()
        .reset_index(name="track_count")
    )
    if not album_weekly.empty:
        best_alb = album_weekly.sort_values("track_count", ascending=False).iloc[0]
        records["album_simul"] = {
            "album": best_alb["album_name"],
            "artist": best_alb["artist_name"],
            "week": best_alb["billboard_week"],
            "count": int(best_alb["track_count"]),
        }
        records["album_simul_list"] = album_weekly.sort_values(
            "track_count", ascending=False
        ).head(15)

    # ── 11. All-Time Greatest (Power Score) ──────────────────────────────
    power_df = compute_power_scores(weekly, top_n)
    records["all_time_greatest"] = power_df.head(20)[
        ["track_id", "track_name", "artist_name", "peak_position", "weeks_on_chart", "weeks_at_no1", "power_score"]
    ].rename(columns={"power_score": "综合评分"})

    # ── 12. Year-End #1 (per-year Power Score) ──────────────────────────
    wy = weekly.copy()
    wy["year"] = pd.to_datetime(wy["billboard_week"]).dt.year
    ye_results = []
    for year, year_df in wy.groupby("year"):
        year_power = compute_power_scores(year_df, top_n)
        if not year_power.empty:
            top = year_power.iloc[0]
            ye_results.append({
                "year": int(year),
                "track_id": top["track_id"],
                "track_name": top["track_name"],
                "artist_name": top["artist_name"],
                "peak": top["peak_position"],
                "weeks_on_chart": top["weeks_on_chart"],
            })
    records["year_end_no1"] = pd.DataFrame(ye_results).sort_values("year", ascending=False) if ye_results else pd.DataFrame()

    # ── 13. Double Debut #1 (双空冠) ─────────────────────────────────────
    if weekly_album is not None:
        first_track_appear = (
            weekly.sort_values("billboard_week")
            .groupby("track_id")
            .first()
            .reset_index()
        )
        debut_tracks = first_track_appear[first_track_appear["rank"] == 1][
            ["track_id", "track_name", "artist_name", "billboard_week"]
        ].copy()
        debut_tracks.columns = ["debut_track_id", "debut_track", "debut_artist", "debut_week"]

        first_album_appear = (
            weekly_album.sort_values("billboard_week")
            .groupby(["album_name", "artist_name"])
            .first()
            .reset_index()
        )
        debut_albums = first_album_appear[first_album_appear["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ].copy()
        debut_albums.columns = ["debut_album", "debut_artist", "debut_week"]

        double_debut = debut_tracks.merge(
            debut_albums, on=["debut_artist", "debut_week"], how="inner"
        ).sort_values("debut_week", ascending=False)
        if not double_debut.empty:
            double_debut["debut_week"] = double_debut["debut_week"].astype(str)
        records["double_debut"] = double_debut
    else:
        records["double_debut"] = pd.DataFrame()

    # ── 14. Weekly Total Plays Ranking (大盘) ────────────────────────────
    if weekly_album is not None and weekly_artist is not None:
        week_total_plays = (
            weekly.groupby("billboard_week")
            .agg(
                total_plays=("play_count", "sum"),
                tracks_count=("track_id", "nunique"),
            )
            .reset_index()
        )
        week_no1 = weekly[weekly["rank"] == 1][
            ["billboard_week", "track_id", "track_name", "artist_name", "play_count"]
        ].copy()
        week_no1.columns = [
            "billboard_week", "no1_track_id", "no1_track",
            "no1_track_artist", "no1_track_plays",
        ]
        week_total_plays = week_total_plays.merge(week_no1, on="billboard_week", how="left")
        week_album_no1 = weekly_album[weekly_album["rank"] == 1][
            ["billboard_week", "album_name", "artist_name", "play_count"]
        ].copy()
        week_album_no1.columns = [
            "billboard_week", "no1_album", "no1_album_artist", "no1_album_plays",
        ]
        week_total_plays = week_total_plays.merge(week_album_no1, on="billboard_week", how="left")
        week_artist_no1 = weekly_artist[weekly_artist["rank"] == 1][
            ["billboard_week", "artist_name", "play_count"]
        ].copy()
        week_artist_no1.columns = [
            "billboard_week", "no1_chart_artist", "no1_chart_artist_plays",
        ]
        week_total_plays = week_total_plays.merge(week_artist_no1, on="billboard_week", how="left")
        week_total_plays = week_total_plays.sort_values("total_plays", ascending=False)
        week_total_plays.index = week_total_plays.index + 1
        week_total_plays["billboard_week"] = week_total_plays["billboard_week"].astype(str)
        records["week_total_plays"] = week_total_plays
    else:
        records["week_total_plays"] = pd.DataFrame()

    return records


# ═══════════════════════════════════════════════════════════════════════════
# Main Billboard computation — mirrors app/pages/billboard/__init__.py:run()
# ═══════════════════════════════════════════════════════════════════════════

def _add_cover_urls(weekly, weekly_album, weekly_artist):
    """为三个周榜 DataFrame 添加 cover_url 列。

    cover_url 统一指向智能封面端点 /covers/{type}/{id}.jpg：
    - 本地有缓存 → 直接返回文件
    - 本地缺失 → 重定向到 Spotify CDN + 后台下载缓存
    - 无任何数据 → null（前端回退 emoji 占位符）
    """
    conn = get_db()

    def _build_url(image_path, image_url, cover_type, entity_id):
        """只要有任何封面数据就返回智能端点 URL，由端点处理回退链。"""
        if image_path or image_url:
            return f"/covers/{cover_type}/{entity_id}.jpg"
        return None

    # ── 曲目榜：track_id → album_id → albums ─────────────────────────
    if not weekly.empty and "track_id" in weekly.columns:
        track_ids = weekly["track_id"].unique().tolist()
        placeholders = ",".join("?" for _ in track_ids)
        rows = conn.execute(
            f"""SELECT t.track_id, al.album_id, al.image_path, al.image_url
                FROM tracks t
                LEFT JOIN albums al ON t.album_id = al.album_id
                WHERE t.track_id IN ({placeholders})""",
            track_ids,
        ).fetchall()
        cover_map = {
            r["track_id"]: _build_url(
                r["image_path"], r["image_url"], "albums", r["album_id"]
            ) if r["album_id"] else None
            for r in rows
        }
        weekly = weekly.copy()
        weekly["cover_url"] = weekly["track_id"].map(cover_map)

    # ── 专辑榜：(album_name, artist_name) → album_id → albums ────────
    if not weekly_album.empty:
        album_rows = conn.execute(
            """SELECT al.album_id, al.album_name, a.artist_name,
                      al.image_path, al.image_url
               FROM albums al
               JOIN artists a ON al.artist_id = a.artist_id"""
        ).fetchall()
        album_cover_map = {}
        for r in album_rows:
            key = (r["album_name"], r["artist_name"])
            url = _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
            # 只保留有封面的；None 不覆盖已有有效 URL
            if url or key not in album_cover_map:
                album_cover_map[key] = url
        # 也查 release_groups: canonical_name → 封面（优先主专辑，回退到成员）
        rg_rows = conn.execute(
            """SELECT rg.group_id, rg.canonical_name, a.artist_name,
                      pa.album_id, pa.image_path, pa.image_url
               FROM release_groups rg
               JOIN albums pa ON rg.primary_album_id = pa.album_id
               JOIN artists a ON pa.artist_id = a.artist_id"""
        ).fetchall()
        for r in rg_rows:
            key = (r["canonical_name"], r["artist_name"])
            if album_cover_map.get(key) is None:
                url = _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
                if url is None:
                    # 主专辑无封面 → 回退到有封面的成员专辑
                    member_row = conn.execute(
                        """SELECT al.album_id, al.image_path, al.image_url
                           FROM release_group_members rgm
                           JOIN albums al ON rgm.album_id = al.album_id
                           WHERE rgm.group_id = ?
                             AND (al.image_path IS NOT NULL AND al.image_path != ''
                                  OR al.image_url IS NOT NULL AND al.image_url != '')
                           ORDER BY al.album_id
                           LIMIT 1""",
                        (r["group_id"],),
                    ).fetchone()
                    if member_row:
                        url = _build_url(
                            member_row["image_path"], member_row["image_url"],
                            "albums", member_row["album_id"],
                        )
                album_cover_map[key] = url

        weekly_album = weekly_album.copy()
        weekly_album["cover_url"] = weekly_album.apply(
            lambda row: album_cover_map.get(
                (row["album_name"], row["artist_name"])
            ), axis=1
        )

    # ── 艺人榜：artist_name → artist_id → artists ────────────────────
    if not weekly_artist.empty:
        artist_rows = conn.execute(
            """SELECT artist_id, artist_name, image_path, image_url
               FROM artists
               WHERE image_path IS NOT NULL AND image_path != ''
                  OR image_url IS NOT NULL AND image_url != ''"""
        ).fetchall()
        artist_cover_map = {
            r["artist_name"]: _build_url(
                r["image_path"], r["image_url"], "artists", r["artist_id"]
            )
            for r in artist_rows
        }
        weekly_artist = weekly_artist.copy()
        weekly_artist["cover_url"] = weekly_artist["artist_name"].map(artist_cover_map)

    conn.close()
    return weekly, weekly_album, weekly_artist


@lru_cache(maxsize=1)
def compute_billboard_data(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute all Billboard data in one call.

    Returns a dict with all DataFrames converted to JSON-safe lists of dicts.
    This single function replaces the 15+ DataFrame computation pipeline
    previously done in Streamlit's billboard/__init__.py:run().

    Parameters
    ----------
    min_ms : int
        Minimum play duration in milliseconds.
    music_only : bool
        Exclude podcasts/audiobooks.
    bb_top_n : int
        Number of tracks per week in the singles chart.
    bb_album_top_n : int
        Number of albums per week in the albums chart.
    bb_artist_top_n : int
        Number of artists per week in the artists chart.
    bb_week_start_dow : int
        Day of week (0=Mon, 6=Sun) that starts a Billboard week.
    bb_week_start_hour : int
        Hour (0-23) that starts a Billboard week.
    year_start : int or None
        Filter to this year and later (inclusive).
    year_end : int or None
        Filter to this year and earlier (inclusive).

    Returns
    -------
    dict with keys:
        meta, weekly, weekly_album, weekly_artist,
        track_summary, artist_summary, artist_track_counts,
        album_track_counts, track_per_album,
        records, power_scores, album_power_scores, artist_power_scores
    """
    # ── Load raw data ──────────────────────────────────────────────────
    df_raw = load_billboard_raw(min_ms, music_only, bb_week_start_dow, bb_week_start_hour)
    album_map = load_track_album_map()

    # ── Year filter ────────────────────────────────────────────────────
    df_raw = df_raw.copy()
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        df_raw = df_raw[df_raw["_year"] >= year_start]
    if year_end is not None:
        df_raw = df_raw[df_raw["_year"] <= year_end]
    df_filtered = df_raw.copy()

    # All weeks
    all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
    all_weeks_desc = sorted(all_weeks_asc, reverse=True)

    # ── Try pre-aggregated tables ──────────────────────────────────────
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

    # ── Compute rankings ───────────────────────────────────────────────
    weekly = compute_weekly_rankings(df_filtered, bb_top_n, pre_agg=_agg_tracks)
    weekly_album = compute_album_weekly_rankings(df_filtered, bb_album_top_n, pre_agg=_agg_albums)
    weekly_artist = compute_artist_weekly_rankings(df_filtered, bb_artist_top_n, pre_agg=_agg_artists)

    # ── Patch tracks_count from weekly when using pre-agg ──────────────
    if _agg_tracks is not None:
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

        _artist_tc = (
            weekly.groupby(["billboard_week", "artist_name"])
            .agg(tracks_count=("track_id", "nunique"))
            .reset_index()
        )
        weekly_artist = weekly_artist.drop(columns=["tracks_count"], errors="ignore").merge(
            _artist_tc, on=["billboard_week", "artist_name"], how="left"
        )
        weekly_artist["tracks_count"] = weekly_artist["tracks_count"].fillna(0).astype(int)

    # Albums count per artist from album chart
    _artist_ac = (
        weekly_album.groupby(["billboard_week", "artist_name"])
        .agg(albums_count=("album_name", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.merge(
        _artist_ac, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["albums_count"] = weekly_artist["albums_count"].fillna(0).astype(int)

    # ── Track summary ──────────────────────────────────────────────────
    track_summary = (
        weekly.groupby(["track_id", "track_name", "artist_name", "album_name"])
        .agg(
            peak_position=("rank", "min"),
            weeks_on_chart=("billboard_week", "nunique"),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
            first_week=("billboard_week", "min"),
            last_week=("billboard_week", "max"),
            total_chart_plays=("play_count", "sum"),
        )
        .reset_index()
    )

    # Total plays per track (all-time)
    track_total_plays = (
        df_filtered.groupby("track_id")
        .agg(total_plays=("ms_played", "count"))
        .reset_index()
    )
    track_summary = track_summary.merge(track_total_plays, on="track_id", how="left")

    # Weeks at #1
    weeks_at_no1 = (
        weekly[weekly["rank"] == 1]
        .groupby("track_id")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
    )
    track_summary = track_summary.merge(weeks_at_no1, on="track_id", how="left")
    track_summary["weeks_at_no1"] = track_summary["weeks_at_no1"].fillna(0).astype(int)

    # First week at peak position
    first_peak = weekly.merge(
        track_summary[["track_id", "peak_position"]], on="track_id"
    )
    first_peak = first_peak[first_peak["rank"] == first_peak["peak_position"]]
    first_peak = first_peak.groupby("track_id")["billboard_week"].min().reset_index()
    first_peak.columns = ["track_id", "first_peak_week"]
    track_summary = track_summary.merge(first_peak, on="track_id", how="left")

    # Running (as-of-week) metrics: PK, 在榜, PK Wks 均截至当周计算

    def _add_running_metrics(df, group_cols):
        """Add running_peak, running_wks, running_peak_wks columns.

        All three metrics are computed up to and including the current week,
        not as all-time aggregates. When the peak improves (e.g. 2→1), the
        peak-weeks count resets to only include weeks at the new peak.
        """
        df = df.sort_values(group_cols + ["billboard_week"])
        df["running_peak"] = df.groupby(group_cols)["rank"].cummin()
        df["running_wks"] = df.groupby(group_cols).cumcount() + 1

        def _running_peak_wks(group):
            ranks = group["rank"].values
            rp = np.minimum.accumulate(ranks)
            rank_counts = {}
            result = np.zeros(len(ranks), dtype=int)
            for i, r in enumerate(ranks):
                rank_counts[r] = rank_counts.get(r, 0) + 1
                result[i] = rank_counts[rp[i]]
            group = group.copy()
            group["running_peak_wks"] = result
            return group

        return df.groupby(group_cols, group_keys=False).apply(_running_peak_wks)

    weekly = _add_running_metrics(weekly, ["track_id"])
    weekly_album = _add_running_metrics(weekly_album, ["artist_name", "album_name"])
    weekly_artist = _add_running_metrics(weekly_artist, ["artist_name"])

    # ── Artist summary ─────────────────────────────────────────────────
    artist_summary = (
        weekly.groupby(["artist_name", "track_id", "track_name", "album_name"])
        .agg(
            peak_position=("rank", "min"),
            weeks_on_chart=("billboard_week", "nunique"),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
            first_week=("billboard_week", "min"),
            last_week=("billboard_week", "max"),
            total_chart_plays=("play_count", "sum"),
        )
        .reset_index()
    )

    # ── Artist track counts ────────────────────────────────────────────
    artist_track_counts = (
        artist_summary.groupby("artist_name")
        .agg(
            total_tracks=("track_id", "nunique"),
            best_peak=("peak_position", "min"),
            total_weeks=("weeks_on_chart", "sum"),
            avg_weeks=("weeks_on_chart", "mean"),
            top1=("peak_position", lambda x: (x == 1).sum()),
            top5=("peak_position", lambda x: (x <= 5).sum()),
            top10=("peak_position", lambda x: (x <= 10).sum()),
        )
        .reset_index()
        .sort_values("total_tracks", ascending=False)
    )
    artist_track_counts["best_peak_track"] = artist_track_counts["artist_name"].apply(
        lambda a: artist_summary[artist_summary["artist_name"] == a]
        .sort_values("peak_position")
        .iloc[0]["track_name"]
    )

    # Artist weeks at #1 (sum of all tracks' weeks at #1)
    artist_weeks_no1 = (
        track_summary.groupby("artist_name")["weeks_at_no1"]
        .sum()
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(artist_weeks_no1, on="artist_name", how="left")

    # Album #1 metrics per artist
    album_no1_artist = weekly_album[weekly_album["rank"] == 1].groupby("artist_name").agg(
        num_no1_albums=("album_name", "nunique"),
        album_no1_weeks=("billboard_week", "nunique"),
    ).reset_index()
    artist_track_counts = artist_track_counts.merge(album_no1_artist, on="artist_name", how="left")
    artist_track_counts["num_no1_albums"] = artist_track_counts["num_no1_albums"].fillna(0).astype(int)
    artist_track_counts["album_no1_weeks"] = artist_track_counts["album_no1_weeks"].fillna(0).astype(int)

    # Artist chart #1 weeks
    artist_no1_weeks = weekly_artist[weekly_artist["rank"] == 1].groupby("artist_name").agg(
        artist_chart_no1_weeks=("billboard_week", "nunique"),
    ).reset_index()
    artist_track_counts = artist_track_counts.merge(artist_no1_weeks, on="artist_name", how="left")
    artist_track_counts["artist_chart_no1_weeks"] = artist_track_counts["artist_chart_no1_weeks"].fillna(0).astype(int)

    # ── Album expanded view (track → all its albums via album_map) ─────
    ts_for_album = track_summary.drop(columns=["album_name"])
    track_albums_expanded = ts_for_album.merge(album_map, on="track_id", how="left")
    track_albums_expanded["album_list"] = track_albums_expanded["album_list"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    track_per_album = track_albums_expanded.explode("album_list")
    track_per_album = track_per_album.dropna(subset=["album_list"])
    track_per_album = track_per_album.rename(columns={"album_list": "album_name"})

    # Normalize album names via release groups
    track_per_album = _normalize_album_column(
        track_per_album,
        dedup_cols=["track_id", "album_name", "artist_name"],
    )

    # ── Album track counts ─────────────────────────────────────────────
    album_track_counts = (
        track_per_album.groupby(["album_name", "artist_name"])
        .agg(
            total_tracks=("track_id", "nunique"),
            best_peak=("peak_position", "min"),
            total_weeks=("weeks_on_chart", "sum"),
            avg_weeks=("weeks_on_chart", "mean"),
            top1=("peak_position", lambda x: (x == 1).sum()),
            top5=("peak_position", lambda x: (x <= 5).sum()),
            top10=("peak_position", lambda x: (x <= 10).sum()),
        )
        .reset_index()
        .sort_values("total_tracks", ascending=False)
    )
    album_track_counts["best_peak_track"] = album_track_counts.apply(
        lambda r: track_per_album[
            (track_per_album["album_name"] == r["album_name"])
            & (track_per_album["artist_name"] == r["artist_name"])
        ]
        .sort_values("peak_position")
        .iloc[0]["track_name"],
        axis=1,
    )

    # Album weeks at #1
    album_weeks_no1 = (
        track_per_album.groupby(["album_name", "artist_name"])["weeks_at_no1"]
        .sum()
        .reset_index()
    )
    album_track_counts = album_track_counts.merge(album_weeks_no1, on=["album_name", "artist_name"], how="left")

    # Album #1 weeks (from weekly_album)
    album_no1 = weekly_album[weekly_album["rank"] == 1].groupby(["album_name", "artist_name"]).agg(
        album_chart_no1_weeks=("billboard_week", "nunique"),
    ).reset_index()
    album_track_counts = album_track_counts.merge(album_no1, on=["album_name", "artist_name"], how="left")
    album_track_counts["album_chart_no1_weeks"] = album_track_counts["album_chart_no1_weeks"].fillna(0).astype(int)

    # ── Records ────────────────────────────────────────────────────────
    records = compute_records(weekly, track_summary, bb_top_n, weekly_album, weekly_artist)

    # ── Power scores ───────────────────────────────────────────────────
    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    # ── Enrich with cover URLs ───────────────────────────────────────
    weekly, weekly_album, weekly_artist = _add_cover_urls(
        weekly, weekly_album, weekly_artist
    )

    # ── Convert to JSON-safe format ────────────────────────────────────
    date_cols_week = ["billboard_week", "first_week", "last_week", "first_peak_week"]

    result = {
        "meta": {
            "total_weeks": len(all_weeks_asc),
            "total_filtered_records": int(len(df_filtered)),
            "all_weeks_asc": [w.isoformat() for w in all_weeks_asc],
            "all_weeks_desc": [w.isoformat() for w in all_weeks_desc],
            "dow_name": DOW_NAMES[bb_week_start_dow],
            "dow_short": DOW_SHORT[bb_week_start_dow],
            "top_n": bb_top_n,
            "album_top_n": bb_album_top_n,
            "artist_top_n": bb_artist_top_n,
            "week_start_dow": bb_week_start_dow,
            "week_start_hour": bb_week_start_hour,
        },
        "weekly": _df_to_json(weekly, date_cols_week),
        "weekly_album": _df_to_json(weekly_album, ["billboard_week"]),
        "weekly_artist": _df_to_json(weekly_artist, ["billboard_week"]),
        "track_summary": _df_to_json(track_summary, date_cols_week),
        "artist_summary": _df_to_json(artist_summary, date_cols_week),
        "artist_track_counts": _df_to_json(artist_track_counts),
        "album_track_counts": _df_to_json(album_track_counts),
        "track_per_album": _df_to_json(track_per_album, date_cols_week),
        "records": _serialize_records(records),
        "power_scores": _df_to_json(power_scores),
        "album_power_scores": _df_to_json(album_power_scores),
        "artist_power_scores": _df_to_json(artist_power_scores),
    }

    return result


def _serialize_records(records):
    """Convert the records dict to JSON-safe format.

    Each value is either a DataFrame (→ list of dicts) or a scalar dict (→ native types).
    """
    result = {}
    for key, val in records.items():
        if isinstance(val, pd.DataFrame):
            result[key] = _df_to_json(val)
        elif isinstance(val, dict):
            result[key] = {k: _py_val(v) for k, v in val.items()}
        elif isinstance(val, list):
            result[key] = val
        else:
            result[key] = _py_val(val)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Track History Detail
# ═══════════════════════════════════════════════════════════════════════════

def _compute_change_column(hist_df):
    """Compute NEW/RE/▲n/▼n/─ change column for a sorted weekly history DataFrame."""
    hist = hist_df.sort_values("billboard_week").copy()
    week_dt = pd.to_datetime(hist["billboard_week"])
    hist["prev_rank"] = hist["rank"].shift(1)
    changes = []
    for i, (_, r) in enumerate(hist.iterrows()):
        p = r["prev_rank"]
        cur = r["rank"]
        if pd.isna(p):
            changes.append("NEW")
        else:
            cw = week_dt.iloc[i]
            pw = week_dt.iloc[i - 1]
            if (cw - pw).days > 8:
                changes.append("RE")
            else:
                diff = int(p) - int(cur)
                if diff > 0:
                    changes.append(f"▲{diff}")
                elif diff < 0:
                    changes.append(f"▼{abs(diff)}")
                else:
                    changes.append("─")
    hist["change"] = changes
    return hist


def _build_gapped_chart_data(hist_df):
    """Build x/y arrays with None gaps for >9 day breaks in chart history."""
    chart_data = hist_df.sort_values("billboard_week")[["billboard_week", "rank", "play_count"]].copy()
    chart_data["week_dt"] = pd.to_datetime(chart_data["billboard_week"])

    x_vals, y_vals, texts = [], [], []
    for i, (_, row) in enumerate(chart_data.iterrows()):
        if i > 0:
            gap_days = (row["week_dt"] - chart_data.iloc[i - 1]["week_dt"]).days
            if gap_days > 9:
                x_vals.append(None)
                y_vals.append(None)
                texts.append(None)
        x_vals.append(str(row["billboard_week"]))
        y_vals.append(int(row["rank"]))
        texts.append(f"#{int(row['rank'])} · {int(row['play_count'])}次")
    return x_vals, y_vals, texts


def get_track_history(track_id, min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
                      bb_week_start_dow, bb_week_start_hour, year_start, year_end):
    """Get detailed track chart history with change column and gapped chart data."""
    data = compute_billboard_data(
        min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
        bb_week_start_dow, bb_week_start_hour, year_start, year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    track_summary = pd.DataFrame(data["track_summary"])
    power_scores = pd.DataFrame(data["power_scores"])

    track_hist = weekly[weekly["track_id"] == track_id]
    if track_hist.empty:
        return {"found": False}

    track_hist = track_hist.sort_values("billboard_week")
    ts_row = track_summary[track_summary["track_id"] == track_id]
    info = ts_row.iloc[0].to_dict() if not ts_row.empty else {}

    tp = power_scores[power_scores["track_id"] == track_id]
    power_score = int(tp.iloc[0]["power_score"]) if not tp.empty else 0
    power_scores_sorted = power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    power_rank = int(power_scores_sorted[power_scores_sorted["track_id"] == track_id].index[0]) + 1 if not tp.empty else None

    # Change column
    hist_with_change = _compute_change_column(track_hist)

    # Gapped chart data
    x_vals, y_vals, texts = _build_gapped_chart_data(track_hist)

    cover_url = track_hist.iloc[0].get("cover_url") if "cover_url" in track_hist.columns else None

    return {
        "found": True,
        "track_id": track_id,
        "track_name": str(track_hist.iloc[0]["track_name"]),
        "artist_name": str(track_hist.iloc[0]["artist_name"]),
        "cover_url": cover_url if pd.notna(cover_url) else None,
        "summary": {
            "peak_position": int(info.get("peak_position", 0)),
            "weeks_on_chart": int(info.get("weeks_on_chart", 0)),
            "weeks_at_peak": int(info.get("weeks_at_peak", 0)),
            "first_week": str(info.get("first_week", "")),
            "last_week": str(info.get("last_week", "")),
            "first_peak_week": str(info.get("first_peak_week", "")) if pd.notna(info.get("first_peak_week")) else None,
            "total_chart_plays": int(info.get("total_chart_plays", 0)),
            "total_plays": int(info.get("total_plays", 0)),
            "weeks_at_no1": int(info.get("weeks_at_no1", 0)),
            "power_score": power_score,
            "power_rank": power_rank,
        },
        "history": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "play_count": int(r["play_count"]),
                "change": r["change"],
                "running_peak": int(r.get("running_peak", r["rank"])),
                "running_wks": int(r.get("running_wks", 1)),
                "running_peak_wks": int(r.get("running_peak_wks", 0)),
            }
            for _, r in hist_with_change.iterrows()
        ],
        "chart_data": {
            "x": x_vals,
            "y": y_vals,
            "texts": texts,
            "top_n": bb_top_n,
            "peak_position": int(info.get("peak_position", 0)),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Artist Chart Detail
# ═══════════════════════════════════════════════════════════════════════════

def get_artist_chart_detail(artist_name, min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
                             bb_week_start_dow, bb_week_start_hour, year_start, year_end):
    """Get detailed artist chart data: history, track/album performances, trend."""
    data = compute_billboard_data(
        min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
        bb_week_start_dow, bb_week_start_hour, year_start, year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_artist = pd.DataFrame(data["weekly_artist"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    artist_track_counts = pd.DataFrame(data["artist_track_counts"])
    artist_summary = pd.DataFrame(data["artist_summary"])
    track_summary = pd.DataFrame(data["track_summary"])
    power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])
    artist_power_scores = pd.DataFrame(data["artist_power_scores"])

    art_row = artist_track_counts[artist_track_counts["artist_name"] == artist_name]
    if art_row.empty:
        return {"found": False}
    art_row = art_row.iloc[0]

    # Artist weekly history
    artist_chart_data = weekly_artist[weekly_artist["artist_name"] == artist_name]
    artist_weekly = weekly[weekly["artist_name"] == artist_name]

    # Artist power score/rank
    aps_sorted = artist_power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    ap_row = aps_sorted[aps_sorted["artist_name"] == artist_name]
    artist_power_score = int(ap_row.iloc[0]["power_score"]) if not ap_row.empty else 0
    artist_power_rank = int(ap_row.iloc[0].name) + 1 if not ap_row.empty else None

    # Track power scores for this artist
    track_power = power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    track_power["power_rank"] = track_power.index + 1
    artist_track_power = track_power[track_power["artist_name"] == artist_name]

    # Album power scores for this artist
    album_power = album_power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    album_power["power_rank"] = album_power.index + 1
    artist_album_power = album_power[album_power["artist_name"] == artist_name]

    # Charting tracks with power scores
    art_tracks = artist_summary[artist_summary["artist_name"] == artist_name].copy()
    art_tracks = art_tracks.merge(
        track_summary[["track_id", "weeks_at_no1", "first_peak_week"]],
        on="track_id", how="left"
    )
    art_tracks["weeks_at_no1"] = art_tracks["weeks_at_no1"].fillna(0).astype(int)
    art_tracks = art_tracks.merge(
        artist_track_power[["track_id", "power_score", "power_rank"]],
        on="track_id", how="left"
    )
    art_tracks["power_score"] = art_tracks["power_score"].fillna(0).astype(int)
    art_tracks["power_rank"] = art_tracks["power_rank"].fillna(0).astype(int)
    art_tracks = art_tracks.sort_values(["peak_position", "weeks_on_chart"], ascending=[True, False])

    # Track cover_url lookup
    track_cover_map = {}
    if "cover_url" in weekly.columns:
        for _, r in weekly[["track_id", "cover_url"]].drop_duplicates("track_id").iterrows():
            if pd.notna(r["cover_url"]):
                track_cover_map[int(r["track_id"])] = r["cover_url"]

    # Best singles rank per week (for overlay chart)
    best_singles = (
        artist_weekly.groupby("billboard_week")["rank"]
        .min()
        .reset_index()
        .sort_values("billboard_week")
    )

    # Artist weekly history with change column and #1 info
    artist_no1 = artist_weekly[artist_weekly["rank"] == 1].groupby("billboard_week").agg(
        no1_track_names=("track_name", lambda x: "、".join(dict.fromkeys(x))),
        no1_track_id=("track_id", "first"),
        no1_count=("track_id", "nunique"),
    ).reset_index()

    # #1 album per week
    week_no1_albums = weekly_album[weekly_album["rank"] == 1][["billboard_week", "album_name", "artist_name"]].copy()

    artist_wk_history = _compute_change_column(artist_chart_data) if not artist_chart_data.empty else pd.DataFrame()

    # Artist chart summary
    chart_summary = {}
    if not artist_chart_data.empty:
        art_peak = int(artist_chart_data["rank"].min())
        chart_summary = {
            "peak_position": art_peak,
            "weeks_on_chart": int(artist_chart_data["billboard_week"].nunique()),
            "first_week": str(artist_chart_data["billboard_week"].min()),
            "first_peak_week": str(artist_chart_data.loc[artist_chart_data["rank"] == art_peak, "billboard_week"].min()),
            "latest_week": str(artist_chart_data["billboard_week"].max()),
            "no1_weeks": int((artist_chart_data["rank"] == 1).sum()),
            "peak_weeks": int((artist_chart_data["rank"] == art_peak).sum()),
            "power_score": artist_power_score,
            "power_rank": artist_power_rank,
        }

    # Album chart performance summary
    artist_albums_all = weekly_album[weekly_album["artist_name"] == artist_name]
    album_perf = []
    if not artist_albums_all.empty:
        album_summary = (
            artist_albums_all.groupby("album_name")
            .agg(
                peak=("rank", "min"),
                pk_wks=("rank", lambda x: (x == x.min()).sum()),
                weeks=("billboard_week", "nunique"),
                first_week=("billboard_week", "min"),
                last_week=("billboard_week", "max"),
                total_plays=("play_count", "sum"),
            )
            .reset_index()
            .sort_values(["peak", "pk_wks", "weeks"], ascending=[True, False, False])
        )
        album_summary = album_summary.merge(
            artist_album_power[["album_name", "power_score", "power_rank"]],
            on="album_name", how="left"
        )
        album_summary["power_score"] = album_summary["power_score"].fillna(0).astype(int)
        album_summary["power_rank"] = album_summary["power_rank"].fillna(0).astype(int)

        # Album cover_url + first_peak_week lookup
        album_cover_map = {}
        album_peak_map = {}
        if "cover_url" in weekly_album.columns:
            for _, r in weekly_album[weekly_album["artist_name"] == artist_name][
                ["album_name", "cover_url", "rank"]
            ].iterrows():
                aname = r["album_name"]
                if aname not in album_cover_map and pd.notna(r["cover_url"]):
                    album_cover_map[aname] = r["cover_url"]
                # Track first week this album hit its peak
                if aname not in album_peak_map:
                    album_peak_map[aname] = r

        album_perf = [
            {
                "album_name": r["album_name"],
                "peak": int(r["peak"]),
                "weeks": int(r["weeks"]),
                "pk_wks": int(r["pk_wks"]),
                "first_week": str(r["first_week"]),
                "first_peak_week": str(
                    artist_albums_all[
                        (artist_albums_all["album_name"] == r["album_name"])
                        & (artist_albums_all["rank"] == int(r["peak"]))
                    ]["billboard_week"].min()
                ),
                "last_week": str(r["last_week"]),
                "total_plays": int(r["total_plays"]),
                "power_score": int(r["power_score"]),
                "power_rank": int(r["power_rank"]) if r["power_rank"] > 0 else None,
                "cover_url": album_cover_map.get(r["album_name"]),
            }
            for _, r in album_summary.iterrows()
        ]

    # Artist cover URL from weekly_artist data
    artist_cover_url = None
    if not artist_chart_data.empty and "cover_url" in artist_chart_data.columns:
        first_cover = artist_chart_data.iloc[0].get("cover_url")
        if pd.notna(first_cover):
            artist_cover_url = first_cover

    return {
        "found": True,
        "artist_name": artist_name,
        "cover_url": artist_cover_url,
        "info": {
            "total_tracks": int(art_row["total_tracks"]),
            "best_peak": int(art_row["best_peak"]),
            "total_weeks": int(art_row["total_weeks"]),
            "avg_weeks": round(float(art_row["avg_weeks"]), 1),
            "top1": int(art_row["top1"]),
            "top5": int(art_row["top5"]),
            "top10": int(art_row["top10"]),
            "weeks_at_no1": int(art_row["weeks_at_no1"]),
            "num_no1_albums": int(art_row.get("num_no1_albums", 0)),
            "album_no1_weeks": int(art_row.get("album_no1_weeks", 0)),
            "total_track_power": int(artist_track_power["power_score"].sum()),
            "total_album_power": int(artist_album_power["power_score"].sum()),
        },
        "chart_summary": chart_summary,
        "artist_weekly_history": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "play_count": int(r["play_count"]),
                "tracks_count": int(r.get("tracks_count", 0)),
                "albums_count": int(r.get("albums_count", 0)),
                "change": r["change"],
                "running_peak": int(r.get("running_peak", r["rank"])),
                "running_wks": int(r.get("running_wks", 1)),
                "running_peak_wks": int(r.get("running_peak_wks", 0)),
            }
            for _, r in artist_wk_history.iterrows()
        ] if not artist_wk_history.empty else [],
        "artist_no1_by_week": [
            {
                "week": str(r["billboard_week"]),
                "no1_track_names": r["no1_track_names"],
                "no1_track_id": int(r["no1_track_id"]) if pd.notna(r.get("no1_track_id")) else None,
                "no1_count": int(r["no1_count"]),
            }
            for _, r in artist_no1.iterrows()
        ],
        "week_no1_albums": [
            {
                "week": str(r["billboard_week"]),
                "album_name": r["album_name"],
                "artist_name": r["artist_name"],
            }
            for _, r in week_no1_albums.iterrows()
        ],
        "best_singles_overlay": [
            {"week": str(r["billboard_week"]), "rank": int(r["rank"])}
            for _, r in best_singles.iterrows()
        ] if not best_singles.empty else [],
        "tracks": [
            {
                "track_id": r["track_id"],
                "track_name": r["track_name"],
                "peak_position": int(r["peak_position"]),
                "weeks_on_chart": int(r["weeks_on_chart"]),
                "weeks_at_peak": int(r["weeks_at_peak"]),
                "first_week": str(r["first_week"]),
                "first_peak_week": str(r.get("first_peak_week", "")),
                "last_week": str(r["last_week"]),
                "total_chart_plays": int(r["total_chart_plays"]),
                "power_score": int(r["power_score"]),
                "power_rank": int(r["power_rank"]) if r["power_rank"] > 0 else None,
                "cover_url": track_cover_map.get(int(r["track_id"])),
            }
            for _, r in art_tracks.iterrows()
        ],
        "albums": album_perf,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Album Chart Detail
# ═══════════════════════════════════════════════════════════════════════════

def get_album_chart_detail(album_name, artist_name, min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
                            bb_week_start_dow, bb_week_start_hour, year_start, year_end):
    """Get detailed album chart data: history, track performances, trend."""
    data = compute_billboard_data(
        min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
        bb_week_start_dow, bb_week_start_hour, year_start, year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    album_track_counts = pd.DataFrame(data["album_track_counts"])
    track_per_album = pd.DataFrame(data["track_per_album"])
    power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])

    # Find matching album
    alb_row = album_track_counts[
        (album_track_counts["album_name"] == album_name) & (album_track_counts["artist_name"] == artist_name)
    ]
    if alb_row.empty:
        return {"found": False}
    alb_row = alb_row.iloc[0]

    # Album chart data
    album_chart_data = weekly_album[
        (weekly_album["album_name"] == album_name) & (weekly_album["artist_name"] == artist_name)
    ]

    # Album power score/rank
    aps_sorted = album_power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    ap_row = aps_sorted[
        (aps_sorted["album_name"] == album_name) & (aps_sorted["artist_name"] == artist_name)
    ]
    album_power_score = int(ap_row.iloc[0]["power_score"]) if not ap_row.empty else 0
    album_power_rank = int(ap_row.iloc[0].name) + 1 if not ap_row.empty else None

    # Album's charting tracks
    alb_track_ids = set(
        track_per_album[
            (track_per_album["album_name"] == album_name) & (track_per_album["artist_name"] == artist_name)
        ]["track_id"].tolist()
    )
    track_power = power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    track_power["power_rank"] = track_power.index + 1
    album_track_power = track_power[track_power["track_id"].isin(alb_track_ids)]

    alb_tracks = track_per_album[
        (track_per_album["album_name"] == album_name) & (track_per_album["artist_name"] == artist_name)
    ].copy()
    alb_tracks = alb_tracks.merge(
        album_track_power[["track_id", "power_score", "power_rank"]],
        on="track_id", how="left"
    )
    alb_tracks["power_score"] = alb_tracks["power_score"].fillna(0).astype(int)
    alb_tracks["power_rank"] = alb_tracks["power_rank"].fillna(0).astype(int)
    alb_tracks = alb_tracks.sort_values(["peak_position", "weeks_on_chart"], ascending=[True, False])

    # Track cover_url lookup
    album_track_cover_map = {}
    if "cover_url" in weekly.columns:
        for _, r in weekly[["track_id", "cover_url"]].drop_duplicates("track_id").iterrows():
            if pd.notna(r["cover_url"]):
                album_track_cover_map[int(r["track_id"])] = r["cover_url"]

    # Singles weekly for this album (for overlay chart)
    album_weekly = weekly[weekly["track_id"].isin(alb_track_ids)]
    best_singles = (
        album_weekly.groupby("billboard_week")["rank"]
        .min()
        .reset_index()
        .sort_values("billboard_week")
    )

    # #1 track info per week
    album_no1 = album_weekly[album_weekly["rank"] == 1].groupby("billboard_week").agg(
        no1_track_names=("track_name", lambda x: "、".join(dict.fromkeys(x))),
        no1_track_id=("track_id", "first"),
        no1_count=("track_id", "nunique"),
    ).reset_index()

    # Album weekly history with change column
    album_wk_history = _compute_change_column(album_chart_data) if not album_chart_data.empty else pd.DataFrame()

    # Chart summary
    chart_summary = {}
    if not album_chart_data.empty:
        alb_peak = int(album_chart_data["rank"].min())
        chart_summary = {
            "peak_position": alb_peak,
            "weeks_on_chart": int(album_chart_data["billboard_week"].nunique()),
            "first_week": str(album_chart_data["billboard_week"].min()),
            "first_peak_week": str(album_chart_data.loc[album_chart_data["rank"] == alb_peak, "billboard_week"].min()),
            "latest_week": str(album_chart_data["billboard_week"].max()),
            "no1_weeks": int((album_chart_data["rank"] == 1).sum()),
            "peak_weeks": int((album_chart_data["rank"] == alb_peak).sum()),
            "power_score": album_power_score,
            "power_rank": album_power_rank,
        }

    # Album cover URL from weekly_album data
    album_cover_url = None
    if not album_chart_data.empty and "cover_url" in album_chart_data.columns:
        first_cover = album_chart_data.iloc[0].get("cover_url")
        if pd.notna(first_cover):
            album_cover_url = first_cover

    return {
        "found": True,
        "album_name": album_name,
        "artist_name": artist_name,
        "cover_url": album_cover_url,
        "info": {
            "total_tracks": int(alb_row["total_tracks"]),
            "best_peak": int(alb_row["best_peak"]),
            "total_weeks": int(alb_row["total_weeks"]),
            "avg_weeks": round(float(alb_row["avg_weeks"]), 1),
            "top1": int(alb_row["top1"]),
            "top5": int(alb_row["top5"]),
            "top10": int(alb_row["top10"]),
            "weeks_at_no1": int(alb_row["weeks_at_no1"]),
            "album_chart_no1_weeks": int(alb_row.get("album_chart_no1_weeks", 0)),
            "total_track_power": int(album_track_power["power_score"].sum()),
        },
        "chart_summary": chart_summary,
        "album_weekly_history": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "play_count": int(r["play_count"]),
                "tracks_count": int(r.get("tracks_count", 0)),
                "change": r["change"],
                "running_peak": int(r.get("running_peak", r["rank"])),
                "running_wks": int(r.get("running_wks", 1)),
                "running_peak_wks": int(r.get("running_peak_wks", 0)),
            }
            for _, r in album_wk_history.iterrows()
        ] if not album_wk_history.empty else [],
        "album_no1_by_week": [
            {
                "week": str(r["billboard_week"]),
                "no1_track_names": r["no1_track_names"],
                "no1_track_id": int(r["no1_track_id"]) if pd.notna(r.get("no1_track_id")) else None,
                "no1_count": int(r["no1_count"]),
            }
            for _, r in album_no1.iterrows()
        ],
        "best_singles_overlay": [
            {"week": str(r["billboard_week"]), "rank": int(r["rank"])}
            for _, r in best_singles.iterrows()
        ] if not best_singles.empty else [],
        "tracks": [
            {
                "track_id": r["track_id"],
                "track_name": r["track_name"],
                "peak_position": int(r["peak_position"]),
                "weeks_on_chart": int(r["weeks_on_chart"]),
                "weeks_at_peak": int(r["weeks_at_peak"]),
                "first_week": str(r["first_week"]),
                "first_peak_week": str(r.get("first_peak_week", "")),
                "last_week": str(r["last_week"]),
                "total_chart_plays": int(r["total_chart_plays"]),
                "power_score": int(r["power_score"]),
                "power_rank": int(r["power_rank"]) if r["power_rank"] > 0 else None,
                "cover_url": album_track_cover_map.get(int(r["track_id"])),
            }
            for _, r in alb_tracks.iterrows()
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Versus
# ═══════════════════════════════════════════════════════════════════════════

def _get_ps_rank(power_scores_df, key_col, key_val, artist_val=None):
    """Look up power score and rank for an entity in a power_scores DataFrame."""
    if power_scores_df is None or len(power_scores_df) == 0:
        return None, None
    ps = power_scores_df.sort_values("power_score", ascending=False).reset_index(drop=True)
    if artist_val is not None:
        mask = (ps[key_col] == key_val) & (ps["artist_name"] == artist_val)
    else:
        mask = ps[key_col] == key_val
    match = ps[mask]
    if len(match) == 0:
        return None, None
    idx = int(match.index[0])
    return int(match.iloc[0]["power_score"]), idx + 1


def _resolve_album_members_vs(album_name, artist_name):
    """Resolve all member album names in a release group."""
    conn = get_db()
    row = conn.execute(
        """SELECT a.album_name FROM release_group_members rgm
           JOIN release_groups rg ON rg.group_id = rgm.group_id
           JOIN albums a ON a.album_id = rgm.album_id
           JOIN artists ar ON a.artist_id = ar.artist_id
           WHERE rg.canonical_name = ? AND ar.artist_name = ?
           UNION SELECT ?""",
        (album_name, artist_name, album_name),
    ).fetchall()
    conn.close()
    if row:
        return [r["album_name"] for r in row]
    return [album_name]


def get_versus_track(tid_a, tid_b, min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
                     bb_week_start_dow, bb_week_start_hour, year_start, year_end):
    """Compare two tracks side-by-side."""
    data = compute_billboard_data(
        min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
        bb_week_start_dow, bb_week_start_hour, year_start, year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    power_scores = pd.DataFrame(data["power_scores"])

    def _track_data(tid):
        grp = weekly[weekly["track_id"] == tid].sort_values("billboard_week")
        if grp.empty:
            return None
        ps_val, ps_rank = _get_ps_rank(power_scores, "track_id", tid)
        return {
            "name": f"{grp['track_name'].iloc[0]} — {grp['artist_name'].iloc[0]}",
            "track_name": str(grp["track_name"].iloc[0]),
            "artist_name": str(grp["artist_name"].iloc[0]),
            "rank_history": [
                {"week": str(r["billboard_week"]), "rank": int(r["rank"]), "play_count": int(r["play_count"])}
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": ps_val,
                "power_rank": ps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "top5_weeks": int((grp["rank"] <= 5).sum()),
                "total_chart_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _track_data(tid_a)
    result_b = _track_data(tid_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一首歌在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b}


def get_versus_album(aname_a, aart_a, aname_b, aart_b, min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
                     bb_week_start_dow, bb_week_start_hour, year_start, year_end):
    """Compare two albums side-by-side."""
    data = compute_billboard_data(
        min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
        bb_week_start_dow, bb_week_start_hour, year_start, year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])

    def _album_data(aname, aart):
        grp = weekly_album[
            (weekly_album["album_name"] == aname) & (weekly_album["artist_name"] == aart)
        ].sort_values("billboard_week")
        if grp.empty:
            return None
        aps_val, aps_rank = _get_ps_rank(album_power_scores, "album_name", aname, aart)

        # Track-level stats via release group members
        member_names = _resolve_album_members_vs(aname, aart)
        album_tracks = weekly[weekly["album_name"].isin(member_names)]
        num_tracks = int(album_tracks["track_id"].nunique())
        num_no1_tracks = int(album_tracks[album_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_weeks = int((album_tracks["rank"] == 1).sum())

        # Sum of track power scores
        album_track_ids = album_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(track_power_scores[
                track_power_scores["track_id"].isin(album_track_ids)
            ]["power_score"].sum())

        return {
            "name": f"{aname} — {aart}",
            "album_name": aname,
            "artist_name": aart,
            "rank_history": [
                {"week": str(r["billboard_week"]), "rank": int(r["rank"]), "play_count": int(r["play_count"])}
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": aps_val,
                "power_rank": aps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "num_tracks": num_tracks,
                "num_no1_tracks": num_no1_tracks,
                "total_no1_track_weeks": total_no1_weeks,
                "track_power_sum": track_ps_sum,
                "total_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _album_data(aname_a, aart_a)
    result_b = _album_data(aname_b, aart_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一张专辑在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b}


def get_versus_artist(sel_a, sel_b, min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
                      bb_week_start_dow, bb_week_start_hour, year_start, year_end):
    """Compare two artists side-by-side."""
    data = compute_billboard_data(
        min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
        bb_week_start_dow, bb_week_start_hour, year_start, year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_artist = pd.DataFrame(data["weekly_artist"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    artist_power_scores = pd.DataFrame(data["artist_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])

    def _artist_data(artist_name):
        grp = weekly_artist[weekly_artist["artist_name"] == artist_name].sort_values("billboard_week")
        if grp.empty:
            return None
        aps_val, aps_rank = _get_ps_rank(artist_power_scores, "artist_name", artist_name)

        # Track-level stats
        artist_tracks = weekly[weekly["artist_name"] == artist_name]
        num_tracks = int(artist_tracks["track_id"].nunique())
        num_no1_tracks = int(artist_tracks[artist_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_track_weeks = int((artist_tracks["rank"] == 1).sum())

        # Sum of track power scores
        artist_track_ids = artist_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(track_power_scores[
                track_power_scores["track_id"].isin(artist_track_ids)
            ]["power_score"].sum())

        # Album-level stats
        artist_albums = weekly_album[weekly_album["artist_name"] == artist_name]
        num_albums = int(artist_albums["album_name"].dropna().nunique())
        num_no1_albums = int(artist_albums[artist_albums["rank"] == 1]["album_name"].nunique())
        total_no1_album_weeks = int((artist_albums["rank"] == 1).sum())

        # Sum of album power scores
        album_ps_sum = 0
        if album_power_scores is not None and len(album_power_scores) > 0:
            album_ps_sum = int(album_power_scores[
                album_power_scores["artist_name"] == artist_name
            ]["power_score"].sum())

        return {
            "name": artist_name,
            "rank_history": [
                {"week": str(r["billboard_week"]), "rank": int(r["rank"]), "play_count": int(r["play_count"])}
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": aps_val,
                "power_rank": aps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "num_tracks": num_tracks,
                "num_no1_tracks": num_no1_tracks,
                "total_no1_track_weeks": total_no1_track_weeks,
                "track_power_sum": track_ps_sum,
                "num_albums": num_albums,
                "num_no1_albums": num_no1_albums,
                "total_no1_album_weeks": total_no1_album_weeks,
                "album_power_sum": album_ps_sum,
                "total_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _artist_data(sel_a)
    result_b = _artist_data(sel_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一位艺人在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b}


def get_billboard_entity_lists(min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
                                bb_week_start_dow, bb_week_start_hour, year_start, year_end):
    """Return entity lists for versus search pickers (tracks, albums, artists)."""
    data = compute_billboard_data(
        min_ms, music_only, bb_top_n, bb_album_top_n, bb_artist_top_n,
        bb_week_start_dow, bb_week_start_hour, year_start, year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    weekly_artist = pd.DataFrame(data["weekly_artist"])

    # Tracks: (display_name, track_id)
    track_agg = weekly.groupby(["track_id", "track_name", "artist_name"])["play_count"].sum().reset_index()
    track_agg = track_agg.sort_values("play_count", ascending=False)
    tracks = [
        {"display": f"{r['track_name']} — {r['artist_name']}", "track_id": r["track_id"]}
        for _, r in track_agg.iterrows()
    ]

    # Albums: (display_name, (album_name, artist_name))
    album_agg = weekly_album.groupby(["album_name", "artist_name"])["play_count"].sum().reset_index()
    album_agg = album_agg.sort_values("play_count", ascending=False)
    albums = [
        {"display": f"{r['album_name']} — {r['artist_name']}", "album_name": r["album_name"], "artist_name": r["artist_name"]}
        for _, r in album_agg.iterrows()
    ]

    # Artists
    artist_agg = weekly_artist.groupby("artist_name")["play_count"].sum().reset_index()
    artist_agg = artist_agg.sort_values("play_count", ascending=False)
    artists = [{"display": r["artist_name"], "artist_name": r["artist_name"]} for _, r in artist_agg.iterrows()]

    return {"tracks": tracks, "albums": albums, "artists": artists}
