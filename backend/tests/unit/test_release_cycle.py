"""Unit tests for release cycle service — offline/degraded paths."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


class TestSpotifyToken:
    def test_network_failure_returns_none(self, monkeypatch):
        import backend.services.release_cycle_service as svc

        monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test-client-secret")

        class FailingSpotifyProvider:
            def get_cc_token(self):
                raise OSError("network disabled")

        monkeypatch.setattr(svc, "SpotifyProvider", FailingSpotifyProvider)
        svc._get_spotify_token.cache_clear()

        result = svc._get_spotify_token()
        assert result is None


def test_advance_singles_cover_uses_shared_track_spotify_album_meta(monkeypatch):
    import backend.services.release_cycle_service as svc

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            image_url TEXT,
            image_path TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE track_albums (
            track_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            ts_date TEXT,
            track_id INTEGER
        );
        CREATE TABLE spotify_track_meta (
            spotify_track_id TEXT PRIMARY KEY,
            track_name TEXT NOT NULL,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta (
            spotify_album_id TEXT PRIMARY KEY,
            album_name TEXT NOT NULL,
            album_type TEXT,
            release_date TEXT,
            image_url TEXT
        );
        """
    )
    conn.execute("INSERT INTO artists VALUES (1, 'Fixture Artist')")
    conn.execute("INSERT INTO albums VALUES (10, 'Fixture Album', 1, NULL, NULL)")
    conn.execute("INSERT INTO albums VALUES (11, 'Fixture Lead Single', 1, NULL, NULL)")
    conn.execute("INSERT INTO tracks VALUES (100, 'Fixture Song', 1, 10, 'spotify-track-100')")
    conn.execute("INSERT INTO track_albums VALUES (100, 10)")
    conn.execute("INSERT INTO track_albums VALUES (100, 11)")
    conn.execute(
        "INSERT INTO spotify_track_meta VALUES "
        "('spotify-track-100', 'Fixture Song', 'spotify-single-album')"
    )
    conn.execute(
        "INSERT INTO spotify_album_meta VALUES "
        "('spotify-single-album', 'Fixture Lead Single (Spotify)', 'single', "
        "'2024-01-05', 'https://i.scdn.co/image/single.jpg')"
    )
    conn.commit()

    monkeypatch.setattr(svc, "get_db", lambda *args, **kwargs: conn)
    monkeypatch.setattr(
        svc,
        "load_artist_releases",
        lambda artist_name: pd.DataFrame(
            [
                {
                    "album_name": "Fixture Album",
                    "db_album_name": "Fixture Album",
                    "album_type": "album",
                    "release_date": pd.Timestamp("2024-02-01"),
                }
            ]
        ),
    )
    monkeypatch.setattr(
        svc,
        "_spotify_search_album",
        lambda album_name, artist_name, skip_db_check=False: {
            "album_name": "Fixture Lead Single (Spotify)",
            "album_type": "single",
            "release_date": "2024-01-05",
            "spotify_album_id": "spotify-single-album",
        },
    )

    result = svc.get_advance_singles("Fixture Artist", "Fixture Album")

    assert result == [
        {
            "single_name": "Fixture Lead Single",
            "release_date": pd.Timestamp("2024-01-05"),
            "cover_url": "/covers/albums/11.jpg",
        }
    ]


def test_public_release_cycle_metadata_is_local_cache_only(monkeypatch):
    import backend.services.release_cycle_service as svc
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )

    provider_called = False

    class FailingSpotifyProvider:
        def get_cc_token(self):
            nonlocal provider_called
            provider_called = True
            raise AssertionError("public release-cycle request attempted Spotify access")

    monkeypatch.setattr(svc, "SpotifyProvider", FailingSpotifyProvider)
    monkeypatch.setattr(svc, "get_db", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    svc._get_spotify_token.cache_clear()
    svc._spotify_search_album.cache_clear()

    token = set_public_readonly_db_guard(True)
    try:
        assert svc._spotify_search_album("Missing Album", "Missing Artist") is None
    finally:
        reset_public_readonly_db_guard(token)
        svc._spotify_search_album.cache_clear()

    assert provider_called is False
