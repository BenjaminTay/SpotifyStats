#!/usr/bin/env python3
"""从 Spotify API 批量下载播放记录中所有艺人/专辑的封面图片到本地。

使用方式：
  1. 确保 .env 中有 SPOTIFY_CLIENT_ID 和 SPOTIFY_CLIENT_SECRET
  2. python3 scripts/fetch_covers.py

输出：
  data/covers/albums/{album_id}.jpg   — 300x300 专辑封面
  data/covers/artists/{artist_id}.jpg — ~160x160 艺人照片

幂等：已有 image_path 的记录自动跳过，可重复运行做增量更新。
"""

import os
import sqlite3
import sys
import time
import unicodedata
import urllib.request
import urllib.parse
import urllib.error
import json
import base64
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import DB_PATH, ensure_schema

ALBUM_BATCH = 20
ARTIST_BATCH = 50

COVERS_DIR = os.path.join(os.path.dirname(DB_PATH), "covers")


# ── helpers ────────────────────────────────────────────────────────────────

def load_dotenv(path: str = ".env") -> None:
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
    if not os.path.exists(env_file):
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def get_access_token(client_id: str, client_secret: str) -> str:
    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())["access_token"]
    except urllib.error.HTTPError as e:
        print(f"认证失败 (HTTP {e.code}): {e.read().decode()}")
        sys.exit(1)


def api_get(url: str, token: str) -> Optional[dict]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            retry_after = int(e.headers.get("Retry-After", 5))
            print(f"    触发速率限制，等待 {retry_after}s...")
            time.sleep(retry_after)
            return api_get(url, token)
        elif e.code == 401:
            return None
        else:
            print(f"    HTTP {e.code}: {e.read().decode()[:150]}")
            return None
    except (urllib.error.URLError, OSError) as e:
        print(f"    网络错误: {e}")
        return None


def download_image(url: str, filepath: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SpotifyStats/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"      下载失败: {e}")
        return False


def extract_spotify_id(uri: str) -> Optional[str]:
    if not uri or not uri.startswith("spotify:track:"):
        return None
    return uri.split(":")[-1]


# ── Resolve Spotify IDs ────────────────────────────────────────────────────

def resolve_album_spotify_ids(db: sqlite3.Connection):
    """为每个本地 album_id 找到对应的 Spotify album_id。

    三级策略（逐步降级）：
    1. spotify_track_meta 表已有映射（最快，不需要 API 调用）
    2. 从 track 的 Spotify URI 反查 /v1/tracks/{id} 获取 album_id
    3. 通过 Spotify Search API 搜索
    """
    rows = db.execute(
        """SELECT DISTINCT al.album_id, al.album_name, a.artist_name
           FROM plays p
           JOIN tracks t ON p.track_id = t.track_id
           JOIN albums al ON t.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE p.track_id IS NOT NULL
             AND al.album_name IS NOT NULL
             AND (al.image_path IS NULL OR al.image_path = '')
           ORDER BY al.album_id"""
    ).fetchall()

    album_to_spotify = {}
    unresolved = []

    for r in rows:
        # ① 从 spotify_track_meta 查已有映射
        row = db.execute(
            """SELECT stm.spotify_album_id
               FROM tracks t
               JOIN spotify_track_meta stm
                 ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
               WHERE t.album_id = ? AND stm.spotify_album_id IS NOT NULL
               LIMIT 1""",
            [r["album_id"]],
        ).fetchone()

        if row:
            album_to_spotify[r["album_id"]] = row["spotify_album_id"]
        else:
            # ② 看看有没有 Spotify URI 可以用来反查
            uri_row = db.execute(
                "SELECT spotify_track_uri FROM tracks WHERE album_id = ? AND spotify_track_uri IS NOT NULL LIMIT 1",
                [r["album_id"]],
            ).fetchone()
            if uri_row:
                # 记录 track URI 用于后续 API 反查
                r = dict(r)
                r["_spotify_track_uri"] = uri_row["spotify_track_uri"]
            unresolved.append(r)

    return album_to_spotify, unresolved


def resolve_album_via_track_api(db, token, client_id, client_secret, unresolved):
    """通过 Spotify /v1/tracks/{id} API 反查 album_id。

    对每张未解析专辑，用其下任意一条 track 的 Spotify URI 查 API，
    从响应中取 album.id。批量 50 个 track ID 一组。
    """
    # 有 track URI 的走 API，没有的走搜索
    with_uri = [(r, extract_spotify_id(r["_spotify_track_uri"]))
                for r in unresolved if r.get("_spotify_track_uri")]
    no_uri = [r for r in unresolved if not r.get("_spotify_track_uri")]

    album_to_spotify = {}

    if with_uri:
        print(f"\n  通过 Track API 反查 {len(with_uri)} 张专辑的 album_id...")
        TRACK_BATCH = 50
        for i in range(0, len(with_uri), TRACK_BATCH):
            batch = with_uri[i:i + TRACK_BATCH]
            batch_ids = [bid for _, bid in batch]
            bn = i // TRACK_BATCH + 1
            total = (len(with_uri) - 1) // TRACK_BATCH + 1
            print(f"    [Track API {bn}/{total}] {len(batch)} 首...", end=" ", flush=True)

            url = f"https://api.spotify.com/v1/tracks?ids={','.join(batch_ids)}"
            data = api_get(url, token)
            if data is None:
                print("重新认证...")
                token = get_access_token(client_id, client_secret)
                data = api_get(url, token)

            if data:
                resolved = 0
                for track in data.get("tracks", []):
                    if track is None:
                        continue
                    # 找到对应的本地 album
                    track_id = track["id"]
                    album_id = track["album"]["id"]
                    album_name = track["album"]["name"]
                    for r, sid in batch:
                        if sid == track_id:
                            r["_spotify_album_id"] = album_id
                            album_to_spotify[r["album_id"]] = album_id
                            # 顺便写入 track meta（如果还没有的话）
                            db.execute(
                                """INSERT OR IGNORE INTO spotify_track_meta(
                                       spotify_track_id, track_name, duration_ms, spotify_album_id)
                                   VALUES (?, ?, ?, ?)""",
                                (track_id, track["name"], track["duration_ms"], album_id),
                            )
                            # 也写入 album meta 基本信息
                            db.execute(
                                """INSERT OR IGNORE INTO spotify_album_meta(
                                       spotify_album_id, album_name, album_type, release_date)
                                   VALUES (?, ?, ?, ?)""",
                                (album_id, album_name,
                                 track["album"].get("album_type"),
                                 track["album"].get("release_date")),
                            )
                            resolved += 1
                            break
                db.commit()
                print(f"✓ {resolved} 已解析")
            else:
                print("✗ 失败")

            if i + TRACK_BATCH < len(with_uri):
                time.sleep(0.3)

    # 分离出已解析和仍未解析的
    resolved_ids = set()
    for r in unresolved:
        if r.get("_spotify_album_id"):
            resolved_ids.add(r["album_id"])

    resolved_map = {}
    still_unresolved = []
    for r in unresolved:
        if r.get("_spotify_album_id"):
            resolved_map[r["album_id"]] = r["_spotify_album_id"]
        elif r.get("_spotify_track_uri"):
            # 有 track URI 但 API 没匹配到 → 清理临时字段，进入搜索阶段
            r_clean = {k: v for k, v in r.items() if not k.startswith("_")}
            still_unresolved.append(r_clean)
        else:
            # 本来就没有 track URI
            r_clean = {k: v for k, v in r.items() if not k.startswith("_")}
            still_unresolved.append(r_clean)

    return resolved_map, still_unresolved, token


def resolve_artist_spotify_ids(db: sqlite3.Connection):
    """为每个本地 artist_id 找到对应的 Spotify artist_id。

    三级策略：
    1. 查 spotify_artist_meta 按名称匹配（最快）
    2. 从 artist 的任意 track URI 反查 /v1/tracks/{id} 获取 artist
    3. 通过 Spotify Search API 搜索
    """
    rows = db.execute(
        """SELECT DISTINCT a.artist_id, a.artist_name
           FROM plays p
           JOIN tracks t ON p.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           WHERE p.track_id IS NOT NULL
             AND (a.image_path IS NULL OR a.image_path = '')
           ORDER BY a.artist_id"""
    ).fetchall()

    artist_to_spotify = {}
    unresolved = []

    for r in rows:
        # ① 从 spotify_artist_meta 按名称匹配
        row = db.execute(
            "SELECT spotify_artist_id FROM spotify_artist_meta WHERE artist_name = ? LIMIT 1",
            [r["artist_name"]],
        ).fetchone()

        if row:
            artist_to_spotify[r["artist_id"]] = row["spotify_artist_id"]
        else:
            # ② 看看有没有 track URI 可以用来反查
            uri_row = db.execute(
                "SELECT spotify_track_uri FROM tracks WHERE artist_id = ? AND spotify_track_uri IS NOT NULL LIMIT 1",
                [r["artist_id"]],
            ).fetchone()
            if uri_row:
                r = dict(r)
                r["_spotify_track_uri"] = uri_row["spotify_track_uri"]
            unresolved.append(r)

    return artist_to_spotify, unresolved


def resolve_artist_via_track_api(db, token, client_id, client_secret, unresolved):
    """通过 Spotify /v1/tracks/{id} API 反查 artist_id，再批量获取 artist 详情。

    对每位未解析艺人，用其下任意一条 track 的 Spotify URI 反查，
    从 track 响应中取 artists[0].id 作为该艺人的 Spotify ID。
    """
    with_uri = [(r, extract_spotify_id(r["_spotify_track_uri"]))
                for r in unresolved if r.get("_spotify_track_uri")]
    no_uri = [r for r in unresolved if not r.get("_spotify_track_uri")]

    if not with_uri:
        return {}, no_uri, token

    print(f"\n  通过 Track API 反查 {len(with_uri)} 位艺人的 Spotify ID...")
    TRACK_BATCH = 50
    for i in range(0, len(with_uri), TRACK_BATCH):
        batch = with_uri[i:i + TRACK_BATCH]
        batch_ids = [bid for _, bid in batch]
        bn = i // TRACK_BATCH + 1
        total = (len(with_uri) - 1) // TRACK_BATCH + 1
        print(f"    [Track API {bn}/{total}] {len(batch)} 首...", end=" ", flush=True)

        url = f"https://api.spotify.com/v1/tracks?ids={','.join(batch_ids)}"
        data = api_get(url, token)
        if data is None:
            print("重新认证...")
            token = get_access_token(client_id, client_secret)
            data = api_get(url, token)

        if data:
            resolved = 0
            for track in data.get("tracks", []):
                if track is None or not track.get("artists"):
                    continue
                track_id = track["id"]
                for r, sid in batch:
                    if sid == track_id:
                        # 找名称匹配的 artist
                        name_lower = r["artist_name"].lower()
                        artists = track["artists"]
                        matched_artist = None
                        # ① 严格匹配
                        for art in artists:
                            if art["name"].lower() == name_lower:
                                matched_artist = art
                                break
                        # ② 去掉重音和特殊字符后匹配
                        if not matched_artist:
                            def _norm(s):
                                n = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
                                return ''.join(c.lower() for c in n if c.isalnum())
                            name_norm = _norm(r["artist_name"])
                            for art in artists:
                                if _norm(art["name"]) == name_norm:
                                    matched_artist = art
                                    break
                        # ③ 只有一位艺人 → 就是他
                        if not matched_artist and len(artists) == 1:
                            matched_artist = artists[0]
                        if matched_artist:
                            r["_spotify_artist_id"] = matched_artist["id"]
                            resolved += 1
                        break
            print(f"✓ {resolved} 已解析")
        else:
            print("✗ 失败")

        if i + TRACK_BATCH < len(with_uri):
            time.sleep(0.3)

    # 分离出已解析和仍未解析的
    resolved_map = {}
    still_unresolved = []
    for r in unresolved:
        if r.get("_spotify_artist_id"):
            resolved_map[r["artist_id"]] = r["_spotify_artist_id"]
        else:
            # 清理临时字段
            r_clean = {k: v for k, v in r.items() if not k.startswith("_")}
            still_unresolved.append(r_clean)

    return resolved_map, still_unresolved, token


# ── Fetch & Store ──────────────────────────────────────────────────────────

def fetch_album_covers(db: sqlite3.Connection, token: str,
                       client_id: str, client_secret: str,
                       album_to_spotify: dict, unresolved: list):
    """批量拉取专辑封面并下载到本地。"""
    # 先处理已解析 Spotify ID 的专辑
    all_albums = [(aid, sid) for aid, sid in album_to_spotify.items()]

    # 搜索未解析的专辑
    if unresolved:
        print(f"\n  搜索 {len(unresolved)} 张未解析专辑的 Spotify ID...")
        for idx, r in enumerate(unresolved):
            aid = r["album_id"]
            name = r["album_name"]
            artist = r["artist_name"]

            matched = None
            # 依次尝试不同的搜索策略
            queries = [
                f"album:{name} artist:{artist}",   # ① 字段精确搜索
                f"{name} artist:{artist}",          # ② 去掉 album: 前缀
            ]
            for qi, q in enumerate(queries):
                data = api_get(
                    f"https://api.spotify.com/v1/search?q={urllib.parse.quote(q)}&type=album&limit=5",
                    token,
                )
                if data is None:
                    token = get_access_token(client_id, client_secret)
                    data = api_get(
                        f"https://api.spotify.com/v1/search?q={urllib.parse.quote(q)}&type=album&limit=5",
                        token,
                    )

                if data and data.get("albums", {}).get("items"):
                    items = data["albums"]["items"]
                    name_lower = name.lower()
                    for item in items:
                        if item["name"].lower() == name_lower:
                            matched = item
                            break
                    # 宽松匹配：去除重音和特殊字符
                    if not matched:
                        def _normalize(s):
                            n = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
                            return ''.join(c.lower() for c in n if c.isalnum())
                        name_norm = _normalize(name)
                        for item in items:
                            if _normalize(item["name"]) == name_norm:
                                matched = item
                                break
                if matched:
                    break

            if matched:
                sid = matched["id"]
                all_albums.append((aid, sid))
                img_url = matched["images"][0]["url"] if matched.get("images") else None
                _upsert_album_meta(db, matched["id"], matched["name"],
                                   matched.get("album_type"), matched.get("release_date"),
                                   matched.get("popularity"), matched.get("label"),
                                   matched.get("genres"), img_url,
                                   matched.get("artists"))
                marker = "~" if matched["name"].lower() != name.lower() else ""
                print(f"    [{idx+1}/{len(unresolved)}] {name[:40]} → {sid} {marker}{matched['name']}{marker}")
            else:
                print(f"    [{idx+1}/{len(unresolved)}] {name[:40]} ✗ 未找到")

            if (idx + 1) % 30 == 0:
                time.sleep(1.0)
            else:
                time.sleep(0.15)

    if not all_albums:
        print("  没有需要下载封面的专辑。")
        return token

    # 分批下载
    spotify_ids = list(set(sid for _, sid in all_albums))
    print(f"\n  共 {len(spotify_ids)} 个唯一 Spotify 专辑，分批下载（每批 {ALBUM_BATCH} 张）...\n")

    downloaded = 0
    for i in range(0, len(spotify_ids), ALBUM_BATCH):
        batch_ids = spotify_ids[i:i + ALBUM_BATCH]
        bn = i // ALBUM_BATCH + 1
        total = (len(spotify_ids) - 1) // ALBUM_BATCH + 1
        print(f"  [专辑 {bn}/{total}] {len(batch_ids)} 张...", end=" ", flush=True)

        url = f"https://api.spotify.com/v1/albums?ids={','.join(batch_ids)}"
        data = api_get(url, token)
        if data is None:
            print("重新认证...")
            token = get_access_token(client_id, client_secret)
            data = api_get(url, token)

        if data:
            batch_dl = 0
            for alb in data.get("albums", []):
                if alb is None or not alb.get("images"):
                    continue
                img_url = alb["images"][0]["url"]

                # 找到所有使用这个 Spotify album 的本地 album_id
                local_ids = [aid for aid, sid in all_albums if sid == alb["id"]]
                for local_id in local_ids:
                    filepath = os.path.join(COVERS_DIR, "albums", f"{local_id}.jpg")
                    if download_image(img_url, filepath):
                        db.execute(
                            "UPDATE albums SET image_url = ?, image_path = ? WHERE album_id = ?",
                            [img_url, f"covers/albums/{local_id}.jpg", local_id],
                        )
                        batch_dl += 1

                _upsert_album_meta(db, alb["id"], alb["name"],
                                   alb.get("album_type"), alb.get("release_date"),
                                   alb.get("popularity"), alb.get("label"),
                                   alb.get("genres"), img_url,
                                   alb.get("artists"))

            db.commit()
            downloaded += batch_dl
            print(f"✓ {batch_dl} 张下载")
        else:
            print("✗ 失败")

        if i + ALBUM_BATCH < len(spotify_ids):
            time.sleep(0.3)

    print(f"\n  专辑封面完成：{downloaded} 张下载\n")
    return token


def _upsert_album_meta(db, spotify_id, name, album_type, release_date,
                       popularity, label, genres, img_url, artists):
    """写入 spotify_album_meta 表。"""
    genres_json = json.dumps(genres, ensure_ascii=False) if genres else None
    artists_json = None
    if artists:
        artist_names = [a.get("name", "") for a in artists if a.get("name")]
        if artist_names:
            artists_json = json.dumps(artist_names, ensure_ascii=False)

    db.execute(
        """INSERT OR REPLACE INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date,
               popularity, label, genres, image_url, album_artists)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (spotify_id, name, album_type, release_date,
         popularity, label, genres_json, img_url, artists_json),
    )


def fetch_artist_covers(db: sqlite3.Connection, token: str,
                        client_id: str, client_secret: str,
                        artist_to_spotify: dict, unresolved: list):
    """批量拉取艺人照片并下载到本地。"""
    all_artists = [(aid, sid) for aid, sid in artist_to_spotify.items()]

    # 搜索未解析的艺人
    if unresolved:
        print(f"\n  搜索 {len(unresolved)} 位未解析艺人的 Spotify ID...")
        for idx, r in enumerate(unresolved):
            aid = r["artist_id"]
            name = r["artist_name"]
            q = urllib.parse.quote(name)
            data = api_get(
                f"https://api.spotify.com/v1/search?q={q}&type=artist&limit=5", token
            )
            if data is None:
                token = get_access_token(client_id, client_secret)
                data = api_get(
                    f"https://api.spotify.com/v1/search?q={q}&type=artist&limit=5", token
                )

            matched = None
            if data and data.get("artists", {}).get("items"):
                items = data["artists"]["items"]
                # ① 严格匹配（忽略大小写）
                name_lower = name.lower()
                for item in items:
                    if item["name"].lower() == name_lower:
                        matched = item
                        break
                # ② 宽松匹配：去除重音符号和特殊字符后比较
                if not matched:
                    def _normalize(s):
                        n = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
                        return ''.join(c.lower() for c in n if c.isalnum())
                    name_norm = _normalize(name)
                    for item in items:
                        if _normalize(item["name"]) == name_norm:
                            matched = item
                            break
                # ③ 最终回退：取搜索结果第一条（名称部分匹配即可）
                if not matched and items:
                    matched = items[0]

            if matched:
                sid = matched["id"]
                all_artists.append((aid, sid))
                img_url = matched["images"][0]["url"] if matched.get("images") else None
                genres = json.dumps(matched.get("genres", []), ensure_ascii=False) if matched.get("genres") else None
                db.execute(
                    """INSERT OR REPLACE INTO spotify_artist_meta(
                           spotify_artist_id, artist_name, popularity, followers,
                           genres, image_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (sid, name, matched.get("popularity"),
                     matched.get("followers", {}).get("total"),
                     genres, img_url),
                )
                marker = "~" if matched["name"].lower() != name_lower else ""
                print(f"    [{idx+1}/{len(unresolved)}] {name[:40]} → {sid} {marker}{matched['name']}{marker}")
            else:
                print(f"    [{idx+1}/{len(unresolved)}] {name[:40]} ✗ 搜索失败")

            if (idx + 1) % 30 == 0:
                time.sleep(1.0)
            else:
                time.sleep(0.15)

    if not all_artists:
        print("  没有需要下载封面的艺人。")
        return token

    # 分批获取
    spotify_ids = list(set(sid for _, sid in all_artists))
    print(f"\n  共 {len(spotify_ids)} 个唯一 Spotify 艺人，分批获取（每批 {ARTIST_BATCH} 位）...\n")

    downloaded = 0
    for i in range(0, len(spotify_ids), ARTIST_BATCH):
        batch_ids = spotify_ids[i:i + ARTIST_BATCH]
        bn = i // ARTIST_BATCH + 1
        total = (len(spotify_ids) - 1) // ARTIST_BATCH + 1
        print(f"  [艺人 {bn}/{total}] {len(batch_ids)} 位...", end=" ", flush=True)

        url = f"https://api.spotify.com/v1/artists?ids={','.join(batch_ids)}"
        data = api_get(url, token)
        if data is None:
            print("重新认证...")
            token = get_access_token(client_id, client_secret)
            data = api_get(url, token)

        if data:
            batch_dl = 0
            for art in data.get("artists", []):
                if art is None or not art.get("images"):
                    continue
                img_url = art["images"][0]["url"]

                local_ids = [aid for aid, sid in all_artists if sid == art["id"]]
                for local_id in local_ids:
                    filepath = os.path.join(COVERS_DIR, "artists", f"{local_id}.jpg")
                    if download_image(img_url, filepath):
                        db.execute(
                            "UPDATE artists SET image_url = ?, image_path = ? WHERE artist_id = ?",
                            [img_url, f"covers/artists/{local_id}.jpg", local_id],
                        )
                        batch_dl += 1

                genres = json.dumps(art.get("genres", []), ensure_ascii=False) if art.get("genres") else None
                db.execute(
                    """INSERT OR REPLACE INTO spotify_artist_meta(
                           spotify_artist_id, artist_name, popularity, followers,
                           genres, image_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (art["id"], art["name"], art.get("popularity"),
                     art.get("followers", {}).get("total"),
                     genres, img_url),
                )

            db.commit()
            downloaded += batch_dl
            print(f"✓ {batch_dl} 张下载")
        else:
            print("✗ 失败")

        if i + ARTIST_BATCH < len(spotify_ids):
            time.sleep(0.15)

    print(f"\n  艺人封面完成：{downloaded} 张下载\n")
    return token


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    load_dotenv()
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("错误：需要设置 Spotify API 凭据")
        print("  cp .env.example .env 并填入凭据，或设置环境变量")
        sys.exit(1)

    ensure_schema()
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # 确保目录存在
    os.makedirs(os.path.join(COVERS_DIR, "albums"), exist_ok=True)
    os.makedirs(os.path.join(COVERS_DIR, "artists"), exist_ok=True)

    print("获取 access token...")
    token = get_access_token(client_id, client_secret)
    print("✓ 认证成功\n")

    # ── 专辑封面 ──────────────────────────────────────────────────────
    print("=" * 60)
    print("PHASE 1/2: 专辑封面")
    print("=" * 60)
    print("查询播放记录中的专辑...")
    album_to_spotify, unresolved_albums = resolve_album_spotify_ids(db)
    print(f"  ① spotify_track_meta 已解析 {len(album_to_spotify)} 张，待处理 {len(unresolved_albums)} 张")

    # ② 通过 Track API 反查 album_id
    if unresolved_albums:
        extra_albums, unresolved_albums, token = resolve_album_via_track_api(
            db, token, client_id, client_secret, unresolved_albums
        )
        album_to_spotify.update(extra_albums)
        print(f"  ② Track API 反查：+{len(extra_albums)} 张，剩余 {len(unresolved_albums)} 张待搜索")
    else:
        unresolved_albums = []

    token = fetch_album_covers(db, token, client_id, client_secret,
                               album_to_spotify, unresolved_albums)

    # 重新认证（可能已过期）
    token = get_access_token(client_id, client_secret)

    # ── 艺人封面 ──────────────────────────────────────────────────────
    print("=" * 60)
    print("PHASE 2/2: 艺人封面")
    print("=" * 60)
    print("查询播放记录中的艺人...")
    artist_to_spotify, unresolved_artists = resolve_artist_spotify_ids(db)
    print(f"  ① spotify_artist_meta 已解析 {len(artist_to_spotify)} 位，待处理 {len(unresolved_artists)} 位")

    # ② 通过 Track API 反查 artist_id
    if unresolved_artists:
        extra_artists, unresolved_artists, token = resolve_artist_via_track_api(
            db, token, client_id, client_secret, unresolved_artists
        )
        artist_to_spotify.update(extra_artists)
        print(f"  ② Track API 反查：+{len(extra_artists)} 位，剩余 {len(unresolved_artists)} 位待搜索")
    else:
        unresolved_artists = []

    token = fetch_artist_covers(db, token, client_id, client_secret,
                                artist_to_spotify, unresolved_artists)

    # ── 汇总 ──────────────────────────────────────────────────────────
    album_count = db.execute(
        "SELECT COUNT(*) AS n FROM albums WHERE image_path IS NOT NULL AND image_path != ''"
    ).fetchone()["n"]
    artist_count = db.execute(
        "SELECT COUNT(*) AS n FROM artists WHERE image_path IS NOT NULL AND image_path != ''"
    ).fetchone()["n"]

    total_size = 0
    for root, dirs, files in os.walk(COVERS_DIR):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))

    print("=" * 60)
    print(f"全部完成：{album_count} 张专辑封面 / {artist_count} 张艺人照片")
    print(f"总占用空间：{total_size / 1024 / 1024:.1f} MB")
    print(f"存储路径：{COVERS_DIR}")

    db.close()


if __name__ == "__main__":
    main()
