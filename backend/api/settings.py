"""Settings API endpoints."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection
from typing import Optional

from backend.dependencies import get_conn
from backend.models.common import SettingsResponse, SettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["Settings"])

# In-memory settings defaults (mirrors st.session_state)
_defaults = {
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "bb_week_start_dow": 4,
    "bb_week_start_hour": 0,
}

_current = dict(_defaults)


@router.get("", response_model=SettingsResponse)
def get_settings(conn: Connection = Depends(get_conn)):
    """Get current settings and database status."""
    db_record_count = 0
    account_data_imported = False
    try:
        db_record_count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        sc = conn.execute("SELECT COUNT(*) FROM search_queries").fetchone()[0]
        account_data_imported = sc > 0
    except Exception:
        pass
    return {**_current, "db_record_count": db_record_count, "account_data_imported": account_data_imported}


@router.put("")
def update_settings(body: SettingsUpdateRequest):
    """Update settings. Returns updated settings."""
    updates = body.dict(exclude_none=True)
    for key in ["min_ms", "music_only", "merge_enabled", "bb_top_n", "bb_album_top_n",
                "bb_artist_top_n", "bb_week_start_dow", "bb_week_start_hour"]:
        if key in updates:
            _current[key] = updates[key]
    return _current


@router.post("/rebuild-agg")
def rebuild_aggregations(conn: Connection = Depends(get_conn)):
    """Rebuild pre-aggregated weekly Billboard tables."""
    from backend.core.db import get_db, build_aggregations
    write_conn = get_db(readonly=False)
    try:
        result = build_aggregations(
            min_ms=_current["min_ms"],
            music_only=_current["music_only"],
            week_start_dow=_current["bb_week_start_dow"],
            week_start_hour=_current["bb_week_start_hour"],
        )
        return {"status": "done", **result}
    finally:
        write_conn.close()
