"""Output helpers for Billboard records: artist name enrichment, cover URLs, serialization."""

import pandas as pd

from backend.core.db import get_db, get_track_artist_names_map
from backend.core.json_helpers import df_to_json as _df_to_json
from backend.core.json_helpers import py_val as _py_val


def _enrich_records_artist_names(records: dict) -> None:
    """Add artist_names column to DataFrames that have a track_id column."""
    names_map = get_track_artist_names_map()
    if not names_map:
        return
    names_df = pd.DataFrame(
        [(tid, names) for tid, names in names_map.items()],
        columns=["track_id", "artist_names"],
    )
    for key, val in records.items():
        if isinstance(val, pd.DataFrame) and "track_id" in val.columns:
            records[key] = val.merge(names_df, on="track_id", how="left")
            records[key]["artist_names"] = records[key]["artist_names"].apply(
                lambda x: x if isinstance(x, list) else None
            )


def _add_cover_urls(weekly, weekly_album, weekly_artist):
    """为三个周榜 DataFrame 添加 cover_url 列。

    cover_url 统一指向智能封面端点 /covers/{type}/{id}.jpg：
    - 本地有缓存 → 直接返回文件
    - 本地缺失 → 重定向到 Spotify CDN + 后台下载缓存
    - 无任何数据 → null（前端回退 emoji 占位符）
    """
    conn = get_db()

    def _build_url(image_path, image_url, cover_type, entity_id):
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
            r["track_id"]: _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
            if r["album_id"]
            else None
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
            if url or key not in album_cover_map:
                album_cover_map[key] = url
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
                            member_row["image_path"],
                            member_row["image_url"],
                            "albums",
                            member_row["album_id"],
                        )
                album_cover_map[key] = url

        weekly_album = weekly_album.copy()
        weekly_album["cover_url"] = weekly_album.apply(
            lambda row: album_cover_map.get((row["album_name"], row["artist_name"])), axis=1
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
            r["artist_name"]: _build_url(r["image_path"], r["image_url"], "artists", r["artist_id"])
            for r in artist_rows
        }
        weekly_artist = weekly_artist.copy()
        weekly_artist["cover_url"] = weekly_artist["artist_name"].map(artist_cover_map)

    conn.close()
    return weekly, weekly_album, weekly_artist


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
