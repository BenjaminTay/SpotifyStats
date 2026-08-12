"""Artist language coverage and review workflow endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.db import get_db, load_plays
from backend.dependencies import PlayFilters, get_conn
from backend.domains.metadata.artist_language_review import (
    ArtistLanguageConflictError,
    ArtistLanguageNotFoundError,
    decide_review,
    get_or_create_review,
    list_reviews,
    pre_review_language,
    save_review_source,
)
from backend.domains.metadata.artist_languages import (
    ArtistLanguageValidationError,
    build_primary_artist_ms,
    compute_artist_language_distribution,
)
from backend.models.artist_language_metadata import (
    ArtistLanguageCoverageResponse,
    ArtistLanguagePreReviewRequest,
    ArtistLanguageReviewCreateRequest,
    ArtistLanguageReviewDecisionRequest,
    ArtistLanguageReviewItem,
    ArtistLanguageReviewListResponse,
    ArtistLanguageReviewMutationResponse,
    ArtistLanguageSourceInput,
    ArtistLanguageSourceItem,
    ReviewStatus,
)

router = APIRouter(
    prefix="/metadata/artist-languages",
    tags=["Artist Language Metadata"],
)


def get_write_conn():
    conn = get_db(readonly=False)
    try:
        yield conn
    finally:
        conn.close()


def _filtered_plays(conn: Connection, filters: PlayFilters):
    return load_plays(
        conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )


def _domain_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ArtistLanguageNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ArtistLanguageConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ArtistLanguageValidationError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "artist_language_validation_error",
                "message": str(exc),
            },
        )
    raise exc


@router.get("/coverage", response_model=ArtistLanguageCoverageResponse)
def get_artist_language_coverage(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    plays_df = _filtered_plays(conn, filters)
    artist_ms, excluded_ms = build_primary_artist_ms(conn, plays_df)
    return compute_artist_language_distribution(
        conn,
        artist_ms,
        excluded_ms=excluded_ms,
    )


@router.get("/reviews", response_model=ArtistLanguageReviewListResponse)
def get_artist_language_reviews(
    status: ReviewStatus = Query(default="open"),
    limit: int = Query(default=50, ge=1, le=200),
    conn: Connection = Depends(get_conn),
):
    total = conn.execute(
        "SELECT COUNT(*) FROM artist_language_review_queue WHERE status=?",
        (status,),
    ).fetchone()[0]
    return {
        "items": list_reviews(conn, status=status, limit=limit),
        "total": total,
    }


@router.post("/reviews", response_model=ArtistLanguageReviewItem)
def create_artist_language_review(
    request: ArtistLanguageReviewCreateRequest,
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_write_conn),
):
    plays_df = _filtered_plays(conn, filters)
    artist_ms, _ = build_primary_artist_ms(conn, plays_df)
    try:
        return get_or_create_review(
            conn,
            artist_id=request.artist_id,
            play_hours_snapshot=artist_ms.get(request.artist_id, 0) / 3_600_000,
            reason=request.reason,
        )
    except (ArtistLanguageNotFoundError, ArtistLanguageConflictError) as exc:
        raise _domain_http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_review_request", "message": str(exc)},
        ) from exc


@router.put(
    "/reviews/{review_id}/source",
    response_model=ArtistLanguageSourceItem,
)
def put_artist_language_review_source(
    review_id: int,
    request: ArtistLanguageSourceInput,
    conn: Connection = Depends(get_write_conn),
):
    try:
        return save_review_source(
            conn,
            review_id=review_id,
            payload=request,
        )
    except (
        ArtistLanguageNotFoundError,
        ArtistLanguageConflictError,
        ArtistLanguageValidationError,
    ) as exc:
        raise _domain_http_error(exc) from exc


@router.patch(
    "/reviews/{review_id}",
    response_model=ArtistLanguageReviewMutationResponse,
)
def patch_artist_language_review(
    review_id: int,
    request: ArtistLanguageReviewDecisionRequest,
    conn: Connection = Depends(get_write_conn),
):
    try:
        result = decide_review(
            conn,
            review_id=review_id,
            action=request.action,
            resolution_note=request.resolution_note,
            reviewed_by="local_user",
        )
        from backend.core.cache_manager import invalidate

        invalidate("yearly_review")
        return result
    except (
        ArtistLanguageNotFoundError,
        ArtistLanguageConflictError,
        ArtistLanguageValidationError,
    ) as exc:
        raise _domain_http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_review_request", "message": str(exc)},
        ) from exc


@router.patch(
    "/reviews/{review_id}/pre-review",
    response_model=ArtistLanguageReviewItem,
)
def patch_artist_language_pre_review(
    review_id: int,
    request: ArtistLanguagePreReviewRequest,
    conn: Connection = Depends(get_write_conn),
):
    try:
        return pre_review_language(
            conn,
            review_id=review_id,
            recommendation=request.recommendation,
            confidence=request.confidence,
            note=request.note,
        )
    except (
        ArtistLanguageNotFoundError,
        ArtistLanguageConflictError,
        ArtistLanguageValidationError,
    ) as exc:
        raise _domain_http_error(exc) from exc
