"""Settings-managed global artist identity API."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.auth import require_auth
from backend.core.cache_manager import invalidate_all
from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue
from backend.dependencies import get_conn
from backend.domains.metadata.artist_identity import (
    create_artist_identity_group,
    get_identity_state,
    list_artist_identity_events,
    list_artist_identity_groups,
    preview_artist_identity_merge,
    search_artist_identity_candidates,
    undo_artist_identity_event,
    update_artist_identity_group,
)

router = APIRouter(prefix="/artist-identities", tags=["Artist Identity"])


class IdentityPreviewRequest(BaseModel):
    artist_ids: list[int] = Field(min_length=2)
    canonical_artist_id: int
    display_name: str = Field(min_length=1, max_length=200)


class IdentityExternalIdInput(BaseModel):
    artist_id: int
    provider: str = Field(min_length=1, max_length=50)
    external_id: str = Field(min_length=1, max_length=200)
    evidence_type: str = Field(default="user_confirmed", min_length=1, max_length=100)
    evidence_source: str | None = Field(default=None, max_length=500)
    confidence: float = Field(default=1.0, ge=0, le=1)
    verified: bool = True


class IdentityCreateRequest(IdentityPreviewRequest):
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)
    confirm_external_id_conflict: bool = False
    external_ids: list[IdentityExternalIdInput] = Field(default_factory=list)


class IdentityUpdateRequest(BaseModel):
    add_ids: list[int] = Field(default_factory=list)
    remove_ids: list[int] = Field(default_factory=list)
    canonical_artist_id: int | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    provider_metadata_artist_id: int | None = None
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)
    confirm_external_id_conflict: bool = False


class IdentityUndoRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=500)


class IdentityMutationResponse(BaseModel):
    event_id: int
    identity_id: int | None = None
    revision: int
    rebuild_job_id: str | None = None


def _mutation_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 409 if "revision conflict" in message else 422
    return HTTPException(status_code=status, detail=message)


def _enqueue_rebuild(revision: int) -> str | None:
    invalidate_all()
    job = Job.create("artist_identity_rebuild", "artist_identity", "global", revision=revision)
    return get_job_queue().enqueue_if_not_pending(job)


@router.get("", response_model=dict[str, Any])
def list_identities(conn: Connection = Depends(get_conn)) -> dict[str, Any]:
    return {
        "state": get_identity_state(conn),
        "groups": list_artist_identity_groups(conn),
    }


@router.get("/candidates", response_model=dict[str, Any])
def search_candidates(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    return {
        "state": get_identity_state(conn),
        "items": search_artist_identity_candidates(conn, q, limit),
    }


@router.post("/preview", response_model=dict[str, Any])
def preview_identity(
    body: IdentityPreviewRequest, conn: Connection = Depends(get_conn)
) -> dict[str, Any]:
    try:
        return preview_artist_identity_merge(
            conn, body.artist_ids, body.canonical_artist_id, body.display_name
        )
    except ValueError as exc:
        raise _mutation_error(exc) from exc


@router.post("", response_model=IdentityMutationResponse)
def create_identity(
    body: IdentityCreateRequest,
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    conn = get_db(readonly=False)
    try:
        result = create_artist_identity_group(
            conn,
            artist_ids=body.artist_ids,
            canonical_artist_id=body.canonical_artist_id,
            display_name=body.display_name,
            expected_revision=body.expected_revision,
            idempotency_key=body.idempotency_key,
            reason=body.reason or "个人管理直接合并",
            confirm_external_id_conflict=body.confirm_external_id_conflict,
            external_ids=[item.model_dump() for item in body.external_ids],
        )
    except ValueError as exc:
        conn.rollback()
        raise _mutation_error(exc) from exc
    finally:
        conn.close()
    result["rebuild_job_id"] = _enqueue_rebuild(int(result["revision"]))
    return result


@router.put("/{identity_id}", response_model=IdentityMutationResponse)
def update_identity(
    identity_id: int,
    body: IdentityUpdateRequest,
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    conn = get_db(readonly=False)
    try:
        result = update_artist_identity_group(
            conn,
            identity_id=identity_id,
            add_ids=body.add_ids,
            remove_ids=body.remove_ids,
            canonical_artist_id=body.canonical_artist_id,
            display_name=body.display_name,
            provider_metadata_artist_id=body.provider_metadata_artist_id,
            expected_revision=body.expected_revision,
            idempotency_key=body.idempotency_key,
            reason=body.reason or "个人管理直接修改",
            confirm_external_id_conflict=body.confirm_external_id_conflict,
        )
    except ValueError as exc:
        conn.rollback()
        raise _mutation_error(exc) from exc
    finally:
        conn.close()
    result["rebuild_job_id"] = _enqueue_rebuild(int(result["revision"]))
    return result


@router.get("/events", response_model=dict[str, Any])
def identity_events(
    limit: int = Query(default=100, ge=1, le=500),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    return {"state": get_identity_state(conn), "items": list_artist_identity_events(conn, limit)}


@router.post("/events/{event_id}/undo", response_model=IdentityMutationResponse)
def undo_identity(
    event_id: int,
    body: IdentityUndoRequest,
    auth: None = Depends(require_auth),
) -> dict[str, Any]:
    conn = get_db(readonly=False)
    try:
        result = undo_artist_identity_event(
            conn,
            event_id=event_id,
            expected_revision=body.expected_revision,
            idempotency_key=body.idempotency_key,
            reason=body.reason or "撤销人工修改",
        )
    except ValueError as exc:
        conn.rollback()
        raise _mutation_error(exc) from exc
    finally:
        conn.close()
    result["rebuild_job_id"] = _enqueue_rebuild(int(result["revision"]))
    return result
