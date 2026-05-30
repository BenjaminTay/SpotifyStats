"""Profile API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.services.profile_service import get_inferences, get_profile, get_sound_capsule

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("")
def user_profile(conn: Connection = Depends(get_conn)):
    return get_profile(conn)


@router.get("/inferences")
def user_inferences(conn: Connection = Depends(get_conn)):
    return get_inferences(conn)


@router.get("/sound-capsule")
def sound_capsule(conn: Connection = Depends(get_conn)):
    return get_sound_capsule(conn)
