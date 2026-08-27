from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.account import router as account_router
from backend.dependencies import get_conn
from backend.domains.account_archive.cohorts import (
    _return_windows,
    _vitality_metrics,
    build_collection_cohorts,
)
from backend.domains.account_archive.context import build_archive_filter_context
from backend.domains.account_archive.journey import (
    _collection_milestones,
    build_collection_journey,
)
from backend.domains.account_archive.returns import (
    _build_return_metrics,
    build_archive_returns,
)
from backend.models.account_archive import (
    ArchiveCohortsResponse,
    ArchiveJourneyResponse,
    ArchiveReturnsResponse,
)

pytestmark = pytest.mark.unit


def _relationship_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO settings VALUES ('min_ms', '30000'), ('merge_enabled', 'True');
        CREATE TABLE saved_tracks (
            track_uri TEXT PRIMARY KEY,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            added_date TEXT,
            spotify_track_id TEXT,
            added_date_source TEXT
        );
        CREATE TABLE saved_albums (album_uri TEXT PRIMARY KEY);
        CREATE TABLE saved_artists (artist_uri TEXT PRIMARY KEY);
        CREATE TABLE saved_shows (show_uri TEXT PRIMARY KEY);
        CREATE TABLE playlists (playlist_id INTEGER PRIMARY KEY);
        CREATE TABLE playlist_tracks (playlist_id INTEGER, track_uri TEXT);
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT,
            artist_id INTEGER,
            release_date TEXT,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_id INTEGER,
            album_id INTEGER,
            spotify_track_uri TEXT,
            spotify_track_id TEXT
        );
        CREATE TABLE spotify_track_meta (
            spotify_track_id TEXT PRIMARY KEY,
            duration_ms INTEGER,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta (
            spotify_album_id TEXT PRIMARY KEY,
            release_date TEXT
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            ts TEXT,
            ms_played INTEGER,
            track_id INTEGER,
            source_album_id INTEGER,
            ts_date TEXT
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            primary_track_id INTEGER,
            scope TEXT,
            parent_group_id INTEGER
        );
        CREATE TABLE track_group_members (group_id INTEGER, track_id INTEGER);

        INSERT INTO artists VALUES (1, 'Archive Artist');
        INSERT INTO albums VALUES
            (1, 'Archive Album', 1, '2001-01-01', '/tmp/cover.jpg', NULL);
        INSERT INTO tracks VALUES
            (1, 'A', 1, 1, 'spotify:track:a', 'a'),
            (2, 'B', 1, 1, 'spotify:track:b', 'b'),
            (3, 'D', 1, 1, 'spotify:track:d', 'd'),
            (4, 'E', 1, 1, 'spotify:track:e', 'e'),
            (5, 'Unsaved', 1, 1, 'spotify:track:unsaved', 'unsaved');
        INSERT INTO spotify_track_meta VALUES
            ('a', 180000, 'album'), ('b', 180000, 'album'),
            ('c', 180000, 'album'), ('d', 180000, 'album'),
            ('e', 180000, 'album'), ('unsaved', 180000, 'album');
        INSERT INTO spotify_album_meta VALUES ('album', '2001-01-01');
        INSERT INTO saved_tracks VALUES
            ('spotify:track:a', 'A', 'Archive Artist', 'Archive Album',
             '2024-01-10T00:05:00Z', 'a', 'oauth'),
            ('spotify:track:b', 'B', 'Archive Artist', 'Archive Album',
             '2024-03-28T00:05:00Z', 'b', 'oauth'),
            ('spotify:track:c', 'C', 'Archive Artist', 'Archive Album',
             '2024-01-15T00:00:00Z', 'c', 'legacy'),
            ('spotify:track:d', 'D', 'Archive Artist', 'Archive Album',
             'not-a-date', 'd', 'legacy'),
            ('spotify:track:e', 'E', 'Archive Artist', 'Archive Album',
             '2024-01-20T00:05:00Z', 'e', 'manual');

        -- `ts` is playback end time. The A/E/B save-triggering plays start
        -- before their save timestamps and must not count as later returns.
        INSERT INTO plays VALUES
            (1, '2023-12-01T00:03:00Z', 180000, 2, 1, '2023-12-01'),
            (2, '2024-01-10T00:06:00Z', 120000, 1, 1, '2024-01-10'),
            (3, '2024-01-11T00:03:00Z', 180000, 5, 1, '2024-01-11'),
            (4, '2024-01-12T00:01:00Z', 60000, 1, 1, '2024-01-12'),
            (5, '2024-01-20T00:06:00Z', 120000, 4, 1, '2024-01-20'),
            (6, '2024-03-28T00:06:00Z', 120000, 2, 1, '2024-03-28'),
            (7, '2024-04-01T00:00:00Z', 10000, 2, 1, '2024-04-01');
        """
    )
    conn.commit()
    return conn


def _context(conn: sqlite3.Connection):
    return build_archive_filter_context(
        conn,
        {
            "min_ms": None,
            "merge_enabled": None,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": None,
            "merge_level": 2,
        },
    )


def test_archive_context_resolves_settings_anchor_and_group_revision() -> None:
    conn = _relationship_conn()
    first = _context(conn)
    conn.execute("INSERT INTO track_groups VALUES (1, 'A Group', 1, 'recording', NULL)")
    conn.execute("INSERT INTO track_group_members VALUES (1, 1)")
    conn.commit()
    second = _context(conn)
    conn.close()

    assert first.min_ms == 30000
    assert first.merge_enabled is True
    assert first.first_play_at == "2023-12-01T00:03:00Z"
    assert first.latest_play_at == "2024-04-01T00:00:00Z"
    assert first.latest_play_date == "2024-04-01"
    assert first.track_group_revision != second.track_group_revision
    assert first.filter_fingerprint != second.filter_fingerprint


def test_collection_journey_uses_exact_dates_durations_and_strict_contract() -> None:
    conn = _relationship_conn()
    result = build_collection_journey(conn, _context(conn))
    conn.close()
    response = ArchiveJourneyResponse.model_validate(result)

    assert response.status == "partial"
    assert response.coverage.saved_tracks == 5
    assert response.coverage.saved_tracks_with_date == 4
    assert response.coverage.invalid_added_dates == 1
    assert response.coverage.saved_tracks_with_known_duration == 5
    assert response.duration.known_duration_ms == 900000
    assert response.duration.release_year_start == 2001
    assert sum(point.saved_tracks for point in response.annual_growth) == 4
    assert response.milestones == []


def test_collection_journey_uses_progressive_hundred_song_milestones() -> None:
    rows = [
        {
            "track_uri": f"spotify:track:{index:04d}",
            "track_name": f"Track {index}",
            "artist_name": "Archive Artist",
            "album_name": "Archive Album",
            "added_date": (
                pd.Timestamp("2024-01-01T00:00:00Z") + pd.Timedelta(hours=index - 1)
            ).isoformat(),
            "local_track_id": index,
            "local_album_id": 1,
            "image_path": "/tmp/cover.jpg",
        }
        for index in range(1, 801)
    ]

    milestones = _collection_milestones(rows)

    assert [item["ordinal"] for item in milestones] == [100, 200, 400, 800]
    assert [item["track_name"] for item in milestones] == [
        "Track 100",
        "Track 200",
        "Track 400",
        "Track 800",
    ]


def test_collection_cohorts_excludes_save_triggering_play_and_right_censors() -> None:
    conn = _relationship_conn()
    result = build_collection_cohorts(conn, _context(conn))
    conn.close()
    response = ArchiveCohortsResponse.model_validate(result)
    serialized = json.dumps(result)

    assert response.status == "partial"
    assert response.coverage.saved_tracks == 5
    assert response.coverage.matched_saved_tracks == 4
    assert response.coverage.unmatched_saved_tracks == 1
    assert response.coverage.dated_canonical_entities == 3
    assert response.coverage.invalid_added_dates == 1
    assert response.coverage.effective_play_events == 6
    assert "track_uri" not in serialized
    assert "query_text" not in serialized
    assert "profile" not in serialized
    assert response.encounter_to_save.eligible_entities == 3
    assert response.encounter_to_save.bins[0].entities == 2

    windows = {item.horizon_days: item for item in response.return_windows}
    assert windows[7].eligible_entities == 2
    assert windows[7].returned_entities == 1
    assert windows[7].display_status == "count_only"
    assert windows[7].return_rate_pct is None
    assert windows[30].eligible_entities == 2
    assert windows[30].returned_entities == 1
    assert windows[90].eligible_entities == 0

    vitality = {item.key: item for item in response.vitality_metrics}
    assert vitality["within_7d"].eligible_entities == 2
    assert vitality["within_7d"].returned_entities == 1
    assert vitality["days_8_30"].eligible_entities == 2
    assert vitality["days_8_30"].returned_entities == 0
    assert vitality["after_180d"].eligible_entities == 0

    symmetric = response.symmetric_30_day_window
    assert symmetric.eligible_entities == 2
    assert symmetric.before_events == 2
    assert symmetric.after_events == 1
    assert symmetric.more_before == 1
    assert symmetric.equal == 1


def test_return_rate_requires_thirty_complete_entities() -> None:
    first = pd.Timestamp("2023-01-01T00:00:00Z")
    latest = pd.Timestamp("2025-01-01T00:00:00Z")
    save = "2024-01-01T00:00:00Z"
    entities = [{"archive_track_id": index, "added_date": save} for index in range(30)]
    times = {index: [pd.Timestamp("2024-01-02T00:00:00Z")] for index in range(30)}

    count_only = _return_windows(entities[:29], times, first, latest)[0]
    stable = _return_windows(entities, times, first, latest)[0]

    assert count_only["display_status"] == "count_only"
    assert count_only["return_rate_pct"] is None
    assert stable["display_status"] == "stable_rate"
    assert stable["return_rate_pct"] == 100.0


def test_vitality_metrics_separate_early_return_from_long_term_survival() -> None:
    first = pd.Timestamp("2022-01-01T00:00:00Z")
    latest = pd.Timestamp("2025-01-01T00:00:00Z")
    entities = [
        {"archive_track_id": index, "added_date": "2023-01-01T00:00:00Z"} for index in range(30)
    ]
    times = {
        index: [
            pd.Timestamp("2023-01-03T00:00:00Z"),
            pd.Timestamp("2023-01-20T00:00:00Z"),
            pd.Timestamp("2024-02-01T00:00:00Z"),
        ]
        for index in range(30)
    }

    metrics = {item["key"]: item for item in _vitality_metrics(entities, times, first, latest)}

    assert metrics["within_7d"]["return_rate_pct"] == 100.0
    assert metrics["days_8_30"]["return_rate_pct"] == 100.0
    assert metrics["after_180d"]["return_rate_pct"] == 100.0
    assert metrics["after_365d"]["return_rate_pct"] == 100.0


def test_journey_and_cohorts_routes_return_strict_json() -> None:
    conn = _relationship_conn()
    app = FastAPI()
    app.include_router(account_router, prefix="/api")
    app.dependency_overrides[get_conn] = lambda: conn
    client = TestClient(app)

    journey = client.get("/api/account/collection-journey?merge_level=2")
    cohorts = client.get("/api/account/collection-cohorts?merge_level=2")
    conn.close()

    assert journey.status_code == 200
    assert journey.json()["schema_version"] == "account_archive_journey_v2"
    assert journey.json()["filter_context"]["merge_level"] == 2
    assert cohorts.status_code == 200
    assert cohorts.json()["schema_version"] == "account_archive_cohorts_v2"
    assert cohorts.json()["vitality_metrics"][0]["key"] == "within_7d"


def test_return_metrics_detect_gap_and_current_sleeping_without_overlap() -> None:
    def entity(track_id: int, saved_at: str) -> dict[str, object]:
        return {
            "archive_track_id": track_id,
            "added_date": saved_at,
            "track_name": f"Track {track_id}",
            "artist_name": "Archive Artist",
            "album_name": "Archive Album",
            "deep_link": f"/music/tracks/{track_id}",
        }

    entities = [
        entity(1, "2024-01-01T00:00:00Z"),
        entity(2, "2024-01-01T00:00:00Z"),
        entity(3, "2024-01-01T00:00:00Z"),
        entity(4, "2024-06-01T00:00:00Z"),
        entity(5, "2024-03-28T00:05:00Z"),
    ]
    times = {
        1: [pd.Timestamp("2024-01-02T00:00:00Z"), pd.Timestamp("2024-04-02T00:00:00Z")],
        2: [
            pd.Timestamp("2023-12-01T00:00:00Z"),
            pd.Timestamp("2024-03-01T00:00:00Z"),
            pd.Timestamp("2024-07-01T00:00:00Z"),
        ],
        3: [pd.Timestamp("2024-01-02T00:00:00Z"), pd.Timestamp("2024-02-01T00:00:00Z")],
        4: [pd.Timestamp("2024-06-02T00:00:00Z")],
        # The long gap ends before Save and must not become a return episode.
        5: [pd.Timestamp("2023-12-01T00:00:00Z"), pd.Timestamp("2024-03-28T00:04:00Z")],
    }

    result = _build_return_metrics(entities, times, pd.Timestamp("2024-07-20T00:00:00Z"))

    assert result["return_eligible_entities"] == 3
    assert result["summary"] == {
        "gap_threshold_days": 90,
        "return_episodes": 3,
        "returned_entities": 2,
        "multiple_return_entities": 1,
        "recent_30_day_return_entities": 1,
        "recent_90_day_return_entities": 1,
        "current_sleeping_entities": 3,
    }
    assert result["latest_returns"][0]["track_name"] == "Track 2"
    assert all(item["dormant_days"] >= 90 for item in result["longest_returns"])
    assert {item["track_name"] for item in result["sleeping_recommendations"]} == {
        "Track 1",
        "Track 3",
        "Track 5",
    }


def test_archive_returns_route_uses_event_start_and_strict_private_contract() -> None:
    conn = _relationship_conn()
    conn.execute(
        "INSERT INTO plays VALUES (?, ?, ?, ?, ?, ?)",
        (8, "2024-04-11T00:03:00Z", 180000, 1, 1, "2024-04-11"),
    )
    conn.commit()

    result = build_archive_returns(conn, _context(conn))
    response = ArchiveReturnsResponse.model_validate(result)
    cohorts = ArchiveCohortsResponse.model_validate(build_collection_cohorts(conn, _context(conn)))
    serialized = json.dumps(result)

    app = FastAPI()
    app.include_router(account_router, prefix="/api")
    app.dependency_overrides[get_conn] = lambda: conn
    route_response = TestClient(app).get("/api/account/returns?merge_level=2")
    conn.close()

    assert response.summary.returned_entities == 1
    assert response.summary.return_episodes == 1
    assert response.latest_returns[0].dormant_days == 90
    assert response.latest_returns[0].returned_at == "2024-04-11T00:00:00Z"
    assert (
        response.summary.current_sleeping_entities
        == cohorts.relationship_matrix.counts.sleeping_saved
    )
    assert "track_uri" not in serialized
    assert "query_text" not in serialized
    assert "profile" not in serialized
    assert route_response.status_code == 200
    assert route_response.json()["schema_version"] == "account_archive_returns_v1"
    assert route_response.json()["filter_context"]["merge_level"] == 2
