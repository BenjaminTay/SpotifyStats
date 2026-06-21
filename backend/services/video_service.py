"""Music video analysis service."""

import sqlite3
from pathlib import Path

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl

VIDEO_CACHE_TTL = 600


def _database_file_path(conn: sqlite3.Connection):
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        if not row[2]:
            return None
        return str(Path(row[2]).resolve())
    return None


def _build_video_stats(conn: sqlite3.Connection) -> dict:
    """Video play stats: platform dist, top tracks, audio vs video comparison."""
    try:
        video_df = pd.read_sql_query(
            """SELECT p.*, t.track_name, a.artist_name
               FROM plays p LEFT JOIN tracks t ON p.track_id = t.track_id
               LEFT JOIN artists a ON t.artist_id = a.artist_id
               WHERE p.content_type = 'video' AND p.ms_played >= 30000
               ORDER BY p.ts""",
            conn,
        )
        audio_count = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE content_type = 'audio'"
        ).fetchone()[0]
    except Exception:
        return {"available": False}

    if video_df.empty:
        return {"available": True, "empty": True}

    # Platform distribution
    platform_dist = video_df["platform"].value_counts().to_dict()

    # Avg duration
    avg_duration = video_df["ms_played"].mean() / 1000

    # Yearly audio vs video (audio count includes all, not just match)
    yearly = conn.execute(
        """SELECT ts_year, content_type, COUNT(*) as cnt
           FROM plays WHERE content_type != 'video' OR ms_played >= 30000
           GROUP BY ts_year, content_type ORDER BY ts_year"""
    ).fetchall()

    yearly_data = {}
    for r in yearly:
        y = r["ts_year"]
        if y not in yearly_data:
            yearly_data[y] = {"audio": 0, "video": 0}
        yearly_data[y][r["content_type"]] = r["cnt"]

    # Top video tracks with audio comparison
    comparison = conn.execute(
        """SELECT t.track_name, a.artist_name,
                  SUM(CASE WHEN p.content_type='video' AND p.ms_played >= 30000 THEN 1 ELSE 0 END) as video_plays,
                  SUM(CASE WHEN p.content_type='audio' THEN 1 ELSE 0 END) as audio_plays
           FROM plays p JOIN tracks t ON p.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           WHERE p.content_type IN ('video', 'audio') AND p.track_id IS NOT NULL
           GROUP BY p.track_id
           HAVING video_plays > 0
           ORDER BY video_plays DESC LIMIT 30"""
    ).fetchall()

    # Resolve track cover URLs for top video tracks
    track_names = [r["track_name"] for r in comparison]
    artist_names = [r["artist_name"] for r in comparison]
    if track_names:
        pairs = list(zip(track_names, artist_names))
        placeholders = ",".join("(?,?)" for _ in pairs)
        flat_params = [v for pair in pairs for v in pair]
        cover_rows = conn.execute(
            f"""SELECT t.track_name, a.artist_name, al.album_id, al.image_path, al.image_url
                FROM tracks t
                JOIN artists a ON t.artist_id = a.artist_id
                LEFT JOIN albums al ON t.album_id = al.album_id
                WHERE (t.track_name, a.artist_name) IN ({placeholders})""",
            flat_params,
        ).fetchall()
        cover_map = {}
        for r in cover_rows:
            key = (r["track_name"], r["artist_name"])
            if key not in cover_map and r["album_id"] and (r["image_path"] or r["image_url"]):
                cover_map[key] = f"/covers/albums/{int(r['album_id'])}.jpg"
    else:
        cover_map = {}

    return {
        "available": True,
        "empty": False,
        "total_video_plays": len(video_df),
        "total_audio_plays": audio_count,
        "avg_duration_sec": round(avg_duration, 1),
        "platform_dist": {k: int(v) for k, v in platform_dist.items()},
        "yearly": [
            {"year": y, "audio": d["audio"], "video": d["video"]}
            for y, d in sorted(yearly_data.items())
        ],
        "top_video_tracks": [
            {
                "track_name": r["track_name"],
                "artist_name": r["artist_name"],
                "video_plays": int(r["video_plays"]),
                "audio_plays": int(r["audio_plays"]),
                "cover_url": cover_map.get((r["track_name"], r["artist_name"])),
            }
            for r in comparison
        ],
    }


@ttl_cached(VIDEO_CACHE_TTL, namespace="video")
def _get_video_stats_cached(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_video_stats(conn)
    finally:
        conn.close()


def get_video_stats(conn: sqlite3.Connection) -> dict:
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_video_stats(conn)
    return _get_video_stats_cached(db_path)


register_ttl("video", "video_stats", _get_video_stats_cached)
