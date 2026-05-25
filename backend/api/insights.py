"""Insights API endpoints."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn
from backend.services.insights_service import get_artist_tiers, get_marquee_conversion

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/tiers")
def artist_tiers(conn: Connection = Depends(get_conn)):
    return get_artist_tiers(conn)


@router.get("/marquee")
def marquee(conn: Connection = Depends(get_conn)):
    return get_marquee_conversion(conn)
