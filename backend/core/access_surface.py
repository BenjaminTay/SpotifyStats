"""Request-surface classification and public read-only policy.

The production deployment has two independently configured reverse proxies:

* ``private-admin`` is reachable through Tailscale Serve and keeps the normal
  single-user application behaviour.
* ``public-readonly`` is reachable through Tailscale Funnel and may only expose
  explicitly approved presentation and analytical operations.

The reverse proxies always overwrite ``SURFACE_HEADER`` before forwarding a
request. The backend is not published directly on the host, so clients cannot
use this header to promote a public request to the private surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import Request

SurfaceName = Literal["private-admin", "public-readonly"]

SURFACE_HEADER = "X-SpotifyStats-Surface"
PRIVATE_ADMIN_SURFACE: SurfaceName = "private-admin"
PUBLIC_READONLY_SURFACE: SurfaceName = "public-readonly"


@dataclass(frozen=True)
class RuntimeCapabilities:
    surface: SurfaceName
    settings: bool
    editing: bool
    imports: bool
    ai: bool
    spotify_oauth: bool
    lyrics: bool

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "surface": self.surface,
            "settings": self.settings,
            "editing": self.editing,
            "imports": self.imports,
            "ai": self.ai,
            "spotify_oauth": self.spotify_oauth,
            "lyrics": self.lyrics,
        }


PRIVATE_ADMIN_CAPABILITIES = RuntimeCapabilities(
    surface=PRIVATE_ADMIN_SURFACE,
    settings=True,
    editing=True,
    imports=True,
    ai=True,
    spotify_oauth=True,
    lyrics=True,
)

PUBLIC_READONLY_CAPABILITIES = RuntimeCapabilities(
    surface=PUBLIC_READONLY_SURFACE,
    settings=False,
    editing=False,
    imports=False,
    ai=False,
    spotify_oauth=False,
    lyrics=False,
)


# These feature families are unavailable on the public presentation surface,
# even when an endpoint happens to use GET.
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

# A few analytical operations use POST because their request body is a
# structured comparison query. They do not mutate source data and remain part
# of the public showcase.
PUBLIC_SAFE_POST_PATHS = frozenset(
    {
        "/api/billboard/release-cycle/compare",
        "/api/billboard/versus/album",
        "/api/billboard/versus/artist",
        "/api/billboard/versus/track",
    }
)


def request_surface(request: Request) -> SurfaceName:
    if request.headers.get(SURFACE_HEADER, "").strip().lower() == PUBLIC_READONLY_SURFACE:
        return PUBLIC_READONLY_SURFACE
    return PRIVATE_ADMIN_SURFACE


def is_public_readonly(request: Request) -> bool:
    return request_surface(request) == PUBLIC_READONLY_SURFACE


def capabilities_for_request(request: Request) -> RuntimeCapabilities:
    if is_public_readonly(request):
        return PUBLIC_READONLY_CAPABILITIES
    return PRIVATE_ADMIN_CAPABILITIES


def public_policy_decision(method: str, path: str) -> Literal["allow", "disabled", "readonly"]:
    """Classify a request made through the public presentation gateway."""

    normalized_method = method.upper()
    if path in {"/docs", "/openapi.json"}:
        return "disabled"
    if any(path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_DISABLED_PREFIXES):
        return "disabled"
    if normalized_method in {"GET", "HEAD", "OPTIONS"}:
        return "allow"
    if normalized_method == "POST" and path in PUBLIC_SAFE_POST_PATHS:
        return "allow"
    return "readonly"
