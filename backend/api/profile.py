"""Profile API endpoint."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn
from backend.services.profile_service import get_profile

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("")
def user_profile(conn: Connection = Depends(get_conn)):
    return get_profile(conn)
