"""Official Spotify Wrapped Hub API endpoint."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn
from backend.services.wrapped_hub_service import get_wrapped_hub

router = APIRouter(prefix="/wrapped-hub", tags=["Wrapped Hub"])


@router.get("")
def wrapped_hub(conn: Connection = Depends(get_conn)):
    return get_wrapped_hub(conn)
