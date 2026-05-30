"""Shared Spotify API utilities: client-credentials token + user OAuth PKCE.

Client-credentials token is TTL-cached in memory (~58 min).
User token is persisted in the settings table as a JSON blob keyed
'spotify_user_token'. Access token is auto-refreshed from refresh_token.
"""

import json
import base64
import sqlite3
import time
import hashlib
import secrets
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

import logging

from backend.core.cache import ttl_cached
from backend.core.config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)
import backend.core.crypto as crypto

logger = logging.getLogger(__name__)

_TOKEN_KEY = "spotify_user_token"
_PROFILE_KEY = "spotify_user_profile"


def get_client_id() -> Optional[str]:
    return SPOTIFY_CLIENT_ID or None


def get_redirect_uri() -> str:
    return SPOTIFY_REDIRECT_URI


# ---- Client Credentials (app-level) ----

@ttl_cached(3500)
def get_client_credentials_token() -> Optional[str]:
    """Get Spotify client_credentials token, TTL-cached ~58 minutes."""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    auth_b64 = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())["access_token"]
    except (OSError, urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None


# ---- PKCE helpers ----

def generate_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(code_challenge: str, state: str) -> str:
    client_id = get_client_id()
    if not client_id:
        raise RuntimeError("SPOTIFY_CLIENT_ID not configured")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": "user-library-read user-read-private user-read-email user-top-read user-read-recently-played user-read-currently-playing user-read-playback-state user-follow-read playlist-read-private playlist-read-collaborative",
        "redirect_uri": get_redirect_uri(),
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state,
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)


# ---- Token exchange & refresh ----

def exchange_code_for_tokens(code: str, code_verifier: str) -> Optional[dict]:
    """Exchange authorization code for access + refresh tokens."""
    client_id = get_client_id()
    if not client_id:
        return None
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": get_redirect_uri(),
        "client_id": client_id,
        "code_verifier": code_verifier,
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


def _refresh_user_token(refresh_token: str) -> Optional[dict]:
    """Refresh an expired access token using the refresh_token."""
    client_id = get_client_id()
    if not client_id:
        return None
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


# ---- Persistent token storage (settings table) ----

def _load_user_token_json(conn) -> Optional[dict]:
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_TOKEN_KEY,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    raw = row[0]
    if crypto.is_encrypted(raw):
        try:
            return json.loads(crypto.decrypt(raw))
        except (json.JSONDecodeError, Exception):
            return None
    # Legacy plaintext — auto-migrate to encrypted storage
    try:
        token_data = json.loads(raw)
        try:
            _save_user_token_json(conn, token_data)
        except sqlite3.OperationalError:
            pass  # Read-only connection (e.g., tests) — will migrate on next write
        return token_data
    except json.JSONDecodeError:
        return None


def _save_user_token_json(conn, token_data: dict) -> None:
    encrypted = crypto.encrypt(json.dumps(token_data))
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (_TOKEN_KEY, encrypted),
    )
    conn.commit()


def is_user_connected(conn) -> bool:
    data = _load_user_token_json(conn)
    return data is not None and "refresh_token" in data


def clear_user_tokens(conn) -> None:
    """Clear all Spotify-related data from settings table."""
    keys_to_clear = [_TOKEN_KEY, _PROFILE_KEY, _RECENT_KEY, _FOLLOWS_KEY, _PLAYLISTS_KEY]
    for tr in TIME_RANGES:
        for item_type in ["artists", "tracks"]:
            keys_to_clear.append(_TOP_KEY.format(type=item_type, time_range=tr))
    for key in keys_to_clear:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()


def get_user_access_token(conn) -> Optional[str]:
    """Get a valid user access token. Auto-refreshes if expired. Returns None if not connected."""
    data = _load_user_token_json(conn)
    if not data or "refresh_token" not in data:
        return None

    access_token = data.get("access_token")
    expires_at = data.get("expires_at", 0)
    if access_token and expires_at > time.time() + 60:
        return access_token

    refreshed = _refresh_user_token(data["refresh_token"])
    if not refreshed:
        logger.warning("Spotify user token refresh failed")
        return None

    new_data = {
        "refresh_token": refreshed.get("refresh_token", data["refresh_token"]),
        "access_token": refreshed["access_token"],
        "expires_at": time.time() + refreshed.get("expires_in", 3600),
        "scope": refreshed.get("scope", data.get("scope", "")),
        "connected_at": data.get("connected_at", ""),
    }
    _save_user_token_json(conn, new_data)
    return new_data["access_token"]


def store_user_tokens(conn, access_token: str, refresh_token: str,
                      expires_in: int, scope: str) -> None:
    token_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
        "scope": scope,
        "connected_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }
    _save_user_token_json(conn, token_data)


# ---- User Profile (Spotify /v1/me) ----

def fetch_spotify_profile(access_token: str) -> Optional[dict]:
    """Fetch Spotify user profile from /v1/me."""
    return spotify_api_get("https://api.spotify.com/v1/me", access_token)


def save_user_profile(conn, profile: dict) -> None:
    """Persist Spotify profile to settings table."""
    data = {
        "id": profile.get("id", ""),
        "display_name": profile.get("display_name", ""),
        "email": profile.get("email", ""),
        "country": profile.get("country", ""),
        "product": profile.get("product", ""),
        "followers": (profile.get("followers") or {}).get("total", 0),
        "images": (profile.get("images") or [])[:3],
        "uri": profile.get("uri", ""),
        "external_urls": profile.get("external_urls", {}),
    }
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (_PROFILE_KEY, json.dumps(data)),
    )
    conn.commit()


def get_user_profile(conn) -> Optional[dict]:
    """Load persisted Spotify profile."""
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_PROFILE_KEY,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


# ---- Top Artists / Tracks (user-top-read) ----

_TOP_KEY = "spotify_top_{type}_{time_range}"

TIME_RANGES = ["short_term", "medium_term", "long_term"]


def fetch_top_artists(access_token: str, time_range: str = "medium_term",
                      limit: int = 50) -> Optional[list[dict]]:
    """Fetch user's top artists from Spotify. Returns list of artist dicts."""
    return _fetch_top_items(access_token, "artists", time_range, limit)


def fetch_top_tracks(access_token: str, time_range: str = "medium_term",
                     limit: int = 50) -> Optional[list[dict]]:
    """Fetch user's top tracks from Spotify. Returns list of track dicts."""
    return _fetch_top_items(access_token, "tracks", time_range, limit)


def _fetch_top_items(access_token: str, item_type: str, time_range: str,
                     limit: int) -> Optional[list[dict]]:
    url = (f"https://api.spotify.com/v1/me/top/{item_type}"
           f"?time_range={time_range}&limit={limit}")
    data = spotify_api_get(url, access_token)
    return data.get("items", []) if data else None


def save_top_items(conn, item_type: str, time_range: str, items: list[dict]) -> None:
    """Persist top artists/tracks to settings table as JSON."""
    key = _TOP_KEY.format(type=item_type, time_range=time_range)
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (key, json.dumps(items)),
    )
    conn.commit()


def get_top_items(conn, item_type: str, time_range: str) -> Optional[list[dict]]:
    """Load persisted top artists/tracks from settings table."""
    key = _TOP_KEY.format(type=item_type, time_range=time_range)
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


# ---- Recently Played (user-read-recently-played) ----

_RECENT_KEY = "spotify_recently_played"


def fetch_recently_played(access_token: str, limit: int = 50) -> Optional[list[dict]]:
    """Fetch user's recently played tracks from Spotify."""
    url = f"https://api.spotify.com/v1/me/player/recently-played?limit={limit}"
    data = spotify_api_get(url, access_token)
    return data.get("items", []) if data else None


def save_recently_played(conn, items: list[dict]) -> None:
    """Persist recently played to settings table as JSON."""
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (_RECENT_KEY, json.dumps(items)),
    )
    conn.commit()


def get_recently_played(conn) -> Optional[list[dict]]:
    """Load persisted recently played from settings table."""
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_RECENT_KEY,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


# ---- Current Playback (user-read-currently-playing / user-read-playback-state) ----

def fetch_current_playback(access_token: str) -> Optional[dict]:
    """Fetch user's current playback state (live, not persisted)."""
    return spotify_api_get("https://api.spotify.com/v1/me/player", access_token)


def fetch_currently_playing(access_token: str) -> Optional[dict]:
    """Fetch user's currently playing track (live, not persisted)."""
    return spotify_api_get("https://api.spotify.com/v1/me/player/currently-playing", access_token)


# ---- Followed Artists (user-follow-read) ----

_FOLLOWS_KEY = "spotify_followed_artists"


def fetch_followed_artists(access_token: str) -> Optional[list[dict]]:
    """Fetch all followed artists from Spotify."""
    items = spotify_api_get_all_pages(
        "https://api.spotify.com/v1/me/following?type=artist", access_token
    )
    return items if items else None


def save_followed_artists(conn, items: list[dict]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (_FOLLOWS_KEY, json.dumps(items)),
    )
    conn.commit()


def get_followed_artists(conn) -> Optional[list[dict]]:
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_FOLLOWS_KEY,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


# ---- Playlists (playlist-read-private + playlist-read-collaborative) ----

_PLAYLISTS_KEY = "spotify_playlists"


def fetch_playlists(access_token: str) -> Optional[list[dict]]:
    """Fetch all user playlists (owned + followed + collaborative)."""
    items = spotify_api_get_all_pages(
        "https://api.spotify.com/v1/me/playlists", access_token
    )
    return items if items else None


def save_playlists(conn, items: list[dict]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (_PLAYLISTS_KEY, json.dumps(items)),
    )
    conn.commit()


def get_playlists(conn) -> Optional[list[dict]]:
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_PLAYLISTS_KEY,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


# ---- Bulk Sync ----

def sync_all_spotify_data(conn, access_token: str) -> dict:
    """Fetch and persist all available Spotify data. Returns summary dict."""
    result = {
        "profile": False,
        "top_artists": [],
        "top_tracks": [],
        "recently_played": False,
        "followed_artists": 0,
        "playlists": 0,
    }

    # Profile (with email from user-read-email scope)
    profile = fetch_spotify_profile(access_token)
    if profile:
        save_user_profile(conn, profile)
        result["profile"] = True

    # Top artists (3 time ranges)
    for tr in TIME_RANGES:
        artists = fetch_top_artists(access_token, tr)
        if artists:
            save_top_items(conn, "artists", tr, artists)
            result["top_artists"].append(tr)

    # Top tracks (3 time ranges)
    for tr in TIME_RANGES:
        tracks = fetch_top_tracks(access_token, tr)
        if tracks:
            save_top_items(conn, "tracks", tr, tracks)
            result["top_tracks"].append(tr)

    # Recently played
    recent = fetch_recently_played(access_token)
    if recent:
        save_recently_played(conn, recent)
        result["recently_played"] = True

    # Followed artists
    follows = fetch_followed_artists(access_token)
    if follows:
        save_followed_artists(conn, follows)
        result["followed_artists"] = len(follows)

    # Playlists
    playlists = fetch_playlists(access_token)
    if playlists:
        save_playlists(conn, playlists)
        result["playlists"] = len(playlists)

    return result


# ---- Spotify API helpers ----

def spotify_api_get(url: str, access_token: str) -> Optional[dict]:
    """GET request to Spotify Web API with Bearer token."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


def spotify_api_get_all_pages(url: str, access_token: str, limit: int = 50) -> list[dict]:
    """Paginate through all pages of a Spotify API endpoint. Returns list of items."""
    all_items: list[dict] = []
    page_url = f"{url}?limit={limit}"
    while page_url:
        data = spotify_api_get(page_url, access_token)
        if not data:
            break
        all_items.extend(data.get("items", []))
        page_url = data.get("next")
    return all_items
