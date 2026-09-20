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


def _get_bool(key: str, default: bool) -> bool:
    value = _get(key, "1" if default else "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


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
SPOTIFY_STATS_BILLBOARD_CACHE_PATH = _get("SPOTIFY_STATS_BILLBOARD_CACHE_PATH", "")
SPOTIFY_STATS_COMMUNITY_CACHE_PATH = _get("SPOTIFY_STATS_COMMUNITY_CACHE_PATH", "")
SPOTIFY_STATS_ARCHIVE_CACHE_PATH = _get("SPOTIFY_STATS_ARCHIVE_CACHE_PATH", "")
SPOTIFY_STATS_ANALYSIS_CACHE_PATH = _get("SPOTIFY_STATS_ANALYSIS_CACHE_PATH", "")
PYTEST_CURRENT_TEST = _get("PYTEST_CURRENT_TEST", "")
MUSIC_SEARCH_CANDIDATE_LKG = _get_bool("MUSIC_SEARCH_CANDIDATE_LKG", True)
MUSIC_SEARCH_STATISTICS_LKG = _get_bool("MUSIC_SEARCH_STATISTICS_LKG", True)
MUSIC_SEARCH_TRACK_CREDIT_DELTA = _get_bool("MUSIC_SEARCH_TRACK_CREDIT_DELTA", True)


def l3_startup_reconcile_enabled() -> bool:
    """Read the startup reconciliation switch at lifespan time.

    Tests set this after module collection, so this one operational switch is
    intentionally dynamic while still keeping environment access centralized.
    """

    return _get_bool("SPOTIFY_STATS_L3_STARTUP_RECONCILE", True)


# AI Agent V2 is the default chat runtime. ``legacy`` remains available as a
# rollback switch while the new runtime is being exercised in production.
AI_AGENT_RUNTIME = _get("AI_AGENT_RUNTIME", "v2").strip().lower()
AI_AGENT_MAX_STEPS = max(1, int(_get("AI_AGENT_MAX_STEPS", "6")))
AI_AGENT_MAX_TOOL_CALLS = max(1, int(_get("AI_AGENT_MAX_TOOL_CALLS", "12")))
AI_AGENT_TURN_TIMEOUT_SECONDS = max(10, int(_get("AI_AGENT_TURN_TIMEOUT_SECONDS", "90")))
AI_AGENT_LLM_TIMEOUT_SECONDS = max(10, int(_get("AI_AGENT_LLM_TIMEOUT_SECONDS", "45")))
AI_AGENT_LLM_RETRIES = max(0, int(_get("AI_AGENT_LLM_RETRIES", "1")))
AI_AGENT_CONTEXT_SOURCE = _get("AI_AGENT_CONTEXT_SOURCE", "memory").strip().lower()
if AI_AGENT_CONTEXT_SOURCE not in {"memory", "event_log"}:
    AI_AGENT_CONTEXT_SOURCE = "memory"

# V5 report-performance switches remain explicit rollback boundaries.  Both
# paths are read-only and keep the V4 quality gates in place.
AI_YEARLY_CONTEXT_SNAPSHOT_V1 = _get_bool("AI_YEARLY_CONTEXT_SNAPSHOT_V1", True)
AI_REPORT_SECTION_WRITER_V2 = _get_bool("AI_REPORT_SECTION_WRITER_V2", True)
AI_REPORT_SECTION_WRITER_CONCURRENCY = max(
    1,
    min(2, int(_get("AI_REPORT_SECTION_WRITER_CONCURRENCY", "2"))),
)

# ── Remote access auth (Task 5) ──────────────────────────────────────

SPOTIFY_STATS_REQUIRE_AUTH = _get("SPOTIFY_STATS_REQUIRE_AUTH", "0")
SPOTIFY_STATS_API_TOKEN = _get("SPOTIFY_STATS_API_TOKEN", "")

# ── Token encryption key (Task 2) ────────────────────────────────────

SPOTIFY_STATS_TOKEN_KEY = _get("SPOTIFY_STATS_TOKEN_KEY", "")

# Local governance health/coverage publications.
SPOTIFY_STATS_GOVERNANCE_CACHE_PATH = os.getenv("SPOTIFY_STATS_GOVERNANCE_CACHE_PATH", "")
