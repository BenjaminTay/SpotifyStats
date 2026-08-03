"""Official Spotify Wrapped Hub API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.domains.metadata.artist_identity import canonicalize_artist_payload
from backend.models.account_center import WrappedHubAvailableYearsResponse, WrappedHubResponse
from backend.services.wrapped_hub_service import get_wrapped_hub

router = APIRouter(prefix="/wrapped-hub", tags=["Wrapped Hub"])


@router.get("/available-years", response_model=WrappedHubAvailableYearsResponse)
def wrapped_hub_available_years(conn: Connection = Depends(get_conn)):
    """Return years with official Wrapped data."""
    try:
        r = conn.execute("SELECT COUNT(*) FROM wrapped_listening_age").fetchone()
        return {"years": [2025] if r and r[0] > 0 else []}
    except Exception:
        return {"years": []}


@router.get("", response_model=WrappedHubResponse, response_model_exclude_unset=True)
def wrapped_hub(conn: Connection = Depends(get_conn)):
    return canonicalize_artist_payload(get_wrapped_hub(conn), conn)
