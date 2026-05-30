"""Podcast listening stats service."""

import sqlite3

import pandas as pd


def get_podcast_stats(conn: sqlite3.Connection) -> dict:
    """Podcast listening: show rankings, monthly trend, interactions."""
    try:
        plays = pd.read_sql_query("SELECT * FROM podcast_plays ORDER BY end_time", conn)
        interactions = pd.read_sql_query("SELECT * FROM podcast_interactions", conn)
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
        plays.groupby("podcast_name")["ms_played"].sum()
        .div(3_600_000)
        .sort_values(ascending=False)
        .head(15)
    )

    # Monthly trend
    plays = plays.copy()
    plays["play_date"] = pd.to_datetime(plays["play_date"])
    monthly = (
        plays.groupby(plays["play_date"].dt.to_period("M"))["ms_played"]
        .sum()
        .div(3_600_000)
    )
    monthly.index = monthly.index.astype(str)

    return {
        "available": True,
        "empty": False,
        "total_plays": len(plays),
        "total_hours": round(plays["ms_played"].sum() / 3_600_000, 1),
        "unique_shows": plays["podcast_name"].nunique(),
        "saved_shows": len(saved_shows) if not saved_shows.empty else 0,
        "top_shows": [
            {"show_name": name, "hours": round(hours, 1)}
            for name, hours in show_hours.items()
        ],
        "monthly_trend": [
            {"period": str(idx), "hours": round(float(val), 1)}
            for idx, val in monthly.items()
        ],
    }


def get_podcast_interactions(conn: sqlite3.Connection) -> list[dict]:
    """Podcast interactions (follows, etc.)."""
    try:
        rows = conn.execute(
            "SELECT interaction_type, entity_uri, content_json, created_at FROM podcast_interactions"
        ).fetchall()
    except Exception:
        return []
    return [
        {"type": r["interaction_type"], "uri": r["entity_uri"] or "",
         "content": r["content_json"] or "", "created_at": r["created_at"] or ""}
        for r in rows
    ]


def get_saved_shows(conn: sqlite3.Connection) -> list[dict]:
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
