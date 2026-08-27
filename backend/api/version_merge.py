"""Version merge API — CRUD for release groups."""

# ruff: noqa: UP045

from __future__ import annotations

import json
from sqlite3 import Connection
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.auth import require_auth
from backend.core.json_helpers import df_to_json
from backend.core.version_merge import (
    apply_detected_groups,
    confirm_album_relation_bundle,
    confirm_track_group_candidate,
    create_group,
    delete_group,
    delete_track_group,
    detect_collaboration_track_group_candidates,
    detect_release_groups,
    get_album_track_comparison,
    get_album_types,
    get_all_groups,
    get_all_track_groups,
    get_group_members,
    get_groups_for_artist,
    get_track_group_members,
    get_ungrouped_albums,
    search_track_l1_candidates,
    set_primary,
    set_primary_track,
    update_group_members,
    update_track_group_members,
)
from backend.dependencies import get_conn
from backend.domains.metadata.track_identity import (
    TrackIdentityConflictError,
    merge_l1_identities,
    split_external_identity,
)

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


class SetPrimaryTrackRequest(BaseModel):
    l1_id: Optional[int] = None
    track_id: Optional[int] = None


class CanonicalTrackMergeRequest(BaseModel):
    survivor_canonical_track_id: int = Field(ge=1)
    absorbed_canonical_track_ids: list[int] = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)


class CanonicalTrackSplitRequest(BaseModel):
    provider: str = Field(default="spotify", min_length=1, max_length=40)
    external_track_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=500)


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


class TrackGroupResponse(BaseModel):
    group_id: int
    canonical_name: str
    primary_track_id: Optional[int] = None
    primary_l1_id: Optional[int] = None
    spotify_track_id: Optional[str] = None
    primary_track_name: Optional[str] = None
    primary_album_id: Optional[int] = None
    artist_name: Optional[str] = None
    scope: str
    is_manual: int
    created_at: str
    member_count: int
    group_status: str = "active"


class TrackGroupMemberResponse(BaseModel):
    l1_id: Optional[int] = None
    spotify_track_id: Optional[str] = None
    track_id: int
    track_name: str
    album_id: Optional[int] = None
    artist_name: Optional[str] = None
    identity_kind: Optional[str] = None
    source_record_count: int = 1
    metadata_conflict: bool = False
    is_primary: int = 0


class TrackL1CandidateResponse(BaseModel):
    l1_id: int
    spotify_track_id: Optional[str] = None
    track_id: int
    track_name: str
    artist_name: Optional[str] = None
    identity_kind: str = "spotify"
    source_record_count: int = 1
    metadata_conflict: bool = False
    album_id: Optional[int] = None
    album_name: Optional[str] = None
    play_count: int = 0
    first_play_date: Optional[str] = None
    last_play_date: Optional[str] = None
    effective_artist_names: list[str] = Field(default_factory=list)
    cover_url: Optional[str] = None


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


class CanonicalTrackMutationResponse(BaseModel):
    status: str
    canonical_track_id: int
    affected_canonical_track_ids: list[int] = Field(default_factory=list)


class CanonicalTrackEventResponse(BaseModel):
    event_id: int
    action: str
    survivor_canonical_track_id: Optional[int] = None
    affected_canonical_track_ids: list[int] = Field(default_factory=list)
    reason: str
    created_at: str


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
    original_l1_id: Optional[int] = None
    original_spotify_track_id: Optional[str] = None
    original_track_id: int
    original_track_name: str
    candidate_l1_id: Optional[int] = None
    candidate_spotify_track_id: Optional[str] = None
    candidate_track_id: int
    candidate_track_name: str
    primary_artist_id: int


class TrackGroupConfirmRequest(BaseModel):
    original_l1_id: Optional[int] = None
    candidate_l1_id: Optional[int] = None
    original_track_id: Optional[int] = None
    candidate_track_id: Optional[int] = None
    scope: str = "composition"


class TrackGroupConfirmResponse(BaseModel):
    status: str
    group_id: Optional[int] = None
    scope: Optional[str] = None
    member_count: Optional[int] = None
    album_projects_rebuilt: bool = False
    message: Optional[str] = None
    error_code: Optional[str] = None
    original_l1_id: Optional[int] = None
    candidate_l1_id: Optional[int] = None


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


@router.get("/track-groups", response_model=list[TrackGroupResponse])
def list_track_groups(conn: Connection = Depends(get_conn)):
    """Get saved L2/L3 track groups with representative metadata."""
    df = get_all_track_groups()
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/track-candidates", response_model=list[TrackL1CandidateResponse])
def track_l1_candidates(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=40, ge=1, le=100),
    conn: Connection = Depends(get_conn),
):
    """Search canonical-track candidates for manual L2/L3 grouping."""
    return search_track_l1_candidates(q, limit)


@router.get(
    "/track-groups/{group_id}/members",
    response_model=list[TrackGroupMemberResponse],
)
def list_track_group_members(group_id: int, conn: Connection = Depends(get_conn)):
    """Get stable track members of one saved track group."""
    df = get_track_group_members(group_id)
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


@router.get(
    "/canonical-tracks/events",
    response_model=list[CanonicalTrackEventResponse],
    include_in_schema=False,
)
def canonical_track_events(
    limit: int = Query(default=50, ge=1, le=200),
    conn: Connection = Depends(get_conn),
):
    """Return the advanced-governance audit trail for canonical tracks."""
    rows = conn.execute(
        """SELECT event_id, action, survivor_l1_id, affected_l1_ids,
                  reason, created_at
             FROM track_identity_events
            ORDER BY event_id DESC LIMIT ?""",
        (int(limit),),
    ).fetchall()
    return [
        {
            "event_id": int(row[0]),
            "action": str(row[1]),
            "survivor_canonical_track_id": int(row[2]) if row[2] is not None else None,
            "affected_canonical_track_ids": [int(value) for value in json.loads(row[3] or "[]")],
            "reason": str(row[4]),
            "created_at": str(row[5]),
        }
        for row in rows
    ]


# ── Mutation endpoints ────────────────────────────────────────────────────


def _finalize_canonical_track_mutation(reason: str) -> None:
    from backend.core.cache_manager import invalidate_playback_caches

    invalidate_playback_caches()
    _refresh_music_search_derived_data(reason)


@router.post(
    "/canonical-tracks/merge",
    response_model=CanonicalTrackMutationResponse,
    include_in_schema=False,
)
def merge_canonical_tracks(
    body: CanonicalTrackMergeRequest,
    auth: None = Depends(require_auth),
):
    """Retired: base identity is the existing track_id and is not user-mergeable."""
    raise HTTPException(
        status_code=410,
        detail="基础 track_id 由 Spotify ID 单一归属规则自动治理；请使用 L2/L3 版本归并。",
    )
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import rebuild_album_projects

    conn = get_db(readonly=False)
    try:
        survivor = merge_l1_identities(
            conn,
            survivor_l1_id=body.survivor_canonical_track_id,
            absorbed_l1_ids=body.absorbed_canonical_track_ids,
            reason=body.reason,
        )
        rebuild_album_projects(conn)
        conn.commit()
    except (TrackIdentityConflictError, ValueError) as exc:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _finalize_canonical_track_mutation("canonical track identities merged")
    return {
        "status": "ok",
        "canonical_track_id": survivor,
        "affected_canonical_track_ids": sorted(
            {int(value) for value in body.absorbed_canonical_track_ids}
        ),
    }


@router.post(
    "/canonical-tracks/{canonical_track_id}/split",
    response_model=CanonicalTrackMutationResponse,
    include_in_schema=False,
)
def split_canonical_track(
    canonical_track_id: int,
    body: CanonicalTrackSplitRequest,
    auth: None = Depends(require_auth),
):
    """Retired: provider ownership corrections are not a public L1 operation."""
    raise HTTPException(
        status_code=410,
        detail="基础 track_id 不提供拆分开关；Spotify ID 归属纠错需走受审计的数据治理流程。",
    )
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import rebuild_album_projects

    conn = get_db(readonly=False)
    try:
        new_id = split_external_identity(
            conn,
            source_l1_id=canonical_track_id,
            provider=body.provider,
            external_track_id=body.external_track_id,
            reason=body.reason,
        )
        rebuild_album_projects(conn)
        conn.commit()
    except (TrackIdentityConflictError, ValueError) as exc:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _finalize_canonical_track_mutation("canonical track identity split")
    return {
        "status": "ok",
        "canonical_track_id": new_id,
        "affected_canonical_track_ids": [int(canonical_track_id)],
    }


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
    references_are_l1 = body.original_l1_id is not None and body.candidate_l1_id is not None
    original_reference = body.original_l1_id if references_are_l1 else body.original_track_id
    candidate_reference = body.candidate_l1_id if references_are_l1 else body.candidate_track_id
    if original_reference is None or candidate_reference is None:
        return {
            "status": "error",
            "error_code": "missing_l1_selection",
            "message": "请选择两首要归并的歌曲",
        }
    result = confirm_track_group_candidate(
        original_track_id=original_reference,
        candidate_track_id=candidate_reference,
        scope=body.scope,
        references_are_l1=references_are_l1,
    )
    _refresh_music_search_derived_data("track group confirmed")
    return result


@router.put("/track-groups/{group_id}/members", response_model=StatusResponse)
def update_track_members(
    group_id: int,
    body: UpdateMembersRequest,
    auth: None = Depends(require_auth),
):
    """Add or remove stable IDs from a saved track group."""
    ok = update_track_group_members(group_id, body.add_ids, body.remove_ids)
    if ok:
        _refresh_music_search_derived_data("track group members changed")
    return {"status": "ok" if ok else "error"}


@router.put("/track-groups/{group_id}/primary", response_model=StatusResponse)
def update_primary_track(
    group_id: int,
    body: SetPrimaryTrackRequest,
    auth: None = Depends(require_auth),
):
    """Change the representative track of a saved group."""
    reference = body.l1_id if body.l1_id is not None else body.track_id
    ok = reference is not None and set_primary_track(group_id, reference)
    if ok:
        _refresh_music_search_derived_data("track group primary changed")
    return {"status": "ok" if ok else "error"}


@router.delete("/track-groups/{group_id}", response_model=StatusResponse)
def remove_track_group(group_id: int, auth: None = Depends(require_auth)):
    """Delete a saved track group while preserving raw metadata facts."""
    ok = delete_track_group(group_id)
    if ok:
        _refresh_music_search_derived_data("track group deleted")
    return {"status": "ok" if ok else "error"}


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
