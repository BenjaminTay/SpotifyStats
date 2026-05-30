"""Search history API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.services.search_service import get_search_stats

router = APIRouter(prefix="/search-history", tags=["Search History"])


@router.get("")
def search_history(conn: Connection = Depends(get_conn)):
    return get_search_stats(conn)
