"""Insights: artist tiers, marquee conversion."""

import sqlite3
from pathlib import Path

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl

INSIGHTS_CACHE_TTL = 600


def _database_file_path(conn: sqlite3.Connection):
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        if not row[2]:
            return None
        return str(Path(row[2]).resolve())
    return None


def _build_artist_tiers(conn: sqlite3.Connection) -> dict:
    """Artist tier classification based on play counts."""
    try:
        artist_df = pd.read_sql_query(
            """SELECT a.artist_name, COUNT(DISTINCT p.play_id) as play_count,
                      SUM(p.ms_played) / 3600000.0 as hours
               FROM plays p
               JOIN tracks t ON p.track_id = t.track_id
               JOIN track_artists ta ON t.track_id = ta.track_id
               JOIN artists a ON ta.artist_id = a.artist_id
               WHERE p.track_id IS NOT NULL
               GROUP BY a.artist_name
               ORDER BY hours DESC""",
            conn,
        )
    except Exception:
        return {"available": False}

    if artist_df.empty:
        return {"available": True, "empty": True}

    artist_df = artist_df.sort_values("hours", ascending=False).reset_index(drop=True)
    artist_df["rank"] = range(1, len(artist_df) + 1)

    def classify_tier(r):
        if r < 5:
            return "超级粉丝 (Top 5)"
        elif r < 15:
            return "核心艺人 (Top 15)"
        else:
            return "泛听艺人"

    artist_df["tier"] = artist_df["rank"].apply(classify_tier)

    tier_hours = artist_df.groupby("tier")["hours"].sum().to_dict()
    tier_counts = artist_df.groupby("tier").size().to_dict()

    # Resolve artist cover URLs
    artists_with_covers = conn.execute(
        "SELECT artist_name, artist_id, image_path, image_url FROM artists"
    ).fetchall()
    cover_map = {}
    for r in artists_with_covers:
        if r["image_path"] or r["image_url"]:
            cover_map[r["artist_name"]] = f"/covers/artists/{int(r['artist_id'])}.jpg"

    return {
        "available": True,
        "empty": False,
        "total_artists": len(artist_df),
        "tier_hours": {k: round(v, 1) for k, v in tier_hours.items()},
        "tier_counts": {k: int(v) for k, v in tier_counts.items()},
        "artists": [
            {
                "rank": int(r.rank),
                "artist_name": r.artist_name,
                "play_count": int(r.play_count),
                "hours": round(r.hours, 1),
                "tier": r.tier,
                "cover_url": cover_map.get(r.artist_name),
            }
            for r in artist_df.itertuples(index=False)
        ],
    }


@ttl_cached(INSIGHTS_CACHE_TTL, namespace="insights")
def _get_artist_tiers_cached(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_artist_tiers(conn)
    finally:
        conn.close()


def get_artist_tiers(conn: sqlite3.Connection) -> dict:
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_artist_tiers(conn)
    return _get_artist_tiers_cached(db_path)


def _build_marquee_conversion(conn: sqlite3.Connection) -> dict:
    """Marquee impression to actual plays conversion."""
    try:
        df = pd.read_sql_query(
            """SELECT mi.artist_name, MAX(mi.segment) as segment,
                      COUNT(DISTINCT mi.id) as impressions,
                      COUNT(DISTINCT p.play_id) as actual_plays,
                      COALESCE(SUM(p.ms_played) / 3600000.0, 0) as actual_hours
               FROM marquee_impressions mi
               LEFT JOIN artists a ON mi.artist_name = a.artist_name
               LEFT JOIN tracks t ON t.artist_id = a.artist_id
               LEFT JOIN plays p ON p.track_id = t.track_id
               GROUP BY mi.artist_name
               ORDER BY impressions DESC""",
            conn,
        )
    except Exception:
        return {"available": False}

    if df.empty:
        return {"available": True, "empty": True}

    # Resolve artist cover URLs
    artists_with_covers = conn.execute(
        "SELECT artist_name, artist_id, image_path, image_url FROM artists"
    ).fetchall()
    cover_map = {}
    for r in artists_with_covers:
        if r["image_path"] or r["image_url"]:
            cover_map[r["artist_name"]] = f"/covers/artists/{int(r['artist_id'])}.jpg"

    conversions = []
    for r in df.itertuples(index=False):
        imp = int(r.impressions)
        plays = int(r.actual_plays)
        rate = plays / imp if imp > 0 else 0
        conversions.append(
            {
                "artist_name": r.artist_name,
                "segment": r.segment or "",
                "impressions": imp,
                "actual_plays": plays,
                "actual_hours": round(r.actual_hours, 1),
                "conversion_rate": round(rate, 4),
                "cover_url": cover_map.get(r.artist_name),
            }
        )
    conversions.sort(key=lambda x: -x["conversion_rate"])

    return {
        "available": True,
        "empty": False,
        "conversions": conversions,
    }


@ttl_cached(INSIGHTS_CACHE_TTL, namespace="insights")
def _get_marquee_conversion_cached(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_marquee_conversion(conn)
    finally:
        conn.close()


def get_marquee_conversion(conn: sqlite3.Connection) -> dict:
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_marquee_conversion(conn)
    return _get_marquee_conversion_cached(db_path)


register_ttl("insights", "artist_tiers", _get_artist_tiers_cached)
register_ttl("insights", "marquee_conversion", _get_marquee_conversion_cached)
