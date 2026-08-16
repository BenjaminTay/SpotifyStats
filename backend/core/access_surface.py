"""Trusted ingress classification and public presentation policy.

Production has two reverse-proxy surfaces which both point at the same API:

* ``private-admin`` keeps the complete single-user application behaviour.
* ``public-readonly`` exposes an explicitly enumerated presentation surface.

The proxy must overwrite both :data:`SURFACE_HEADER` and
:data:`GATEWAY_TOKEN_HEADER`.  When trusted-gateway enforcement is enabled,
the backend rejects every non-health request which cannot prove that it came
through one of those proxies.  The public policy is deliberately allowlist
based: adding a new GET route never publishes it by accident.
"""

from __future__ import annotations

import hmac
import os
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Literal

from fastapi import Request

SurfaceName = Literal["private-admin", "public-readonly"]
DeploymentProfile = Literal["full", "showcase"]
PolicyDecision = Literal["allow", "disabled", "readonly"]

ACCESS_POLICY_VERSION = "access-policy-v1"
SURFACE_HEADER = "X-SpotifyStats-Surface"
GATEWAY_TOKEN_HEADER = "X-SpotifyStats-Gateway-Token"
GATEWAY_TOKEN_ENV = "SPOTIFY_STATS_GATEWAY_TOKEN"
TRUSTED_GATEWAY_REQUIRED_ENV = "SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED"
RELEASE_SHA_ENV = "SPOTIFY_STATS_RELEASE_SHA"

PRIVATE_ADMIN_SURFACE: SurfaceName = "private-admin"
PUBLIC_READONLY_SURFACE: SurfaceName = "public-readonly"
_VALID_SURFACES = frozenset({PRIVATE_ADMIN_SURFACE, PUBLIC_READONLY_SURFACE})

_public_readonly_db_guard: ContextVar[bool] = ContextVar(
    "spotify_stats_public_readonly_db_guard",
    default=False,
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def trusted_gateway_required() -> bool:
    """Whether all non-health requests must carry trusted proxy credentials."""

    return _env_flag(TRUSTED_GATEWAY_REQUIRED_ENV)


def _release_sha() -> str:
    return (
        os.environ.get(RELEASE_SHA_ENV, "").strip()
        or os.environ.get("IMAGE_TAG", "").strip()
        or "development"
    )


@dataclass(frozen=True)
class RuntimeCapabilities:
    surface: SurfaceName
    profile: DeploymentProfile
    settings: bool
    editing: bool
    imports: bool
    ai: bool
    spotify_oauth: bool
    lyrics: bool
    metadata_governance: bool
    data_rebuild: bool
    yearly_generation: bool
    community_write: bool
    cover_enrichment: bool
    account_connection: bool

    def as_dict(self) -> dict[str, str | bool]:
        return {
            # ``surface`` is retained for existing clients. ``profile`` is the
            # versioned deployment-profile name used by new clients.
            "surface": self.surface,
            "profile": self.profile,
            "policy_version": ACCESS_POLICY_VERSION,
            "release_sha": _release_sha(),
            "settings": self.settings,
            "editing": self.editing,
            "imports": self.imports,
            "ai": self.ai,
            "spotify_oauth": self.spotify_oauth,
            "lyrics": self.lyrics,
            "metadata_governance": self.metadata_governance,
            "data_rebuild": self.data_rebuild,
            "yearly_generation": self.yearly_generation,
            "community_write": self.community_write,
            "cover_enrichment": self.cover_enrichment,
            "account_connection": self.account_connection,
        }


PRIVATE_ADMIN_CAPABILITIES = RuntimeCapabilities(
    surface=PRIVATE_ADMIN_SURFACE,
    profile="full",
    settings=True,
    editing=True,
    imports=True,
    ai=True,
    spotify_oauth=True,
    lyrics=True,
    metadata_governance=True,
    data_rebuild=True,
    yearly_generation=True,
    community_write=True,
    cover_enrichment=True,
    account_connection=True,
)

PUBLIC_READONLY_CAPABILITIES = RuntimeCapabilities(
    surface=PUBLIC_READONLY_SURFACE,
    profile="showcase",
    settings=False,
    editing=False,
    imports=False,
    ai=False,
    spotify_oauth=False,
    lyrics=False,
    metadata_governance=False,
    data_rebuild=False,
    yearly_generation=False,
    community_write=False,
    cover_enrichment=False,
    account_connection=False,
)


# Sensitive feature families are hidden rather than advertised as read-only.
# Prefixes are safe here because they can only make future endpoints *less*
# public. Publication itself is controlled by the exact templates below.
PUBLIC_DISABLED_PREFIXES = (
    "/api/admin",
    "/api/ai-insights",
    "/api/ai/tasks",
    "/api/artist-identities",
    "/api/billboard/enrichment",
    "/api/chat",
    "/api/import",
    "/api/jobs",
    "/api/lyrics",
    "/api/metadata/artist-genres",
    "/api/metadata/artist-languages",
    "/api/music-metadata/track-credits",
    "/api/profile",
    "/api/search-history",
    "/api/settings/llm-profiles",
    "/api/spotify/auth",
    "/api/version-merge",
)

# Every public GET is represented by one explicit current route template.
# Parameters without ``:path`` match one segment; ``:path`` parameters may
# contain slashes, mirroring Starlette's route converter.
PUBLIC_SAFE_GET_TEMPLATES = frozenset(
    {
        "/covers/{cover_type}/{entity_id}.jpg",
        "/api/health",
        "/api/runtime/capabilities",
        "/api/settings",
        "/api/home/overview",
        "/api/analysis/overview",
        "/api/analysis/stats",
        "/api/analysis/charts",
        "/api/analysis/plays",
        "/api/analysis/play-dates",
        "/api/analysis/records",
        "/api/dashboard/summary",
        "/api/dashboard/full",
        "/api/dashboard/top-tracks",
        "/api/dashboard/platform-dist",
        "/api/dashboard/dow-dist",
        "/api/dashboard/random-track",
        "/api/timeline/annual",
        "/api/timeline/monthly",
        "/api/timeline/weekly",
        "/api/leaderboard",
        "/api/behavior",
        "/api/listening-hours/heatmap",
        "/api/listening-hours/yearly",
        "/api/listening-hours/late-night",
        "/api/listening-hours/weekday-weekend",
        "/api/listening-hours/platform-hourly",
        "/api/artist/list",
        "/api/artist/{name}/deep-dive",
        "/api/wrapped/available-years",
        "/api/wrapped/{year}",
        "/api/wrapped/{year}/full",
        "/api/library",
        "/api/library/playlists",
        "/api/library/playlists/{playlist_id}/tracks",
        "/api/library/saved-tracks",
        "/api/library/playlist-overlap",
        "/api/insights/tiers",
        "/api/insights/marquee",
        "/api/podcast",
        "/api/podcast/interactions",
        "/api/podcast/saved-shows",
        "/api/video",
        "/api/wrapped-hub",
        "/api/wrapped-hub/available-years",
        "/api/yearly-review/available-years",
        "/api/yearly-review/{year}",
        "/api/yearly-review/{year}/records",
        "/api/billboard/data",
        "/api/billboard/weekly",
        "/api/billboard/records",
        "/api/billboard/power-scores",
        "/api/billboard/summaries",
        "/api/billboard/all-time",
        "/api/billboard/year-end",
        "/api/billboard/release-cycle/artist-list",
        "/api/billboard/release-cycle/artist/{artist_name:path}",
        "/api/billboard/release-cycle/artist/{artist_name:path}/album/{album_name:path}",
        "/api/billboard/track/{track_id}",
        "/api/billboard/artist/{artist_name:path}",
        "/api/billboard/album/{album_name:path}",
        "/api/billboard/entity-lists",
        "/api/billboard/versus/track",
        "/api/billboard/versus/album",
        "/api/billboard/versus/artist",
        "/api/community/feed",
        "/api/community/trending",
        "/api/community/post/{post_id}",
        "/api/music/search",
        "/api/music/search/context",
        "/api/music/tracks/{track_id}/stats",
        "/api/music/albums/{album_name}/stats",
        "/api/music/artists/{artist_name}/stats",
        "/api/music/albums/{album_name}/rankings",
        "/api/music/artists/{artist_name}/rankings",
        "/api/music/tracks/{track_id}/plays",
        "/api/music/albums/{album_name}/plays",
        "/api/music/artists/{artist_name}/plays",
        "/api/music/tracks/{track_id}/play-dates",
        "/api/music/albums/{album_name}/play-dates",
        "/api/music/artists/{artist_name}/play-dates",
        "/api/account/archive-overview",
        "/api/account/collection-journey",
        "/api/account/collection-cohorts",
        "/api/account/returns",
        "/api/account/discovery",
        "/api/account/library/{entity_type}",
        "/api/account/other-media",
    }
)

# Structured comparison bodies are read-only computations despite using POST.
PUBLIC_SAFE_POST_PATHS = frozenset(
    {
        "/api/billboard/release-cycle/compare",
        "/api/billboard/versus/album",
        "/api/billboard/versus/artist",
        "/api/billboard/versus/track",
    }
)

_TEMPLATE_PARAM_RE = re.compile(r"\{([^{}]+)\}")
_INTEGER_PUBLIC_ROUTE_PARAMETERS = frozenset({"year", "entity_id", "track_id"})


def _compile_route_template(template: str) -> re.Pattern[str]:
    cursor = 0
    parts: list[str] = ["^"]
    for match in _TEMPLATE_PARAM_RE.finditer(template):
        parts.append(re.escape(template[cursor : match.start()]))
        parameter, _, converter = match.group(1).partition(":")
        if converter == "path":
            parts.append(".+")
        elif parameter in _INTEGER_PUBLIC_ROUTE_PARAMETERS:
            parts.append(r"\d+")
        else:
            parts.append("[^/]+")
        cursor = match.end()
    parts.extend((re.escape(template[cursor:]), "$"))
    return re.compile("".join(parts))


_PUBLIC_SAFE_GET_PATTERNS = tuple(
    _compile_route_template(template) for template in sorted(PUBLIC_SAFE_GET_TEMPLATES)
)


def _is_safe_public_get_path(path: str) -> bool:
    return any(pattern.fullmatch(path) for pattern in _PUBLIC_SAFE_GET_PATTERNS)


def _raw_surface(request: Request) -> str:
    return request.headers.get(SURFACE_HEADER, "").strip().lower()


def trusted_request_surface(request: Request) -> SurfaceName | None:
    """Resolve a surface, returning ``None`` for an untrusted required ingress."""

    raw_surface = _raw_surface(request)
    if not trusted_gateway_required():
        if raw_surface == PUBLIC_READONLY_SURFACE:
            return PUBLIC_READONLY_SURFACE
        # Preserve zero-config local development and existing unit tests.
        return PRIVATE_ADMIN_SURFACE

    if raw_surface not in _VALID_SURFACES:
        return None
    expected = os.environ.get(GATEWAY_TOKEN_ENV, "")
    supplied = request.headers.get(GATEWAY_TOKEN_HEADER, "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        return None
    return raw_surface  # type: ignore[return-value]


def request_surface(request: Request) -> SurfaceName:
    resolved = getattr(request.state, "spotify_stats_surface", None)
    if resolved in _VALID_SURFACES:
        return resolved
    trusted = trusted_request_surface(request)
    # Middleware rejects ``None`` before route execution. Keep this helper
    # fail-closed if it is called independently of middleware.
    if trusted is None:
        raise PermissionError("untrusted SpotifyStats gateway")
    return trusted


def is_public_readonly(request: Request) -> bool:
    try:
        return request_surface(request) == PUBLIC_READONLY_SURFACE
    except PermissionError:
        return False


def capabilities_for_request(request: Request) -> RuntimeCapabilities:
    if request_surface(request) == PUBLIC_READONLY_SURFACE:
        return PUBLIC_READONLY_CAPABILITIES
    return PRIVATE_ADMIN_CAPABILITIES


def set_public_readonly_db_guard(enabled: bool) -> Token[bool]:
    """Set the request-scoped database fail-safe used by :func:`get_db`."""

    return _public_readonly_db_guard.set(enabled)


def reset_public_readonly_db_guard(token: Token[bool]) -> None:
    _public_readonly_db_guard.reset(token)


def public_readonly_db_guard_active() -> bool:
    return _public_readonly_db_guard.get()


def public_policy_decision(method: str, path: str) -> PolicyDecision:
    """Classify a request made through the public presentation gateway."""

    normalized_method = method.upper()
    if path in {"/docs", "/redoc", "/openapi.json"}:
        return "disabled"
    if any(path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_DISABLED_PREFIXES):
        return "disabled"

    safe_get = _is_safe_public_get_path(path)
    if normalized_method in {"GET", "HEAD"}:
        return "allow" if safe_get else "disabled"
    if normalized_method == "OPTIONS":
        if safe_get or path in PUBLIC_SAFE_POST_PATHS:
            return "allow"
        return "disabled"
    if normalized_method == "POST" and path in PUBLIC_SAFE_POST_PATHS:
        return "allow"
    return "readonly"
