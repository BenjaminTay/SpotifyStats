"""Artist genre metadata coverage and review endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.db import get_db
from backend.dependencies import get_conn
from backend.domains.metadata.artist_genre_review import list_reviews, review_suggestion
from backend.domains.metadata.artist_genres import (
    compute_genre_coverage,
    compute_genre_taxonomy_audit,
)
from backend.models.artist_genre_metadata import (
    ArtistGenreCoverageResponse,
    ArtistGenreReviewDecisionResponse,
    ArtistGenreReviewListResponse,
    ArtistGenreTaxonomyResponse,
)

router = APIRouter(prefix="/metadata/artist-genres", tags=["Artist Genre Metadata"])


def get_write_conn():
    conn = get_db(readonly=False)
    try:
        yield conn
    finally:
        conn.close()


def _load_artist_play_hours(conn: Connection) -> dict[str, float]:
    rows = conn.execute(
        """SELECT a.artist_name AS artist_name,
                  SUM(p.ms_played) / 3600000.0 AS hours
           FROM plays p
           JOIN tracks t ON p.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           WHERE p.track_id IS NOT NULL
             AND COALESCE(p.content_type, 'audio') = 'audio'
           GROUP BY a.artist_name
           HAVING hours > 0
           ORDER BY hours DESC"""
    ).fetchall()
    return {
        row["artist_name"]: float(row["hours"] or 0)
        for row in rows
        if row["artist_name"] and float(row["hours"] or 0) > 0
    }


@router.get("/coverage", response_model=ArtistGenreCoverageResponse)
def get_artist_genre_coverage(conn: Connection = Depends(get_conn)):
    artist_hours = _load_artist_play_hours(conn)
    report = compute_genre_coverage(conn, artist_hours)
    report["artist_count"] = len(artist_hours)
    report["total_hours"] = round(sum(artist_hours.values()), 1)
    return report


@router.get("/taxonomy", response_model=ArtistGenreTaxonomyResponse)
def get_artist_genre_taxonomy(conn: Connection = Depends(get_conn)):
    artist_hours = _load_artist_play_hours(conn)
    return compute_genre_taxonomy_audit(conn, artist_hours)


@router.get("/reviews", response_model=ArtistGenreReviewListResponse)
def get_artist_genre_reviews(
    status: str = Query(default="open", max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    conn: Connection = Depends(get_conn),
):
    return {"items": list_reviews(conn, status=status, limit=limit)}


@router.post(
    "/reviews/{review_id}/approve",
    response_model=ArtistGenreReviewDecisionResponse,
)
def approve_artist_genre_review(
    review_id: int,
    conn: Connection = Depends(get_write_conn),
):
    try:
        return review_suggestion(conn, review_id=review_id, decision="approve")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/reviews/{review_id}/reject",
    response_model=ArtistGenreReviewDecisionResponse,
)
def reject_artist_genre_review(
    review_id: int,
    conn: Connection = Depends(get_write_conn),
):
    try:
        return review_suggestion(conn, review_id=review_id, decision="reject")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
