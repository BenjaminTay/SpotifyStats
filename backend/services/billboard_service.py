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

    # Running peak weeks (cumulative)
    wp = weekly.merge(
        track_summary[["track_id", "peak_position"]], on="track_id", how="left"
    )
    wp = wp.sort_values(["track_id", "billboard_week"])
    wp["at_peak"] = (wp["rank"] == wp["peak_position"]).astype(int)
    wp["running_peak_wks"] = wp.groupby("track_id")["at_peak"].cumsum()
    weekly = wp.drop(columns=["peak_position", "at_peak"])

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
