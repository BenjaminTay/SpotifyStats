"""发行周期分析 — 数据加载与指标计算."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import streamlit as st
import pandas as pd
import numpy as np

from app.db import get_db
from app.version_merge import get_album_group_mapping, normalize_album_name


@st.cache_data(ttl=3600)
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


@st.cache_data(ttl=3500)
def _get_spotify_token():
    """获取 Spotify client_credentials token，缓存 ~58 分钟（token 有效期 1 小时）。

    所有 Spotify API 调用共享此函数，避免每次独立请求 token。
    """
    import json
    import base64
    import urllib.request
    import urllib.parse

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
        return json.loads(resp.read().decode())["access_token"]


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
    import urllib.request
    import urllib.parse
    import urllib.error

    if not spotify_album_ids:
        return set()

    token = _get_spotify_token()
    if not token:
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
                        """INSERT INTO spotify_album_meta(
                               spotify_album_id, album_name, album_type, release_date,
                               popularity, label, genres, image_url, album_artists)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(spotify_album_id) DO UPDATE SET
                               album_name = excluded.album_name,
                               album_type = excluded.album_type,
                               release_date = excluded.release_date,
                               popularity = excluded.popularity,
                               label = excluded.label,
                               genres = excluded.genres,
                               image_url = excluded.image_url,
                               album_artists = excluded.album_artists""",
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
    自动过滤 release group 中非 primary 的成员，避免发行列表重复。

    Returns DataFrame with columns:
      album_name, album_type, release_date, spotify_album_id,
      db_album_id, db_album_name, is_primary
    """
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT DISTINCT
               sam.album_name,
               sam.album_type,
               sam.release_date,
               sam.spotify_album_id,
               al.album_id AS db_album_id,
               al.album_name AS db_album_name,
               a.artist_name
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
    df = df.sort_values("release_date", ascending=False).reset_index(drop=True)

    # 通过 Spotify API 验证专辑主艺人，过滤群星合辑（如 HELP(2)）
    unique_album_ids = set(df["spotify_album_id"].dropna().unique())
    if unique_album_ids:
        valid_ids = _verify_album_artists(unique_album_ids, artist_name)
        df = df[df["spotify_album_id"].isin(valid_ids)]

    # 过滤 release group 中非 primary 的成员
    df = _filter_release_group_duplicates(df)

    # 去重：同一 spotify_album_id 可能关联多个 al.album_id（曲目共享导致）。
    # 优先保留 album_name == db_album_name 的"原生"行，防止错位行挤掉正确行。
    df["_is_native"] = df["album_name"] == df["db_album_name"]
    df = df.sort_values("_is_native", ascending=False)
    df = df.drop_duplicates(subset=["spotify_album_id"], keep="first")
    df = df.drop(columns=["_is_native"])
    df = df.sort_values("release_date", ascending=False).reset_index(drop=True)

    return df


def _filter_release_group_duplicates(releases_df):
    """移除 release group 中非 primary 的成员，避免发行列表重复。

    匹配键使用 spotify_album_id（稳定 Spotify ID），而非 db_album_id
    （albums 表主键），因为同一张 Spotify 专辑可通过 track_albums 链
    关联到多个不同的 albums 行，导致 db_album_id 不可靠。

    保留规则：
      - 不在任何 group 中的 → 保留
      - 是 group 的 primary 成员 → 保留，新增 canonical_name 列
      - 是 group 的非 primary 成员 → 移除（但其信息存入 primary 行的 sub_albums 列）
    """
    import json

    releases_df["canonical_name"] = None
    releases_df["sub_albums"] = None

    if releases_df.empty:
        return releases_df

    # 获取 releases_df 涉及的艺人列表
    artists = releases_df["artist_name"].dropna().unique().tolist()
    if not artists:
        return releases_df

    conn = get_db()
    artist_placeholders = ",".join("?" for _ in artists)

    # 查询相关艺人的所有 release groups，并通过 track_albums 链
    # 映射到稳定的 spotify_album_id
    members = pd.read_sql_query(
        f"""SELECT DISTINCT al.album_id, al.album_name, a.artist_name,
                   rg.canonical_name, rg.primary_album_id,
                   sam.spotify_album_id
            FROM release_group_members rgm
            JOIN release_groups rg ON rgm.group_id = rg.group_id
            JOIN albums al ON rgm.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            JOIN track_albums ta ON ta.album_id = al.album_id
            JOIN tracks t ON t.track_id = ta.track_id
            JOIN spotify_track_meta stm
              ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
            JOIN spotify_album_meta sam
              ON stm.spotify_album_id = sam.spotify_album_id
            WHERE a.artist_name IN ({artist_placeholders})""",
        conn,
        params=list(artists),
    )
    conn.close()

    if members.empty:
        return releases_df

    # 按 canonical_name 分组，收集 primary 和 non-primary 的 spotify_album_id
    groups = {}  # canonical_name → {primary_sids: set, non_primary_sids: set}
    for _, row in members.iterrows():
        canonical = row["canonical_name"]
        sid = row["spotify_album_id"]
        aid = int(row["album_id"])
        primary_aid = int(row["primary_album_id"])

        if canonical not in groups:
            groups[canonical] = {"primary_sids": set(), "non_primary_sids": set()}

        if aid == primary_aid:
            groups[canonical]["primary_sids"].add(sid)
        else:
            groups[canonical]["non_primary_sids"].add(sid)

    # 从 non_primary_sids 中排除也出现在 primary_sids 中的（共享 spotify_album_id）
    for canonical, g in groups.items():
        g["non_primary_sids"] -= g["primary_sids"]

    # 每个 canonical group 只保留一个「展示主条目」：album_name 匹配 canonical_name 的优先，
    # 其余 primary spotify_album_id 降级为子专辑（同一 albums 行可能关联多个 Spotify 专辑）
    sid_to_album_name = dict(zip(releases_df["spotify_album_id"], releases_df["album_name"]))
    for canonical, g in groups.items():
        if len(g["primary_sids"]) <= 1:
            continue
        # 优先选 album_name == canonical_name 的，其次选最早发行的
        best = None
        best_name = None
        for sid in g["primary_sids"]:
            name = sid_to_album_name.get(sid, "")
            if name.lower() == canonical.lower():
                best = sid
                best_name = name
                break
            if best is None:
                best = sid
                best_name = name
        # 将其余 primary_sids 降级为 non-primary
        demoted = g["primary_sids"] - {best}
        g["primary_sids"] = {best}
        g["non_primary_sids"] |= demoted

    # 构建 spotify_album_id → canonical_name 的映射
    non_primary_sids = set()
    sid_to_canonical = {}
    primary_sid_to_canonical = {}

    for canonical, g in groups.items():
        for sid in g["primary_sids"]:
            primary_sid_to_canonical[sid] = canonical
        for sid in g["non_primary_sids"]:
            non_primary_sids.add(sid)
            sid_to_canonical[sid] = canonical

    # 过滤：单曲不应被合并到专辑中（单曲是独立发行，非专辑子版本）
    if non_primary_sids:
        sid_to_type = dict(zip(releases_df["spotify_album_id"], releases_df["album_type"]))
        filtered_sids = set()
        for sid in non_primary_sids:
            canonical = sid_to_canonical.get(sid)
            rel_type = sid_to_type.get(sid, "unknown")
            # 找到此 canonical 对应的 primary spotify_album_id
            primary_sid = None
            for psid, canon in primary_sid_to_canonical.items():
                if canon == canonical:
                    primary_sid = psid
                    break
            primary_type = sid_to_type.get(primary_sid, "unknown") if primary_sid else "unknown"
            if rel_type == "single" and primary_type == "album":
                continue
            filtered_sids.add(sid)
        non_primary_sids = filtered_sids

    if not non_primary_sids:
        # 只有 primary 成员，标记 canonical_name
        for sid, canonical in primary_sid_to_canonical.items():
            releases_df.loc[releases_df["spotify_album_id"] == sid, "canonical_name"] = canonical
        releases_df = releases_df.sort_values("release_date", ascending=False).reset_index(drop=True)
        return _ad_hoc_name_grouping(releases_df)

    # 从 releases_df 中 non-primary 行提取子专辑元数据
    sub_albums_by_canonical = {}  # canonical_name → [{album_name, release_date, album_type}]
    non_primary_rows = releases_df[releases_df["spotify_album_id"].isin(non_primary_sids)]

    for _, rel in non_primary_rows.iterrows():
        sid = rel["spotify_album_id"]
        canonical = sid_to_canonical.get(sid)
        if not canonical:
            continue
        sub_albums_by_canonical.setdefault(canonical, []).append({
            "album_name": rel["album_name"],
            "release_date": rel["release_date"].strftime("%Y-%m-%d") if pd.notna(rel["release_date"]) else None,
            "album_type": rel.get("album_type", "unknown"),
        })

    # 去重（同一 canonical 下按 album_name + release_date）
    for canonical in sub_albums_by_canonical:
        deduped = []
        seen = set()
        for sa in sub_albums_by_canonical[canonical]:
            key = (sa["album_name"], sa["release_date"])
            if key not in seen:
                seen.add(key)
                deduped.append(sa)
        deduped.sort(key=lambda x: x["release_date"] or "9999")
        sub_albums_by_canonical[canonical] = deduped

    # 移除非 primary 行（按 spotify_album_id）
    releases_df = releases_df[~releases_df["spotify_album_id"].isin(non_primary_sids)]

    # 标记 primary 行的 canonical_name + 子专辑信息
    for sid, canonical in primary_sid_to_canonical.items():
        mask = releases_df["spotify_album_id"] == sid
        releases_df.loc[mask, "canonical_name"] = canonical
        # 统一 primary 显示名为 canonical（处理同一 spotify_album 不同本地名）
        for idx in releases_df[mask].index:
            if releases_df.at[idx, "album_name"] != canonical:
                releases_df.at[idx, "album_name"] = canonical
        subs = sub_albums_by_canonical.get(canonical, [])
        if subs:
            releases_df.loc[mask, "sub_albums"] = json.dumps(subs, ensure_ascii=False)

    releases_df = releases_df.sort_values("release_date", ascending=False).reset_index(drop=True)
    return _ad_hoc_name_grouping(releases_df)


def _parse_sub_albums(raw):
    """解析 sub_albums JSON 字段，返回 list[dict]."""
    import json
    if pd.isna(raw) or not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _ad_hoc_name_grouping(releases_df):
    """Phase 2: 名称归一化 ad-hoc 分组。

    对未被 release_group_members 覆盖的专辑（canonical_name 为空），
    按 normalize_album_name 做临时分组。处理同一 album_id 对应多个
    spotify_album_id 的情况（如 1989 TV / 1989 TV [Deluxe]）。
    """
    import json

    ungrouped_mask = releases_df["canonical_name"].isna()
    ungrouped = releases_df[ungrouped_mask]

    if len(ungrouped) < 2:
        return releases_df

    to_drop = []
    to_update = {}  # primary_idx → (canonical_name, sub_albums_json)

    for artist in ungrouped["artist_name"].unique():
        artist_rows = ungrouped[ungrouped["artist_name"] == artist]
        if len(artist_rows) < 2:
            continue

        norms = artist_rows["album_name"].apply(normalize_album_name)
        for norm_name, count in norms.value_counts().items():
            if count < 2 or not norm_name:
                continue

            group_mask = norms == norm_name
            group = artist_rows[group_mask]

            if group["album_name"].nunique() < 2:
                continue

            # 选主版本：album_name == norm_name 的优先，其中原生行（album_name == db_album_name）更优先，其次最早发行
            exact = group[group["album_name"] == norm_name]
            if not exact.empty:
                native_exact = exact[exact["album_name"] == exact["db_album_name"]]
                if not native_exact.empty:
                    primary_idx = native_exact.index[0]
                else:
                    primary_idx = exact.index[0]
            else:
                native_group = group[group["album_name"] == group["db_album_name"]]
                if not native_group.empty:
                    primary_idx = native_group["release_date"].idxmin()
                else:
                    primary_idx = group["release_date"].idxmin()

            primary_name = releases_df.at[primary_idx, "album_name"]

            # 收集子专辑（排除与 primary 同名的行，例如不同 Spotify 专辑同名）
            sub_albums = []
            for idx in group.index:
                if idx == primary_idx:
                    continue
                row = releases_df.loc[idx]
                if row["album_name"] == primary_name:
                    to_drop.append(idx)
                    continue
                sub_albums.append({
                    "album_name": row["album_name"],
                    "release_date": row["release_date"].strftime("%Y-%m-%d")
                        if pd.notna(row["release_date"]) else None,
                    "album_type": row.get("album_type", "unknown"),
                })
                to_drop.append(idx)

            # 合并已有 sub_albums
            existing = _parse_sub_albums(releases_df.at[primary_idx, "sub_albums"])
            all_subs = existing + sub_albums
            deduped = []
            seen = set()
            for sa in all_subs:
                key = (sa["album_name"], sa["release_date"])
                if key not in seen:
                    seen.add(key)
                    deduped.append(sa)
            deduped.sort(key=lambda x: x["release_date"] or "9999")

            to_update[primary_idx] = (norm_name, json.dumps(deduped, ensure_ascii=False))

    # 应用更新
    for idx, (canonical, subs_json) in to_update.items():
        releases_df.at[idx, "canonical_name"] = canonical
        releases_df.at[idx, "sub_albums"] = subs_json
        if releases_df.at[idx, "album_name"] != canonical:
            releases_df.at[idx, "album_name"] = canonical

    if to_drop:
        releases_df = releases_df.drop(to_drop)

    return releases_df


@st.cache_data(ttl=3600)
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


def _resolve_album_group(artist_name, album_name):
    """返回给定专辑应包含的所有 album_name（含 release group 成员）。

    同时尝试按 albums.album_name 和 spotify_album_meta.album_name 匹配，
    以防调用方传入的是 Spotify 元数据中的名称。

    Returns:
        (album_names: list[str], canonical_name: str, primary_name: str)
        primary_name 是主版本在 albums 表中的名称，用于 DB 查询。
    """
    conn = get_db()

    row = None
    # 尝试 1: 直接按 albums.album_name 匹配
    row = conn.execute(
        """SELECT rg.canonical_name, pa.album_name AS primary_db_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id
           WHERE al.album_name = ? AND a.artist_name = ?""",
        [album_name, artist_name],
    ).fetchone()

    # 尝试 2: 通过 spotify_album_meta.album_name → track_albums 链匹配
    if not row:
        row = conn.execute(
            """SELECT rg.canonical_name, pa.album_name AS primary_db_name
               FROM release_group_members rgm
               JOIN release_groups rg ON rgm.group_id = rg.group_id
               JOIN track_albums ta ON ta.album_id = rgm.album_id
               JOIN tracks t ON t.track_id = ta.track_id
               JOIN spotify_track_meta stm
                 ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
               JOIN spotify_album_meta sam
                 ON stm.spotify_album_id = sam.spotify_album_id
               JOIN artists a ON a.artist_name = ?
               LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id
               WHERE sam.album_name = ? AND a.artist_name = ?
               LIMIT 1""",
            [artist_name, album_name, artist_name],
        ).fetchone()

    if not row:
        conn.close()
        return [album_name], album_name, album_name

    canonical = row[0]
    primary_db_name = row[1] or canonical
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
    return [m[0] for m in members], canonical, primary_db_name


def compute_album_play_timeline(df_raw, artist_name, album_name):
    """计算某专辑每周的播放量和曲目数（全量，含 release group 内所有版本）。"""
    album_names, _, _ = _resolve_album_group(artist_name, album_name)
    album_df = df_raw[
        (df_raw["artist_name"] == artist_name) & (df_raw["album_name"].isin(album_names))
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
    """获取专辑中每首歌的每周播放量（含 release group 内所有版本）。"""
    album_names, _, _ = _resolve_album_group(artist_name, album_name)
    album_df = df_raw[
        (df_raw["artist_name"] == artist_name) & (df_raw["album_name"].isin(album_names))
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


def _group_by_release_week(df, release_date, weeks_before, weeks_after):
    """按发行日锚定的精确7日窗口聚合每周播放次数。

    使用 ts_date_dt 直接计算 week_offset = (播放日 - 发行日).days // 7，
    不再依赖 billboard_week 对齐，避免周五发行日跨周导致的偏差。
    不 copy df，避免大 DataFrame 的深拷贝开销。
    """
    release_dt = pd.to_datetime(release_date)
    week_offset = (df["ts_date_dt"] - release_dt).dt.days // 7

    mask = (week_offset >= -weeks_before) & (week_offset <= weeks_after)
    if not mask.any():
        return pd.DataFrame()

    filtered = df.loc[mask]
    filtered_offsets = week_offset.loc[mask]

    weekly = (
        filtered.groupby(filtered_offsets)
        .agg(play_count=("ms_played", "count"),
             total_ms=("ms_played", "sum"),
             tracks_count=("track_id", "nunique"))
        .reset_index()
    )
    weekly.columns = ["week_offset", "play_count", "total_ms", "tracks_count"]
    return weekly.sort_values("week_offset")


def compute_release_cycle(df_raw, artist_name, album_name, release_date,
                          weekly_artist=None, weekly_album=None,
                          weeks_before=12, weeks_after=24,
                          artist_df=None, artist_median=None, total_daily=None):
    """以发行日为锚点，聚合发行周期内的所有数据。

    播放量统计使用精确7日窗口（从发行日当天起算），消除 Billboard 周边界偏差。
    排名数据仍基于 Billboard 周（weekly_artist/weekly_album）。

    可选预计算参数（同艺人多次调用时复用，避免重复过滤/聚合）：
        artist_df:     df_raw[df_raw["artist_name"] == artist_name] 的预过滤结果
        artist_median: 艺人全时段周播放中位数（float）
        total_daily:   df_raw 按 ts_date_dt 聚合的每日播放量 Series
    """
    album_info = _resolve_album_group(artist_name, album_name)
    canonical = album_info[1]
    album_names = album_info[0]
    release_dt = pd.to_datetime(release_date)

    result = {
        "release_date": release_dt,
        "artist_timeline": pd.DataFrame(),
        "album_timeline": pd.DataFrame(),
        "track_timelines": pd.DataFrame(),
        "artist_ranks": pd.DataFrame(),
        "album_ranks": pd.DataFrame(),
        "total_timeline": pd.DataFrame(),
        "artist_all_time_median": 0,
    }

    # ── 艺人数据（优先用预计算） ──────────────────────────────────────
    if artist_df is None:
        artist_df = df_raw[df_raw["artist_name"] == artist_name]

    # ── 艺人全时段中位数 ────────────────────────────────────────────
    if artist_median is not None:
        result["artist_all_time_median"] = artist_median
    elif not artist_df.empty:
        dow = artist_df["ts_date_dt"].dt.dayofweek
        week_start = artist_df["ts_date_dt"] - pd.to_timedelta(dow, unit="D")
        artist_all_agg = (
            artist_df.groupby(week_start)
            .agg(play_count=("ms_played", "count"))
        )
        if not artist_all_agg.empty:
            result["artist_all_time_median"] = float(artist_all_agg["play_count"].median())

    # ── 艺人播放时间线（精确7日窗口） ──────────────────────────────
    if not artist_df.empty:
        result["artist_timeline"] = _group_by_release_week(
            artist_df, release_date, weeks_before, weeks_after,
        )

    # ── 专辑播放时间线（含 release group 成员） ────────────────────
    album_all = artist_df[artist_df["album_name"].isin(album_names)]
    if not album_all.empty:
        result["album_timeline"] = _group_by_release_week(
            album_all, release_date, weeks_before, weeks_after,
        )

    # ── 单曲播放时间线 ────────────────────────────────────────────
    if not album_all.empty:
        track_offsets = (album_all["ts_date_dt"] - release_dt).dt.days // 7
        track_mask = (track_offsets >= -weeks_before) & (track_offsets <= weeks_after)
        if track_mask.any():
            track_filtered = album_all.loc[track_mask]
            track_offsets_f = track_offsets.loc[track_mask]
            result["track_timelines"] = (
                track_filtered.groupby([track_offsets_f, "track_id", "track_name"])
                .agg(play_count=("ms_played", "count"))
                .reset_index()
            )
            result["track_timelines"].columns = ["week_offset", "track_id", "track_name", "play_count"]
            result["track_timelines"] = result["track_timelines"].sort_values(
                ["week_offset", "play_count"], ascending=[True, False]
            )

    # ── 全量播放时间线（优先用预计算的每日聚合） ──────────────────
    if total_daily is not None:
        offsets = (total_daily.index - release_dt).days // 7
        mask = (offsets >= -weeks_before) & (offsets <= weeks_after)
        if mask.any():
            filtered = total_daily.loc[mask]
            filtered_offsets = offsets[mask]
            weekly = (
                filtered.groupby(filtered_offsets)
                .sum()
                .reset_index()
            )
            weekly.columns = ["week_offset", "play_count"]
            result["total_timeline"] = weekly.sort_values("week_offset")
    else:
        result["total_timeline"] = _group_by_release_week(
            df_raw, release_date, weeks_before, weeks_after,
        )

    # ── 排名数据（仍用 Billboard 周对齐） ──────────────────────────
    if weekly_artist is not None:
        art_ranks = weekly_artist[weekly_artist["artist_name"] == artist_name][
            ["billboard_week", "rank", "play_count"]
        ].copy()
        result["artist_ranks"] = align_to_release(art_ranks, release_date, weeks_before, weeks_after)

    if weekly_album is not None:
        alb_ranks = weekly_album[
            (weekly_album["artist_name"] == artist_name)
            & (weekly_album["album_name"] == canonical)
        ][["billboard_week", "rank", "play_count"]].copy()
        result["album_ranks"] = align_to_release(alb_ranks, release_date, weeks_before, weeks_after)

    # ── 洁净基线窗口（用于冲击力计算的混合基线） ──────────────────
    # 如果存在先行曲，洁净窗口 = 最早先行曲前 4 周 ~ 最早先行曲
    # 无先行曲时 = 发行前 4 周
    advance = get_advance_singles(artist_name, album_name)
    if advance:
        first_single_date = min(pd.to_datetime(s["release_date"]) for s in advance)
        anchor = min(release_dt, first_single_date)
    else:
        anchor = release_dt
    clean_start_offset = int((anchor - release_dt).days // 7) - 4
    result["clean_baseline_start"] = clean_start_offset

    return result


def _compute_artist_impact(cycle_data):
    """艺人收听冲击力 — 该发行对艺人收听行为的改变程度。

    三因子加权: 0.35×体量 + 0.35×增幅 + 0.30×归因

    体量: log₂(post_album / max(median, 10)) — 这张专辑听了多少（固定除4周）
    增幅: log₂(post_artist / max(baseline, 10)) — 艺人收听涨了多少
        baseline 优先取洁净期（先行曲发行前），无先行曲时取发行前4周，
        均无数据时回退到全时段中位数。先行曲带来的增长视为专辑发行周期的一部分。
    归因: post_album / post_artist — 涨幅是否由本专辑导致

    Returns (score: float|None, factors: dict|None)
    """
    artist_tl = cycle_data.get("artist_timeline", pd.DataFrame())
    album_tl = cycle_data.get("album_timeline", pd.DataFrame())
    artist_median = cycle_data.get("artist_all_time_median", 0)
    clean_start = cycle_data.get("clean_baseline_start", -4)
    _floor = 10.0

    if artist_tl.empty or album_tl.empty:
        return None, None

    post_artist = artist_tl[(artist_tl["week_offset"] >= 0) & (artist_tl["week_offset"] <= 3)]
    post_album = album_tl[(album_tl["week_offset"] >= 0) & (album_tl["week_offset"] <= 3)]
    if post_artist.empty or post_album.empty:
        return None, None

    # 固定除 4（非稀疏 mean），避免周数据缺失导致虚高
    post_artist_avg = float(post_artist["play_count"].sum()) / 4
    post_album_avg = float(post_album["play_count"].sum()) / 4

    # 体量
    if artist_median > 0 and post_album_avg > 0:
        magnitude = max(0.0, np.log2(post_album_avg / max(artist_median, _floor)))
    else:
        magnitude = 0.0

    # 增幅 — 洁净期基线（先行曲归入发行周期，不予扣除）
    baseline_source = "发行前4周"
    pre_artist_rows = artist_tl[(artist_tl["week_offset"] >= -4) & (artist_tl["week_offset"] <= -1)]
    pre_artist_avg = float(pre_artist_rows["play_count"].sum()) / 4 if not pre_artist_rows.empty else 0.0

    clean_artist_avg = 0.0
    used_clean = False
    if clean_start < -4:
        clean_end = clean_start + 4
        clean_rows = artist_tl[(artist_tl["week_offset"] >= clean_start) & (artist_tl["week_offset"] < clean_end)]
        if not clean_rows.empty:
            clean_artist_avg = float(clean_rows["play_count"].sum()) / 4

    if clean_artist_avg > 0:
        baseline_avg = clean_artist_avg
        baseline_source = f"洁净期基线 ({clean_artist_avg:.0f}次/周)"
        used_clean = True
    elif pre_artist_avg > 0:
        baseline_avg = pre_artist_avg
    elif artist_median > 0:
        baseline_avg = float(artist_median)
        baseline_source = "全时段中位数"
    else:
        baseline_avg = 0.0

    if baseline_avg > 0 and post_artist_avg > 0:
        growth = max(0.0, np.log2(post_artist_avg / max(baseline_avg, _floor)))
        raw_boost = post_artist_avg / baseline_avg
    else:
        growth = 0.0
        raw_boost = 0

    # 归因
    attribution = min(1.0, post_album_avg / post_artist_avg) if post_artist_avg > 0 else 0.0

    score = 0.35 * magnitude + 0.35 * growth + 0.30 * attribution
    score = round(score, 2)

    factors = {
        "score": score,
        "magnitude": round(magnitude, 2),
        "growth": round(growth, 2),
        "attribution": round(attribution, 2),
        "baseline_avg": round(baseline_avg, 1),
        "pre_artist_avg": round(pre_artist_avg, 1),
        "clean_artist_avg": round(clean_artist_avg, 1) if used_clean else None,
        "post_artist_avg": round(post_artist_avg, 1),
        "post_album_avg": round(post_album_avg, 1),
        "artist_median": round(artist_median, 1),
        "raw_boost": round(raw_boost, 2),
        "baseline_source": baseline_source,
    }
    return score, factors


def _compute_market_impact(cycle_data):
    """大盘冲击力 — 该发行对你整体音乐收听格局的冲击程度。

    三因子加权: 0.30×市占率 + 0.30×绝对体量 + 0.40×市场位移

    市占率: post_album / total_post — 发行后总播放中这张专辑占比
    绝对体量: log₂(post_album / 10) — 绝对播放量级
    市场位移: log₂(1 + album_delta / max(total_pre, 10)) — 发行带来的绝对收听增量，
        相对于发行前大盘体量。不依赖大盘是否增长（相关性→因果性），
        无论大盘涨跌，只要专辑自身增量足够大就能得分。

    Returns (score: float|None, factors: dict|None)
    """
    album_tl = cycle_data.get("album_timeline", pd.DataFrame())
    total_tl = cycle_data.get("total_timeline", pd.DataFrame())
    _floor = 10.0

    if album_tl.empty:
        return None, None

    post_album = album_tl[(album_tl["week_offset"] >= 0) & (album_tl["week_offset"] <= 3)]
    if post_album.empty:
        return None, None

    post_album_avg = float(post_album["play_count"].sum()) / 4

    # 市占率
    market_share = 0.0
    total_post_avg = None
    total_pre_avg = None
    if not total_tl.empty:
        post_total = total_tl[(total_tl["week_offset"] >= 0) & (total_tl["week_offset"] <= 3)]
        if not post_total.empty:
            total_post_avg = float(post_total["play_count"].sum()) / 4
            market_share = min(1.0, post_album_avg / max(1.0, total_post_avg))

    # 绝对体量
    volume = max(0.0, np.log2(post_album_avg / _floor))

    # 市场位移 — 专辑自身带来的绝对增量，相对于发行前大盘体量
    market_shift = 0.0
    pre_album_avg = 0.0
    album_delta = 0.0
    if not total_tl.empty:
        pre_total_rows = total_tl[(total_tl["week_offset"] >= -4) & (total_tl["week_offset"] <= -1)]
        total_pre_for_shift = float(pre_total_rows["play_count"].sum()) / 4 if not pre_total_rows.empty else 0.0
        total_pre_avg = total_pre_for_shift

        pre_album_rows = album_tl[(album_tl["week_offset"] >= -4) & (album_tl["week_offset"] <= -1)]
        pre_album_avg = float(pre_album_rows["play_count"].sum()) / 4 if not pre_album_rows.empty else 0.0

        album_delta = max(0.0, post_album_avg - pre_album_avg)
        market_shift = max(0.0, np.log2(1 + album_delta / max(total_pre_for_shift, _floor)))

    score = 0.30 * market_share + 0.30 * volume + 0.40 * market_shift
    score = round(score, 2)

    factors = {
        "score": score,
        "market_share": round(market_share, 2),
        "volume": round(volume, 2),
        "market_shift": round(market_shift, 2),
        "post_album_avg": round(post_album_avg, 1),
        "total_pre_avg": round(total_pre_avg, 1) if total_pre_avg else None,
        "total_post_avg": round(total_post_avg, 1) if total_post_avg else None,
        "pre_album_avg": round(pre_album_avg, 1),
        "album_delta": round(album_delta, 1),
    }
    return score, factors


def format_artist_impact(score):
    """格式化艺人收听冲击力为展示文本。"""
    if score is None:
        return "—"
    if score >= 0.8:
        return f"{score:.2f} · 现象级"
    if score >= 0.5:
        return f"{score:.2f} · 强冲击"
    if score >= 0.3:
        return f"{score:.2f} · 有冲击"
    return f"{score:.2f} · 微弱"


def format_market_impact(score):
    """格式化大盘冲击力为展示文本。"""
    if score is None:
        return "—"
    if score >= 0.8:
        return f"{score:.2f} · 统治级"
    if score >= 0.5:
        return f"{score:.2f} · 强冲击"
    if score >= 0.3:
        return f"{score:.2f} · 有冲击"
    return f"{score:.2f} · 微弱"


def format_artist_impact_help(detail):
    """生成艺人收听冲击力构成解释文本。"""
    if detail is None:
        return "数据不足"

    mag = detail["magnitude"]
    growth = detail["growth"]
    attr = detail["attribution"]
    score = detail["score"]

    lines = [
        f"艺人收听冲击力 = 0.35×体量 + 0.35×增幅 + 0.30×归因",
        f"                = 0.35×{mag:.2f} + 0.35×{growth:.2f} + 0.30×{attr:.2f}",
        f"                = {score:.2f}",
        "",
        f"体量 {mag:.2f} (权重35%): 这张专辑你听了多少",
        f"  发行后4周专辑周均 {detail['post_album_avg']:.0f} 次 vs 艺人平时 {detail['artist_median']:.0f} 次/周",
        f"  log₂({detail['post_album_avg']:.0f} / max({detail['artist_median']:.0f}, 10)) = {mag:.2f}",
        "",
        f"增幅 {growth:.2f} (权重35%): 该艺人收听涨了多少",
        f"  后4周周均 {detail['post_artist_avg']:.0f} 次 vs 基线 {detail['baseline_avg']:.0f} 次/周 ({detail['baseline_source']})",
    ]
    if detail.get("clean_artist_avg") is not None:
        lines += [
            f"    洁净期基线: {detail['clean_artist_avg']:.0f} 次/周 · 发行前基线: {detail['pre_artist_avg']:.0f} 次/周",
            f"    先行曲效应归入发行周期，不计入基线扣除",
        ]
    lines += [
        f"  原始增幅 {detail['raw_boost']:.1f}x，log₂ = {growth:.2f}",
        "",
        f"归因 {attr:.2f} (权重30%): 涨幅是否来自本专辑",
        f"  本专辑 {detail['post_album_avg']:.0f} / 艺人 {detail['post_artist_avg']:.0f} = {attr:.0%}",
    ]
    return "\n".join(lines)


def format_market_impact_help(detail):
    """生成大盘冲击力构成解释文本。"""
    if detail is None:
        return "数据不足"

    ms = detail["market_share"]
    vol = detail["volume"]
    mshift = detail["market_shift"]
    score = detail["score"]

    lines = [
        f"大盘冲击力 = 0.30×市占率 + 0.30×绝对体量 + 0.40×市场位移",
        f"         = 0.30×{ms:.2f} + 0.30×{vol:.2f} + 0.40×{mshift:.2f}",
        f"         = {score:.2f}",
        "",
        f"市占率 {ms:.2f} (权重30%): 发行后总播放中这张专辑占比",
        f"  专辑 {detail['post_album_avg']:.0f} / 总 {detail.get('total_post_avg', 0) or 0:.0f} = {ms:.0%}",
        "",
        f"绝对体量 {vol:.2f} (权重30%): 绝对播放量级",
        f"  发行后4周周均 {detail['post_album_avg']:.0f} 次，log₂({detail['post_album_avg']:.0f} / 10) = {vol:.2f}",
        "",
        f"市场位移 {mshift:.2f} (权重40%): 发行带来的绝对收听增量",
    ]
    if detail.get("total_pre_avg") is not None:
        ad = detail.get("album_delta", detail.get("album_increase", 0))
        lines += [
            f"  专辑增量 {ad:.0f} / 发行前大盘周均 {detail['total_pre_avg']:.0f}",
            f"  log₂(1 + {ad:.0f} / {max(detail['total_pre_avg'], 10):.0f}) = {mshift:.2f}",
            f"  衡量专辑「制造」了多少新播放，不依赖大盘是否涨跌",
        ]
    else:
        lines += [
            f"  (无大盘基线数据)",
        ]

    return "\n".join(lines)


def compute_release_metrics(cycle_data, album_type="album"):
    """从 release_cycle 结果中计算各项指标。

    Returns dict with keys: debut_rank, peak_rank, weeks_to_peak,
        weeks_on_chart, artist_impact, market_impact, half_life,
        peak_play_count, release_week_plays, pre_release_avg
    """
    metrics = {
        "debut_rank": None,
        "peak_rank": None,
        "weeks_to_peak": None,
        "weeks_on_chart": 0,
        "artist_impact": None,
        "market_impact": None,
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

    metrics["artist_impact"], metrics["artist_impact_detail"] = _compute_artist_impact(cycle_data)
    metrics["market_impact"], metrics["market_impact_detail"] = _compute_market_impact(cycle_data)

    peak_plays = metrics["peak_play_count"]
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


def compute_artist_summary(artist_name, releases_df, weekly, weekly_artist, weekly_album):
    """计算艺人级别的快速汇总指标（空冠统计、发行计数等，不涉及逐发行 cycle 计算）。"""
    summary = {
        "total_albums": 0,
        "total_singles": 0,
        "album_debut_no1_count": 0,
        "single_debut_no1_count": 0,
        "double_debut_count": 0,
        "max_artist_impact": None,
        "max_artist_impact_album": "",
        "max_market_impact": None,
        "max_market_impact_album": "",
        "total_catalog_reentries": 0,
    }

    if releases_df.empty:
        return summary

    albums = releases_df[releases_df["album_type"] == "album"]
    singles = releases_df[releases_df["album_type"] == "single"]
    summary["total_albums"] = len(albums)
    summary["total_singles"] = len(singles)

    # ── 歌曲空冠：weekly 中该艺人首次入榜即 rank==1 的歌曲 ──────────
    if weekly is not None:
        artist_tracks = weekly[weekly["artist_name"] == artist_name]
        if not artist_tracks.empty:
            first_track_appear = (
                artist_tracks.sort_values("billboard_week")
                .groupby("track_id")
                .first()
                .reset_index()
            )
            summary["single_debut_no1_count"] = int(
                (first_track_appear["rank"] == 1).sum()
            )

    # ── 专辑空冠：weekly_album 中该艺人首次入榜即 rank==1 的专辑 ─────
    if weekly_album is not None:
        artist_albums = weekly_album[weekly_album["artist_name"] == artist_name]
        if not artist_albums.empty:
            first_album_appear = (
                artist_albums.sort_values("billboard_week")
                .groupby(["album_name", "artist_name"])
                .first()
                .reset_index()
            )
            summary["album_debut_no1_count"] = int(
                (first_album_appear["rank"] == 1).sum()
            )

    # ── 双空冠：同一艺人同周歌曲+专辑同时空冠 ─────────────────────────
    if weekly is not None and weekly_album is not None:
        all_track_first = (
            weekly.sort_values("billboard_week")
            .groupby("track_id")
            .first()
            .reset_index()
        )
        debut_tracks = all_track_first[all_track_first["rank"] == 1][
            ["track_id", "artist_name", "billboard_week"]
        ]

        all_album_first = (
            weekly_album.sort_values("billboard_week")
            .groupby(["album_name", "artist_name"])
            .first()
            .reset_index()
        )
        debut_albums = all_album_first[all_album_first["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ]

        if not debut_tracks.empty and not debut_albums.empty:
            double = debut_tracks.merge(
                debut_albums, on=["artist_name", "billboard_week"], how="inner"
            )
            summary["double_debut_count"] = int(
                (double["artist_name"] == artist_name).sum()
            )

    return summary


def fill_summary_from_cycles(summary, artist_name, releases_df, all_cycles, df_raw):
    """用预计算的 cycles 填充冲击力极值和老歌回榜统计。"""
    for _, rel in releases_df.iterrows():
        album_name = rel["album_name"]
        album_type = rel["album_type"]

        cycle = all_cycles.get(album_name)
        if cycle is None:
            continue
        metrics = compute_release_metrics(cycle, album_type)

        if metrics["artist_impact"] is not None:
            if summary["max_artist_impact"] is None or metrics["artist_impact"] > summary["max_artist_impact"]:
                summary["max_artist_impact"] = metrics["artist_impact"]
                summary["max_artist_impact_album"] = album_name
        if metrics["market_impact"] is not None:
            if summary["max_market_impact"] is None or metrics["market_impact"] > summary["max_market_impact"]:
                summary["max_market_impact"] = metrics["market_impact"]
                summary["max_market_impact_album"] = album_name

        if album_type == "album":
            reentries = detect_catalog_reentries(
                df_raw, artist_name, rel["release_date"], album_name
            )
            summary["total_catalog_reentries"] += len(reentries)


def _save_album_meta_to_db(spotify_album_id, album_name, album_type, release_date,
                          album_artists=None):
    """将 Spotify 专辑元数据持久化到 spotify_album_meta 表。

    已有行不会丢失其他列的数据（INSERT OR REPLACE 仅覆盖提供的列）。
    """
    try:
        conn = get_db(readonly=False)
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date, album_artists)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(spotify_album_id) DO UPDATE SET
                   album_name = excluded.album_name,
                   album_type = excluded.album_type,
                   release_date = excluded.release_date,
                   album_artists = excluded.album_artists""",
            (spotify_album_id, album_name, album_type, release_date, album_artists),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


@st.cache_data(ttl=3600)
def _spotify_search_album(album_name, artist_name, skip_db_check=False):
    """获取专辑/单曲元数据 — 优先 DB，缺失时调 Spotify Search API。

    两级策略：
    ① 查 spotify_album_meta（DB），已有完整元数据直接返回，不调 API
    ② DB 无数据时调 Spotify API，结果持久化到 DB

    skip_db_check=True 时跳过 DB 直调 API（用于 DB 元数据不可信的场景）。
    """
    import json
    import urllib.request
    import urllib.parse
    import urllib.error

    if not skip_db_check:
        # Tier 1: DB 中已有完整元数据 → 直接返回，零 API 调用
        try:
            conn = get_db()
            row = pd.read_sql_query(
                """SELECT spotify_album_id, album_name, album_type, release_date
                   FROM spotify_album_meta
                   WHERE album_name = ? AND album_type IS NOT NULL AND release_date IS NOT NULL
                   LIMIT 1""",
                conn,
                params=[album_name],
            )
            conn.close()
            if not row.empty:
                return {
                    "album_name": row["album_name"].iloc[0],
                    "album_type": row["album_type"].iloc[0],
                    "release_date": row["release_date"].iloc[0],
                    "spotify_album_id": row["spotify_album_id"].iloc[0],
                }
        except Exception:
            pass

    # Tier 2: DB 无数据 → 调 Spotify Search API
    token = _get_spotify_token()
    if not token:
        return None

    try:
        q = urllib.parse.quote(f"album:{album_name} artist:{artist_name}")
        url = f"https://api.spotify.com/v1/search?q={q}&type=album&limit=5"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        for album in data.get("albums", {}).get("items", []):
            if album["name"].lower() == album_name.lower():
                artist_names = [a["name"] for a in album.get("artists", [])]
                album_artists = ", ".join(artist_names) if artist_names else None

                result = {
                    "album_name": album["name"],
                    "album_type": album.get("album_type"),
                    "release_date": album.get("release_date"),
                    "spotify_album_id": album["id"],
                }
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
    # 优先用 db_album_name（本地专辑名，更可靠）匹配，回退到 album_name（展示名）。
    # 曲目共享会导致单曲的 album_name 指向 Spotify 专辑名，album_name 匹配可能拿到错误行。
    album_row = releases[releases["db_album_name"] == album_name]
    if album_row.empty:
        album_row = releases[releases["album_name"] == album_name]
    if album_row.empty:
        return []

    album_release_date = album_row["release_date"].iloc[0]
    # 使用 db_album_name 进行 SQL 查询（匹配 albums 表）
    db_name = album_row["db_album_name"].iloc[0] if "db_album_name" in album_row.columns and pd.notna(album_row["db_album_name"].iloc[0]) else album_name

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
        params=[db_name, artist_name],
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
        db_has_wrong_type = False  # DB 有记录但类型不是 single → 需强制 API
        if not meta.empty:
            db_type = meta["album_type"].iloc[0]
            if db_type == "single":
                db_rd = meta["release_date"].iloc[0]
                if pd.notna(db_rd):
                    release_date = pd.to_datetime(db_rd)
            elif pd.notna(db_type):
                # DB 有记录但类型不是 single → 标记，强制调 API
                db_has_wrong_type = True

        # Tier 2: Spotify API search
        # 若 Tier 1 DB 返回了非 single 类型，强制跳过 DB 直调 API
        if release_date is None:
            spotify_meta = _spotify_search_album(
                candidate_name, artist_name,
                skip_db_check=db_has_wrong_type,
            )
            if spotify_meta and spotify_meta.get("album_type") == "single":
                release_date = pd.to_datetime(spotify_meta["release_date"])

        # Tier 3: earliest play date heuristic (only for confirmed singles)
        if release_date is None and not db_has_wrong_type:
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

        if release_date is not None and pd.notna(release_date) and release_date < album_release_date:
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
    earlier = releases[pd.to_datetime(releases["release_date"]) < current_rel_date]
    # 使用 db_album_name 与 df_raw 匹配（df_raw 的 album_name 来源于 albums 表）
    earlier_albums = earlier["db_album_name"].tolist() if "db_album_name" in earlier.columns else earlier["album_name"].tolist()

    old_songs = artist_df[artist_df["album_name"].isin(earlier_albums)].copy()
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
