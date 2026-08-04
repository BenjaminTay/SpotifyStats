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
def artist_genre_metadata_db(tmp_path) -> Generator[sqlite3.Connection, None, None]:
    db_path = tmp_path / "artist-genre-metadata-api.db"
    original = db_mod.DB_PATH
    db_mod.DB_PATH = str(db_path)
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
    db_mod.DB_PATH = original


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
    assert payload["display_taxonomy_version"] == "consumer_v1"
    assert payload["raw_genre_count"] == 1
    assert payload["canonical_genre_count"] == 1
    assert payload["noncanonical_passthrough_count"] == 0
    axes = {row["axis"]: row for row in payload["axis_summary"]}
    assert set(axes) == {"style", "scene", "context", "role"}
    assert axes["style"] == {
        "axis": "style",
        "label": "风格",
        "hours": 1.0,
        "share_pct": 25.0,
        "coverage_pct": 25.0,
        "unknown_hours": 3.0,
        "unknown_pct": 75.0,
        "canonical_count": 1,
        "interpretation": "声音/风格偏好，可作为主要流派分析。",
    }
    pop = payload["top_canonical_genres"][0]
    assert pop["name"] == "pop"
    assert pop["axis"] == "style"
    assert pop["confidence_tier"] == "medium"
    assert pop["share_pct"] == 100.0
    assert pop["overall_share_pct"] == 25.0
    assert pop["source_mix"] == [
        {
            "source": "spotify",
            "hours": 1.0,
            "share_pct": 100.0,
            "confidence": 1.0,
            "evidence_pct": 100.0,
        }
    ]
    assert pop["top_artists"][0]["artist_name"] == "Spotify Artist"
    assert {flag["code"] for flag in pop["risk_flags"]} == {"single_artist_dominance"}
    assert payload["top_raw_genres"][0]["raw_genre"] == "spotify pop"
    assert payload["top_raw_genres"][0]["canonical_genres"] == ["pop"]
    assert payload["mapping_examples"][0]["raw_genre"] == "spotify pop"
    assert payload["mapping_examples"][0]["canonical_genres"] == ["pop"]
    assert "style/scene/context/role" in payload["caveat"]
    assert "单一高播放艺人" in payload["caveat"]


def test_artist_genre_axis_gaps_returns_play_weighted_style_queue(client, artist_genre_metadata_db):
    artist_genre_metadata_db.execute(
        "INSERT INTO artists(artist_id, artist_name) VALUES (4, 'Scene Artist')"
    )
    artist_genre_metadata_db.execute(
        "INSERT INTO tracks(track_id, track_name, artist_id) VALUES (40, 'Scene Song', 4)"
    )
    artist_genre_metadata_db.execute(
        """INSERT INTO plays(
               play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
               ts_date, platform, ms_played, track_id, content_type
           ) VALUES (400, '2024-01-04T12:00:00Z', 2024, 1, 1, 1, 12,
                     '2024-01-04', 'web', 10800000, 40, 'audio')"""
    )
    artist_genre_metadata_db.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp-scene", "Scene Artist", json.dumps(["mandopop"])),
    )
    artist_genre_metadata_db.commit()
    db_mod._load_plays_cached.cache_clear()

    response = client.get("/api/metadata/artist-genres/axis-gaps?axis=style&limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["axis"] == "style"
    assert payload["items"][0]["artist_name"] == "Scene Artist"
    assert payload["items"][0]["hours"] == pytest.approx(3.0)
    assert payload["items"][0]["raw_genres"] == ["mandopop"]
    assert payload["items"][0]["resolved_axes"] == {"scene": ["c-pop"]}


def test_artist_genre_axis_gaps_rejects_unsupported_axis(client):
    response = client.get("/api/metadata/artist-genres/axis-gaps?axis=unsupported")

    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported genre axis: unsupported"


def test_artist_genre_metadata_api_lists_open_reviews(client, artist_genre_metadata_db):
    response = client.get("/api/metadata/artist-genres/reviews?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["artist_name"] == "Review Artist"
    assert payload["items"][0]["genres"] == ["review pop"]
    assert payload["items"][0]["source_status"] == "suggested"
    assert payload["items"][0]["review_id"] == 1


def test_artist_genre_pre_review_is_non_terminal_and_does_not_change_statistics(
    client, artist_genre_metadata_db
):
    before = client.get("/api/metadata/artist-genres/taxonomy").json()

    response = client.patch(
        "/api/metadata/artist-genres/reviews/1/pre-review",
        json={
            "recommendation": "manual_review",
            "confidence": 0.82,
            "note": "Evidence is plausible, but this artist has material distribution impact.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_status"] == "open"
    assert payload["source_status"] == "suggested"
    assert payload["pre_review_recommendation"] == "manual_review"
    assert payload["pre_reviewed_by"] == "codex_first_pass"
    assert client.get("/api/metadata/artist-genres/taxonomy").json() == before


def test_artist_genre_metadata_api_approves_review(client, artist_genre_metadata_db):
    evidence = client.patch(
        "/api/metadata/artist-genres/reviews/1/evidence",
        json={
            "evidence_url": "https://example.com/review-artist",
            "evidence_summary": "Editor profile supports the proposed genre tags.",
        },
    )
    assert evidence.status_code == 200
    response = client.post(
        "/api/metadata/artist-genres/reviews/1/approve",
        json={"resolution_note": "Evidence checked in contract test."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"] == "approved"
    resolved = resolve_artist_genres(artist_genre_metadata_db, "Review Artist")
    assert resolved.source == "llm"
    assert resolved.genres == ["review pop"]


def test_artist_genre_metadata_api_rejects_review(client, artist_genre_metadata_db):
    response = client.post(
        "/api/metadata/artist-genres/reviews/1/reject",
        json={"resolution_note": "Suggestion is not supported."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"] == "rejected"
    resolved = resolve_artist_genres(artist_genre_metadata_db, "Review Artist")
    assert resolved.source == "unknown"


def test_artist_genre_metadata_api_returns_404_for_stale_review(
    client,
    artist_genre_metadata_db,
):
    client.patch(
        "/api/metadata/artist-genres/reviews/1/evidence",
        json={
            "evidence_url": "https://example.com/review-artist",
            "evidence_summary": "Editor profile supports the proposed genre tags.",
        },
    )
    client.post(
        "/api/metadata/artist-genres/reviews/1/approve",
        json={"resolution_note": "Approved once."},
    )

    response = client.post(
        "/api/metadata/artist-genres/reviews/1/reject",
        json={"resolution_note": "Stale second decision."},
    )

    assert response.status_code == 422
    assert response.headers["x-request-id"]
