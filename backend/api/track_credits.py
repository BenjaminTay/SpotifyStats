"""Settings-managed track credit metadata API."""

from __future__ import annotations

from sqlite3 import Connection, OperationalError
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.auth import require_auth
from backend.core.cache_manager import invalidate_all
from backend.core.db import get_db
from backend.dependencies import get_conn
from backend.domains.metadata.track_credits import (
    apply_track_credit_override,
    get_track_credit_state,
    list_track_credit_change_sets,
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
    idempotent_replay: bool = False


def _mutation_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 409 if "revision conflict" in message else 422
    return HTTPException(status_code=status, detail=message)


def _mutation_database_error(exc: OperationalError) -> HTTPException:
    message = str(exc).lower()
    if "locked" in message or "busy" in message:
        return HTTPException(
            status_code=409,
            detail="track credit revision conflict: another mutation is in progress",
        )
    return HTTPException(status_code=500, detail="track credit mutation failed")


def _enqueue_rebuild(revision: int) -> str | None:
    from backend.services.music_search_maintenance_service import (
        mark_music_search_for_rebuild,
    )
    from backend.services.track_credit_rebuild_service import (
        ensure_track_credit_rebuild_job,
    )

    invalidate_all()
    search_conn = get_db(readonly=False)
    try:
        changes = list_track_credit_change_sets(
            search_conn,
            after_revision=revision - 1,
            through_revision=revision,
        )
        role_only = (
            bool(changes)
            and {int(change["to_revision"]) for change in changes} == {revision}
            and all(not bool(change.get("statistics_membership_changed")) for change in changes)
        )
        if role_only:
            mark_music_search_for_rebuild(
                reason="track credit role-only revision changed",
                documents=True,
                revision_kinds=("candidate",),
                statistics=False,
                conn=search_conn,
            )
        else:
            mark_music_search_for_rebuild(
                reason="track credit revision changed",
                documents=True,
                conn=search_conn,
            )
        return ensure_track_credit_rebuild_job(revision, conn=search_conn)
    finally:
        search_conn.close()


def _write_override(**kwargs: Any) -> dict[str, Any]:
    kwargs["reason"] = str(kwargs.get("reason") or "个人管理直接修改").strip()
    kwargs["evidence_type"] = str(kwargs.get("evidence_type") or "user_confirmed").strip()
    conn = get_db(readonly=False)
    try:
        result = apply_track_credit_override(conn, **kwargs)
    except ValueError as exc:
        conn.rollback()
        raise _mutation_error(exc) from exc
    except OperationalError as exc:
        conn.rollback()
        raise _mutation_database_error(exc) from exc
    finally:
        conn.close()
    if result.get("idempotent_replay"):
        result["rebuild_job_id"] = None
    else:
        result["rebuild_job_id"] = _enqueue_rebuild(int(result["revision"]))
    return result


def _track_credit_maintenance_status(conn: Connection) -> dict[str, Any]:
    state = get_track_credit_state(conn)
    from backend.domains.music_search.index import (
        get_music_search_candidate_maintenance_state,
        get_music_search_index_state,
    )

    serving = get_music_search_index_state(conn)
    candidate = get_music_search_candidate_maintenance_state(conn)
    variants: list[dict[str, Any]] = []
    if conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='music_search_snapshot_variant_state'"""
    ).fetchone():
        for row in conn.execute(
            """SELECT merge_level, dynamic_threshold, active_snapshot_key,
                      active_filter_fingerprint, target_filter_fingerprint,
                      maintenance_status, last_error, updated_at
               FROM music_search_snapshot_variant_state
               ORDER BY CASE
                   WHEN merge_level=2 AND dynamic_threshold=1 THEN 0
                   WHEN merge_level=3 AND dynamic_threshold=1 THEN 1
                   WHEN merge_level=2 AND dynamic_threshold=0 THEN 2 ELSE 3 END"""
        ).fetchall():
            item = dict(row)
            item["dynamic_threshold"] = bool(item["dynamic_threshold"])
            if not item.get("active_snapshot_key"):
                item["freshness"] = "unavailable"
            elif item.get("maintenance_status") == "ready" and item.get(
                "active_filter_fingerprint"
            ) == item.get("target_filter_fingerprint"):
                item["freshness"] = "current"
            else:
                item["freshness"] = "last_known_good"
            variants.append(item)
    current_revision = int(state.get("current_revision") or 0)
    active_revision = int(state.get("active_aggregate_revision") or 0)
    queued_or_running = False
    if conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='background_jobs'"""
    ).fetchone():
        queued_or_running = bool(
            conn.execute(
                """SELECT 1 FROM background_jobs
                   WHERE status IN ('pending', 'running')
                     AND job_type IN ('track_credit_rebuild', 'music_search_snapshot_rebuild')
                   LIMIT 1"""
            ).fetchone()
        )
    maintenance_failed = (
        str(state.get("rebuild_status") or "") == "failed"
        or str(candidate.get("maintenance_status") or "") == "failed"
        or any(item["maintenance_status"] == "failed" for item in variants)
    )
    pending_without_job = (
        current_revision > active_revision
        or str(state.get("rebuild_status") or "") in {"pending", "running"}
        or str(candidate.get("maintenance_status") or "") in {"pending", "building"}
        or any(item["maintenance_status"] in {"pending", "building"} for item in variants)
    ) and not queued_or_running
    built_at = serving.get("built_at")
    lkg_age = None
    if built_at:
        age_row = conn.execute(
            "SELECT MAX(0, CAST((julianday('now') - julianday(?)) * 86400 AS INTEGER))",
            (built_at,),
        ).fetchone()
        lkg_age = int(age_row[0]) if age_row is not None and age_row[0] is not None else None
    return {
        **state,
        "serving_revision": active_revision,
        "target_revision": current_revision,
        "serving_candidate_generation": serving.get("active_generation_id"),
        "candidate_maintenance_status": candidate.get("maintenance_status", "missing"),
        "statistics_variant_statuses": variants,
        "queued_or_running_job": queued_or_running,
        "lkg_age": lkg_age,
        "retry_allowed": maintenance_failed or pending_without_job,
    }


@router.get("/status", response_model=dict[str, Any])
def track_credit_status(
    conn: Connection = Depends(get_conn),
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    return {"state": _track_credit_maintenance_status(conn)}


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
    except OperationalError as exc:
        conn.rollback()
        raise _mutation_database_error(exc) from exc
    finally:
        conn.close()
    if result.get("idempotent_replay"):
        result["rebuild_job_id"] = None
    else:
        result["rebuild_job_id"] = _enqueue_rebuild(int(result["revision"]))
    return result


@router.post("/rebuild", response_model=dict[str, Any])
def retry_credit_rebuild(auth: None = Depends(require_auth)) -> dict[str, Any]:
    from backend.services.track_credit_rebuild_service import ensure_track_credit_rebuild_job

    conn = get_db(readonly=False)
    try:
        status = _track_credit_maintenance_status(conn)
        revision = int(status.get("current_revision") or 0)
        active_revision = int(status.get("active_aggregate_revision") or 0)
        if active_revision < revision or status.get("rebuild_status") in {
            "pending",
            "running",
            "failed",
        }:
            job_id = ensure_track_credit_rebuild_job(revision, conn=conn)
        else:
            from backend.services.music_search_maintenance_service import (
                enqueue_music_search_snapshot_rebuild,
            )

            candidate_status = str(status.get("candidate_maintenance_status") or "missing")
            job_id = enqueue_music_search_snapshot_rebuild(
                rebuild_documents=candidate_status != "ready",
                conn=conn,
            )
    finally:
        conn.close()
    return {"revision": revision, "rebuild_job_id": job_id}
