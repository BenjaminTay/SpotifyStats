"""Admin endpoints: cache stats, health details. Protected behind require_auth."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.auth import require_auth
from backend.core.cache_manager import get_stats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cache-stats")
def cache_stats(auth: None = Depends(require_auth)):
    """Return cache hit/miss/size metrics grouped by namespace."""
    return {"cache_stats": get_stats()}
