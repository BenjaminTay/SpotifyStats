"""Centralized runtime configuration — single source of truth for all env vars.

Loads .env once at import time via python-dotenv so os.environ is populated
uniformly. All other modules must import config attributes from here instead
of reading os.environ or parsing .env files manually.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── Spotify ──────────────────────────────────────────────────────────────

SPOTIFY_CLIENT_ID = _get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = _get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = _get(
    "SPOTIFY_REDIRECT_URI", "http://localhost:5173/api/spotify/auth/callback"
)

# ── Genius ────────────────────────────────────────────────────────────────

GENIUS_ACCESS_TOKEN = _get("GENIUS_ACCESS_TOKEN")
GENIUS_PROXY = _get("GENIUS_PROXY")

# ── Last.fm ───────────────────────────────────────────────────────────────

LASTFM_API_KEY = _get("LASTFM_API_KEY")

# ── Proxy ────────────────────────────────────────────────────────────────

HTTPS_PROXY = _get("HTTPS_PROXY") or _get("https_proxy")
HTTP_PROXY = _get("HTTP_PROXY") or _get("http_proxy")

# ── Frontend / CORS ─────────────────────────────────────────────────────

FRONTEND_ORIGIN = _get("FRONTEND_ORIGIN", "http://localhost:5173")

# ── App behaviour ───────────────────────────────────────────────────────

SPOTIFY_STATS_WARMUP = _get("SPOTIFY_STATS_WARMUP", "1")
PYTEST_CURRENT_TEST = _get("PYTEST_CURRENT_TEST", "")

# ── Remote access auth (Task 5) ──────────────────────────────────────

SPOTIFY_STATS_REQUIRE_AUTH = _get("SPOTIFY_STATS_REQUIRE_AUTH", "0")
SPOTIFY_STATS_API_TOKEN = _get("SPOTIFY_STATS_API_TOKEN", "")

# ── Token encryption key (Task 2) ────────────────────────────────────

SPOTIFY_STATS_TOKEN_KEY = _get("SPOTIFY_STATS_TOKEN_KEY", "")
