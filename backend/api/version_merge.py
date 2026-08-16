"""Version merge API — CRUD for release groups."""

# ruff: noqa: UP045

from __future__ import annotations

from sqlite3 import Connection
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.core.auth import require_auth
from backend.core.json_helpers import df_to_json
from backend.core.version_merge import (
    apply_detected_groups,
    confirm_album_relation_bundle,
    confirm_track_group_candidate,
    create_group,
    delete_group,
    detect_collaboration_track_group_candidates,
    detect_release_groups,
    get_album_track_comparison,
    get_album_types,
    get_all_groups,
    get_group_members,
    get_groups_for_artist,
    get_ungrouped_albums,
    set_primary,
    update_group_members,
)
from backend.dependencies import get_conn

router = APIRouter(prefix="/version-merge", tags=["Version Merge"])


def _refresh_music_search_derived_data(reason: str) -> None:
    from backend.core.db import get_db
    from backend.services.music_search_maintenance_service import (
        enqueue_music_search_snapshot_rebuild,
        mark_music_search_for_rebuild,
    )

    conn = get_db(readonly=False)
    try:
        mark_music_search_for_rebuild(
            reason=reason,
            documents=True,
            revision_kinds=("metadata", "candidate"),
            conn=conn,
        )
        enqueue_music_search_snapshot_rebuild(
            rebuild_documents=True,
            conn=conn,
        )
    finally:
        conn.close()


# ── Request models ───────────────────────────────────────────────────────────


class CreateGroupRequest(BaseModel):
    canonical_name: str
    artist_id: int
    primary_album_id: int
    member_ids: list[int]
    scope: str = "release"


class UpdateMembersRequest(BaseModel):
    add_ids: Optional[list[int]] = None
    remove_ids: Optional[list[int]] = None


class SetPrimaryRequest(BaseModel):
    album_id: int


# ── Response models ──────────────────────────────────────────────────────────


class ReleaseGroupResponse(BaseModel):
    group_id: int
    canonical_name: str
    artist_name: str
    primary_album_id: Optional[int] = None
    primary_album_name: Optional[str] = None
    scope: str = "release"
    is_manual: int
    created_at: str


class GroupMemberResponse(BaseModel):
    album_id: int
    album_name: str
    is_primary: Optional[int] = None


class UngroupedAlbumResponse(BaseModel):
    album_id: int
    album_name: str
    artist_name: str


class TrackComparisonResponse(BaseModel):
    shared: list[list]
    only_in_a: list[list]
    only_in_b: list[list]


class StatusResponse(BaseModel):
    status: str


class CreateGroupResponse(BaseModel):
    status: str
    group_id: Optional[int] = None
    message: Optional[str] = None


class ApplyDetectionResponse(BaseModel):
    status: str
    created_count: int
    skipped_count: int


class DetectionMemberResponse(BaseModel):
    album_id: int
    album_name: str
    release_date: Optional[str] = None


class OverlapDetailResponse(BaseModel):
    album_name: str
    album_id: int
    overlap: float


class DetectionResultResponse(BaseModel):
    artist_name: str
    artist_id: int
    canonical_name: str
    primary_album_name: str
    primary_album_id: int
    member_count: int
    confidence: str
    members: list[DetectionMemberResponse]
    group_type: str
    reason: str
    overlap_details: list[OverlapDetailResponse]


class TrackGroupCandidateResponse(BaseModel):
    original_track_id: int
    original_track_name: str
    candidate_track_id: int
    candidate_track_name: str
    primary_artist_id: int


class TrackGroupConfirmRequest(BaseModel):
    original_track_id: int
    candidate_track_id: int
    scope: str = "composition"


class TrackGroupConfirmResponse(BaseModel):
    status: str
    group_id: Optional[int] = None
    scope: Optional[str] = None
    member_count: Optional[int] = None
    album_projects_rebuilt: bool = False
    message: Optional[str] = None


class AlbumRelationConfirmRequest(BaseModel):
    canonical_name: str
    primary_album_id: int
    member_album_ids: list[int]
    scope: str = "composition"
    relation_type: str = "rerecord"
    confirm_track_pairs: bool = True


class AlbumRelationTrackPairResponse(BaseModel):
    original_track_id: int
    original_track_name: str
    candidate_track_id: int
    candidate_track_name: str
    candidate_album_id: int


class AlbumRelationExclusiveTrackResponse(BaseModel):
    track_id: int
    track_name: str
    source_album_id: int


class AlbumRelationConfirmResponse(BaseModel):
    status: str
    release_group_id: Optional[int] = None
    scope: Optional[str] = None
    relation_type: Optional[str] = None
    candidate_track_pair_count: int = 0
    confirmed_track_pair_count: int = 0
    exclusive_track_count: int = 0
    track_pairs: list[AlbumRelationTrackPairResponse] = Field(default_factory=list)
    exclusive_tracks: list[AlbumRelationExclusiveTrackResponse] = Field(default_factory=list)
    album_projects_rebuilt: bool = False
    message: Optional[str] = None


# ── Query endpoints ──────────────────────────────────────────────────────


@router.get("/groups", response_model=list[ReleaseGroupResponse])
def list_groups(conn: Connection = Depends(get_conn)):
    """Get all saved release groups with member details."""
    df = get_all_groups()
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberResponse])
def get_members(group_id: int, conn: Connection = Depends(get_conn)):
    """Get members of a specific release group."""
    df = get_group_members(group_id)
    return df.to_dict(orient="records")


@router.get("/groups/artist/{artist_name}", response_model=list[ReleaseGroupResponse])
def artist_groups(artist_name: str, conn: Connection = Depends(get_conn)):
    """Get all release groups for an artist."""
    df = get_groups_for_artist(artist_name)
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/ungrouped", response_model=list[UngroupedAlbumResponse])
def ungrouped_albums(
    artist_name: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    """Get albums not yet assigned to any release group."""
    df = get_ungrouped_albums(artist_name)
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/compare", response_model=TrackComparisonResponse)
def compare_albums(
    album_id_a: int = Query(...),
    album_id_b: int = Query(...),
):
    """Compare tracks between two albums (via Spotify API data)."""
    return get_album_track_comparison(album_id_a, album_id_b)


@router.get("/album-types", response_model=dict[str, str])
def album_types(album_ids: str = Query(..., description="Comma-separated album IDs")):
    """Get album types (album/single/compilation) for a set of album IDs."""
    ids = [int(x.strip()) for x in album_ids.split(",") if x.strip()]
    return {str(album_id): album_type for album_id, album_type in get_album_types(ids).items()}


@router.get(
    "/track-group-candidates/collaboration",
    response_model=list[TrackGroupCandidateResponse],
)
def collaboration_candidates(auth: None = Depends(require_auth)):
    """Find collaboration/remix track-group candidates for user confirmation."""
    df = detect_collaboration_track_group_candidates()
    if df.empty:
        return []
    return df.where(pd.notna(df), None).to_dict(orient="records")


# ── Mutation endpoints ────────────────────────────────────────────────────


@router.post("/groups", response_model=CreateGroupResponse)
def create_new_group(body: CreateGroupRequest, auth: None = Depends(require_auth)):
    """Manually create a release group."""
    group_id = create_group(
        canonical_name=body.canonical_name,
        artist_id=body.artist_id,
        primary_album_id=body.primary_album_id,
        member_ids=body.member_ids,
        scope=body.scope,
    )
    if group_id is None:
        return {"status": "error", "message": "Failed to create group"}
    _refresh_music_search_derived_data("release group created")
    return {"status": "ok", "group_id": group_id}


@router.post("/track-groups/confirm", response_model=TrackGroupConfirmResponse)
def confirm_track_group(body: TrackGroupConfirmRequest, auth: None = Depends(require_auth)):
    """Confirm a track candidate and rebuild album project rows."""
    result = confirm_track_group_candidate(
        original_track_id=body.original_track_id,
        candidate_track_id=body.candidate_track_id,
        scope=body.scope,
    )
    _refresh_music_search_derived_data("track group confirmed")
    return result


@router.post("/album-relations/confirm", response_model=AlbumRelationConfirmResponse)
def confirm_album_relation(
    body: AlbumRelationConfirmRequest,
    auth: None = Depends(require_auth),
):
    """Confirm an album-level relation and derive matching track relations."""
    result = confirm_album_relation_bundle(
        canonical_name=body.canonical_name,
        primary_album_id=body.primary_album_id,
        member_album_ids=body.member_album_ids,
        scope=body.scope,
        relation_type=body.relation_type,
        confirm_track_pairs=body.confirm_track_pairs,
    )
    _refresh_music_search_derived_data("album relation confirmed")
    return result


@router.put("/groups/{group_id}/members", response_model=StatusResponse)
def update_members(group_id: int, body: UpdateMembersRequest, auth: None = Depends(require_auth)):
    """Add or remove members from a release group."""
    ok = update_group_members(group_id, body.add_ids, body.remove_ids)
    if ok:
        _refresh_music_search_derived_data("release group members changed")
    return {"status": "ok" if ok else "error"}


@router.put("/groups/{group_id}/primary", response_model=StatusResponse)
def set_primary_album(group_id: int, body: SetPrimaryRequest, auth: None = Depends(require_auth)):
    """Change the primary album of a release group."""
    ok = set_primary(group_id, body.album_id)
    if ok:
        _refresh_music_search_derived_data("release group primary changed")
    return {"status": "ok" if ok else "error"}


@router.delete("/groups/{group_id}", response_model=StatusResponse)
def remove_group(group_id: int, auth: None = Depends(require_auth)):
    """Delete a release group and its member relationships."""
    ok = delete_group(group_id)
    if ok:
        _refresh_music_search_derived_data("release group deleted")
    return {"status": "ok" if ok else "error"}


@router.post("/album-projects/rebuild", response_model=StatusResponse)
def rebuild_album_project_rows(auth: None = Depends(require_auth)):
    """Rebuild inferred album project rows from current version metadata."""
    from backend.core.cache_manager import invalidate
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import rebuild_album_projects

    conn = get_db(readonly=False)
    try:
        rebuild_album_projects(conn)
    finally:
        conn.close()
    invalidate("analysis")
    invalidate("billboard")
    invalidate("yearly_review")
    _refresh_music_search_derived_data("album projects rebuilt")
    return {"status": "ok"}


# ── Detection & Apply ─────────────────────────────────────────────────────


@router.post("/detect", response_model=list[DetectionResultResponse])
def run_detection(
    overlap_threshold: float = Query(default=0.4, ge=0.1, le=1.0),
    auth: None = Depends(require_auth),
):
    """Auto-detect release groups by album name suffix + track overlap + superset."""
    result = detect_release_groups(overlap_threshold=overlap_threshold)
    if result.empty:
        return []
    return df_to_json(result)


@router.post("/apply", response_model=ApplyDetectionResponse)
def apply_detection(detection_result: dict, auth: None = Depends(require_auth)):
    """Apply detected release groups to the database."""
    df = pd.DataFrame(detection_result.get("confirmed_groups", []))
    if df.empty:
        return {"status": "ok", "created_count": 0}

    created_count = apply_detected_groups(df)
    if created_count:
        _refresh_music_search_derived_data("detected release groups applied")
    # Convert numpy types
    return {
        "status": "ok",
        "created_count": int(created_count),
        "skipped_count": max(int(len(df)) - int(created_count), 0),
    }


def _serialize_detection(result: dict) -> dict:
    """Convert detection result to JSON-safe dict."""

    out = {}
    for key, val in result.items():
        if isinstance(val, dict):
            out[key] = _serialize_detection(val)
        elif isinstance(val, list):
            out[key] = [
                _serialize_detection(item)
                if isinstance(item, dict)
                else int(item)
                if isinstance(item, np.integer)
                else float(item)
                if isinstance(item, np.floating)
                else item
                for item in val
            ]
        elif isinstance(val, np.integer):
            out[key] = int(val)
        elif isinstance(val, np.floating):
            out[key] = float(val)
        elif isinstance(val, pd.DataFrame):
            out[key] = val.where(pd.notna(val), None).to_dict(orient="records")
        else:
            out[key] = val
    return out
