from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_024


def _conn() -> sqlite3.Connection:
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
        INSERT INTO artists VALUES (1, 'Artist');
        INSERT INTO artists VALUES (2, 'Other Artist');
        INSERT INTO tracks VALUES (10, 'Track', 1);
        """
    )
    return conn


def _insert_source(
    conn: sqlite3.Connection,
    *,
    artist_id: int = 1,
    source_key: str = "source",
    status: str = "suggested",
) -> int:
    cursor = conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code,
               origin, source_key, status
           ) VALUES (?, 'single_language', 'en', 'manual', ?, ?)""",
        (artist_id, source_key, status),
    )
    return int(cursor.lastrowid)


def test_migrate_024_creates_language_tables_and_six_indexes_idempotently() -> None:
    conn = _conn()
    migrate_024(conn)
    migrate_024(conn)

    tables = {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "artist_language_sources",
        "artist_language_evidence",
        "artist_language_review_queue",
    } <= tables

    indexes = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert {
        "uq_artist_language_one_approved",
        "idx_artist_language_sources_artist",
        "idx_artist_language_evidence_source",
        "uq_artist_language_one_open_review",
        "uq_artist_language_source_review",
        "idx_artist_language_reviews_status",
    } <= indexes


def test_migrate_024_enforces_source_checks_and_unique_approved_fact() -> None:
    conn = _conn()
    migrate_024(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_sources(
                   artist_id, classification, origin, source_key
               ) VALUES (1, 'single_language', 'manual', 'missing-code')"""
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_sources(
                   artist_id, classification, primary_language_code,
                   language_variant, origin, source_key
               ) VALUES (1, 'multilingual', NULL, 'mandarin', 'manual', 'invalid-variant')"""
        )

    _insert_source(conn, source_key="approved-1", status="approved")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_source(conn, source_key="approved-2", status="approved")


def test_migrate_024_enforces_evidence_checks_and_foreign_keys() -> None:
    conn = _conn()
    migrate_024(conn)
    source_id = _insert_source(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_evidence(
                   source_id, evidence_kind, performer_attribution,
                   evidence_url, evidence_title, evidence_accessed_at, evidence_summary
               ) VALUES (?, 'artist_profile', 'artist_vocal_confirmed',
                         'http://example.com', 'Title', '2026-07-11', 'Summary')""",
            (source_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_evidence(
                   source_id, evidence_kind, performer_attribution,
                   evidence_url, evidence_title, evidence_accessed_at, evidence_summary
               ) VALUES (?, 'unsupported', 'artist_vocal_confirmed',
                         'https://example.com', 'Title', '2026-07-11', 'Summary')""",
            (source_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_evidence(
                   source_id, local_track_id, evidence_kind, performer_attribution,
                   evidence_url, evidence_title, evidence_accessed_at, evidence_summary
               ) VALUES (?, 999, 'track_language', 'track_language_only',
                         'https://example.com', 'Title', '2026-07-11', 'Summary')""",
            (source_id,),
        )


def test_migrate_024_enforces_review_terminal_state_and_unique_open_review() -> None:
    conn = _conn()
    migrate_024(conn)
    source_id = _insert_source(conn)

    conn.execute(
        """INSERT INTO artist_language_review_queue(
               artist_id, suggested_source_id, reason
           ) VALUES (1, ?, 'Needs review')""",
        (source_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_review_queue(artist_id, reason)
               VALUES (1, 'Duplicate open review')"""
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_review_queue(
                   artist_id, suggested_source_id, reason, status
               ) VALUES (2, ?, 'Incomplete decision', 'approved')""",
            (source_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_review_queue(
                   artist_id, reason, status,
                   reviewed_by, reviewed_at, resolution_note
               ) VALUES (2, 'No candidate', 'rejected',
                         'reviewer', '2026-07-11', 'Rejected')"""
        )


def test_migrate_024_allows_insufficient_evidence_without_source() -> None:
    conn = _conn()
    migrate_024(conn)

    conn.execute(
        """INSERT INTO artist_language_review_queue(
               artist_id, reason, status,
               reviewed_by, reviewed_at, resolution_note
           ) VALUES (1, 'No reliable source', 'insufficient_evidence',
                     'reviewer', '2026-07-11', 'Leave unresolved')"""
    )
