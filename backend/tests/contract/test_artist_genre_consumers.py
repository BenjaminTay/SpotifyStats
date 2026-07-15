from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator

import pandas as pd
import pytest

from backend.core import db as db_mod
from backend.core import migrations
from backend.domains.billboard import details as billboard_details
from backend.domains.billboard import versus as billboard_versus
from backend.domains.metadata.artist_genres import upsert_genre_source
from backend.services import wrapped_service
from backend.services.account_service import get_collection_insights
from backend.services.wrapped_service import get_wrapped_full

pytestmark = pytest.mark.contract


ARTISTS = [
    (1, "Spotify Genre Artist", "spotify:artist:spotify"),
    (2, "Curated Fallback Artist", "spotify:artist:fallback"),
    (3, "Unknown Genre Artist", "spotify:artist:unknown"),
]


@pytest.fixture()
def artist_genre_consumer_conn(tmp_path) -> Generator[sqlite3.Connection, None, None]:
    db_path = tmp_path / "artist-genre-consumers.db"
    original = db_mod.DB_PATH
    db_mod.DB_PATH = str(db_path)
    db_mod.init_db()
    migrations.run_migrations()

    db_mod._load_plays_cached.cache_clear()
    db_mod._load_plays_for_artists_cached.cache_clear()
    db_mod.get_track_artist_names_map.cache_clear()
    db_mod.get_track_all_artists_map.cache_clear()
    get_wrapped_full.__globals__["_get_wrapped_full_cached"].cache_clear()

    conn = db_mod.get_db(readonly=False)
    _seed_artist_genre_consumer_db(conn)
    yield conn
    conn.close()
    db_mod.DB_PATH = original


def _seed_artist_genre_consumer_db(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "albums", "release_date", "TEXT")
    conn.executemany(
        "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
        [(artist_id, artist_name) for artist_id, artist_name, _ in ARTISTS],
    )
    conn.executemany(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
        [
            (101, "Spotify Genre Album", 1),
            (102, "Curated Fallback Album", 2),
            (103, "Unknown Genre Album", 3),
        ],
    )
    conn.executemany(
        """INSERT INTO tracks(
               track_id, track_name, artist_id, album_id, spotify_track_uri, spotify_track_id
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (1001, "Spotify Genre Song", 1, 101, "spotify:track:spotify", "sp-track"),
            (1002, "Curated Fallback Song", 2, 102, "spotify:track:fallback", "fb-track"),
            (1003, "Unknown Genre Song", 3, 103, "spotify:track:unknown", "uk-track"),
        ],
    )
    conn.executemany(
        "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
        [(1001, 1), (1002, 2), (1003, 3)],
    )
    conn.executemany(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, duration_ms, spotify_album_id
           ) VALUES (?, ?, ?, ?)""",
        [
            ("sp-track", "Spotify Genre Song", 180_000, "sp-album"),
            ("fb-track", "Curated Fallback Song", 180_000, "fb-album"),
            ("uk-track", "Unknown Genre Song", 180_000, "uk-album"),
        ],
    )
    conn.executemany(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date, total_tracks
           ) VALUES (?, ?, 'album', ?, 1)""",
        [
            ("sp-album", "Spotify Genre Album", "2024-01-01"),
            ("fb-album", "Curated Fallback Album", "2024-01-01"),
            ("uk-album", "Unknown Genre Album", "2024-01-01"),
        ],
    )
    conn.executemany(
        """INSERT INTO spotify_artist_meta(
               spotify_artist_id, artist_name, popularity, followers, genres, image_url
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (
                "sp-artist",
                "Spotify Genre Artist",
                70,
                7000,
                json.dumps(["spotify rock"]),
                "https://example.test/spotify.jpg",
            ),
            (
                "fb-artist",
                "Curated Fallback Artist",
                80,
                8000,
                json.dumps([]),
                "https://example.test/fallback.jpg",
            ),
            (
                "uk-artist",
                "Unknown Genre Artist",
                10,
                100,
                json.dumps([]),
                "https://example.test/unknown.jpg",
            ),
        ],
    )
    conn.execute(
        """INSERT INTO artist_genre_sources(
               artist_name, spotify_artist_id, source, source_key,
               raw_genres_json, normalized_genres_json, primary_genre,
               language, region, confidence, evidence_summary, status
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')""",
        (
            "Curated Fallback Artist",
            "fb-artist",
            "curated_seed",
            "local-fixture",
            json.dumps(["Bedroom Pop"]),
            json.dumps(["bedroom pop"]),
            "bedroom pop",
            "english",
            "美国",
            0.92,
            "contract fixture",
        ),
    )
    conn.executemany(
        """INSERT INTO saved_tracks(
               track_uri, track_name, artist_name, album_name, added_date, spotify_track_id
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (
                "spotify:track:spotify",
                "Spotify Genre Song",
                "Spotify Genre Artist",
                "Spotify Genre Album",
                "2024-01-05",
                "sp-track",
            ),
            (
                "spotify:track:fallback",
                "Curated Fallback Song",
                "Curated Fallback Artist",
                "Curated Fallback Album",
                "2024-02-05",
                "fb-track",
            ),
            (
                "spotify:track:unknown",
                "Unknown Genre Song",
                "Unknown Genre Artist",
                "Unknown Genre Album",
                "2024-03-05",
                "uk-track",
            ),
        ],
    )
    conn.executemany(
        """INSERT INTO plays(
               play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
               ts_date, platform, ms_played, track_id, content_type
           ) VALUES (?, ?, 2024, ?, ?, ?, 12, ?, 'web', 180000, ?, 'audio')""",
        [
            (1, "2024-01-10T12:00:00Z", 1, 2, 3, "2024-01-10", 1001),
            (2, "2024-02-10T12:00:00Z", 2, 6, 6, "2024-02-10", 1002),
            (3, "2024-03-10T12:00:00Z", 3, 10, 3, "2024-03-10", 1003),
        ],
    )
    conn.commit()


def _ensure_column(
    conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str
) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def test_wrapped_genre_panorama_uses_resolved_fallback_and_reports_coverage(
    artist_genre_consumer_conn,
):
    result = get_wrapped_full(
        artist_genre_consumer_conn,
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        year=2024,
    )

    panorama = result["genre_panorama"]
    names = {row["name"] for row in panorama["top_genres"]}

    assert "rock/alternative" in names
    assert "pop" in names
    assert "其他流派" not in names
    style_axis = next(row for row in panorama["axes"] if row["axis"] == "style")
    assert style_axis["coverage_pct"] == pytest.approx(66.7)
    assert style_axis["unknown_hours"] == pytest.approx(0.1)
    assert panorama["coverage"]["source_hours"]["curated_seed"] == 0.1
    assert panorama["coverage"]["unknown_hours"] == 0.1
    assert "style/scene/context/role" in panorama["caveat"]
    assert "不等同于声音风格" in panorama["caveat"]
    assert "单一高播放艺人" in panorama["caveat"]


def test_wrapped_cache_reflects_newly_approved_artist_genre_source(
    artist_genre_consumer_conn,
):
    first = get_wrapped_full(
        artist_genre_consumer_conn,
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        year=2024,
    )
    first_names = {row["name"] for row in first["genre_panorama"]["top_genres"]}
    assert "hip hop/rap" not in first_names

    upsert_genre_source(
        artist_genre_consumer_conn,
        artist_name="Unknown Genre Artist",
        spotify_artist_id="uk-artist",
        source="llm",
        source_key="llm:unknown-genre-artist",
        raw_genres=["new approved hip hop"],
        normalized_genres=["new approved hip hop"],
        primary_genre="new approved hip hop",
        language="english",
        region="全球",
        confidence=0.8,
        evidence_url=None,
        evidence_summary="Approved after cached Wrapped response.",
        status="approved",
    )
    artist_genre_consumer_conn.commit()

    second = get_wrapped_full(
        artist_genre_consumer_conn,
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        year=2024,
    )
    second_names = {row["name"] for row in second["genre_panorama"]["top_genres"]}

    assert "hip hop/rap" in second_names
    assert second["genre_panorama"]["coverage"]["source_hours"]["llm"] == 0.1
    assert second["genre_panorama"]["coverage"]["unknown_hours"] == 0.0


def test_account_collection_genre_migration_uses_resolved_fallback(
    artist_genre_consumer_conn,
):
    result = get_collection_insights(artist_genre_consumer_conn)

    assert "rock/alternative" in result["genre_migration"]["2024"]
    assert "pop" in result["genre_migration"]["2024"]


def test_artist_detail_metadata_returns_resolved_genre_source_and_confidence(
    artist_genre_consumer_conn,
):
    meta = billboard_details._get_artist_spotify_meta("Curated Fallback Artist")

    assert meta["popularity"] == 80
    assert meta["followers"] == 8000
    assert meta["genres"] == ["bedroom pop"]
    assert meta["genre_source"] == "curated_seed"
    assert meta["genre_confidence"] == 0.92


def test_artist_versus_metadata_returns_resolved_genre_source_and_confidence(
    artist_genre_consumer_conn,
    monkeypatch,
):
    monkeypatch.setattr(billboard_versus, "compute_billboard_data", _versus_fixture_data)

    result = billboard_versus.get_versus_artist(
        "Curated Fallback Artist",
        "Spotify Genre Artist",
        30_000,
        True,
        30,
        20,
        20,
        4,
        0,
        None,
        None,
    )

    assert result["found"] is True
    assert result["entity_a"]["genres"] == ["bedroom pop"]
    assert result["entity_a"]["genre_source"] == "curated_seed"
    assert result["entity_a"]["genre_confidence"] == 0.92


def test_globetrotter_score_does_not_count_unknown_artists_as_overseas(
    artist_genre_consumer_conn,
):
    artist_agg = pd.DataFrame(
        {
            "plays": [1, 9],
            "hours": [0.1, 0.9],
        },
        index=["Spotify Genre Artist", "Unknown Genre Artist"],
    )

    score = wrapped_service._calc_globetrotter_score(
        artist_genre_consumer_conn,
        pd.DataFrame(),
        artist_agg,
    )

    assert score == 10.0


def test_music_map_prefers_resolved_region_over_genre_guess(
    artist_genre_consumer_conn,
):
    artist_agg = pd.DataFrame(
        {
            "plays": [1],
            "hours": [1.0],
        },
        index=["Curated Fallback Artist"],
    )

    music_map = wrapped_service._build_music_map(
        artist_genre_consumer_conn,
        pd.DataFrame(),
        artist_agg,
    )

    assert music_map["regions"][0]["region"] == "美国"
    assert music_map["top_overseas_artists"][0]["region"] == "美国"


def _versus_fixture_data(*_args, **_kwargs) -> dict:
    return {
        "weekly": [
            {
                "billboard_week": "2024-01-12",
                "track_id": 1001,
                "track_name": "Spotify Genre Song",
                "artist_name": "Spotify Genre Artist",
                "album_name": "Spotify Genre Album",
                "rank": 2,
                "play_count": 1,
            },
            {
                "billboard_week": "2024-01-12",
                "track_id": 1002,
                "track_name": "Curated Fallback Song",
                "artist_name": "Curated Fallback Artist",
                "album_name": "Curated Fallback Album",
                "rank": 1,
                "play_count": 1,
            },
        ],
        "weekly_artist": [
            {
                "billboard_week": "2024-01-12",
                "artist_name": "Spotify Genre Artist",
                "rank": 2,
                "play_count": 1,
            },
            {
                "billboard_week": "2024-01-12",
                "artist_name": "Curated Fallback Artist",
                "rank": 1,
                "play_count": 1,
            },
        ],
        "weekly_album": [
            {
                "billboard_week": "2024-01-12",
                "album_name": "Spotify Genre Album",
                "artist_name": "Spotify Genre Artist",
                "rank": 2,
                "play_count": 1,
            },
            {
                "billboard_week": "2024-01-12",
                "album_name": "Curated Fallback Album",
                "artist_name": "Curated Fallback Artist",
                "rank": 1,
                "play_count": 1,
            },
        ],
        "artist_power_scores": [
            {
                "artist_name": "Spotify Genre Artist",
                "power_score": 8,
                "peak_position": 2,
                "weeks_on_chart": 1,
            },
            {
                "artist_name": "Curated Fallback Artist",
                "power_score": 10,
                "peak_position": 1,
                "weeks_on_chart": 1,
            },
        ],
        "power_scores": [
            {
                "track_id": 1001,
                "power_score": 8,
                "peak_position": 2,
                "weeks_on_chart": 1,
            },
            {
                "track_id": 1002,
                "power_score": 10,
                "peak_position": 1,
                "weeks_on_chart": 1,
            },
        ],
        "album_power_scores": [
            {
                "album_name": "Spotify Genre Album",
                "artist_name": "Spotify Genre Artist",
                "power_score": 8,
                "peak_position": 2,
                "weeks_on_chart": 1,
            },
            {
                "album_name": "Curated Fallback Album",
                "artist_name": "Curated Fallback Artist",
                "power_score": 10,
                "peak_position": 1,
                "weeks_on_chart": 1,
            },
        ],
    }
