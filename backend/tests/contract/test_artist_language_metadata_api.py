from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.contract


def valid_single_payload() -> dict[str, Any]:
    return {
        "classification": "single_language",
        "primary_language_code": "English",
        "evidence": [
            {
                "claimed_language_code": "English",
                "evidence_kind": "artist_profile",
                "performer_attribution": "artist_vocal_confirmed",
                "evidence_url": "https://example.com/artist-profile",
                "evidence_title": "Official artist profile",
                "evidence_summary": "The profile documents the artist's vocal language.",
            }
        ],
    }


@pytest.fixture
def artist_language_db(tmp_path, monkeypatch) -> Iterator[str]:
    import backend.core.db as db_mod
    from backend.core.migrations import run_migrations

    db_path = str(tmp_path / "artist-language-api.db")
    monkeypatch.setattr(db_mod, "DB_PATH", db_path)
    db_mod.init_db()
    run_migrations()

    conn = db_mod.get_db(readonly=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executemany(
        "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
        [(9001, "Reviewed Artist"), (9002, "Unknown Artist")],
    )
    conn.executemany(
        """INSERT INTO tracks(
               track_id, track_name, artist_id, spotify_track_id, spotify_track_uri
           ) VALUES (?, ?, ?, ?, ?)""",
        [
            (9101, "Reviewed Song", 9001, "spotify-reviewed", "spotify:track:reviewed"),
            (9102, "Unknown Song", 9002, "spotify-unknown", "spotify:track:unknown"),
        ],
    )
    conn.executemany(
        "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
        [(9101, 9001), (9102, 9002)],
    )
    conn.executemany(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, duration_ms)
           VALUES (?, ?, ?)""",
        [
            ("spotify-reviewed", "Reviewed Song", 200_000),
            ("spotify-unknown", "Unknown Song", 200_000),
        ],
    )
    conn.executemany(
        """INSERT INTO plays(
               ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
               platform, ms_played, track_id, content_type, spotify_track_id_at_play
           ) VALUES (?, 2026, 7, 27, 2, ?, '2026-07-01',
                     'test', ?, ?, 'audio', ?)""",
        [
            ("2026-07-01T10:00:00Z", 10, 3_600_000, 9101, "spotify-reviewed"),
            ("2026-07-01T12:00:00Z", 12, 1_800_000, 9102, "spotify-unknown"),
        ],
    )
    conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code,
               origin, source_key, status
           ) VALUES (9001, 'single_language', 'en', 'manual',
                     'fixture-reviewed', 'approved')"""
    )
    conn.execute(
        """INSERT INTO artist_language_evidence(
               source_id, claimed_language_code, evidence_kind,
               performer_attribution, evidence_url, evidence_title,
               evidence_accessed_at, evidence_summary
           ) VALUES (last_insert_rowid(), 'en', 'artist_profile',
                     'artist_vocal_confirmed', 'https://example.com/reviewed',
                     'Reviewed source', '2026-07-11T00:00:00Z',
                     'Reviewed fixture evidence')"""
    )
    conn.commit()
    conn.close()
    db_mod._load_plays_cached.cache_clear()

    yield db_path

    db_mod._load_plays_cached.cache_clear()


@pytest.fixture
def client(artist_language_db: str) -> Iterator[TestClient]:  # noqa: ARG001
    from backend.main import app

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()


def test_language_coverage_uses_reviewed_facts_and_conserves_hours(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/metadata/artist-languages/coverage",
        params={
            "min_ms": 30_000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 45,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible_hours"] == pytest.approx(1.5)
    assert payload["classified_hours"] == pytest.approx(1.0)
    assert payload["unknown_hours"] == pytest.approx(0.5)
    assert sum(row["hours"] for row in payload["buckets"]) == pytest.approx(
        payload["eligible_hours"]
    )
    assert payload["source_hours"] == {"manual": pytest.approx(1.0)}
    assert payload["top_missing"][0]["artist_id"] == 9002


def test_review_api_supports_full_manual_flow(client: TestClient) -> None:
    started = client.post(
        "/api/metadata/artist-languages/reviews",
        params={"min_ms": 30_000, "dynamic_threshold": True},
        json={"artist_id": 9002, "reason": "manual_research"},
    )
    assert started.status_code == 200
    assert started.json()["play_hours_snapshot"] == pytest.approx(0.5)
    review_id = started.json()["review_id"]

    saved = client.put(
        f"/api/metadata/artist-languages/reviews/{review_id}/source",
        json=valid_single_payload(),
    )
    assert saved.status_code == 200
    assert saved.json()["primary_language_code"] == "en"
    assert saved.json()["origin"] == "manual"
    assert saved.json()["source_key"].startswith("manual:")
    assert saved.json()["evidence"][0]["evidence_accessed_at"]

    approved = client.patch(
        f"/api/metadata/artist-languages/reviews/{review_id}",
        json={
            "action": "approve",
            "resolution_note": "Official profile reviewed.",
            "reviewed_by": "untrusted_client",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["source_status"] == "approved"

    listed = client.get(
        "/api/metadata/artist-languages/reviews",
        params={"status": "approved", "limit": 1},
    )
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["reviewed_by"] == "local_user"


def test_language_pre_review_is_non_terminal_and_does_not_change_coverage(
    client: TestClient,
) -> None:
    before = client.get("/api/metadata/artist-languages/coverage").json()
    started = client.post(
        "/api/metadata/artist-languages/reviews",
        json={"artist_id": 9002, "reason": "codex_first_pass"},
    ).json()
    review_id = started["review_id"]

    response = client.patch(
        f"/api/metadata/artist-languages/reviews/{review_id}/pre-review",
        json={
            "recommendation": "insufficient_evidence",
            "confidence": 0.7,
            "note": "No artist-level vocal-language source has been attached yet.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "open"
    assert payload["suggested_source_id"] is None
    assert payload["pre_review_recommendation"] == "insufficient_evidence"
    assert payload["pre_reviewed_by"] == "codex_first_pass"
    assert client.get("/api/metadata/artist-languages/coverage").json() == before


def test_review_api_maps_not_found_conflict_and_validation_errors(
    client: TestClient,
) -> None:
    missing_artist = client.post(
        "/api/metadata/artist-languages/reviews",
        json={"artist_id": 999_999, "reason": "manual_research"},
    )
    assert missing_artist.status_code == 404

    started = client.post(
        "/api/metadata/artist-languages/reviews",
        json={"artist_id": 9002, "reason": "manual_research"},
    )
    review_id = started.json()["review_id"]
    invalid = client.put(
        f"/api/metadata/artist-languages/reviews/{review_id}/source",
        json={
            "classification": "single_language",
            "primary_language_code": "not-a-language",
            "evidence": [],
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == {
        "code": "artist_language_validation_error",
        "message": "unsupported language code: not-a-language",
    }

    insufficient = client.patch(
        f"/api/metadata/artist-languages/reviews/{review_id}",
        json={
            "action": "insufficient_evidence",
            "resolution_note": "No reliable public source was found.",
        },
    )
    assert insufficient.status_code == 200
    assert insufficient.json()["source_id"] is None
    assert insufficient.json()["source_status"] is None

    conflict = client.patch(
        f"/api/metadata/artist-languages/reviews/{review_id}",
        json={
            "action": "insufficient_evidence",
            "resolution_note": "Repeated terminal decision.",
        },
    )
    assert conflict.status_code == 409

    missing_review = client.put(
        "/api/metadata/artist-languages/reviews/999999/source",
        json=valid_single_payload(),
    )
    assert missing_review.status_code == 404


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_url", "http://example.com/not-https", "evidence_url must use https://"),
        ("evidence_title", "   ", "evidence_title must not be empty"),
        ("evidence_summary", "", "evidence_summary must not be empty"),
    ],
)
def test_review_api_returns_structured_validation_error_for_invalid_evidence(
    client: TestClient,
    field: str,
    value: str,
    message: str,
) -> None:
    started = client.post(
        "/api/metadata/artist-languages/reviews",
        json={"artist_id": 9002, "reason": "manual_research"},
    )
    payload = valid_single_payload()
    payload["evidence"][0][field] = value

    response = client.put(
        f"/api/metadata/artist-languages/reviews/{started.json()['review_id']}/source",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "artist_language_validation_error",
        "message": message,
    }


def test_review_api_returns_structured_validation_error_for_unknown_local_track(
    client: TestClient,
) -> None:
    started = client.post(
        "/api/metadata/artist-languages/reviews",
        json={"artist_id": 9002, "reason": "manual_research"},
    )
    payload = valid_single_payload()
    payload["evidence"][0]["local_track_id"] = 999_999

    response = client.put(
        f"/api/metadata/artist-languages/reviews/{started.json()['review_id']}/source",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "artist_language_validation_error",
        "message": "local_track_id 999999 does not exist",
    }


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("origin", "curated_seed"),
        ("source_key", "client-controlled-key"),
        ("evidence_accessed_at", "2020-01-01T00:00:00Z"),
    ],
)
def test_review_source_api_rejects_client_provenance_fields(
    client: TestClient,
    path: str,
    value: str,
) -> None:
    started = client.post(
        "/api/metadata/artist-languages/reviews",
        json={"artist_id": 9002, "reason": "manual_research"},
    )
    payload = valid_single_payload()
    if path == "evidence_accessed_at":
        payload["evidence"][0][path] = value
    else:
        payload[path] = value

    response = client.put(
        f"/api/metadata/artist-languages/reviews/{started.json()['review_id']}/source",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_review_listing_validates_status_and_limit(client: TestClient) -> None:
    invalid_status = client.get(
        "/api/metadata/artist-languages/reviews", params={"status": "pending"}
    )
    invalid_limit = client.get("/api/metadata/artist-languages/reviews", params={"limit": 201})

    assert invalid_status.status_code == 422
    assert invalid_limit.status_code == 422


def test_review_listing_reports_total_independently_from_limit(
    client: TestClient,
    artist_language_db: str,
) -> None:
    conn = sqlite3.connect(artist_language_db)
    conn.executemany(
        "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
        [(9010, "Queued Artist 1"), (9011, "Queued Artist 2"), (9012, "Queued Artist 3")],
    )
    conn.executemany(
        """INSERT INTO artist_language_review_queue(
               artist_id, play_hours_snapshot, reason, status
           ) VALUES (?, ?, 'manual_research', 'open')""",
        [(9010, 3.0), (9011, 2.0), (9012, 1.0)],
    )
    conn.commit()
    conn.close()

    response = client.get(
        "/api/metadata/artist-languages/reviews",
        params={"status": "open", "limit": 1},
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 3


def test_music_search_artist_result_exposes_artist_id(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Unknown Artist", "kind": "artist", "include_chart": False},
    )

    assert response.status_code == 200
    assert response.json()["artists"][0]["artist_id"] == 9002
