from __future__ import annotations

import json
import sqlite3

import pytest

from backend.domains.metadata.artist_genres import resolve_artist_genres, upsert_genre_source

pytestmark = pytest.mark.unit


def _review_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            genres TEXT
        );
        CREATE TABLE artist_genre_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            spotify_artist_id TEXT,
            source TEXT NOT NULL,
            source_key TEXT NOT NULL,
            raw_genres_json TEXT,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            evidence_url TEXT,
            evidence_summary TEXT,
            status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_name, source, source_key)
        );
        CREATE TABLE artist_genre_overrides (
            artist_name TEXT PRIMARY KEY,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 1.0,
            note TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE artist_genre_review_queue (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            play_hours REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            suggested_source_id INTEGER REFERENCES artist_genre_sources(source_id),
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO spotify_artist_meta VALUES ('sp-missing', 'Review Artist', '[]');
        """
    )
    upsert_genre_source(
        conn,
        artist_name="Review Artist",
        spotify_artist_id="sp-missing",
        source="llm",
        source_key="llm:Review Artist",
        raw_genres=["pop", "singer-songwriter"],
        normalized_genres=["pop", "singer-songwriter"],
        primary_genre="pop",
        language="english",
        region="美国",
        confidence=0.82,
        evidence_url=None,
        evidence_summary="LLM suggestion from external evidence.",
        status="suggested",
    )
    source_id = conn.execute("SELECT source_id FROM artist_genre_sources").fetchone()[0]
    conn.execute(
        """INSERT INTO artist_genre_review_queue(
               artist_name, play_hours, reason, suggested_source_id, status
           ) VALUES (?, ?, ?, ?, 'open')""",
        ("Review Artist", 12.5, "llm_artist_genre_suggestion", source_id),
    )
    conn.commit()
    return conn


def test_list_open_reviews_includes_source_metadata():
    from scripts.review_artist_genre_suggestions import list_reviews

    conn = _review_conn()

    rows = list_reviews(conn, status="open", limit=10)

    assert rows == [
        {
            "review_id": 1,
            "artist_name": "Review Artist",
            "play_hours": 12.5,
            "reason": "llm_artist_genre_suggestion",
            "source_id": 1,
            "source": "llm",
            "source_key": "llm:Review Artist",
            "source_status": "suggested",
            "genres": ["pop", "singer-songwriter"],
            "primary_genre": "pop",
            "language": "english",
            "region": "美国",
            "confidence": 0.82,
            "evidence_summary": "LLM suggestion from external evidence.",
        }
    ]


def test_approve_review_marks_source_approved_and_enables_resolver():
    from scripts.review_artist_genre_suggestions import review_suggestion

    conn = _review_conn()

    report = review_suggestion(conn, review_id=1, decision="approve")
    source_status = conn.execute(
        "SELECT status FROM artist_genre_sources WHERE source_id = 1"
    ).fetchone()[0]
    review_status = conn.execute(
        "SELECT status FROM artist_genre_review_queue WHERE review_id = 1"
    ).fetchone()[0]
    resolved = resolve_artist_genres(conn, "Review Artist")

    assert report == {
        "review_id": 1,
        "artist_name": "Review Artist",
        "decision": "approve",
        "source_id": 1,
        "source_status": "approved",
        "review_status": "approved",
    }
    assert source_status == "approved"
    assert review_status == "approved"
    assert resolved.source == "llm"
    assert resolved.genres == ["pop", "singer-songwriter"]


def test_reject_review_marks_source_rejected_and_keeps_resolver_unknown():
    from scripts.review_artist_genre_suggestions import review_suggestion

    conn = _review_conn()

    report = review_suggestion(conn, review_id=1, decision="reject")
    resolved = resolve_artist_genres(conn, "Review Artist")

    assert report["source_status"] == "rejected"
    assert report["review_status"] == "rejected"
    assert resolved.source == "unknown"
    assert resolved.genres == []


def test_review_script_cli_writes_json_report(monkeypatch, tmp_path):
    from scripts import review_artist_genre_suggestions

    conn = _review_conn()
    monkeypatch.setattr(
        review_artist_genre_suggestions,
        "get_db",
        lambda readonly=False: conn,
    )
    output_path = tmp_path / "review.json"

    exit_code = review_artist_genre_suggestions.main(
        ["approve", "1", "--json-output", str(output_path)]
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["source_status"] == "approved"


def test_review_suggestion_rejects_non_open_review():
    from scripts.review_artist_genre_suggestions import review_suggestion

    conn = _review_conn()
    review_suggestion(conn, review_id=1, decision="approve")

    with pytest.raises(ValueError, match="open suggested review"):
        review_suggestion(conn, review_id=1, decision="reject")


def test_review_suggestion_rejects_stale_source_status_without_changing_rows():
    from scripts.review_artist_genre_suggestions import review_suggestion

    conn = _review_conn()
    conn.execute("UPDATE artist_genre_sources SET status = 'approved' WHERE source_id = 1")
    conn.commit()

    with pytest.raises(ValueError, match="open suggested review"):
        review_suggestion(conn, review_id=1, decision="reject")

    source_status = conn.execute(
        "SELECT status FROM artist_genre_sources WHERE source_id = 1"
    ).fetchone()[0]
    review_status = conn.execute(
        "SELECT status FROM artist_genre_review_queue WHERE review_id = 1"
    ).fetchone()[0]
    assert source_status == "approved"
    assert review_status == "open"
