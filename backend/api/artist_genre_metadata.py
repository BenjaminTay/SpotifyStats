"""Artist genre metadata coverage and review endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.db import get_db, load_plays
from backend.dependencies import PlayFilters, get_conn
from backend.domains.metadata.artist_genre_review import (
    list_reviews,
    pre_review_suggestion,
    review_suggestion,
    update_review_evidence,
)
from backend.domains.metadata.artist_genres import (
    AXIS_ORDER,
    compute_genre_axis_gaps,
    compute_genre_coverage,
    compute_genre_taxonomy_audit,
)
from backend.domains.metadata.artist_languages import build_primary_artist_ms
from backend.models.artist_genre_metadata import (
    ArtistGenreAxisGapResponse,
    ArtistGenreCoverageResponse,
    ArtistGenreEvidenceUpdateRequest,
    ArtistGenreReviewDecisionRequest,
    ArtistGenreReviewDecisionResponse,
    ArtistGenreReviewItem,
    ArtistGenreReviewListResponse,
    ArtistGenreTaxonomyResponse,
    MetadataPreReviewRequest,
)

router = APIRouter(prefix="/metadata/artist-genres", tags=["Artist Genre Metadata"])


def get_write_conn():
    conn = get_db(readonly=False)
    try:
        yield conn
    finally:
        conn.close()


def _load_artist_play_hours(
    conn: Connection,
    filters: PlayFilters,
) -> tuple[dict[str, float], float]:
    plays = load_plays(
        conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    artist_ms, excluded_ms = build_primary_artist_ms(conn, plays)
    names: dict[int, str] = {}
    artist_ids = list(artist_ms)
    for offset in range(0, len(artist_ids), 500):
        chunk = artist_ids[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT artist_id, artist_name FROM artists WHERE artist_id IN ({placeholders})",
            chunk,
        ).fetchall()
        names.update({int(row[0]): str(row[1]) for row in rows})
    return (
        {
            names[artist_id]: ms / 3_600_000
            for artist_id, ms in artist_ms.items()
            if artist_id in names and ms > 0
        },
        excluded_ms / 3_600_000,
    )


@router.get("/coverage", response_model=ArtistGenreCoverageResponse)
def get_artist_genre_coverage(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    artist_hours, excluded_hours = _load_artist_play_hours(conn, filters)
    report = compute_genre_coverage(conn, artist_hours)
    report["artist_count"] = len(artist_hours)
    report["total_hours"] = round(sum(artist_hours.values()), 1)
    report["excluded_unattributed_hours"] = excluded_hours
    return report


@router.get("/taxonomy", response_model=ArtistGenreTaxonomyResponse)
def get_artist_genre_taxonomy(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    artist_hours, _ = _load_artist_play_hours(conn, filters)
    return compute_genre_taxonomy_audit(conn, artist_hours)


@router.get("/axis-gaps", response_model=ArtistGenreAxisGapResponse)
def get_artist_genre_axis_gaps(
    axis: str = Query(default="style"),
    limit: int = Query(default=50, ge=1, le=200),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    if axis not in AXIS_ORDER:
        raise HTTPException(status_code=422, detail=f"unsupported genre axis: {axis}")
    artist_hours, _ = _load_artist_play_hours(conn, filters)
    gaps = compute_genre_axis_gaps(conn, artist_hours, axis=axis)
    artist_names = [item["artist_name"] for item in gaps]
    reviews_by_artist = {}
    if artist_names:
        placeholders = ",".join("?" for _ in artist_names)
        rows = conn.execute(
            f"""SELECT review_id, artist_name, status, pre_review_recommendation
                FROM artist_genre_review_queue
                WHERE artist_name IN ({placeholders}) AND status='open'
                ORDER BY review_id DESC""",
            artist_names,
        ).fetchall()
        reviews_by_artist = {row["artist_name"]: row for row in rows}
    for item in gaps:
        review = reviews_by_artist.get(item["artist_name"])
        item["review_id"] = int(review["review_id"]) if review else None
        item["review_status"] = review["status"] if review else None
        item["pre_review_recommendation"] = review["pre_review_recommendation"] if review else None
    return {
        "axis": axis,
        "total": len(gaps),
        "unknown_hours": round(sum(float(item["hours"]) for item in gaps), 1),
        "items": gaps[:limit],
    }


@router.get("/reviews", response_model=ArtistGenreReviewListResponse)
def get_artist_genre_reviews(
    status: str = Query(default="open", max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    conn: Connection = Depends(get_conn),
):
    total = conn.execute(
        "SELECT COUNT(*) FROM artist_genre_review_queue WHERE status=?", (status,)
    ).fetchone()[0]
    return {"items": list_reviews(conn, status=status, limit=limit), "total": total}


@router.patch("/reviews/{review_id}/evidence", response_model=ArtistGenreReviewItem)
def patch_artist_genre_review_evidence(
    review_id: int,
    request: ArtistGenreEvidenceUpdateRequest,
    conn: Connection = Depends(get_write_conn),
):
    try:
        return update_review_evidence(
            conn,
            review_id=review_id,
            evidence_url=request.evidence_url,
            evidence_summary=request.evidence_summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/reviews/{review_id}/pre-review", response_model=ArtistGenreReviewItem)
def patch_artist_genre_pre_review(
    review_id: int,
    request: MetadataPreReviewRequest,
    conn: Connection = Depends(get_write_conn),
):
    try:
        return pre_review_suggestion(
            conn,
            review_id=review_id,
            recommendation=request.recommendation,
            confidence=request.confidence,
            note=request.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/reviews/{review_id}/approve",
    response_model=ArtistGenreReviewDecisionResponse,
)
def approve_artist_genre_review(
    review_id: int,
    request: ArtistGenreReviewDecisionRequest,
    conn: Connection = Depends(get_write_conn),
):
    try:
        result = review_suggestion(
            conn,
            review_id=review_id,
            decision="approve",
            resolution_note=request.resolution_note,
        )
        from backend.core.cache_manager import invalidate

        invalidate("yearly_review")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/reviews/{review_id}/reject",
    response_model=ArtistGenreReviewDecisionResponse,
)
def reject_artist_genre_review(
    review_id: int,
    request: ArtistGenreReviewDecisionRequest,
    conn: Connection = Depends(get_write_conn),
):
    try:
        return review_suggestion(
            conn,
            review_id=review_id,
            decision="reject",
            resolution_note=request.resolution_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
