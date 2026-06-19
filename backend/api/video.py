"""Video API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.models.account_center import VideoStatsResponse
from backend.services.video_service import get_video_stats

router = APIRouter(prefix="/video", tags=["Video"])


@router.get("", response_model=VideoStatsResponse, response_model_exclude_unset=True)
def video_stats(conn: Connection = Depends(get_conn)):
    return get_video_stats(conn)
