"""Official Spotify Wrapped Hub API endpoint."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn
from backend.services.wrapped_hub_service import get_wrapped_hub

router = APIRouter(prefix="/wrapped-hub", tags=["Wrapped Hub"])


@router.get("/available-years")
def wrapped_hub_available_years(conn: Connection = Depends(get_conn)):
    """Return years with official Wrapped data."""
    try:
        r = conn.execute(
            "SELECT COUNT(*) FROM wrapped_listening_age"
        ).fetchone()
        return {"years": [2025] if r and r[0] > 0 else []}
    except Exception:
        return {"years": []}


@router.get("")
def wrapped_hub(conn: Connection = Depends(get_conn)):
    return get_wrapped_hub(conn)
