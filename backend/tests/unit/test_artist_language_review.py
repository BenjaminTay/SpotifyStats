from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

from backend.core.migrations import migrate_024
from backend.domains.metadata.artist_language_review import (
    ArtistLanguageConflictError,
    ArtistLanguageNotFoundError,
    decide_review,
    get_or_create_review,
    get_review,
    list_reviews,
    save_review_source,
)
from backend.domains.metadata.artist_languages import ArtistLanguageValidationError

pytestmark = pytest.mark.unit


@pytest.fixture
def language_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id)
        );
        CREATE TABLE track_artists (
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            role TEXT NOT NULL DEFAULT 'primary',
            UNIQUE(track_id, artist_id)
        );
        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'Review Artist'),
            (2, 'Other Artist');
        INSERT INTO tracks(track_id, track_name, artist_id)
        VALUES (10, 'Review Track', 1);
        INSERT INTO track_artists(track_id, artist_id, role)
        VALUES (10, 1, 'primary');
        """
    )
    migrate_024(conn)
    conn.commit()
    yield conn
    conn.close()


def valid_single_source(
    code: str = "en",
    variant: str | None = None,
    *,
    source_key: str | None = None,
) -> dict[str, Any]:
    return {
        "classification": "single_language",
        "primary_language_code": code,
        "language_variant": variant,
        "raw_language": code,
        "origin": "manual",
        "source_key": source_key,
        "evidence": [
            {
                "local_track_id": None,
                "claimed_language_code": code,
                "claimed_language_variant": variant,
                "evidence_kind": "artist_profile",
                "performer_attribution": "artist_vocal_confirmed",
                "evidence_url": "https://example.com/artist-profile",
                "evidence_title": "Artist profile",
                "evidence_accessed_at": None,
                "evidence_summary": "The profile identifies the artist's vocal language.",
            }
        ],
    }


def seed_approved_source(
    conn: sqlite3.Connection,
    *,
    artist_id: int,
    code: str,
) -> int:
    cursor = conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code,
               origin, source_key, status
           ) VALUES (?, 'single_language', ?, 'manual', ?, 'approved')""",
        (artist_id, code, f"approved-{code}"),
    )
    conn.execute(
        """INSERT INTO artist_language_evidence(
               source_id, claimed_language_code, evidence_kind,
               performer_attribution, evidence_url, evidence_title,
               evidence_accessed_at, evidence_summary
           ) VALUES (?, ?, 'artist_profile', 'artist_vocal_confirmed',
                     'https://example.com/existing', 'Existing source',
                     '2026-07-11T00:00:00Z', 'Existing evidence')""",
        (cursor.lastrowid, code),
    )
    conn.commit()
    return int(cursor.lastrowid)


def test_get_or_create_open_review_is_idempotent(
    language_conn: sqlite3.Connection,
) -> None:
    first = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )
    second = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=99.0,
        reason="different_reason",
    )

    assert first["review_id"] == second["review_id"]
    assert second["play_hours_snapshot"] == 10.0
    assert second["reason"] == "manual_research"
    assert list_reviews(language_conn, status="open", limit=50) == [second]


def test_missing_artist_and_review_raise_domain_not_found(
    language_conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ArtistLanguageNotFoundError, match="artist 999"):
        get_or_create_review(
            language_conn,
            artist_id=999,
            play_hours_snapshot=1.0,
            reason="manual_research",
        )
    with pytest.raises(ArtistLanguageNotFoundError, match="review 999"):
        get_review(language_conn, 999)


def test_save_review_source_creates_and_replaces_suggestion_and_evidence(
    language_conn: sqlite3.Connection,
) -> None:
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )
    first = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=valid_single_source("English"),
    )
    updated_payload = valid_single_source("Chinese", "Mandarin")
    updated_payload["evidence"].append(
        {
            "local_track_id": 10,
            "claimed_language_code": "zh",
            "claimed_language_variant": "mandarin",
            "evidence_kind": "track_language",
            "performer_attribution": "track_language_only",
            "evidence_url": "https://example.com/track",
            "evidence_title": "Track language",
            "evidence_accessed_at": "2026-07-10T00:00:00Z",
            "evidence_summary": "The credited track uses Mandarin.",
        }
    )

    second = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=updated_payload,
    )

    assert second["source_id"] == first["source_id"]
    assert second["source_key"].startswith("manual:")
    assert second["primary_language_code"] == "zh"
    assert second["language_variant"] == "mandarin"
    assert len(second["evidence"]) == 2
    assert all(item["evidence_accessed_at"] for item in second["evidence"])
    assert (
        language_conn.execute(
            "SELECT COUNT(*) FROM artist_language_evidence WHERE source_id=?",
            (second["source_id"],),
        ).fetchone()[0]
        == 2
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_url", "http://example.com/not-https", "evidence_url must use https://"),
        ("evidence_title", "  ", "evidence_title must not be empty"),
        ("evidence_summary", "", "evidence_summary must not be empty"),
    ],
)
def test_save_review_source_rejects_evidence_before_database_check(
    language_conn: sqlite3.Connection,
    field: str,
    value: str,
    message: str,
) -> None:
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=1.0,
        reason="manual_research",
    )
    payload = valid_single_source()
    payload["evidence"][0][field] = value

    with pytest.raises(ArtistLanguageValidationError, match=message):
        save_review_source(
            language_conn,
            review_id=review["review_id"],
            payload=payload,
        )

    assert language_conn.execute("SELECT COUNT(*) FROM artist_language_sources").fetchone()[0] == 0


def test_save_review_source_rejects_unknown_local_track_before_database_write(
    language_conn: sqlite3.Connection,
) -> None:
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=1.0,
        reason="manual_research",
    )
    payload = valid_single_source()
    payload["evidence"][0]["local_track_id"] = 999_999

    with pytest.raises(
        ArtistLanguageValidationError,
        match="local_track_id 999999 does not exist",
    ):
        save_review_source(
            language_conn,
            review_id=review["review_id"],
            payload=payload,
        )

    assert language_conn.execute("SELECT COUNT(*) FROM artist_language_sources").fetchone()[0] == 0
    assert language_conn.execute("SELECT COUNT(*) FROM artist_language_evidence").fetchone()[0] == 0


def test_approve_without_evidence_fails_and_leaves_review_open(
    language_conn: sqlite3.Connection,
) -> None:
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )
    payload = valid_single_source("en")
    payload["evidence"] = []
    saved = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=payload,
    )

    with pytest.raises(ArtistLanguageValidationError, match="single_language"):
        decide_review(
            language_conn,
            review_id=review["review_id"],
            action="approve",
            resolution_note="No valid evidence.",
            reviewed_by="local_user",
        )

    assert get_review(language_conn, review["review_id"])["status"] == "open"
    assert (
        language_conn.execute(
            "SELECT status FROM artist_language_sources WHERE source_id=?",
            (saved["source_id"],),
        ).fetchone()[0]
        == "suggested"
    )


def test_reject_closes_review_and_rejects_candidate(
    language_conn: sqlite3.Connection,
) -> None:
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )
    saved = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=valid_single_source("en"),
    )

    result = decide_review(
        language_conn,
        review_id=review["review_id"],
        action="reject",
        resolution_note="The source is not reliable.",
        reviewed_by="local_user",
    )

    assert result == {
        "review_id": review["review_id"],
        "review_status": "rejected",
        "source_id": saved["source_id"],
        "source_status": "rejected",
    }
    assert get_review(language_conn, review["review_id"])["reviewed_by"] == "local_user"


def test_insufficient_evidence_closes_review_without_source(
    language_conn: sqlite3.Connection,
) -> None:
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )

    result = decide_review(
        language_conn,
        review_id=review["review_id"],
        action="insufficient_evidence",
        resolution_note="No reliable source was found.",
        reviewed_by="local_user",
    )

    assert result["review_status"] == "insufficient_evidence"
    assert result["source_id"] is None
    assert result["source_status"] is None


def test_approve_replaces_existing_source_atomically(
    language_conn: sqlite3.Connection,
) -> None:
    existing_id = seed_approved_source(language_conn, artist_id=1, code="en")
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )
    saved = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=valid_single_source("zh", "mandarin"),
    )

    result = decide_review(
        language_conn,
        review_id=review["review_id"],
        action="approve",
        resolution_note="Verified artist profile.",
        reviewed_by="local_user",
    )

    assert result["source_status"] == "approved"
    assert (
        language_conn.execute(
            "SELECT status FROM artist_language_sources WHERE source_id=?", (existing_id,)
        ).fetchone()[0]
        == "superseded"
    )
    replacement = language_conn.execute(
        """SELECT status, replaces_source_id
           FROM artist_language_sources WHERE source_id=?""",
        (saved["source_id"],),
    ).fetchone()
    assert tuple(replacement) == ("approved", existing_id)


def test_terminal_and_stale_review_mutations_raise_conflict(
    language_conn: sqlite3.Connection,
) -> None:
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )
    saved = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=valid_single_source("en"),
    )
    decide_review(
        language_conn,
        review_id=review["review_id"],
        action="reject",
        resolution_note="Rejected.",
        reviewed_by="local_user",
    )

    with pytest.raises(ArtistLanguageConflictError, match="terminal"):
        save_review_source(
            language_conn,
            review_id=review["review_id"],
            payload=valid_single_source("zh", "mandarin"),
        )
    with pytest.raises(ArtistLanguageConflictError, match="terminal"):
        decide_review(
            language_conn,
            review_id=review["review_id"],
            action="reject",
            resolution_note="Again.",
            reviewed_by="local_user",
        )

    second_review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="retry",
    )
    second_saved = save_review_source(
        language_conn,
        review_id=second_review["review_id"],
        payload=valid_single_source("en", source_key="stale-source"),
    )
    language_conn.execute(
        "UPDATE artist_language_sources SET status='rejected' WHERE source_id=?",
        (second_saved["source_id"],),
    )
    language_conn.commit()

    with pytest.raises(ArtistLanguageConflictError, match="stale"):
        decide_review(
            language_conn,
            review_id=second_review["review_id"],
            action="approve",
            resolution_note="Stale candidate.",
            reviewed_by="local_user",
        )
    assert saved["source_id"] != second_saved["source_id"]


def test_helpers_do_not_commit_or_rollback_an_outer_transaction(
    language_conn: sqlite3.Connection,
) -> None:
    language_conn.execute("BEGIN IMMEDIATE")
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="batch_import",
    )
    save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=valid_single_source("en"),
    )

    assert language_conn.in_transaction is True
    language_conn.rollback()
    assert (
        language_conn.execute("SELECT COUNT(*) FROM artist_language_review_queue").fetchone()[0]
        == 0
    )
    assert language_conn.execute("SELECT COUNT(*) FROM artist_language_sources").fetchone()[0] == 0


def test_failure_after_supersede_rolls_back_entire_decision(
    language_conn: sqlite3.Connection,
) -> None:
    existing_id = seed_approved_source(language_conn, artist_id=1, code="en")
    review = get_or_create_review(
        language_conn,
        artist_id=1,
        play_hours_snapshot=10.0,
        reason="manual_research",
    )
    saved = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=valid_single_source("zh", "mandarin"),
    )
    language_conn.execute(
        f"""CREATE TRIGGER fail_candidate_approval
            BEFORE UPDATE OF status ON artist_language_sources
            WHEN NEW.source_id = {saved["source_id"]} AND NEW.status = 'approved'
            BEGIN
                SELECT RAISE(ABORT, 'simulated approval failure');
            END"""
    )
    language_conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="simulated approval failure"):
        decide_review(
            language_conn,
            review_id=review["review_id"],
            action="approve",
            resolution_note="Should roll back.",
            reviewed_by="local_user",
        )

    rows = language_conn.execute(
        """SELECT source_id, status, replaces_source_id
           FROM artist_language_sources WHERE artist_id=1 ORDER BY source_id"""
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (existing_id, "approved", None),
        (saved["source_id"], "suggested", None),
    ]
    assert get_review(language_conn, review["review_id"])["status"] == "open"
