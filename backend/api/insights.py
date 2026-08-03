"""Insights API endpoints."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.domains.metadata.artist_identity import canonicalize_artist_payload
from backend.models.account_center import ArtistTiersResponse, MarqueeConversionResponse
from backend.services.insights_service import get_artist_tiers, get_marquee_conversion

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/tiers", response_model=ArtistTiersResponse, response_model_exclude_unset=True)
def artist_tiers(conn: Connection = Depends(get_conn)):
    return canonicalize_artist_payload(get_artist_tiers(conn), conn)


@router.get("/marquee", response_model=MarqueeConversionResponse, response_model_exclude_unset=True)
def marquee(conn: Connection = Depends(get_conn)):
    return canonicalize_artist_payload(get_marquee_conversion(conn), conn)
