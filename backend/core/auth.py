"""API authentication dependency.

When SPOTIFY_STATS_REQUIRE_AUTH=1, all mutating endpoints require a valid
Bearer token. When off (default), all requests pass through — preserving
the local-dev experience.

Usage:
    @router.post("/something")
    def my_endpoint(auth: None = Depends(require_auth)):
        ...
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.core.config import SPOTIFY_STATS_REQUIRE_AUTH, SPOTIFY_STATS_API_TOKEN

bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    if SPOTIFY_STATS_REQUIRE_AUTH != "1":
        return
    if credentials is None or credentials.credentials != SPOTIFY_STATS_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
