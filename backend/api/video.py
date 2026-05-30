"""Video API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.services.video_service import get_video_stats

router = APIRouter(prefix="/video", tags=["Video"])


@router.get("")
def video_stats(conn: Connection = Depends(get_conn)):
    return get_video_stats(conn)
