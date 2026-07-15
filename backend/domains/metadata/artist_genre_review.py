"""Review helpers for artist genre suggestions."""

from __future__ import annotations

import json
from typing import Any

from backend.domains.metadata.artist_genres import normalize_genres

PRE_REVIEW_RECOMMENDATIONS = {
    "recommend_approve",
    "manual_review",
    "insufficient_evidence",
    "recommend_reject",
}


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
        "evidence_url": row["evidence_url"],
        "review_status": row["review_status"],
        "pre_review_recommendation": row["pre_review_recommendation"],
        "pre_review_confidence": (
            float(row["pre_review_confidence"])
            if row["pre_review_confidence"] is not None
            else None
        ),
        "pre_review_note": row["pre_review_note"],
        "pre_reviewed_by": row["pre_reviewed_by"],
        "pre_reviewed_at": row["pre_reviewed_at"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "resolution_note": row["resolution_note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
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
                  s.evidence_summary,
                  s.evidence_url,
                  q.status AS review_status,
                  q.pre_review_recommendation,
                  q.pre_review_confidence,
                  q.pre_review_note,
                  q.pre_reviewed_by,
                  q.pre_reviewed_at,
                  q.reviewed_by,
                  q.reviewed_at,
                  q.resolution_note,
                  q.created_at,
                  q.updated_at
           FROM artist_genre_review_queue q
           JOIN artist_genre_sources s ON s.source_id = q.suggested_source_id
           WHERE q.status = ?
           ORDER BY q.play_hours DESC, q.review_id ASC
           LIMIT ?""",
        (status, int(limit)),
    ).fetchall()
    return [_row_to_review(row) for row in rows]


def pre_review_suggestion(
    conn,
    *,
    review_id: int,
    recommendation: str,
    confidence: float,
    note: str,
    reviewed_by: str = "codex_first_pass",
) -> dict[str, Any]:
    if recommendation not in PRE_REVIEW_RECOMMENDATIONS:
        raise ValueError(f"unsupported pre-review recommendation: {recommendation}")
    normalized_note = note.strip()
    normalized_actor = reviewed_by.strip()
    if not normalized_note or not normalized_actor:
        raise ValueError("pre-review note and reviewer must not be empty")
    normalized_confidence = float(confidence)
    if not 0.0 <= normalized_confidence <= 1.0:
        raise ValueError("pre-review confidence must be between 0 and 1")
    cursor = conn.execute(
        """UPDATE artist_genre_review_queue
           SET pre_review_recommendation=?, pre_review_confidence=?,
               pre_review_note=?, pre_reviewed_by=?, pre_reviewed_at=datetime('now'),
               updated_at=datetime('now')
           WHERE review_id=? AND status='open'""",
        (
            recommendation,
            normalized_confidence,
            normalized_note,
            normalized_actor,
            int(review_id),
        ),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError(f"review_id {review_id} is not open")
    conn.commit()
    items = list_reviews(conn, status="open", limit=200)
    return next(item for item in items if item["review_id"] == int(review_id))


def update_review_evidence(
    conn,
    *,
    review_id: int,
    evidence_url: str,
    evidence_summary: str,
) -> dict[str, Any]:
    normalized_url = evidence_url.strip()
    normalized_summary = evidence_summary.strip()
    if not normalized_url.startswith("https://"):
        raise ValueError("证据链接必须使用 https://")
    if not normalized_summary:
        raise ValueError("证据摘要不能为空")
    cursor = conn.execute(
        """UPDATE artist_genre_sources
           SET evidence_url=?, evidence_summary=?, updated_at=datetime('now')
           WHERE source_id=(
               SELECT suggested_source_id FROM artist_genre_review_queue
               WHERE review_id=? AND status='open'
           ) AND status='suggested'""",
        (normalized_url, normalized_summary, int(review_id)),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError(f"review_id {review_id} is not an open suggested review")
    conn.commit()
    items = list_reviews(conn, status="open", limit=200)
    return next(item for item in items if item["review_id"] == int(review_id))


def review_suggestion(
    conn,
    *,
    review_id: int,
    decision: str,
    resolution_note: str = "本地审核完成。",
) -> dict[str, Any]:
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
                      s.status AS source_status,
                      s.evidence_url
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
        if decision == "approve" and not str(row["evidence_url"] or "").startswith("https://"):
            conn.rollback()
            raise ValueError("批准前必须补充可复核的 HTTPS 证据链接")

        source_cursor = conn.execute(
            """UPDATE artist_genre_sources
               SET status = ?, updated_at = datetime('now')
               WHERE source_id = ? AND status = 'suggested'""",
            (source_status, int(row["source_id"])),
        )
        review_cursor = conn.execute(
            """UPDATE artist_genre_review_queue
               SET status = ?, reviewed_by='local_user', reviewed_at=datetime('now'),
                   resolution_note=?, updated_at = datetime('now')
               WHERE review_id = ? AND status = 'open'""",
            (source_status, resolution_note.strip(), int(review_id)),
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
