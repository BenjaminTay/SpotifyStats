from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def _backfill_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            ms_played INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'audio'
        );
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
            play_hours REAL NOT NULL DEFAULT 0.0,
            reason TEXT NOT NULL,
            suggested_source_id INTEGER,
            status TEXT NOT NULL DEFAULT 'open',
            reviewer_note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO artists VALUES
            (1, 'Known Artist'),
            (2, 'Missing Artist'),
            (3, 'Tiny Missing Artist');
        INSERT INTO tracks VALUES
            (10, 'Known Song', 1),
            (20, 'Missing Song', 2),
            (30, 'Tiny Song', 3);
        INSERT INTO plays(play_id, ms_played, track_id, content_type) VALUES
            (100, 3600000, 10, 'audio'),
            (200, 7200000, 20, 'audio'),
            (300, 60000, 30, 'audio');
        INSERT INTO spotify_artist_meta VALUES
            ('known', 'Known Artist', '["rock"]'),
            ('missing', 'Missing Artist', '[]'),
            ('tiny', 'Tiny Missing Artist', '[]');
        """
    )
    return conn


def test_select_missing_genre_artists_skips_existing_spotify_genres_and_min_hours():
    from backend.services.artist_genre_backfill_service import select_missing_genre_artists

    conn = _backfill_conn()
    try:
        selected = select_missing_genre_artists(conn, limit=10, min_hours=0.5)
    finally:
        conn.close()

    assert selected == [{"artist_name": "Missing Artist", "hours": 2.0}]


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        json.dumps({"genres": [], "confidence": 0.9, "evidence_summary": "ok"}),
        json.dumps({"genres": ["pop"], "confidence": 0.59, "evidence_summary": "ok"}),
        json.dumps({"genres": ["pop"], "confidence": 0.9, "evidence_summary": ""}),
    ],
)
def test_parse_llm_genre_suggestion_rejects_low_quality_outputs(raw: str):
    from backend.services.artist_genre_backfill_service import parse_llm_genre_suggestion

    assert parse_llm_genre_suggestion(raw) is None


def test_parse_llm_genre_suggestion_normalizes_valid_json():
    from backend.services.artist_genre_backfill_service import parse_llm_genre_suggestion

    parsed = parse_llm_genre_suggestion(
        json.dumps(
            {
                "genres": ["Pop", " Singer-Songwriter ", "pop"],
                "primary_genre": "Pop",
                "language": "english",
                "region": "美国",
                "confidence": 0.82,
                "evidence_summary": "Two sources support these genres.",
            }
        )
    )

    assert parsed == {
        "genres": ["pop", "singer-songwriter"],
        "primary_genre": "pop",
        "language": "english",
        "region": "美国",
        "confidence": 0.82,
        "evidence_summary": "Two sources support these genres.",
    }


def test_external_consensus_rejects_low_confidence_matching_sources():
    from backend.services.artist_genre_backfill_service import _external_consensus_suggestion

    evidence = {
        "lastfm": [
            {
                "source": "lastfm",
                "normalized_genres": ["pop"],
                "confidence": 0.55,
                "evidence_summary": "Low confidence Last.fm tag.",
            }
        ],
        "musicbrainz": [
            {
                "source": "musicbrainz",
                "normalized_genres": ["pop"],
                "confidence": 0.60,
                "evidence_summary": "Low score MusicBrainz tag.",
            }
        ],
        "wikidata": [],
    }

    assert _external_consensus_suggestion("Low Quality Artist", evidence) is None


def test_enqueue_review_is_idempotent_for_open_source():
    from backend.services.artist_genre_backfill_service import _enqueue_review, _save_genre_source

    conn = _backfill_conn()
    try:
        source_id = _save_genre_source(
            conn,
            artist_name="Missing Artist",
            source="llm",
            source_key="llm:Missing Artist",
            suggestion={
                "genres": ["pop"],
                "primary_genre": "pop",
                "language": "english",
                "region": "美国",
                "confidence": 0.82,
                "evidence_summary": "LLM suggestion from corroborated evidence.",
            },
            evidence_url=None,
            status="suggested",
        )
        for _ in range(2):
            _enqueue_review(
                conn,
                artist_name="Missing Artist",
                play_hours=2.0,
                suggested_source_id=source_id,
                reason="llm_artist_genre_suggestion",
            )
        queue_count = conn.execute(
            "SELECT COUNT(*) FROM artist_genre_review_queue WHERE suggested_source_id = ?",
            (source_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    assert queue_count == 1


def test_provider_rate_limit_waits_between_same_provider_calls(monkeypatch):
    from backend.services import artist_genre_backfill_service

    provider = SimpleNamespace(config=SimpleNamespace(name="musicbrainz", rate_limit_rps=1.0))
    monotonic_values = iter([100.0, 100.2, 101.2])
    sleeps = []
    monkeypatch.setattr(
        artist_genre_backfill_service.time,
        "monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(artist_genre_backfill_service.time, "sleep", sleeps.append)
    artist_genre_backfill_service._PROVIDER_LAST_CALL_AT.clear()

    artist_genre_backfill_service._respect_provider_rate_limit(provider)
    artist_genre_backfill_service._respect_provider_rate_limit(provider)

    assert sleeps == [pytest.approx(0.8)]
