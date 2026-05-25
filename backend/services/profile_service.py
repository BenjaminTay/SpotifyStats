"""User profile service."""

import sqlite3


def get_profile(conn: sqlite3.Connection) -> dict:
    """User profile, follows, prompts, basic stats."""
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
            {"type": r["relationship_type"], "name": r["display_name"]}
            for r in follows
        ]
    except Exception:
        follows_list = []

    try:
        prompts = conn.execute(
            "SELECT message, created_timestamp FROM user_prompts"
        ).fetchall()
        prompts_list = [
            {"message": r["message"], "created": r["created_timestamp"] or ""}
            for r in prompts
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
        banned = conn.execute(
            "SELECT item_name, item_type FROM banned_items"
        ).fetchall()
        banned_list = [
            {"name": r["item_name"], "type": r["item_type"]}
            for r in banned
        ]
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
