"""Personal music front-page API."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Response

from backend.dependencies import get_conn, get_yearly_review_context
from backend.domains.music_search.timing import MusicSearchTiming
from backend.models.home import HomeOverviewResponse
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.home_service import get_home_overview

router = APIRouter(prefix="/home", tags=["Home"])


@router.get("/overview", response_model=HomeOverviewResponse)
def home_overview(
    response: Response,
    context: YearlyReviewFilterContext = Depends(get_yearly_review_context),
    conn: Connection = Depends(get_conn),
) -> HomeOverviewResponse:
    timing = MusicSearchTiming()
    with timing.measure("home_service"):
        result = get_home_overview(conn, context)
    response.headers["Server-Timing"] = timing.server_timing_header()
    return result
