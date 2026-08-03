"""Settings-managed track credit metadata API."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.auth import require_auth
from backend.core.cache_manager import invalidate_all
from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue
from backend.dependencies import get_conn
from backend.domains.metadata.track_credits import (
    apply_track_credit_override,
    get_track_credit_state,
    list_track_credit_detail,
    list_track_credit_events,
    preview_track_credit_override,
    search_track_credit_artist_candidates,
    search_track_credit_tracks,
    undo_track_credit_event,
)

router = APIRouter(prefix="/music-metadata/track-credits", tags=["Music Metadata"])


class TrackCreditPreviewRequest(BaseModel):
    track_id: int = Field(gt=0)
    artist_id: int = Field(gt=0)
    action: Literal["add", "remove", "set_role"]
    role: Literal["primary", "featured"] | None = None


class TrackCreditMutationRequest(TrackCreditPreviewRequest):
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)
    evidence_type: str | None = Field(default=None, max_length=100)
    evidence_source: str | None = Field(default=None, max_length=500)
    confirm_duplicate_identity: bool = False


class TrackCreditRoleUpdateRequest(BaseModel):
    role: Literal["primary", "featured"]
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)
    evidence_type: str | None = Field(default=None, max_length=100)
    evidence_source: str | None = Field(default=None, max_length=500)


class TrackCreditRemoveRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)
    evidence_type: str | None = Field(default=None, max_length=100)
    evidence_source: str | None = Field(default=None, max_length=500)


class TrackCreditUndoRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)


class TrackCreditMutationResponse(BaseModel):
    event_id: int
    override_id: int | None = None
    track_id: int
    artist_id: int
    revision: int
    rebuild_job_id: str | None = None


def _mutation_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 409 if "revision conflict" in message else 422
    return HTTPException(status_code=status, detail=message)


def _enqueue_rebuild(revision: int) -> str | None:
    invalidate_all()
    job = Job.create("track_credit_rebuild", "track_credit", "global", revision=revision)
    return get_job_queue().enqueue_if_not_pending(job)


def _write_override(**kwargs: Any) -> dict[str, Any]:
    kwargs["reason"] = str(kwargs.get("reason") or "个人管理直接修改").strip()
    kwargs["evidence_type"] = str(kwargs.get("evidence_type") or "user_confirmed").strip()
    conn = get_db(readonly=False)
    try:
        result = apply_track_credit_override(conn, **kwargs)
    except ValueError as exc:
        conn.rollback()
        raise _mutation_error(exc) from exc
    finally:
        conn.close()
    result["rebuild_job_id"] = _enqueue_rebuild(int(result["revision"]))
    return result


@router.get("/status", response_model=dict[str, Any])
def track_credit_status(conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    return {"state": get_track_credit_state(conn)}


@router.get("/tracks", response_model=dict[str, Any])
def search_tracks(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    return {
        "state": get_track_credit_state(conn),
        "items": search_track_credit_tracks(conn, q, limit),
    }


@router.get("/artist-candidates", response_model=dict[str, Any])
def search_artist_candidates(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    return {
        "state": get_track_credit_state(conn),
        "items": search_track_credit_artist_candidates(conn, q, limit),
    }


@router.get("/events", response_model=dict[str, Any])
def credit_events(
    track_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    return {
        "state": get_track_credit_state(conn),
        "items": list_track_credit_events(conn, track_id=track_id, limit=limit),
    }


@router.get("/manual-changes", response_model=dict[str, Any])
def manual_changes(conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    from backend.domains.metadata.track_credits import list_active_track_credit_overrides

    return {
        "state": get_track_credit_state(conn),
        "items": list_active_track_credit_overrides(conn),
    }


@router.get("/tracks/{track_id}", response_model=dict[str, Any])
def track_credits(track_id: int, conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    try:
        return list_track_credit_detail(conn, track_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/preview", response_model=dict[str, Any])
def preview_credit(
    body: TrackCreditPreviewRequest, conn: Connection = Depends(get_conn)
) -> dict[str, Any]:
    try:
        return preview_track_credit_override(conn, **body.model_dump())
    except ValueError as exc:
        raise _mutation_error(exc) from exc


@router.post("/overrides", response_model=TrackCreditMutationResponse)
def create_override(
    body: TrackCreditMutationRequest,
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    return _write_override(**body.model_dump(), actor="local-user")


@router.put("/overrides/{override_id}", response_model=TrackCreditMutationResponse)
def update_override_role(
    override_id: int,
    body: TrackCreditRoleUpdateRequest,
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT track_id, artist_id FROM track_credit_overrides
               WHERE override_id=? AND active=1""",
            (override_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="active track credit override not found")
    return _write_override(
        track_id=int(row["track_id"]),
        artist_id=int(row["artist_id"]),
        action="set_role",
        actor="local-user",
        **body.model_dump(),
    )


@router.post("/overrides/{override_id}/remove", response_model=TrackCreditMutationResponse)
def remove_override_credit(
    override_id: int,
    body: TrackCreditRemoveRequest,
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT track_id, artist_id FROM track_credit_overrides
               WHERE override_id=? AND active=1""",
            (override_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="active track credit override not found")
    return _write_override(
        track_id=int(row["track_id"]),
        artist_id=int(row["artist_id"]),
        action="remove",
        role=None,
        actor="local-user",
        confirm_duplicate_identity=False,
        **body.model_dump(),
    )


@router.post("/events/{event_id}/undo", response_model=TrackCreditMutationResponse)
def undo_credit(
    event_id: int,
    body: TrackCreditUndoRequest,
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    conn = get_db(readonly=False)
    try:
        result = undo_track_credit_event(
            conn,
            event_id=event_id,
            actor="local-user",
            **{
                **body.model_dump(),
                "reason": body.reason or "撤销人工修改",
            },
        )
    except ValueError as exc:
        conn.rollback()
        raise _mutation_error(exc) from exc
    finally:
        conn.close()
    result["rebuild_job_id"] = _enqueue_rebuild(int(result["revision"]))
    return result


@router.post("/rebuild", response_model=dict[str, Any])
def retry_credit_rebuild(auth: None = Depends(require_auth)) -> dict[str, Any]:
    conn = get_db()
    try:
        revision = get_track_credit_state(conn).get("current_revision", 0)
    finally:
        conn.close()
    return {"revision": revision, "rebuild_job_id": _enqueue_rebuild(int(revision))}
