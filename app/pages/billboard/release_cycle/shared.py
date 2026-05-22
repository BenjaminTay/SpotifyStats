"""发行周期分析 — 数据加载与指标计算."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import streamlit as st
import pandas as pd
import numpy as np

from app.db import get_db


def load_artist_list(df_raw):
    """从 df_raw 中提取所有艺人名列表（按入榜曲数降序）。"""
    artists = (
        df_raw.groupby("artist_name")["track_id"]
        .nunique()
        .sort_values(ascending=False)
        .reset_index()
    )
    artists.columns = ["artist_name", "track_count"]
    return artists["artist_name"].tolist()


def _verify_album_artists(spotify_album_ids, artist_name):
    """验证专辑的主艺人是否包含目标艺人。优先读 DB，缺失时批量调 API。

    返回 (valid_ids, unknown_ids):
      valid_ids: 验证通过的 spotify_album_id
      unknown_ids: DB 中无 album_artists 且 API 也无法获取的 id（降级为信任）
    """
    import json

    if not spotify_album_ids:
        return set(), set()

    conn = get_db()
    artist_lower = artist_name.lower()
    verified = set()
    need_api = []

    # 1) 从 DB 中读取已有 album_artists 的，直接验证
    placeholders = ",".join("?" for _ in spotify_album_ids)
    rows = pd.read_sql_query(
        f"SELECT spotify_album_id, album_artists FROM spotify_album_meta "
        f"WHERE spotify_album_id IN ({placeholders})",
        conn,
        params=list(spotify_album_ids),
    )
    conn.close()

    db_ids = set()
    for _, row in rows.iterrows():
        db_id = row["spotify_album_id"]
        db_ids.add(db_id)
        artists_str = row.get("album_artists")
        if artists_str:
            artists = [a.strip().lower() for a in artists_str.split(",")]
            if artist_lower in artists:
                verified.add(db_id)
            # album_artists 非空但不包含目标艺人 → 合辑，不加入 verified
        else:
            # album_artists 为空，需要 API 补充
            need_api.append(db_id)

    # 不在 DB 中的 id 也加入 need_api（可能 spotify_album_meta 缺行）
    for sid in spotify_album_ids:
        if sid not in db_ids:
            need_api.append(sid)

    # 2) 对缺失 album_artists 的，批量调 Spotify API
    if need_api:
        api_verified = _fetch_album_artists_from_api(need_api, artist_name)
        verified.update(api_verified)
        # API 成功获取但未匹配的 id 不会被加入 verified，不被信任
        # API 网络失败时会返回整个 need_api 集合（降级信任）

    return verified


def _fetch_album_artists_from_api(spotify_album_ids, artist_name):
    """批量调用 Spotify /v1/albums?ids= 获取专辑主艺人并持久化到 DB。

    返回 set: 验证通过的 spotify_album_id。
    网络/认证失败时返回全部输入 ids（降级为信任数据库结果）。
    """
    import json
    import base64
    import urllib.request
    import urllib.parse
    import urllib.error

    if not spotify_album_ids:
        return set()

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    env_path = os.path.join(project_root, ".env")

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if (not client_id or not client_secret) and os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "SPOTIFY_CLIENT_ID":
                    client_id = v
                elif k == "SPOTIFY_CLIENT_SECRET":
                    client_secret = v

    if not client_id or not client_secret:
        return set(spotify_album_ids)

    try:
        auth_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            token = json.loads(resp.read().decode())["access_token"]
    except Exception:
        return set(spotify_album_ids)

    verified = set()
    ids_list = list(dedup_preserve_order(spotify_album_ids))
    artist_lower = artist_name.lower()

    conn = get_db(readonly=False)

    for i in range(0, len(ids_list), 20):
        batch = ids_list[i:i + 20]
        try:
            url = f"https://api.spotify.com/v1/albums?ids={','.join(batch)}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            for album in data.get("albums", []):
                if album is None:
                    continue

                artist_names = [a["name"] for a in album.get("artists", [])]
                album_artists_str = ", ".join(artist_names)
                album_artists_lower = [n.lower() for n in artist_names]

                # 持久化到 DB：下次启动/刷新直接从 DB 验证，不再调 API
                try:
                    genres = json.dumps(album.get("genres", []), ensure_ascii=False) if album.get("genres") else None
                    img_url = album["images"][0]["url"] if album.get("images") else None
                    conn.execute(
                        """INSERT OR REPLACE INTO spotify_album_meta(
                               spotify_album_id, album_name, album_type, release_date,
                               popularity, label, genres, image_url, album_artists)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            album["id"],
                            album["name"],
                            album.get("album_type"),
                            album.get("release_date"),
                            album.get("popularity"),
                            album.get("label"),
                            genres,
                            img_url,
                            album_artists_str,
                        ),
                    )
                except Exception:
                    pass

                if artist_lower in album_artists_lower:
                    verified.add(album["id"])

        except Exception:
            # 单批失败时信任该批所有 id，避免因网络问题丢数据
            verified.update(batch)

    conn.commit()
    conn.close()
    return verified


def dedup_preserve_order(seq):
    """列表去重保持顺序。"""
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


@st.cache_data(ttl=3600)
def load_artist_releases(artist_name):
    """获取某艺人的所有发行（专辑+单曲），含发行日期和类型。

    通过 artists → albums → track_albums → tracks → spotify_track_meta → spotify_album_meta
    链式 JOIN 获取。排除 compilation 类型，并通过 Spotify API 验证专辑主艺人。
    """
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT DISTINCT
               sam.album_name,
               sam.album_type,
               sam.release_date,
               sam.spotify_album_id
           FROM artists a
           JOIN albums al ON al.artist_id = a.artist_id
           JOIN track_albums ta ON ta.album_id = al.album_id
           JOIN tracks t ON t.track_id = ta.track_id
           JOIN spotify_track_meta stm
             ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
           JOIN spotify_album_meta sam
             ON stm.spotify_album_id = sam.spotify_album_id
           WHERE a.artist_name = ?
             AND sam.album_type IN ('album', 'single')
             AND sam.release_date IS NOT NULL
           ORDER BY sam.release_date""",
        conn,
        params=[artist_name],
    )
    conn.close()

    if df.empty:
        return df

    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df.dropna(subset=["release_date"])
    df = df.sort_values("release_date").reset_index(drop=True)

    # 通过 Spotify API 验证专辑主艺人，过滤群星合辑（如 HELP(2)）
    unique_album_ids = set(df["spotify_album_id"].dropna().unique())
    if unique_album_ids:
        valid_ids = _verify_album_artists(unique_album_ids, artist_name)
        df = df[df["spotify_album_id"].isin(valid_ids)]

    return df


def compute_artist_play_timeline(df_raw, artist_name):
    """计算某艺人每周的播放量和曲目数（全量，不限 Top N）。"""
    artist_df = df_raw[df_raw["artist_name"] == artist_name]
    if artist_df.empty:
        return pd.DataFrame()
    weekly = (
        artist_df.groupby("billboard_week")
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    return weekly.sort_values("billboard_week")


def compute_album_play_timeline(df_raw, artist_name, album_name):
    """计算某专辑每周的播放量和曲目数（全量）。"""
    album_df = df_raw[
        (df_raw["artist_name"] == artist_name) & (df_raw["album_name"] == album_name)
    ]
    if album_df.empty:
        return pd.DataFrame()
    weekly = (
        album_df.groupby("billboard_week")
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    return weekly.sort_values("billboard_week")


def compute_track_timelines(df_raw, artist_name, album_name):
    """获取专辑中每首歌的每周播放量。"""
    album_df = df_raw[
        (df_raw["artist_name"] == artist_name) & (df_raw["album_name"] == album_name)
    ]
    if album_df.empty:
        return pd.DataFrame()
    weekly = (
        album_df.groupby(["billboard_week", "track_id", "track_name"])
        .agg(play_count=("ms_played", "count"))
        .reset_index()
    )
    return weekly.sort_values(["billboard_week", "play_count"], ascending=[True, False])


def align_to_release(weekly_df, release_date, weeks_before=12, weeks_after=24):
    """将周数据按发行日对齐，添加 week_offset 列。

    week_offset: 0 = 发行周，负数为发行前，正数为发行后。
    """
    if weekly_df.empty:
        return weekly_df

    release_date = pd.to_datetime(release_date)
    weekly_df = weekly_df.copy()
    weekly_df["bw_dt"] = pd.to_datetime(weekly_df["billboard_week"])
    weekly_df["week_offset"] = (
        (weekly_df["bw_dt"] - release_date).dt.days / 7.0
    ).apply(lambda x: int(round(x)))

    weekly_df = weekly_df[
        (weekly_df["week_offset"] >= -weeks_before)
        & (weekly_df["week_offset"] <= weeks_after)
    ]
    return weekly_df.drop(columns=["bw_dt"])


def compute_release_cycle(df_raw, artist_name, album_name, release_date,
                          weekly_artist=None, weekly_album=None,
                          weeks_before=12, weeks_after=24):
    """以发行日为锚点，聚合发行周期内的所有数据。

    Returns dict:
        artist_timeline, album_timeline, track_timelines,
        artist_ranks, album_ranks, release_date
    """
    result = {
        "release_date": pd.to_datetime(release_date),
        "artist_timeline": pd.DataFrame(),
        "album_timeline": pd.DataFrame(),
        "track_timelines": pd.DataFrame(),
        "artist_ranks": pd.DataFrame(),
        "album_ranks": pd.DataFrame(),
    }

    artist_tl = compute_artist_play_timeline(df_raw, artist_name)
    result["artist_timeline"] = align_to_release(artist_tl, release_date, weeks_before, weeks_after)

    album_tl = compute_album_play_timeline(df_raw, artist_name, album_name)
    result["album_timeline"] = align_to_release(album_tl, release_date, weeks_before, weeks_after)

    track_tl = compute_track_timelines(df_raw, artist_name, album_name)
    result["track_timelines"] = align_to_release(track_tl, release_date, weeks_before, weeks_after)

    if weekly_artist is not None:
        art_ranks = weekly_artist[weekly_artist["artist_name"] == artist_name][
            ["billboard_week", "rank", "play_count"]
        ].copy()
        result["artist_ranks"] = align_to_release(art_ranks, release_date, weeks_before, weeks_after)

    if weekly_album is not None:
        alb_ranks = weekly_album[
            (weekly_album["artist_name"] == artist_name)
            & (weekly_album["album_name"] == album_name)
        ][["billboard_week", "rank", "play_count"]].copy()
        result["album_ranks"] = align_to_release(alb_ranks, release_date, weeks_before, weeks_after)

    return result


def compute_release_metrics(cycle_data, album_type="album"):
    """从 release_cycle 结果中计算各项指标。

    Returns dict with keys: debut_rank, peak_rank, weeks_to_peak,
        weeks_on_chart, impact_force, half_life, peak_play_count,
        release_week_plays, pre_release_avg
    """
    metrics = {
        "debut_rank": None,
        "peak_rank": None,
        "weeks_to_peak": None,
        "weeks_on_chart": 0,
        "impact_force": None,
        "half_life": None,
        "peak_play_count": 0,
        "release_week_plays": 0,
        "pre_release_avg": 0,
    }

    atl = cycle_data.get("album_timeline", pd.DataFrame())
    if atl.empty:
        return metrics

    release_row = atl[atl["week_offset"] == 0]
    if not release_row.empty:
        metrics["release_week_plays"] = int(release_row["play_count"].iloc[0])

    pre_rows = atl[(atl["week_offset"] >= -4) & (atl["week_offset"] <= -1)]
    if not pre_rows.empty:
        metrics["pre_release_avg"] = float(pre_rows["play_count"].mean())

    post_rows = atl[(atl["week_offset"] >= 0) & (atl["week_offset"] <= 24)]
    if not post_rows.empty:
        peak_row = post_rows.loc[post_rows["play_count"].idxmax()]
        metrics["peak_play_count"] = int(peak_row["play_count"])

    pre_avg = metrics["pre_release_avg"]
    peak_plays = metrics["peak_play_count"]
    if pre_avg > 0 and peak_plays > 0:
        metrics["impact_force"] = round((peak_plays - pre_avg) / pre_avg * 100, 1)

    if peak_plays > 0 and not post_rows.empty:
        peak_offset = int(post_rows.loc[post_rows["play_count"].idxmax(), "week_offset"])
        decay_rows = atl[
            (atl["week_offset"] > peak_offset)
            & (atl["play_count"] <= peak_plays * 0.5)
        ]
        if not decay_rows.empty:
            decay_offset = int(decay_rows["week_offset"].min())
            metrics["half_life"] = decay_offset - peak_offset

    ar = cycle_data.get("album_ranks", pd.DataFrame())
    if not ar.empty:
        metrics["peak_rank"] = int(ar["rank"].min())
        metrics["weeks_on_chart"] = int(ar["billboard_week"].nunique())

        debut = ar[ar["week_offset"] == 0]
        if not debut.empty:
            metrics["debut_rank"] = int(debut["rank"].iloc[0])

        peak_rank = metrics["peak_rank"]
        peak_rows = ar[ar["rank"] == peak_rank]
        if not peak_rows.empty and peak_rank is not None:
            first_peak_offset = int(peak_rows["week_offset"].min())
            first_entry = int(ar["week_offset"].min())
            metrics["weeks_to_peak"] = first_peak_offset - first_entry

    return metrics


def compute_artist_summary(artist_name, releases_df, df_raw, weekly_artist, weekly_album):
    """计算艺人级别的汇总指标。"""
    summary = {
        "total_albums": 0,
        "total_singles": 0,
        "debut_no1_count": 0,
        "max_impact": 0.0,
        "max_impact_album": "",
        "total_catalog_reentries": 0,
    }

    if releases_df.empty:
        return summary

    albums = releases_df[releases_df["album_type"] == "album"]
    singles = releases_df[releases_df["album_type"] == "single"]
    summary["total_albums"] = len(albums)
    summary["total_singles"] = len(singles)

    for _, rel in releases_df.iterrows():
        album_name = rel["album_name"]
        release_date = rel["release_date"]
        album_type = rel["album_type"]

        cycle = compute_release_cycle(
            df_raw, artist_name, album_name, release_date,
            weekly_artist=weekly_artist, weekly_album=weekly_album,
            weeks_before=4, weeks_after=24,
        )
        metrics = compute_release_metrics(cycle, album_type)

        if metrics["debut_rank"] == 1:
            summary["debut_no1_count"] += 1

        if metrics["impact_force"] is not None and metrics["impact_force"] > summary["max_impact"]:
            summary["max_impact"] = metrics["impact_force"]
            summary["max_impact_album"] = album_name

        if album_type == "album":
            reentries = detect_catalog_reentries(
                df_raw, artist_name, release_date, album_name
            )
            summary["total_catalog_reentries"] += len(reentries)

    return summary


def _save_album_meta_to_db(spotify_album_id, album_name, album_type, release_date,
                          album_artists=None):
    """将 Spotify 专辑元数据持久化到 spotify_album_meta 表。

    已有行不会丢失其他列的数据（INSERT OR REPLACE 仅覆盖提供的列）。
    """
    try:
        conn = get_db(readonly=False)
        conn.execute(
            """INSERT OR REPLACE INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date, album_artists)
               VALUES (?, ?, ?, ?, ?)""",
            (spotify_album_id, album_name, album_type, release_date, album_artists),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _spotify_search_album(album_name, artist_name):
    """通过 Spotify API 搜索专辑/单曲元数据。返回 dict 或 None。

    成功获取的元数据会持久化到 spotify_album_meta 表，避免重复调用 API。
    """
    import json
    import base64
    import urllib.request
    import urllib.parse
    import urllib.error

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    env_path = os.path.join(project_root, ".env")

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if (not client_id or not client_secret) and os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "SPOTIFY_CLIENT_ID":
                    client_id = v
                elif k == "SPOTIFY_CLIENT_SECRET":
                    client_secret = v

    if not client_id or not client_secret:
        return None

    try:
        auth_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            token = json.loads(resp.read().decode())["access_token"]
    except Exception:
        return None

    try:
        q = urllib.parse.quote(f"album:{album_name} artist:{artist_name}")
        url = f"https://api.spotify.com/v1/search?q={q}&type=album&limit=5"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        for album in data.get("albums", {}).get("items", []):
            if album["name"].lower() == album_name.lower():
                # 提取主艺人列表
                artist_names = [a["name"] for a in album.get("artists", [])]
                album_artists = ", ".join(artist_names) if artist_names else None

                result = {
                    "album_name": album["name"],
                    "album_type": album.get("album_type"),
                    "release_date": album.get("release_date"),
                    "spotify_album_id": album["id"],
                }
                # 持久化到数据库，下次启动/刷新直接从 DB 读取
                _save_album_meta_to_db(
                    album["id"], album["name"],
                    album.get("album_type"), album.get("release_date"),
                    album_artists=album_artists,
                )
                return result
    except Exception:
        pass

    return None


@st.cache_data(ttl=3600)
def get_advance_singles(artist_name, album_name):
    """获取专辑的所有先行单曲。

    三级查找策略：
    ① spotify_album_meta 库内匹配
    ② Spotify API 实时搜索（补全库内缺失的单曲元数据）
    ③ 最早播放日期启发式兜底（无 API 凭据时的降级方案）
    """
    releases = load_artist_releases(artist_name)
    album_row = releases[releases["album_name"] == album_name]
    if album_row.empty:
        return []

    album_release_date = album_row["release_date"].iloc[0]

    conn = get_db()
    # Find all albums in local DB that share tracks with the target album
    shared = pd.read_sql_query(
        """SELECT DISTINCT al_other.album_name, al_other.album_id
           FROM artists a
           JOIN albums al_target ON al_target.artist_id = a.artist_id AND al_target.album_name = ?
           JOIN track_albums ta_target ON ta_target.album_id = al_target.album_id
           JOIN track_albums ta_other
             ON ta_other.track_id = ta_target.track_id
             AND ta_other.album_id != ta_target.album_id
           JOIN albums al_other ON al_other.album_id = ta_other.album_id
           WHERE a.artist_name = ?""",
        conn,
        params=[album_name, artist_name],
    )

    if shared.empty:
        conn.close()
        return []

    results = []
    for _, row in shared.iterrows():
        candidate_name = row["album_name"]

        # Tier 1: spotify_album_meta by album name
        meta = pd.read_sql_query(
            "SELECT album_type, release_date FROM spotify_album_meta WHERE album_name = ? LIMIT 1",
            conn,
            params=[candidate_name],
        )

        release_date = None
        if not meta.empty and meta["album_type"].iloc[0] == "single":
            release_date = pd.to_datetime(meta["release_date"].iloc[0])

        # Tier 2: Spotify API search
        if release_date is None:
            spotify_meta = _spotify_search_album(candidate_name, artist_name)
            if spotify_meta and spotify_meta.get("album_type") == "single":
                release_date = pd.to_datetime(spotify_meta["release_date"])

        # Tier 3: earliest play date heuristic
        if release_date is None:
            earliest = pd.read_sql_query(
                """SELECT MIN(p.ts_date) AS first_play
                   FROM track_albums ta
                   JOIN plays p ON p.track_id = ta.track_id
                   WHERE ta.album_id = ?""",
                conn,
                params=[int(row["album_id"])],
            )
            if not earliest.empty and earliest["first_play"].iloc[0] is not None:
                release_date = pd.to_datetime(earliest["first_play"].iloc[0])

        if release_date is not None and release_date < album_release_date:
            results.append({
                "single_name": candidate_name,
                "release_date": release_date,
            })

    conn.close()

    if not results:
        return []

    results.sort(key=lambda x: x["release_date"])
    return results


def detect_catalog_reentries(df_raw, artist_name, release_date, current_album_name,
                              pre_window=4, post_window=24):
    """检测发行后老歌回榜。

    Returns list[dict]: [{track_name, source_album, reentry_offset, weeks_in_chart}]
    """
    release_date = pd.to_datetime(release_date)
    artist_df = df_raw[df_raw["artist_name"] == artist_name].copy()

    releases = load_artist_releases(artist_name)
    if releases.empty:
        return []

    current_rel = releases[releases["album_name"] == current_album_name]
    if current_rel.empty:
        return []

    current_rel_date = pd.to_datetime(current_rel["release_date"].iloc[0])
    earlier_albums = releases[
        pd.to_datetime(releases["release_date"]) < current_rel_date
    ]["album_name"].tolist()

    old_songs = artist_df[artist_df["album_name"].isin(earlier_albums)]
    if old_songs.empty:
        return []

    old_songs["bw_dt"] = pd.to_datetime(old_songs["billboard_week"])
    old_songs["week_offset"] = (
        (old_songs["bw_dt"] - release_date).dt.days / 7.0
    ).apply(lambda x: int(round(x)))

    pre_mask = (old_songs["week_offset"] >= -pre_window) & (old_songs["week_offset"] <= -1)
    pre_active_tracks = set(old_songs[pre_mask]["track_id"].unique())

    post_mask = (old_songs["week_offset"] >= 1) & (old_songs["week_offset"] <= post_window)
    post_data = old_songs[post_mask]

    if post_data.empty:
        return []

    reentries = []
    for track_id, group in post_data.groupby("track_id"):
        if track_id in pre_active_tracks:
            continue

        track_name = group["track_name"].iloc[0]
        source_album = group["album_name"].iloc[0]
        reentry_offset = int(group["week_offset"].min())
        weeks_in_chart = int(group["billboard_week"].nunique())

        reentries.append({
            "track_name": track_name,
            "source_album": source_album,
            "reentry_offset": reentry_offset,
            "weeks_in_chart": weeks_in_chart,
        })

    return sorted(reentries, key=lambda x: x["reentry_offset"])
