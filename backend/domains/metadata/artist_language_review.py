"""Transactional review workflow for artist language metadata."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.domains.metadata.artist_languages import (
    ArtistLanguageValidationError,
    validate_approved_language_source,
)
from backend.domains.metadata.language_registry import normalize_language_claim


class ArtistLanguageNotFoundError(LookupError):
    """Raised when an artist or review does not exist."""


class ArtistLanguageConflictError(RuntimeError):
    """Raised when a review or candidate is stale or already terminal."""


_LANGUAGE_ORIGINS = {"manual", "curated_seed", "legacy_import"}
_EVIDENCE_KINDS = {
    "artist_profile",
    "artist_repertoire",
    "editorial_source",
    "track_credit",
    "track_language",
}
_PERFORMER_ATTRIBUTIONS = {
    "artist_vocal_confirmed",
    "artist_instrumental_confirmed",
    "track_language_only",
    "not_applicable",
}
_PRE_REVIEW_RECOMMENDATIONS = {
    "recommend_approve",
    "manual_review",
    "insufficient_evidence",
    "recommend_reject",
}


@contextmanager
def immediate_transaction(conn: sqlite3.Connection):
    """Open an immediate transaction without taking ownership from a caller."""
    owns_transaction = not conn.in_transaction
    if owns_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        if owns_transaction:
            conn.rollback()
        raise
    else:
        if owns_transaction:
            conn.commit()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "keys"):
        return {key: value[key] for key in value.keys()}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"unsupported artist language value: {type(value)!r}")


def _source_with_evidence(
    conn: sqlite3.Connection,
    source_id: int | None,
) -> dict[str, Any] | None:
    if source_id is None:
        return None
    source_row = conn.execute(
        "SELECT * FROM artist_language_sources WHERE source_id=?",
        (source_id,),
    ).fetchone()
    if source_row is None:
        return None
    source = _as_dict(source_row)
    source["evidence"] = [
        _as_dict(row)
        for row in conn.execute(
            """SELECT * FROM artist_language_evidence
               WHERE source_id=? ORDER BY evidence_id""",
            (source_id,),
        ).fetchall()
    ]
    return source


def get_review(conn: sqlite3.Connection, review_id: int) -> dict[str, Any]:
    row = conn.execute(
        """SELECT review.*, artists.artist_name
           FROM artist_language_review_queue AS review
           JOIN artists ON artists.artist_id = review.artist_id
           WHERE review.review_id=?""",
        (review_id,),
    ).fetchone()
    if row is None:
        raise ArtistLanguageNotFoundError(f"review {review_id} not found")
    review = _as_dict(row)
    review["source"] = _source_with_evidence(conn, review["suggested_source_id"])
    return review


def list_reviews(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status is not None:
        where = "WHERE status=?"
        params.append(status)
    params.append(max(1, min(int(limit), 200)))
    review_ids = conn.execute(
        f"""SELECT review_id FROM artist_language_review_queue
            {where}
            ORDER BY CASE WHEN status='open' THEN 0 ELSE 1 END,
                     play_hours_snapshot DESC, review_id DESC
            LIMIT ?""",
        params,
    ).fetchall()
    return [get_review(conn, int(row[0])) for row in review_ids]


def pre_review_language(
    conn: sqlite3.Connection,
    *,
    review_id: int,
    recommendation: str,
    confidence: float,
    note: str,
    reviewed_by: str = "codex_first_pass",
) -> dict[str, Any]:
    if recommendation not in _PRE_REVIEW_RECOMMENDATIONS:
        raise ArtistLanguageValidationError(
            f"unsupported pre-review recommendation: {recommendation}"
        )
    normalized_note = note.strip()
    normalized_actor = reviewed_by.strip()
    normalized_confidence = float(confidence)
    if not normalized_note or not normalized_actor:
        raise ArtistLanguageValidationError("pre-review note and reviewer must not be empty")
    if not 0.0 <= normalized_confidence <= 1.0:
        raise ArtistLanguageValidationError("pre-review confidence must be between 0 and 1")
    with immediate_transaction(conn):
        _load_open_review(conn, review_id)
        conn.execute(
            """UPDATE artist_language_review_queue
               SET pre_review_recommendation=?, pre_review_confidence=?,
                   pre_review_note=?, pre_reviewed_by=?, pre_reviewed_at=?,
                   updated_at=datetime('now')
               WHERE review_id=? AND status='open'""",
            (
                recommendation,
                normalized_confidence,
                normalized_note,
                normalized_actor,
                _utc_now(),
                int(review_id),
            ),
        )
    return get_review(conn, review_id)


def get_or_create_review(
    conn: sqlite3.Connection,
    *,
    artist_id: int,
    play_hours_snapshot: float,
    reason: str,
) -> dict[str, Any]:
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("review reason must not be empty")
    with immediate_transaction(conn):
        artist = conn.execute(
            "SELECT artist_id FROM artists WHERE artist_id=?",
            (artist_id,),
        ).fetchone()
        if artist is None:
            raise ArtistLanguageNotFoundError(f"artist {artist_id} not found")
        existing = conn.execute(
            """SELECT review_id FROM artist_language_review_queue
               WHERE artist_id=? AND status='open'""",
            (artist_id,),
        ).fetchone()
        if existing is None:
            cursor = conn.execute(
                """INSERT INTO artist_language_review_queue(
                       artist_id, play_hours_snapshot, reason
                   ) VALUES (?, ?, ?)""",
                (artist_id, max(0.0, float(play_hours_snapshot)), clean_reason),
            )
            review_id = int(cursor.lastrowid)
        else:
            review_id = int(existing["review_id"])
    return get_review(conn, review_id)


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ArtistLanguageValidationError(f"{field} must not be empty")
    return text


def normalize_language_source_payload(
    conn: sqlite3.Connection,
    payload: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize source data and enforce evidence structure and foreign keys."""
    try:
        source = _as_dict(payload)
    except TypeError as exc:
        raise ArtistLanguageValidationError("source payload must be an object") from exc

    raw_evidence = source.pop("evidence", [])
    if not isinstance(raw_evidence, list):
        raise ArtistLanguageValidationError("evidence must be a list")
    try:
        evidence = [_as_dict(item) for item in raw_evidence]
    except TypeError as exc:
        raise ArtistLanguageValidationError("each evidence item must be an object") from exc

    origin = _required_text(source.get("origin") or "manual", "origin")
    if origin not in _LANGUAGE_ORIGINS:
        raise ArtistLanguageValidationError(f"unsupported language origin: {origin}")
    source["origin"] = origin
    if source.get("source_key") is not None:
        source["source_key"] = _required_text(source["source_key"], "source_key")

    classification = str(source.get("classification") or "")
    if classification == "single_language":
        try:
            code, variant = normalize_language_claim(
                str(source.get("primary_language_code") or ""),
                source.get("language_variant"),
            )
        except ValueError as exc:
            raise ArtistLanguageValidationError(str(exc)) from exc
        source["primary_language_code"] = code
        source["language_variant"] = variant
    elif classification in {"multilingual", "instrumental"}:
        source["primary_language_code"] = None
        source["language_variant"] = None
    else:
        raise ArtistLanguageValidationError(
            f"unsupported language classification: {classification}"
        )

    local_track_ids: set[int] = set()
    for item in evidence:
        local_track_id = item.get("local_track_id")
        if local_track_id is not None:
            try:
                normalized_track_id = int(local_track_id)
            except (TypeError, ValueError) as exc:
                raise ArtistLanguageValidationError("local_track_id must be an integer") from exc
            item["local_track_id"] = normalized_track_id
            local_track_ids.add(normalized_track_id)
        code = item.get("claimed_language_code")
        variant = item.get("claimed_language_variant")
        if code is not None or variant is not None:
            try:
                normalized_code, normalized_variant = normalize_language_claim(
                    str(code or ""), variant
                )
            except ValueError as exc:
                raise ArtistLanguageValidationError(str(exc)) from exc
            item["claimed_language_code"] = normalized_code
            item["claimed_language_variant"] = normalized_variant
        evidence_kind = _required_text(item.get("evidence_kind"), "evidence_kind")
        if evidence_kind not in _EVIDENCE_KINDS:
            raise ArtistLanguageValidationError(f"unsupported evidence_kind: {evidence_kind}")
        item["evidence_kind"] = evidence_kind
        attribution = _required_text(item.get("performer_attribution"), "performer_attribution")
        if attribution not in _PERFORMER_ATTRIBUTIONS:
            raise ArtistLanguageValidationError(f"unsupported performer_attribution: {attribution}")
        item["performer_attribution"] = attribution
        evidence_url = _required_text(item.get("evidence_url"), "evidence_url")
        if not evidence_url.startswith("https://"):
            raise ArtistLanguageValidationError("evidence_url must use https://")
        item["evidence_url"] = evidence_url
        item["evidence_title"] = _required_text(item.get("evidence_title"), "evidence_title")
        item["evidence_summary"] = _required_text(item.get("evidence_summary"), "evidence_summary")
        if item.get("evidence_accessed_at") is None:
            item["evidence_accessed_at"] = _utc_now()
        else:
            item["evidence_accessed_at"] = _required_text(
                item["evidence_accessed_at"], "evidence_accessed_at"
            )

    for offset in range(0, len(local_track_ids), 500):
        chunk = sorted(local_track_ids)[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        existing = {
            int(row[0])
            for row in conn.execute(
                f"SELECT track_id FROM tracks WHERE track_id IN ({placeholders})",
                chunk,
            ).fetchall()
        }
        missing = set(chunk) - existing
        if missing:
            missing_text = ", ".join(str(track_id) for track_id in sorted(missing))
            raise ArtistLanguageValidationError(f"local_track_id {missing_text} does not exist")
    return source, evidence


def _load_open_review(conn: sqlite3.Connection, review_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM artist_language_review_queue WHERE review_id=?",
        (review_id,),
    ).fetchone()
    if row is None:
        raise ArtistLanguageNotFoundError(f"review {review_id} not found")
    review = _as_dict(row)
    if review["status"] != "open":
        raise ArtistLanguageConflictError(f"review {review_id} is terminal ({review['status']})")
    return review


def save_review_source(
    conn: sqlite3.Connection,
    *,
    review_id: int,
    payload: Any,
) -> dict[str, Any]:
    source, evidence = normalize_language_source_payload(conn, payload)
    with immediate_transaction(conn):
        review = _load_open_review(conn, review_id)
        source_id = review["suggested_source_id"]
        origin = str(source.get("origin") or "manual")
        source_key = source.get("source_key")

        if source_id is None:
            if not source_key:
                source_key = f"{origin}:{uuid4()}"
            cursor = conn.execute(
                """INSERT INTO artist_language_sources(
                       artist_id, classification, primary_language_code,
                       language_variant, raw_language, origin, source_key, status
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 'suggested')""",
                (
                    review["artist_id"],
                    source["classification"],
                    source.get("primary_language_code"),
                    source.get("language_variant"),
                    source.get("raw_language"),
                    origin,
                    source_key,
                ),
            )
            source_id = int(cursor.lastrowid)
            conn.execute(
                """UPDATE artist_language_review_queue
                   SET suggested_source_id=?, updated_at=datetime('now')
                   WHERE review_id=?""",
                (source_id, review_id),
            )
        else:
            existing = conn.execute(
                """SELECT artist_id, status, source_key
                   FROM artist_language_sources WHERE source_id=?""",
                (source_id,),
            ).fetchone()
            if (
                existing is None
                or int(existing["artist_id"]) != int(review["artist_id"])
                or existing["status"] != "suggested"
            ):
                raise ArtistLanguageConflictError(
                    f"review {review_id} has a stale suggested source"
                )
            source_key = source_key or existing["source_key"]
            conn.execute(
                """UPDATE artist_language_sources
                   SET classification=?, primary_language_code=?, language_variant=?,
                       raw_language=?, origin=?, source_key=?, updated_at=datetime('now')
                   WHERE source_id=?""",
                (
                    source["classification"],
                    source.get("primary_language_code"),
                    source.get("language_variant"),
                    source.get("raw_language"),
                    origin,
                    source_key,
                    source_id,
                ),
            )
            conn.execute(
                "DELETE FROM artist_language_evidence WHERE source_id=?",
                (source_id,),
            )

        for item in evidence:
            conn.execute(
                """INSERT INTO artist_language_evidence(
                       source_id, local_track_id, claimed_language_code,
                       claimed_language_variant, evidence_kind,
                       performer_attribution, evidence_url, evidence_title,
                       evidence_accessed_at, evidence_summary
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source_id,
                    item.get("local_track_id"),
                    item.get("claimed_language_code"),
                    item.get("claimed_language_variant"),
                    item["evidence_kind"],
                    item["performer_attribution"],
                    str(item["evidence_url"]).strip(),
                    str(item["evidence_title"]).strip(),
                    item["evidence_accessed_at"],
                    str(item["evidence_summary"]).strip(),
                ),
            )
    saved = _source_with_evidence(conn, int(source_id))
    if saved is None:
        raise ArtistLanguageConflictError(f"review {review_id} has a stale suggested source")
    return saved


def _candidate_for_review(
    conn: sqlite3.Connection,
    review: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_id = review["suggested_source_id"]
    if source_id is None:
        raise ArtistLanguageValidationError("approve requires a suggested source")
    source = _source_with_evidence(conn, int(source_id))
    if (
        source is None
        or int(source["artist_id"]) != int(review["artist_id"])
        or source["status"] != "suggested"
    ):
        raise ArtistLanguageConflictError(
            f"review {review['review_id']} has a stale suggested source"
        )
    return source, list(source.pop("evidence"))


def _reject_attached_candidate(
    conn: sqlite3.Connection,
    review: Mapping[str, Any],
) -> tuple[int | None, str | None]:
    source_id = review["suggested_source_id"]
    if source_id is None:
        return None, None
    source = conn.execute(
        "SELECT artist_id, status FROM artist_language_sources WHERE source_id=?",
        (source_id,),
    ).fetchone()
    if (
        source is None
        or int(source["artist_id"]) != int(review["artist_id"])
        or source["status"] != "suggested"
    ):
        raise ArtistLanguageConflictError(
            f"review {review['review_id']} has a stale suggested source"
        )
    conn.execute(
        """UPDATE artist_language_sources
           SET status='rejected', updated_at=datetime('now') WHERE source_id=?""",
        (source_id,),
    )
    return int(source_id), "rejected"


def decide_review(
    conn: sqlite3.Connection,
    *,
    review_id: int,
    action: str,
    resolution_note: str,
    reviewed_by: str,
) -> dict[str, Any]:
    if action not in {"approve", "reject", "insufficient_evidence"}:
        raise ValueError(f"unsupported review action: {action}")
    clean_note = resolution_note.strip()
    clean_reviewer = reviewed_by.strip()
    if not clean_note or not clean_reviewer:
        raise ValueError("reviewer and resolution note must not be empty")
    review_status = {
        "approve": "approved",
        "reject": "rejected",
        "insufficient_evidence": "insufficient_evidence",
    }[action]

    with immediate_transaction(conn):
        review = _load_open_review(conn, review_id)
        source_id: int | None
        source_status: str | None

        if action == "approve":
            candidate, evidence = _candidate_for_review(conn, review)
            normalized_source, normalized_evidence = validate_approved_language_source(
                conn,
                int(review["artist_id"]),
                candidate,
                evidence,
            )
            source_id = int(normalized_source["source_id"])
            approved = conn.execute(
                """SELECT source_id FROM artist_language_sources
                   WHERE artist_id=? AND status='approved' AND source_id != ?""",
                (review["artist_id"], source_id),
            ).fetchone()
            replaces_source_id = int(approved["source_id"]) if approved else None
            conn.execute(
                """UPDATE artist_language_sources SET replaces_source_id=?
                   WHERE source_id=?""",
                (replaces_source_id, source_id),
            )
            if replaces_source_id is not None:
                conn.execute(
                    """UPDATE artist_language_sources
                       SET status='superseded', updated_at=datetime('now')
                       WHERE source_id=? AND status='approved'""",
                    (replaces_source_id,),
                )
            conn.execute(
                """UPDATE artist_language_sources
                   SET classification=?, primary_language_code=?, language_variant=?,
                       status='approved', updated_at=datetime('now')
                   WHERE source_id=? AND status='suggested'""",
                (
                    normalized_source["classification"],
                    normalized_source.get("primary_language_code"),
                    normalized_source.get("language_variant"),
                    source_id,
                ),
            )
            for item in normalized_evidence:
                conn.execute(
                    """UPDATE artist_language_evidence
                       SET claimed_language_code=?, claimed_language_variant=?
                       WHERE evidence_id=?""",
                    (
                        item.get("claimed_language_code"),
                        item.get("claimed_language_variant"),
                        item["evidence_id"],
                    ),
                )
            source_status = "approved"
        else:
            source_id, source_status = _reject_attached_candidate(conn, review)
            if action == "reject" and source_id is None:
                raise ArtistLanguageValidationError("reject requires a suggested source")

        conn.execute(
            """UPDATE artist_language_review_queue
               SET status=?, resolution_note=?, reviewed_by=?, reviewed_at=?,
                   updated_at=datetime('now')
               WHERE review_id=? AND status='open'""",
            (review_status, clean_note, clean_reviewer, _utc_now(), review_id),
        )

    return {
        "review_id": review_id,
        "review_status": review_status,
        "source_id": source_id,
        "source_status": source_status,
    }
