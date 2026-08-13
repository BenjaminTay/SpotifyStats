"""Search history analysis service."""

import sqlite3
from pathlib import Path

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.core.db import connect_sqlite_path

SEARCH_CACHE_TTL = 120


def _database_file_path(conn: sqlite3.Connection):
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        if not row[2]:
            return None
        return str(Path(row[2]).resolve())
    return None


def _build_search_stats(conn: sqlite3.Connection) -> dict:
    """Search history: daily volume, intent distribution, top queries, heatmap."""
    try:
        df = pd.read_sql_query("SELECT * FROM search_queries ORDER BY search_time_utc", conn)
    except Exception:
        return {"available": False}

    if df.empty:
        return {"available": True, "empty": True}

    # Get artist/track names for intent classification
    artist_names = set(r[0] for r in conn.execute("SELECT artist_name FROM artists").fetchall())
    track_names = set(r[0] for r in conn.execute("SELECT track_name FROM tracks").fetchall())

    # Simple intent classification
    def classify_intent(q, artists, tracks):
        q_lower = q.lower().strip()
        if q_lower in (a.lower() for a in artists):
            return "艺人搜索"
        if q_lower in (t.lower() for t in tracks):
            return "曲目搜索"
        return "一般搜索"

    df["intent"] = df["query_text"].apply(lambda q: classify_intent(q, artist_names, track_names))

    # Daily volume
    daily = df.groupby("search_date").size().reset_index(name="cnt")
    daily = daily.sort_values("search_date")

    # Top 30 queries
    top_queries = df["query_text"].value_counts().head(30).reset_index()
    top_queries.columns = ["query", "cnt"]

    # Intent distribution
    intent_dist = df["intent"].value_counts().reset_index()
    intent_dist.columns = ["intent", "cnt"]

    # DOW x Hour heatmap
    pivot = df.groupby(["search_dow", "search_hour"]).size().unstack(fill_value=0)
    dow_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    z = []
    for d in range(7):
        row = [
            int(pivot.loc[d, h]) if d in pivot.index and h in pivot.columns else 0
            for h in range(24)
        ]
        z.append(row)

    return {
        "available": True,
        "empty": False,
        "total_searches": len(df),
        "daily_volume": [
            {"date": r.search_date, "count": int(r.cnt)} for r in daily.itertuples(index=False)
        ],
        "top_queries": [
            {"query": r.query, "count": int(r.cnt)} for r in top_queries.itertuples(index=False)
        ],
        "intent_dist": [
            {"intent": r.intent, "count": int(r.cnt)} for r in intent_dist.itertuples(index=False)
        ],
        "heatmap": {"z": z, "x": list(range(24)), "y": dow_names},
    }


@ttl_cached(SEARCH_CACHE_TTL, namespace="search")
def _get_search_stats_cached(db_path: str) -> dict:
    conn = connect_sqlite_path(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_search_stats(conn)
    finally:
        conn.close()


def get_search_stats(conn: sqlite3.Connection) -> dict:
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_search_stats(conn)
    return _get_search_stats_cached(db_path)


register_ttl("search", "search_stats", _get_search_stats_cached)
