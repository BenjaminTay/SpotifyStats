"""User profile service."""

import sqlite3
from pathlib import Path

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl

PROFILE_CACHE_TTL = 300


def _database_file_path(conn: sqlite3.Connection):
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        if not row[2]:
            return None
        return str(Path(row[2]).resolve())
    return None


@ttl_cached(PROFILE_CACHE_TTL, namespace="profile")
def _get_profile_cached(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_profile(conn)
    finally:
        conn.close()


def get_profile(conn: sqlite3.Connection) -> dict:
    """User profile, follows, prompts, basic stats."""
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_profile(conn)
    return _get_profile_cached(db_path)


def _build_profile(conn: sqlite3.Connection) -> dict:
    try:
        profile_rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
        profile = {r["key"]: r["value"] for r in profile_rows}
    except Exception:
        profile = {}

    try:
        follows = conn.execute(
            "SELECT relationship_type, display_name FROM user_follows"
        ).fetchall()
        follows_list = [
            {"type": r["relationship_type"], "name": r["display_name"]} for r in follows
        ]
    except Exception:
        follows_list = []

    try:
        prompts = conn.execute("SELECT message, created_timestamp FROM user_prompts").fetchall()
        prompts_list = [
            {"message": r["message"], "created": r["created_timestamp"] or ""} for r in prompts
        ]
    except Exception:
        prompts_list = []

    try:
        first_play = conn.execute("SELECT MIN(ts_date) FROM plays").fetchone()[0]
        audio_count = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE content_type='audio'"
        ).fetchone()[0]
    except Exception:
        first_play = None
        audio_count = 0

    try:
        banned = conn.execute("SELECT item_name, item_type FROM banned_items").fetchall()
        banned_list = [{"name": r["item_name"], "type": r["item_type"]} for r in banned]
    except Exception:
        banned_list = []

    return {
        "profile": profile,
        "follows": follows_list,
        "prompts": prompts_list,
        "stats": {
            "first_play_date": first_play,
            "total_audio_plays": audio_count,
        },
        "banned_items": banned_list,
    }


def get_inferences(conn: sqlite3.Connection) -> dict:
    """Get categorized inferences from the DB."""
    try:
        rows = conn.execute(
            "SELECT inference_text, category FROM inferences ORDER BY category"
        ).fetchall()
    except Exception:
        return {"available": False, "total": 0, "categories": {}}
    if not rows:
        return {"available": False, "total": 0, "categories": {}}
    categories: dict[str, list[str]] = {}
    for r in rows:
        cat = r["category"] or "other"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r["inference_text"])
    return {"available": True, "total": len(rows), "categories": categories}


def get_sound_capsule(conn: sqlite3.Connection) -> dict:
    """Get sound capsule highlights and daily stats."""
    try:
        highlights = conn.execute(
            "SELECT highlight_date, highlight_type, entity_name, detail_json "
            "FROM sound_capsule_highlights ORDER BY highlight_date DESC"
        ).fetchall()
        daily = conn.execute(
            "SELECT date, stream_count, seconds_played, top_data_json "
            "FROM sound_capsule_daily ORDER BY date DESC"
        ).fetchall()
    except Exception:
        return {"available": False}
    if not highlights and not daily:
        return {"available": False}
    return {
        "available": True,
        "highlights": [
            {
                "date": r["highlight_date"],
                "type": r["highlight_type"],
                "entity_name": r["entity_name"] or "",
                "detail": r["detail_json"],
            }
            for r in highlights
        ],
        "daily": [
            {
                "date": r["date"],
                "stream_count": r["stream_count"],
                "seconds_played": r["seconds_played"],
                "top_data": r["top_data_json"],
            }
            for r in daily
        ],
    }


register_ttl("profile", "data", _get_profile_cached)
