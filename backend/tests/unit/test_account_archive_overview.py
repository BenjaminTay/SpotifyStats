from __future__ import annotations

import json
import sqlite3

import pytest
from pydantic import ValidationError

from backend.domains.account_archive.overview import get_archive_overview
from backend.domains.account_archive.revision import bump_archive_revision
from backend.models.account_archive import ArchiveOverviewResponse

pytestmark = pytest.mark.unit


def _archive_db(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
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
        CREATE TABLE plays (play_id INTEGER PRIMARY KEY, ts_date TEXT);
        CREATE TABLE account_archive_state (
            state_id INTEGER PRIMARY KEY,
            account_import_revision INTEGER,
            collection_date_revision INTEGER,
            updated_at TEXT
        );
        INSERT INTO account_archive_state VALUES (1, 3, 5, datetime('now'));
        INSERT INTO saved_tracks VALUES
            ('spotify:track:linked', 'Linked Song', 'Local Artist', 'Local Album',
             '2022-01-02T00:00:00Z', 'linked', 'oauth'),
            ('spotify:track:remote', 'Remote Song', 'Remote Artist', 'Remote Album',
             '2024-03-04T00:00:00Z', 'remote', 'legacy');
        INSERT INTO saved_albums VALUES ('spotify:album:one');
        INSERT INTO saved_artists VALUES ('spotify:artist:one');
        INSERT INTO playlists VALUES (1);
        INSERT INTO playlist_tracks VALUES (1, 'spotify:track:linked');
        INSERT INTO artists VALUES (1, 'Local Artist');
        INSERT INTO albums VALUES
            (1, 'Local Album', 1, '1999-01-01', '/tmp/cover.jpg', NULL);
        INSERT INTO tracks VALUES
            (1, 'Linked Song', 1, 1, 'spotify:track:linked', 'linked');
        INSERT INTO spotify_track_meta VALUES
            ('linked', 180000, 'spotify-album-local'),
            ('remote', 240000, 'spotify-album-remote');
        INSERT INTO spotify_album_meta VALUES
            ('spotify-album-local', '1999-01-01'),
            ('spotify-album-remote', '2023-01-01');
        INSERT INTO plays VALUES (1, '2021-01-01'), (2, '2025-06-30');
        """
    )
    conn.commit()
    return conn


def _all_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_all_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value), set())
    return set()


def test_archive_overview_is_compact_strict_and_privacy_whitelisted(tmp_path) -> None:
    conn = _archive_db(tmp_path / "archive.db")
    payload = get_archive_overview(conn)
    conn.close()
    response = ArchiveOverviewResponse.model_validate(payload)

    assert response.status == "partial"
    assert response.counts.saved_tracks == 2
    assert response.counts.playlists == 1
    assert response.coverage.saved_tracks_with_date_pct == 100.0
    assert response.coverage.saved_tracks_linked_to_history_pct == 50.0
    assert response.coverage.known_duration_ms == 420000
    assert response.date_provenance.oauth == 1
    assert response.date_provenance.legacy == 1
    assert response.capabilities.collection_timeline == "available"
    assert response.capabilities.playback_cross_analysis == "partial"
    assert response.featured_items
    assert len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) < 40_000

    forbidden = {
        "profile",
        "birthdate",
        "postal_code",
        "family_address",
        "prompts",
        "inferences",
        "query_text",
        "banned_items",
        "track_uri",
    }
    assert _all_keys(payload).isdisjoint(forbidden)


def test_archive_overview_contract_rejects_unknown_fields(tmp_path) -> None:
    conn = _archive_db(tmp_path / "strict.db")
    payload = get_archive_overview(conn)
    conn.close()
    payload["raw_profile"] = {"birthdate": "private"}

    with pytest.raises(ValidationError):
        ArchiveOverviewResponse.model_validate(payload)


def test_archive_overview_cache_key_changes_with_import_revision(tmp_path) -> None:
    conn = _archive_db(tmp_path / "revision.db")
    first = get_archive_overview(conn)
    conn.execute(
        "INSERT INTO saved_tracks VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "spotify:track:new",
            "New Snapshot Track",
            "New Artist",
            "New Album",
            None,
            "new",
            None,
        ),
    )
    bump_archive_revision(conn, "account_import")
    conn.commit()

    second = get_archive_overview(conn)
    conn.close()

    assert first["counts"]["saved_tracks"] == 2
    assert second["counts"]["saved_tracks"] == 3
    assert first["data_revision"] != second["data_revision"]
