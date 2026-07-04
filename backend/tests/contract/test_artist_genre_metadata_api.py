from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator

import pytest

from backend.core import db as db_mod
from backend.core import migrations
from backend.domains.metadata.artist_genres import resolve_artist_genres, upsert_genre_source

pytestmark = pytest.mark.contract


@pytest.fixture()
def artist_genre_metadata_db(tmp_path, monkeypatch) -> Generator[sqlite3.Connection, None, None]:
    db_path = tmp_path / "artist-genre-metadata-api.db"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    db_mod.init_db()
    migrations.run_migrations()

    conn = db_mod.get_db(readonly=False)
    conn.executemany(
        "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
        [(1, "Spotify Artist"), (2, "Review Artist"), (3, "Missing Artist")],
    )
    conn.executemany(
        "INSERT INTO tracks(track_id, track_name, artist_id) VALUES (?, ?, ?)",
        [(10, "Spotify Song", 1), (20, "Review Song", 2), (30, "Missing Song", 3)],
    )
    conn.executemany(
        """INSERT INTO plays(
               play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
               ts_date, platform, ms_played, track_id, content_type
           ) VALUES (?, ?, 2024, 1, 1, 1, 12, ?, 'web', ?, ?, 'audio')""",
        [
            (100, "2024-01-01T12:00:00Z", "2024-01-01", 3_600_000, 10),
            (200, "2024-01-02T12:00:00Z", "2024-01-02", 7_200_000, 20),
            (300, "2024-01-03T12:00:00Z", "2024-01-03", 3_600_000, 30),
        ],
    )
    conn.executemany(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        [
            ("sp-spotify", "Spotify Artist", json.dumps(["spotify pop"])),
            ("sp-review", "Review Artist", json.dumps([])),
            ("sp-missing", "Missing Artist", json.dumps([])),
        ],
    )
    upsert_genre_source(
        conn,
        artist_name="Review Artist",
        spotify_artist_id="sp-review",
        source="llm",
        source_key="llm:Review Artist",
        raw_genres=["review pop"],
        normalized_genres=["review pop"],
        primary_genre="review pop",
        language="english",
        region="全球",
        confidence=0.8,
        evidence_url=None,
        evidence_summary="Review candidate.",
        status="suggested",
    )
    source_id = conn.execute(
        "SELECT source_id FROM artist_genre_sources WHERE artist_name = 'Review Artist'"
    ).fetchone()[0]
    conn.execute(
        """INSERT INTO artist_genre_review_queue(
               artist_name, play_hours, reason, suggested_source_id, status
           ) VALUES (?, ?, ?, ?, 'open')""",
        ("Review Artist", 2.0, "llm_artist_genre_suggestion", source_id),
    )
    conn.commit()
    yield conn
    conn.close()


def test_artist_genre_metadata_api_returns_coverage(client, artist_genre_metadata_db):
    response = client.get("/api/metadata/artist-genres/coverage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artist_count"] == 3
    assert payload["known_pct"] == pytest.approx(25.0)
    assert payload["unknown_pct"] == pytest.approx(75.0)
    assert payload["top_missing"][0]["artist_name"] == "Review Artist"


def test_artist_genre_metadata_api_returns_taxonomy_audit(client, artist_genre_metadata_db):
    response = client.get("/api/metadata/artist-genres/taxonomy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_genre_count"] == 1
    assert payload["canonical_genre_count"] == 1
    assert payload["noncanonical_passthrough_count"] == 0
    assert payload["axis_summary"] == [
        {
            "axis": "style",
            "label": "风格",
            "hours": 1.0,
            "share_pct": 25.0,
            "canonical_count": 1,
            "interpretation": "声音/风格偏好，可作为主要流派分析。",
        }
    ]
    assert payload["top_canonical_genres"] == [
        {
            "name": "pop",
            "axis": "style",
            "label": "Pop",
            "interpretation": "声音/风格偏好，可作为主要流派分析。",
            "confidence_tier": "high",
            "hours": 1.0,
            "share_pct": 25.0,
            "source_mix": [{"source": "spotify", "hours": 1.0, "share_pct": 100.0}],
            "top_artists": [
                {
                    "artist_name": "Spotify Artist",
                    "hours": 1.0,
                    "share_pct": 100.0,
                    "source": "spotify",
                    "raw_genres": ["spotify pop"],
                }
            ],
            "dominance_warning": "Spotify Artist contributes 100.0% of this label",
            "risk_flags": [
                {
                    "code": "single_artist_dominance",
                    "severity": "medium",
                    "message": "Spotify Artist contributes 100.0% of this label",
                }
            ],
        }
    ]
    assert payload["top_raw_genres"][0]["raw_genre"] == "spotify pop"
    assert payload["top_raw_genres"][0]["canonical_genres"] == ["pop"]
    assert payload["mapping_examples"][0]["raw_genre"] == "spotify pop"
    assert payload["mapping_examples"][0]["canonical_genres"] == ["pop"]
    assert "style/scene/context/role" in payload["caveat"]
    assert "单一高播放艺人" in payload["caveat"]


def test_artist_genre_metadata_api_lists_open_reviews(client, artist_genre_metadata_db):
    response = client.get("/api/metadata/artist-genres/reviews?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["artist_name"] == "Review Artist"
    assert payload["items"][0]["genres"] == ["review pop"]
    assert payload["items"][0]["source_status"] == "suggested"
    assert payload["items"][0]["review_id"] == 1


def test_artist_genre_metadata_api_approves_review(client, artist_genre_metadata_db):
    response = client.post("/api/metadata/artist-genres/reviews/1/approve")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"] == "approved"
    resolved = resolve_artist_genres(artist_genre_metadata_db, "Review Artist")
    assert resolved.source == "llm"
    assert resolved.genres == ["review pop"]


def test_artist_genre_metadata_api_rejects_review(client, artist_genre_metadata_db):
    response = client.post("/api/metadata/artist-genres/reviews/1/reject")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"] == "rejected"
    resolved = resolve_artist_genres(artist_genre_metadata_db, "Review Artist")
    assert resolved.source == "unknown"


def test_artist_genre_metadata_api_returns_404_for_stale_review(
    client,
    artist_genre_metadata_db,
):
    client.post("/api/metadata/artist-genres/reviews/1/approve")

    response = client.post("/api/metadata/artist-genres/reviews/1/reject")

    assert response.status_code == 404
    assert response.headers["x-request-id"]
