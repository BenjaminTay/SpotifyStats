from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.account import router as account_router
from backend.dependencies import get_conn
from backend.domains.account_archive.library import build_archive_library_page
from backend.models.account_archive import ArchiveLibraryPageResponse

pytestmark = pytest.mark.unit


def _library_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE saved_tracks (
            track_uri TEXT PRIMARY KEY,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            added_date TEXT,
            spotify_track_id TEXT
        );
        CREATE TABLE saved_albums (
            album_uri TEXT PRIMARY KEY,
            album_name TEXT,
            artist_name TEXT
        );
        CREATE TABLE saved_artists (
            artist_uri TEXT PRIMARY KEY,
            artist_name TEXT
        );
        CREATE TABLE playlists (
            playlist_id INTEGER PRIMARY KEY,
            playlist_name TEXT,
            last_modified_date TEXT,
            track_count INTEGER,
            follower_count INTEGER
        );
        CREATE TABLE playlist_tracks (
            playlist_id INTEGER,
            track_uri TEXT,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            added_date TEXT
        );
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT,
            artist_id INTEGER,
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

        INSERT INTO artists VALUES
            (1, 'Alpha Artist', '/tmp/artist.jpg', NULL),
            (2, 'Beta Artist', NULL, NULL);
        INSERT INTO albums VALUES
            (10, 'Alpha Album', 1, '/tmp/album.jpg', NULL),
            (11, 'Beta Album', 2, NULL, NULL);
        INSERT INTO tracks VALUES
            (100, 'Alpha Song', 1, 10, 'spotify:track:alpha', 'alpha'),
            (101, '100% Song', 1, 10, 'spotify:track:percent', 'percent');
        INSERT INTO saved_tracks VALUES
            ('spotify:track:alpha', 'Alpha Song', 'Alpha Artist', 'Alpha Album',
             '2024-02-01T00:00:00Z', 'alpha'),
            ('spotify:track:percent', '100% Song', 'Alpha Artist', 'Alpha Album',
             '2024-01-01T00:00:00Z', 'percent'),
            ('spotify:track:missing', 'Missing Song', 'Beta Artist', 'Beta Album',
             NULL, 'missing');
        INSERT INTO saved_albums VALUES
            ('spotify:album:alpha', 'Alpha Album', 'Alpha Artist'),
            ('spotify:album:missing', 'Missing Album', 'Beta Artist');
        INSERT INTO saved_artists VALUES
            ('spotify:artist:alpha', 'Alpha Artist'),
            ('spotify:artist:missing', 'Missing Artist');
        INSERT INTO playlists VALUES
            (1, 'Small Mix', '2024-01-01', 99, 2),
            (2, 'Large Mix', '2024-02-01', 0, 0);
        INSERT INTO playlist_tracks VALUES
            (1, 'spotify:track:alpha', 'Alpha Song', 'Alpha Artist', 'Alpha Album', NULL),
            (2, 'spotify:track:alpha', 'Alpha Song', 'Alpha Artist', 'Alpha Album', NULL),
            (2, 'spotify:track:percent', '100% Song', 'Alpha Artist', 'Alpha Album', NULL),
            (2, 'spotify:track:missing', 'Missing Song', 'Beta Artist', 'Beta Album', NULL),
            (2, 'spotify:track:four', 'Fourth Song', 'Beta Artist', 'Beta Album', NULL);
        """
    )
    conn.commit()
    return conn


def test_track_library_is_server_paginated_sorted_and_private() -> None:
    conn = _library_conn()
    result = build_archive_library_page(conn, "tracks", page=2, limit=2, search="", sort="recent")
    conn.close()
    response = ArchiveLibraryPageResponse.model_validate(result)
    serialized = json.dumps(result)

    assert response.total == 3
    assert response.total_pages == 2
    assert response.page == 2
    assert len(response.items) == 1
    assert response.items[0].entity_type == "track"
    assert response.items[0].track_name == "Missing Song"
    assert response.items[0].deep_link is None
    assert response.items[0].item_key.startswith("saved-track:")
    assert "spotify:track:" not in serialized
    assert "track_uri" not in serialized


def test_library_search_escapes_wildcards_and_returns_local_deep_link() -> None:
    conn = _library_conn()
    result = build_archive_library_page(conn, "tracks", page=1, limit=20, search="%", sort="name")
    conn.close()
    response = ArchiveLibraryPageResponse.model_validate(result)

    assert response.search_applied is True
    assert response.total == 1
    assert response.items[0].track_name == "100% Song"
    assert response.items[0].cover_url == "/covers/albums/10.jpg"
    assert response.items[0].deep_link == "/music/tracks/101"


def test_album_artist_and_playlist_pages_use_stable_local_facts() -> None:
    conn = _library_conn()
    albums = ArchiveLibraryPageResponse.model_validate(
        build_archive_library_page(conn, "albums", sort="artist")
    )
    artists = ArchiveLibraryPageResponse.model_validate(
        build_archive_library_page(conn, "artists", sort="name")
    )
    playlists = ArchiveLibraryPageResponse.model_validate(
        build_archive_library_page(conn, "playlists", sort="tracks")
    )
    conn.close()

    assert albums.items[0].entity_type == "album"
    assert albums.items[0].cover_url == "/covers/albums/10.jpg"
    assert albums.items[0].deep_link == "/music/albums/Alpha%20Album?artist=Alpha%20Artist"
    assert artists.items[0].entity_type == "artist"
    assert artists.items[0].cover_url == "/covers/artists/1.jpg"
    assert artists.items[0].deep_link == "/music/artists/Alpha%20Artist"
    assert playlists.items[0].entity_type == "playlist"
    assert playlists.items[0].playlist_name == "Large Mix"
    assert playlists.items[0].track_count == 4
    assert len(playlists.items[0].preview_tracks) == 3


def test_library_revision_changes_when_content_changes_without_count_change() -> None:
    conn = _library_conn()
    first = ArchiveLibraryPageResponse.model_validate(build_archive_library_page(conn, "tracks"))
    conn.execute(
        "UPDATE saved_tracks SET track_name = 'Renamed Song' WHERE track_name = 'Alpha Song'"
    )
    conn.commit()
    second = ArchiveLibraryPageResponse.model_validate(build_archive_library_page(conn, "tracks"))
    conn.close()

    assert first.total == second.total
    assert first.data_revision != second.data_revision


def test_saved_variants_keep_unique_item_keys_when_catalogue_identity_is_shared() -> None:
    conn = _library_conn()
    conn.execute(
        "INSERT INTO saved_tracks VALUES (?, ?, ?, ?, ?, ?)",
        (
            "spotify:track:alpha-variant",
            "Alpha Song",
            "Alpha Artist",
            "Alpha Album",
            "2024-03-01T00:00:00Z",
            "alpha",
        ),
    )
    conn.execute(
        "INSERT INTO saved_albums VALUES (?, ?, ?)",
        ("spotify:album:alpha-variant", "Alpha Album", "Alpha Artist"),
    )
    conn.execute(
        "INSERT INTO saved_artists VALUES (?, ?)",
        ("spotify:artist:alpha-variant", "Alpha Artist"),
    )
    conn.commit()

    pages = [
        build_archive_library_page(conn, "tracks", limit=20),
        build_archive_library_page(conn, "albums", limit=20),
        build_archive_library_page(conn, "artists", limit=20),
    ]
    conn.close()

    for page in pages:
        item_keys = [item["item_key"] for item in page["items"]]
        assert len(item_keys) == len(set(item_keys))


def test_library_browses_account_export_without_local_music_catalog() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE saved_tracks (
            track_uri TEXT PRIMARY KEY, track_name TEXT, artist_name TEXT,
            album_name TEXT, added_date TEXT, spotify_track_id TEXT
        );
        CREATE TABLE saved_albums (
            album_uri TEXT PRIMARY KEY, album_name TEXT, artist_name TEXT
        );
        CREATE TABLE saved_artists (
            artist_uri TEXT PRIMARY KEY, artist_name TEXT
        );
        CREATE TABLE playlists (
            playlist_id INTEGER PRIMARY KEY, playlist_name TEXT,
            last_modified_date TEXT, track_count INTEGER, follower_count INTEGER
        );
        CREATE TABLE playlist_tracks (
            playlist_id INTEGER, track_uri TEXT, track_name TEXT,
            artist_name TEXT, album_name TEXT, added_date TEXT
        );
        INSERT INTO saved_tracks VALUES
            ('spotify:track:only', 'Export Track', 'Export Artist', 'Export Album', NULL, 'only');
        INSERT INTO saved_albums VALUES
            ('spotify:album:only', 'Export Album', 'Export Artist');
        INSERT INTO saved_artists VALUES
            ('spotify:artist:only', 'Export Artist');
        """
    )

    tracks = ArchiveLibraryPageResponse.model_validate(build_archive_library_page(conn, "tracks"))
    albums = ArchiveLibraryPageResponse.model_validate(build_archive_library_page(conn, "albums"))
    artists = ArchiveLibraryPageResponse.model_validate(build_archive_library_page(conn, "artists"))
    conn.close()

    assert tracks.total == albums.total == artists.total == 1
    assert tracks.items[0].deep_link is None
    assert albums.items[0].deep_link is None
    assert artists.items[0].deep_link is None


def test_library_route_validates_entity_sort_and_page_bounds() -> None:
    conn = _library_conn()
    app = FastAPI()
    app.include_router(account_router, prefix="/api")
    app.dependency_overrides[get_conn] = lambda: conn
    client = TestClient(app)

    valid = client.get("/api/account/library/tracks?limit=2&page=1&sort=recent")
    invalid_entity = client.get("/api/account/library/shows")
    invalid_sort = client.get("/api/account/library/artists?sort=recent")
    invalid_limit = client.get("/api/account/library/tracks?limit=51")
    conn.close()

    assert valid.status_code == 200
    assert valid.json()["entity_type"] == "tracks"
    assert len(valid.json()["items"]) == 2
    assert invalid_entity.status_code == 422
    assert invalid_sort.status_code == 422
    assert invalid_sort.json()["detail"][0]["loc"] == ["query", "sort"]
    assert invalid_limit.status_code == 422
