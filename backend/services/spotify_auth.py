"""Spotify OAuth PKCE service — auth flow, saved tracks sync."""

import secrets
import sqlite3

from backend.core.cache_manager import invalidate
from backend.core.spotify_utils import (
    build_auth_url,
    exchange_code_for_tokens,
    fetch_currently_playing,
    generate_pkce_pair,
    get_followed_artists,
    get_playlists,
    get_recently_played,
    get_top_items,
    get_user_access_token,
    get_user_profile,
    is_user_connected,
    spotify_api_get_all_pages,
    store_user_tokens,
    sync_all_spotify_data,
)
from backend.domains.account_archive.revision import bump_archive_revision

# In-memory state → code_verifier mapping (single-user local app)
_pkce_store: dict[str, str] = {}


def begin_oauth_flow() -> dict:
    """Start PKCE flow. Returns {'auth_url': str, 'state': str}."""
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_hex(32)
    _pkce_store[state] = verifier
    auth_url = build_auth_url(challenge, state)
    return {"auth_url": auth_url, "state": state}


def complete_oauth_flow(conn: sqlite3.Connection, code: str, state: str) -> dict:
    """Complete PKCE flow. Exchanges code for tokens, stores them."""
    expected_verifier = _pkce_store.pop(state, None)
    if expected_verifier is None:
        return {"success": False, "error": "invalid_state"}

    token_resp = exchange_code_for_tokens(code, expected_verifier)
    if not token_resp or "access_token" not in token_resp:
        return {"success": False, "error": "token_exchange_failed"}

    store_user_tokens(
        conn,
        access_token=token_resp["access_token"],
        refresh_token=token_resp.get("refresh_token", ""),
        expires_in=token_resp.get("expires_in", 3600),
        scope=token_resp.get("scope", ""),
    )

    # Fetch and persist all available Spotify data
    sync_all_spotify_data(conn, token_resp["access_token"])

    return {"success": True}


def get_connection_status(conn: sqlite3.Connection) -> dict:
    """Return current Spotify connection status with data summary."""
    if not is_user_connected(conn):
        return {"connected": False}
    from backend.core.spotify_utils import _load_user_token_json

    data = _load_user_token_json(conn)
    profile = get_user_profile(conn)

    # Summarize available data
    available = {}
    for item_type in ["artists", "tracks"]:
        for tr in ["short_term", "medium_term", "long_term"]:
            label = f"top_{item_type}_{tr}"
            items = get_top_items(conn, item_type, tr)
            available[label] = len(items) if items else 0
    recent = get_recently_played(conn)
    available["recently_played"] = len(recent) if recent else 0
    follows = get_followed_artists(conn)
    available["followed_artists"] = len(follows) if follows else 0
    playlists = get_playlists(conn)
    available["playlists"] = len(playlists) if playlists else 0

    return {
        "connected": True,
        "scope": (data or {}).get("scope", ""),
        "connected_at": (data or {}).get("connected_at", ""),
        "profile": profile,
        "available_data": available,
    }


def get_live_playback(conn: sqlite3.Connection) -> dict:
    """Get current playback state (live, not cached)."""
    token = get_user_access_token(conn)
    if not token:
        return {"error": "not_connected"}
    current = fetch_currently_playing(token)
    if current and current.get("item"):
        item = current["item"]
        return {
            "is_playing": current.get("is_playing", False),
            "progress_ms": current.get("progress_ms"),
            "track": {
                "name": item.get("name"),
                "artists": [a.get("name") for a in item.get("artists", [])],
                "album": (item.get("album") or {}).get("name"),
                "duration_ms": item.get("duration_ms"),
                "uri": item.get("uri"),
                "images": (item.get("album") or {}).get("images", []),
            },
        }
    return {"is_playing": False, "track": None}


def fetch_saved_tracks(conn: sqlite3.Connection) -> dict:
    """Fetch all saved tracks from Spotify API and backfill added_date."""
    access_token = get_user_access_token(conn)
    if not access_token:
        return {"success": False, "error": "not_connected"}

    items = spotify_api_get_all_pages("https://api.spotify.com/v1/me/tracks", access_token)
    if not items:
        return {"success": False, "error": "api_fetch_failed"}

    uri_date_map: dict[str, str] = {}
    for item in items:
        track = item.get("track", {})
        uri = track.get("uri", "")
        added_at = item.get("added_at", "")
        if uri and added_at:
            uri_date_map[uri] = added_at

    saved_track_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(saved_tracks)").fetchall()
    }
    has_date_source = "added_date_source" in saved_track_columns
    updated = 0
    for uri, added_at in uri_date_map.items():
        if has_date_source:
            cur = conn.execute(
                "UPDATE saved_tracks SET added_date = ?, added_date_source = 'oauth' "
                "WHERE track_uri = ? AND (added_date IS NULL OR TRIM(added_date) = '')",
                (added_at, uri),
            )
        else:
            cur = conn.execute(
                "UPDATE saved_tracks SET added_date = ? "
                "WHERE track_uri = ? AND (added_date IS NULL OR TRIM(added_date) = '')",
                (added_at, uri),
            )
        updated += cur.rowcount
    if updated:
        bump_archive_revision(conn, "collection_date")
    conn.commit()
    if updated:
        invalidate("account")
        invalidate("account_archive")

    total_local = conn.execute("SELECT COUNT(*) FROM saved_tracks").fetchone()[0]
    matched = conn.execute(
        "SELECT COUNT(*) FROM saved_tracks WHERE added_date IS NOT NULL AND added_date != ''"
    ).fetchone()[0]

    return {
        "success": True,
        "total_in_spotify": len(items),
        "total_in_db": total_local,
        "matched": matched,
        "new_dates": updated,
    }
