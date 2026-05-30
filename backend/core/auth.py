"""API authentication dependency.

When SPOTIFY_STATS_REQUIRE_AUTH=1, all mutating endpoints require a valid
Bearer token. When off (default), all requests pass through — preserving
the local-dev experience.

Usage:
    @router.post("/something")
    def my_endpoint(auth: None = Depends(require_auth)):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import SPOTIFY_STATS_API_TOKEN, SPOTIFY_STATS_REQUIRE_AUTH

bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    if SPOTIFY_STATS_REQUIRE_AUTH != "1":
        return
    if credentials is None or credentials.credentials != SPOTIFY_STATS_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
