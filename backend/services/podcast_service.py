"""Podcast listening stats service."""

import sqlite3
from pathlib import Path

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl

PODCAST_CACHE_TTL = 600


def _database_file_path(conn: sqlite3.Connection):
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        if not row[2]:
            return None
        return str(Path(row[2]).resolve())
    return None


def _build_podcast_stats(conn: sqlite3.Connection) -> dict:
    """Podcast listening: show rankings, monthly trend, interactions."""
    try:
        plays = pd.read_sql_query("SELECT * FROM podcast_plays ORDER BY end_time", conn)
        saved_shows = pd.read_sql_query("SELECT * FROM saved_shows", conn)
    except Exception:
        return {"available": False}

    if plays.empty:
        return {"available": True, "empty": True}

    # Filter out very short plays (previews / autoplay noise), same threshold as video
    plays = plays[plays["ms_played"] >= 30000]

    if plays.empty:
        return {"available": True, "empty": True}

    # Show rankings by listening time (descending)
    show_hours = (
        plays.groupby("podcast_name")["ms_played"]
        .sum()
        .div(3_600_000)
        .sort_values(ascending=False)
        .head(15)
    )

    # Monthly trend
    plays = plays.copy()
    plays["play_date"] = pd.to_datetime(plays["play_date"])
    monthly = plays.groupby(plays["play_date"].dt.to_period("M"))["ms_played"].sum().div(3_600_000)
    monthly.index = monthly.index.astype(str)

    return {
        "available": True,
        "empty": False,
        "total_plays": len(plays),
        "total_hours": round(plays["ms_played"].sum() / 3_600_000, 1),
        "unique_shows": plays["podcast_name"].nunique(),
        "saved_shows": len(saved_shows) if not saved_shows.empty else 0,
        "top_shows": [
            {"show_name": name, "hours": round(hours, 1)} for name, hours in show_hours.items()
        ],
        "monthly_trend": [
            {"period": str(idx), "hours": round(float(val), 1)} for idx, val in monthly.items()
        ],
    }


@ttl_cached(PODCAST_CACHE_TTL, namespace="podcast")
def _get_podcast_stats_cached(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_podcast_stats(conn)
    finally:
        conn.close()


def get_podcast_stats(conn: sqlite3.Connection) -> dict:
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_podcast_stats(conn)
    return _get_podcast_stats_cached(db_path)


def _build_podcast_interactions(conn: sqlite3.Connection) -> list[dict]:
    """Podcast interactions (follows, etc.)."""
    try:
        rows = conn.execute(
            "SELECT interaction_type, entity_uri, content_json, created_at FROM podcast_interactions"
        ).fetchall()
    except Exception:
        return []
    return [
        {
            "type": r["interaction_type"],
            "uri": r["entity_uri"] or "",
            "content": r["content_json"] or "",
            "created_at": r["created_at"] or "",
        }
        for r in rows
    ]


@ttl_cached(PODCAST_CACHE_TTL, namespace="podcast")
def _get_podcast_interactions_cached(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_podcast_interactions(conn)
    finally:
        conn.close()


def get_podcast_interactions(conn: sqlite3.Connection) -> list[dict]:
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_podcast_interactions(conn)
    return _get_podcast_interactions_cached(db_path)


def _build_saved_shows(conn: sqlite3.Connection) -> list[dict]:
    """Saved/followed shows."""
    try:
        rows = conn.execute(
            "SELECT show_uri, show_name, publisher FROM saved_shows ORDER BY show_name"
        ).fetchall()
    except Exception:
        return []
    return [
        {"uri": r["show_uri"], "name": r["show_name"], "publisher": r["publisher"] or ""}
        for r in rows
    ]


@ttl_cached(PODCAST_CACHE_TTL, namespace="podcast")
def _get_saved_shows_cached(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_saved_shows(conn)
    finally:
        conn.close()


def get_saved_shows(conn: sqlite3.Connection) -> list[dict]:
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_saved_shows(conn)
    return _get_saved_shows_cached(db_path)


register_ttl("podcast", "podcast_stats", _get_podcast_stats_cached)
register_ttl("podcast", "podcast_interactions", _get_podcast_interactions_cached)
register_ttl("podcast", "saved_shows", _get_saved_shows_cached)
