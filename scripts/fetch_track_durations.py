#!/usr/bin/env python3
"""从 Spotify Web API 批量获取歌曲/专辑/艺人全量元数据并存入数据库。

数据获取范围：
  歌曲 (tracks)    — duration_ms, popularity, explicit, track_number, disc_number, isrc
  专辑 (albums)    — album_type, release_date, popularity, label, genres, image_url
  艺人 (artists)   — popularity, followers, genres, image_url

使用方式：
  1. cp .env.example .env 并填入 Spotify API 凭据
  2. python3 scripts/fetch_track_durations.py

  可选参数：python3 scripts/fetch_track_durations.py --phase tracks|albums|artists|all
"""

import argparse
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import json
import base64
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import DB_PATH, ensure_schema

TRACK_BATCH = 50   # /v1/tracks 单次最多 50
ALBUM_BATCH = 20   # /v1/albums 单次最多 20
ARTIST_BATCH = 50  # /v1/artists 单次最多 50


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


def extract_spotify_id(uri: str) -> Optional[str]:
    if not uri or not uri.startswith("spotify:track:"):
        return None
    return uri.split(":")[-1]


def api_get(url: str, token: str) -> Optional[dict]:
    """GET 请求，自动处理 429 限速和 401 过期。返回 JSON 或 None。"""
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
            return None  # token 过期，由 caller 重试
        else:
            print(f"    HTTP {e.code}: {e.read().decode()[:150]}")
            return None
    except (urllib.error.URLError, OSError) as e:
        print(f"    网络错误: {e}")
        return None


# ── Phase 1: Tracks ────────────────────────────────────────────────────────

def fetch_tracks(db: sqlite3.Connection, token: str, client_id: str, client_secret: str):
    """批量获取所有歌曲的元数据。"""
    rows = db.execute(
        "SELECT t.track_id, t.track_name, t.album_id, t.spotify_track_uri FROM tracks t "
        "WHERE t.spotify_track_uri IS NOT NULL AND t.spotify_track_uri != '' "
        "AND REPLACE(t.spotify_track_uri, 'spotify:track:', '') "
        "    NOT IN (SELECT spotify_track_id FROM spotify_track_meta)"
    ).fetchall()

    if not rows:
        print("所有曲目已有时长数据，跳过。")
        return set(), set()

    # 建立 spotify_id → db record 映射
    pairs = []
    skipped = 0
    for r in rows:
        sid = extract_spotify_id(r["spotify_track_uri"])
        if sid:
            pairs.append((sid, r["track_id"], r["album_id"], r["track_name"]))
        else:
            skipped += 1

    print(f"共 {len(rows)} 首曲目待获取，{skipped} 首无有效 URI 跳过")
    print(f"分批请求，每批 {TRACK_BATCH} 首，约需 {(len(pairs) - 1) // TRACK_BATCH + 1} 次\n")

    spotify_album_ids = set()  # 收集到的专辑 ID
    updated = 0
    not_found = 0

    for i in range(0, len(pairs), TRACK_BATCH):
        batch = pairs[i : i + TRACK_BATCH]
        batch_ids = [p[0] for p in batch]
        bn = i // TRACK_BATCH + 1
        total = (len(pairs) - 1) // TRACK_BATCH + 1
        print(f"[曲目 {bn}/{total}] {len(batch)} 首...", end=" ", flush=True)

        fetched = _fetch_track_batch(db, token, batch, batch_ids)
        if fetched is None:
            print("重新认证...")
            token = get_access_token(client_id, client_secret)
            fetched = _fetch_track_batch(db, token, batch, batch_ids)

        if fetched:
            bu, bnf, album_ids = fetched
            updated += bu
            not_found += bnf
            spotify_album_ids.update(album_ids)
            print(f"✓ {bu} 已更新" + (f", {bnf} 未找到" if bnf else ""))
        else:
            print("✗ 失败")

        if i + TRACK_BATCH < len(pairs):
            time.sleep(0.3)

    # 写入 spotify_album_id → internal album_id 映射到临时表（供 album phase 使用）
    db.commit()
    print(f"\n曲目完成：{updated} 已更新, {not_found} 未找到, 收集到 {len(spotify_album_ids)} 个专辑 ID\n")
    return spotify_album_ids, set()


def _fetch_track_batch(db, token, batch, batch_ids):
    """获取一批曲目，写入 spotify_track_meta 表。返回 (updated, not_found, album_ids) 或 None。"""
    url = f"https://api.spotify.com/v1/tracks?ids={','.join(batch_ids)}"
    data = api_get(url, token)
    if data is None:
        return None

    updated = 0
    not_found = 0
    album_ids = set()

    for track in data.get("tracks", []):
        if track is None:
            not_found += 1
            continue

        # 找到对应的 db track_id
        matched = None
        for sid, tid, aid, tname in batch:
            if sid == track["id"]:
                matched = (tid, aid)
                break
        if matched is None:
            not_found += 1
            continue

        track_id, album_id = matched
        album_ids.add(track["album"]["id"])

        db.execute(
            """INSERT OR REPLACE INTO spotify_track_meta(
                   spotify_track_id, track_name, duration_ms, popularity,
                   explicit, track_number, disc_number, isrc, spotify_album_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                track["id"],
                track["name"],
                track["duration_ms"],
                track.get("popularity"),
                1 if track.get("explicit") else 0,
                track.get("track_number"),
                track.get("disc_number"),
                track.get("external_ids", {}).get("isrc"),
                track["album"]["id"],
            ),
        )

        updated += 1

    db.commit()
    return updated, not_found, album_ids


# ── Phase 2: Albums ────────────────────────────────────────────────────────

def fetch_albums(db: sqlite3.Connection, token: str, client_id: str, client_secret: str,
                 track_album_ids: set):
    """批量获取专辑详情（label, genres, popularity, copyrights）。"""
    # 从 spotify_track_meta 收集专辑 ID（独立元数据表，不依赖主维度表）
    if track_album_ids:
        # 从 track phase 收集到的专辑 ID，排除已抓取的
        already = {r[0] for r in db.execute(
            "SELECT spotify_album_id FROM spotify_album_meta"
        ).fetchall()}
        pending_ids = [aid for aid in track_album_ids if aid not in already]
        album_rows = [{"spotify_album_id": aid, "album_name": None} for aid in pending_ids]
    else:
        album_rows = db.execute(
            "SELECT DISTINCT stm.spotify_album_id, NULL AS album_name FROM spotify_track_meta stm "
            "WHERE stm.spotify_album_id IS NOT NULL "
            "AND stm.spotify_album_id NOT IN (SELECT spotify_album_id FROM spotify_album_meta)"
        ).fetchall()

    if not album_rows:
        print("所有专辑已有元数据，跳过。")
        return

    ids = [r["spotify_album_id"] for r in album_rows]
    print(f"共 {len(ids)} 张专辑待获取")
    print(f"分批请求，每批 {ALBUM_BATCH} 张，约需 {(len(ids) - 1) // ALBUM_BATCH + 1} 次\n")

    updated = 0
    failed_ids = set()

    for i in range(0, len(ids), ALBUM_BATCH):
        batch_ids = ids[i : i + ALBUM_BATCH]
        bn = i // ALBUM_BATCH + 1
        total = (len(ids) - 1) // ALBUM_BATCH + 1
        print(f"[专辑 {bn}/{total}] {len(batch_ids)} 张...", end=" ", flush=True)

        url = f"https://api.spotify.com/v1/albums?ids={','.join(batch_ids)}"
        data = api_get(url, token)
        if data is None:
            print("重新认证...")
            token = get_access_token(client_id, client_secret)
            data = api_get(url, token)

        if data:
            bu = 0
            for alb in data.get("albums", []):
                if alb is None:
                    failed_ids.add(None)
                    continue
                img_url = alb["images"][0]["url"] if alb.get("images") else None
                genres = json.dumps(alb.get("genres", []), ensure_ascii=False) if alb.get("genres") else None
                db.execute(
                    """INSERT OR REPLACE INTO spotify_album_meta(
                           spotify_album_id, album_name, album_type, release_date,
                           popularity, label, genres, image_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        alb["id"],
                        alb["name"],
                        alb.get("album_type"),
                        alb.get("release_date"),
                        alb.get("popularity"),
                        alb.get("label"),
                        genres,
                        img_url,
                    ),
                )
                bu += 1
            updated += bu
            print(f"✓ {bu} 已更新")
        else:
            print("✗ 失败")

        if i + ALBUM_BATCH < len(ids):
            time.sleep(0.3)

    db.commit()
    print(f"\n专辑完成：{updated} 已更新\n")


# ── Phase 3: Artists ───────────────────────────────────────────────────────

def fetch_artists(db: sqlite3.Connection, token: str, client_id: str, client_secret: str):
    """通过搜索匹配艺人名，获取 Spotify 艺人详情。"""
    # 找出尚未获取 Spotify 元数据的艺人（不在 spotify_artist_meta 中的）
    artist_rows = db.execute(
        "SELECT artist_id, artist_name FROM artists "
        "WHERE artist_name NOT IN (SELECT artist_name FROM spotify_artist_meta)"
    ).fetchall()

    if not artist_rows:
        print("所有艺人已有 Spotify 数据，跳过。")
        return

    print(f"共 {len(artist_rows)} 位艺人待获取，逐位搜索...\n")

    updated = 0
    not_found = 0

    for idx, row in enumerate(artist_rows):
        aid = row["artist_id"]
        name = row["artist_name"]
        print(f"[艺人 {idx+1}/{len(artist_rows)}] {name[:40]}...", end=" ", flush=True)

        # 搜索艺人
        q = urllib.parse.quote(name)
        data = api_get(f"https://api.spotify.com/v1/search?q={q}&type=artist&limit=3", token)
        if data is None:
            token = get_access_token(client_id, client_secret)
            data = api_get(f"https://api.spotify.com/v1/search?q={q}&type=artist&limit=3", token)

        if data and data.get("artists", {}).get("items"):
            # 按名称精确匹配
            items = data["artists"]["items"]
            matched = None
            name_lower = name.lower()
            for item in items:
                if item["name"].lower() == name_lower:
                    matched = item
                    break

            if matched:
                genres = json.dumps(matched.get("genres", []), ensure_ascii=False) if matched.get("genres") else None
                img_url = matched["images"][0]["url"] if matched.get("images") else None
                db.execute(
                    """INSERT OR REPLACE INTO spotify_artist_meta(
                           spotify_artist_id, artist_name, popularity, followers,
                           genres, image_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        matched["id"],
                        name,
                        matched.get("popularity"),
                        matched.get("followers", {}).get("total"),
                        genres,
                        img_url,
                    ),
                )
                updated += 1
                print(f"✓ popularity={matched.get('popularity')} genres={matched.get('genres', [])}")
            else:
                not_found += 1
                print(f"✗ 搜索无精确匹配")
        else:
            not_found += 1
            print("✗ 搜索失败")

        if (idx + 1) % 30 == 0:
            time.sleep(1.0)  # 搜索端点速率限制更严
        else:
            time.sleep(0.15)

    db.commit()
    print(f"\n艺人完成：{updated} 已更新, {not_found} 未匹配\n")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="从 Spotify API 获取全量元数据")
    parser.add_argument("--client-id", help="Spotify Client ID")
    parser.add_argument("--client-secret", help="Spotify Client Secret")
    parser.add_argument("--db", default=DB_PATH, help="数据库路径")
    parser.add_argument("--phase", choices=["tracks", "albums", "artists", "all"],
                        default="all", help="只执行指定阶段 (默认 all)")
    args = parser.parse_args()

    load_dotenv()
    client_id = args.client_id or os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = args.client_secret or os.environ.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("错误：需要设置 Spotify API 凭据")
        print("  cp .env.example .env 并填入凭据，或设置环境变量")
        print("  export SPOTIFY_CLIENT_ID='xxx'")
        print("  export SPOTIFY_CLIENT_SECRET='yyy'")
        sys.exit(1)

    # 确保 schema 包含新列
    ensure_schema()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    print("获取 access token...")
    token = get_access_token(client_id, client_secret)
    print("✓ 认证成功\n")

    track_album_ids = set()

    if args.phase in ("tracks", "all"):
        print("=" * 60)
        print("PHASE 1/3: 歌曲元数据")
        print("=" * 60)
        result = fetch_tracks(db, token, client_id, client_secret)
        if result:
            track_album_ids, _ = result
        # 重新获取 token（可能已过期）
        token = get_access_token(client_id, client_secret)

    if args.phase in ("albums", "all"):
        print("=" * 60)
        print("PHASE 2/3: 专辑详情")
        print("=" * 60)
        fetch_albums(db, token, client_id, client_secret, track_album_ids)
        token = get_access_token(client_id, client_secret)

    if args.phase in ("artists", "all"):
        print("=" * 60)
        print("PHASE 3/3: 艺人详情")
        print("=" * 60)
        fetch_artists(db, token, client_id, client_secret)

    # 汇总
    tc = db.execute("SELECT COUNT(*) AS n FROM spotify_track_meta").fetchone()["n"]
    ac = db.execute("SELECT COUNT(*) AS n FROM spotify_album_meta").fetchone()["n"]
    rc = db.execute("SELECT COUNT(*) AS n FROM spotify_artist_meta").fetchone()["n"]

    print("=" * 60)
    print(f"全部完成：{tc} 首歌曲 / {ac} 张专辑 / {rc} 位艺人 已获取 Spotify 元数据")

    db.close()


if __name__ == "__main__":
    main()
