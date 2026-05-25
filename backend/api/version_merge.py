"""Version merge API — CRUD for release groups."""

from typing import Optional, List

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlite3 import Connection
from pydantic import BaseModel

from backend.core.version_merge import (
    get_all_groups,
    get_group_members,
    create_group,
    update_group_members,
    set_primary,
    delete_group,
    get_album_track_comparison,
    detect_release_groups,
    apply_detected_groups,
    get_ungrouped_albums,
    get_groups_for_artist,
    get_album_types,
)
from backend.core.json_helpers import df_to_json, py_val
from backend.dependencies import get_conn

router = APIRouter(prefix="/version-merge", tags=["Version Merge"])

# ── Pydantic models ──────────────────────────────────────────────────────

class CreateGroupRequest(BaseModel):
    canonical_name: str
    artist_id: int
    primary_album_id: int
    member_ids: List[int]


class UpdateMembersRequest(BaseModel):
    add_ids: Optional[List[int]] = None
    remove_ids: Optional[List[int]] = None


class SetPrimaryRequest(BaseModel):
    album_id: int


# ── Query endpoints ──────────────────────────────────────────────────────

@router.get("/groups")
def list_groups(conn: Connection = Depends(get_conn)):
    """Get all saved release groups with member details."""
    df = get_all_groups()
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/groups/{group_id}/members")
def get_members(group_id: int, conn: Connection = Depends(get_conn)):
    """Get members of a specific release group."""
    df = get_group_members(group_id)
    return df.to_dict(orient="records")


@router.get("/groups/artist/{artist_name}")
def artist_groups(artist_name: str, conn: Connection = Depends(get_conn)):
    """Get all release groups for an artist."""
    df = get_groups_for_artist(artist_name)
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/ungrouped")
def ungrouped_albums(
    artist_name: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    """Get albums not yet assigned to any release group."""
    df = get_ungrouped_albums(artist_name)
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/compare")
def compare_albums(
    album_id_a: int = Query(...),
    album_id_b: int = Query(...),
):
    """Compare tracks between two albums (via Spotify API data)."""
    return get_album_track_comparison(album_id_a, album_id_b)


@router.get("/album-types")
def album_types(album_ids: str = Query(..., description="Comma-separated album IDs")):
    """Get album types (album/single/compilation) for a set of album IDs."""
    ids = [int(x.strip()) for x in album_ids.split(",") if x.strip()]
    return get_album_types(ids)


# ── Mutation endpoints ────────────────────────────────────────────────────

@router.post("/groups")
def create_new_group(body: CreateGroupRequest):
    """Manually create a release group."""
    group_id = create_group(
        canonical_name=body.canonical_name,
        artist_id=body.artist_id,
        primary_album_id=body.primary_album_id,
        member_ids=body.member_ids,
    )
    if group_id is None:
        return {"status": "error", "message": "Failed to create group"}
    return {"status": "ok", "group_id": group_id}


@router.put("/groups/{group_id}/members")
def update_members(group_id: int, body: UpdateMembersRequest):
    """Add or remove members from a release group."""
    ok = update_group_members(group_id, body.add_ids, body.remove_ids)
    return {"status": "ok" if ok else "error"}


@router.put("/groups/{group_id}/primary")
def set_primary_album(group_id: int, body: SetPrimaryRequest):
    """Change the primary album of a release group."""
    ok = set_primary(group_id, body.album_id)
    return {"status": "ok" if ok else "error"}


@router.delete("/groups/{group_id}")
def remove_group(group_id: int):
    """Delete a release group and its member relationships."""
    ok = delete_group(group_id)
    return {"status": "ok" if ok else "error"}


# ── Detection & Apply ─────────────────────────────────────────────────────

@router.post("/detect")
def run_detection(
    overlap_threshold: float = Query(default=0.4, ge=0.1, le=1.0),
):
    """Auto-detect release groups by album name suffix + track overlap + superset."""
    result = detect_release_groups(overlap_threshold=overlap_threshold)
    if result.empty:
        return []
    return df_to_json(result)


@router.post("/apply")
def apply_detection(detection_result: dict):
    """Apply detected release groups to the database."""
    df = pd.DataFrame(detection_result.get("confirmed_groups", []))
    if df.empty:
        return {"status": "ok", "created_count": 0}

    result = apply_detected_groups(df)
    # Convert numpy types
    return {
        "status": "ok",
        "created_count": int(result.get("created_count", 0)),
        "skipped_count": int(result.get("skipped_count", 0)),
    }


def _serialize_detection(result: dict) -> dict:
    """Convert detection result to JSON-safe dict."""
    import numpy as np

    out = {}
    for key, val in result.items():
        if isinstance(val, dict):
            out[key] = _serialize_detection(val)
        elif isinstance(val, list):
            out[key] = [
                _serialize_detection(item) if isinstance(item, dict)
                else int(item) if isinstance(item, (np.integer,))
                else float(item) if isinstance(item, (np.floating,))
                else item
                for item in val
            ]
        elif isinstance(val, (np.integer,)):
            out[key] = int(val)
        elif isinstance(val, (np.floating,)):
            out[key] = float(val)
        elif isinstance(val, pd.DataFrame):
            out[key] = val.where(pd.notna(val), None).to_dict(orient="records")
        else:
            out[key] = val
    return out
