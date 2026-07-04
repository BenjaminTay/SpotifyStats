"""Review helpers for artist genre suggestions."""

from __future__ import annotations

import json
from typing import Any

from backend.domains.metadata.artist_genres import normalize_genres


def _loads_genres(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = []
    return normalize_genres(value if isinstance(value, list) else [])


def _row_to_review(row) -> dict[str, Any]:
    return {
        "review_id": int(row["review_id"]),
        "artist_name": row["artist_name"],
        "play_hours": float(row["play_hours"] or 0.0),
        "reason": row["reason"],
        "source_id": int(row["source_id"]),
        "source": row["source"],
        "source_key": row["source_key"],
        "source_status": row["source_status"],
        "genres": _loads_genres(row["normalized_genres_json"]),
        "primary_genre": row["primary_genre"],
        "language": row["language"],
        "region": row["region"],
        "confidence": float(row["confidence"] or 0.0),
        "evidence_summary": row["evidence_summary"],
    }


def list_reviews(conn, *, status: str = "open", limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT q.review_id,
                  q.artist_name,
                  q.play_hours,
                  q.reason,
                  s.source_id AS source_id,
                  s.source AS source,
                  s.source_key AS source_key,
                  s.status AS source_status,
                  s.normalized_genres_json,
                  s.primary_genre,
                  s.language,
                  s.region,
                  s.confidence,
                  s.evidence_summary
           FROM artist_genre_review_queue q
           JOIN artist_genre_sources s ON s.source_id = q.suggested_source_id
           WHERE q.status = ?
           ORDER BY q.play_hours DESC, q.review_id ASC
           LIMIT ?""",
        (status, int(limit)),
    ).fetchall()
    return [_row_to_review(row) for row in rows]


def review_suggestion(conn, *, review_id: int, decision: str) -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")

    source_status = "approved" if decision == "approve" else "rejected"
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT q.review_id,
                      q.artist_name,
                      q.status AS review_status,
                      q.suggested_source_id,
                      s.source_id AS source_id,
                      s.status AS source_status
               FROM artist_genre_review_queue q
               JOIN artist_genre_sources s ON s.source_id = q.suggested_source_id
               WHERE q.review_id = ?
                 AND q.status = 'open'
                 AND s.status = 'suggested'""",
            (int(review_id),),
        ).fetchone()
        if row is None:
            conn.rollback()
            raise ValueError(f"review_id {review_id} is not an open suggested review")

        source_cursor = conn.execute(
            """UPDATE artist_genre_sources
               SET status = ?, updated_at = datetime('now')
               WHERE source_id = ? AND status = 'suggested'""",
            (source_status, int(row["source_id"])),
        )
        review_cursor = conn.execute(
            """UPDATE artist_genre_review_queue
               SET status = ?, updated_at = datetime('now')
               WHERE review_id = ? AND status = 'open'""",
            (source_status, int(review_id)),
        )
        if source_cursor.rowcount != 1 or review_cursor.rowcount != 1:
            conn.rollback()
            raise ValueError(f"review_id {review_id} is not an open suggested review")
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise

    return {
        "review_id": int(row["review_id"]),
        "artist_name": row["artist_name"],
        "decision": decision,
        "source_id": int(row["source_id"]),
        "source_status": source_status,
        "review_status": source_status,
    }
