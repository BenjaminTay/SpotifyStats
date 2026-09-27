from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_032, migrate_034, migrate_035, migrate_060
from backend.domains.music_search.index import rebuild_music_search_index
from backend.services.music_search_candidate_service import search_music_candidates

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER NOT NULL,
            ms_played INTEGER,
            source_album_id INTEGER
        );
        INSERT INTO artists VALUES (1, 'Taylor Swift');
        INSERT INTO albums VALUES (10, 'folklore', 1);
        INSERT INTO tracks VALUES (100, 'cardigan', 1, 10);
        INSERT INTO plays VALUES (1, 100, 200000, 10);
        """
    )
    return conn


def test_current_candidates_use_bounded_fallback_without_exact_snapshot(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate path must not load filtered plays or Billboard")

    monkeypatch.setattr(
        "backend.services.music_search_service.load_period_plays",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_summaries_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_power_scores_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_weekly_data",
        forbidden,
    )

    result = search_music_candidates(_conn(), query="card", eligibility="current")

    assert result.snapshot_status == "unavailable"
    assert result.candidate_status == "degraded"
    assert result.candidate_freshness == "fallback"
    assert result.total == 1
    assert result.tracks[0].entity_key == "track:100"

    mismatched_builder = search_music_candidates(
        _conn(),
        query="card",
        eligibility="current",
        snapshot_status="ready",
        snapshot_key=None,
    )
    assert mismatched_builder.snapshot_status == "unavailable"
    assert mismatched_builder.total == 1


def _indexed_conn() -> sqlite3.Connection:
    conn = _conn()
    migrate_032(conn)
    migrate_034(conn)
    migrate_035(conn)
    migrate_060(conn)
    rebuild_music_search_index(conn)
    return conn


@pytest.mark.parametrize("maintenance_status", ("pending", "building", "failed"))
def test_current_candidates_keep_serving_active_generation_while_maintenance_is_not_ready(
    monkeypatch,
    maintenance_status,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate path must not load filtered plays or Billboard")

    monkeypatch.setattr("backend.services.music_search_service.load_period_plays", forbidden)
    monkeypatch.setattr("backend.services.music_search_service.compute_summaries_staged", forbidden)
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_power_scores_staged", forbidden
    )
    monkeypatch.setattr("backend.services.music_search_service.compute_weekly_data", forbidden)
    conn = _indexed_conn()
    conn.execute(
        """UPDATE music_search_candidate_maintenance_state
              SET maintenance_status=?, target_source_revision='target-new',
                  target_candidate_index_version='candidate-new'
            WHERE state_id=1""",
        (maintenance_status,),
    )

    result = search_music_candidates(
        conn,
        query="card",
        kinds=("track",),
        eligibility="current",
        snapshot_status="warming",
    )

    assert result.snapshot_status == "warming"
    assert result.statistics_status == "warming"
    assert result.statistics_freshness == "unavailable"
    assert result.candidate_status in {"ready", "degraded"}
    assert result.candidate_freshness == "last_known_good"
    assert result.total == 1
    assert result.tracks[0].entity_key == "track:100"


def test_current_candidates_use_current_active_generation_without_snapshot() -> None:
    conn = _indexed_conn()

    result = search_music_candidates(
        conn,
        query="card",
        kinds=("track",),
        eligibility="current",
        snapshot_status="unavailable",
    )

    assert result.candidate_freshness == "current"
    assert result.snapshot_status == "unavailable"
    assert result.total == 1


def test_indexed_candidates_publish_no_cover_without_metadata() -> None:
    conn = _indexed_conn()

    result = search_music_candidates(
        conn,
        query="card",
        kinds=("track",),
        eligibility="current",
    )

    assert result.tracks[0].cover_url is None


def test_indexed_candidates_keep_valid_metadata_backed_cover() -> None:
    conn = _conn()
    conn.execute("ALTER TABLE artists ADD COLUMN image_path TEXT")
    conn.execute("ALTER TABLE artists ADD COLUMN image_url TEXT")
    conn.execute("ALTER TABLE albums ADD COLUMN image_path TEXT")
    conn.execute("ALTER TABLE albums ADD COLUMN image_url TEXT")
    conn.execute("UPDATE artists SET image_url='https://example.test/taylor.jpg'")
    conn.execute("UPDATE albums SET image_path='covers/albums/10.jpg'")
    migrate_032(conn)
    migrate_034(conn)
    migrate_035(conn)
    migrate_060(conn)
    rebuild_music_search_index(conn)

    track = search_music_candidates(conn, query="card", kinds=("track",), eligibility="current")
    artist = search_music_candidates(conn, query="taylor", kinds=("artist",), eligibility="current")

    assert track.tracks[0].cover_url == "/covers/albums/10.jpg"
    assert artist.artists[0].cover_url == "/covers/artists/1.jpg"


def test_indexed_candidates_sanitize_stale_persisted_cover_without_rebuild() -> None:
    conn = _indexed_conn()
    generation_id = conn.execute(
        "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
    ).fetchone()[0]
    conn.execute(
        """UPDATE music_search_documents SET cover_url='/covers/albums/10.jpg'
           WHERE generation_id=? AND entity_key='track:100'""",
        (generation_id,),
    )

    result = search_music_candidates(conn, query="card", kinds=("track",), eligibility="current")

    assert result.tracks[0].cover_url is None


def test_private_any_local_returns_clickable_candidate_without_context_metrics(
    monkeypatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate path must not load filtered plays or Billboard")

    monkeypatch.setattr(
        "backend.services.music_search_service.load_period_plays",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_summaries_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_power_scores_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_weekly_data",
        forbidden,
    )

    result = search_music_candidates(
        _conn(),
        query="  CARD  ",
        kinds=("track",),
        eligibility="any_local",
    )

    assert result.snapshot_status == "unavailable"
    assert result.normalized_query == "card"
    assert result.total == 1
    item = result.tracks[0]
    assert item.entity_key == "track:100"
    assert item.href == "/music/tracks/100"
    assert item.match_field == "label"
    assert item.match_quality == "prefix"
    payload = item.model_dump()
    assert "play_events" not in payload
    assert "total_ms" not in payload
    assert "chart" not in payload


def test_latin_single_character_is_gated_before_resolver(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("short query must not reach resolver")

    monkeypatch.setattr(
        "backend.services.music_search_candidate_service.resolve_entities",
        forbidden,
    )

    result = search_music_candidates(_conn(), query="a", eligibility="any_local")

    assert result.snapshot_status == "unavailable"
    assert result.total == 0
