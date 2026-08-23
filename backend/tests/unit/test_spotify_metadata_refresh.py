from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            source_album_id INTEGER,
            ts_date TEXT,
            spotify_track_id_at_play TEXT,
            spotify_album_id_at_play TEXT,
            import_generation_id TEXT
        );
        CREATE TABLE artists(
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT,
            spotify_artist_id TEXT,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT,
            image_path TEXT
        );
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            artist_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE track_artists(
            track_id INTEGER,
            artist_id INTEGER,
            role TEXT
        );
        CREATE TABLE albums(
            album_id INTEGER PRIMARY KEY,
            album_name TEXT,
            artist_id INTEGER,
            spotify_album_id TEXT,
            image_url TEXT,
            image_path TEXT
        );
        CREATE TABLE spotify_track_meta(
            spotify_track_id TEXT PRIMARY KEY,
            track_name TEXT,
            duration_ms INTEGER,
            popularity INTEGER,
            explicit INTEGER,
            track_number INTEGER,
            disc_number INTEGER,
            isrc TEXT,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY,
            album_name TEXT,
            album_type TEXT,
            release_date TEXT,
            popularity INTEGER,
            label TEXT,
            genres TEXT,
            image_url TEXT,
            album_artists TEXT,
            total_tracks INTEGER,
            track_list TEXT
        );
        CREATE TABLE spotify_artist_meta(
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT
        );
        CREATE TABLE album_spotify_links(
            album_id INTEGER NOT NULL,
            spotify_album_id TEXT NOT NULL,
            evidence TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            play_count INTEGER NOT NULL DEFAULT 0,
            track_count INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(album_id, spotify_album_id, evidence)
        );
        """
    )
    return conn


def test_select_missing_play_track_ids_prefers_play_time_ids():
    from backend.domains.metadata.spotify_refresh import select_missing_track_ids

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'old-track')")
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date, spotify_track_id_at_play) "
        "VALUES (1, 1, 10, '2026-06-01', 'new-track')"
    )

    assert select_missing_track_ids(conn, limit=50) == ["new-track", "old-track"]


def test_upsert_track_batch_updates_play_album_ids_and_album_links():
    from backend.domains.metadata.spotify_refresh import upsert_track_batch

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'track-a')")
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date, spotify_track_id_at_play) "
        "VALUES (1, 1, 10, '2026-06-01', 'track-a')"
    )

    updated = upsert_track_batch(
        conn,
        [
            {
                "id": "track-a",
                "name": "Track A",
                "duration_ms": 180000,
                "popularity": 42,
                "explicit": False,
                "track_number": 3,
                "disc_number": 1,
                "external_ids": {"isrc": "ISRC-A"},
                "album": {"id": "album-a"},
            }
        ],
    )

    assert updated == 1
    row = conn.execute("SELECT spotify_album_id FROM spotify_track_meta").fetchone()
    assert row["spotify_album_id"] == "album-a"
    play = conn.execute("SELECT spotify_album_id_at_play FROM plays").fetchone()
    assert play["spotify_album_id_at_play"] == "album-a"
    link = conn.execute("SELECT * FROM album_spotify_links").fetchone()
    assert link["album_id"] == 10
    assert link["spotify_album_id"] == "album-a"
    assert link["evidence"] == "play_track_api"
    assert link["play_count"] == 1


def test_upsert_track_batch_links_exact_local_artist():
    from backend.domains.metadata.spotify_refresh import upsert_track_batch

    conn = _conn()
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (7, 'Beyoncé')")
    conn.execute(
        "INSERT INTO tracks(track_id, artist_id, spotify_track_id) VALUES (1, 7, 'track-a')"
    )

    upsert_track_batch(
        conn,
        [
            {
                "id": "track-a",
                "name": "Track A",
                "artists": [{"id": "artist-a", "name": "Beyonce"}],
                "album": {},
            }
        ],
    )

    row = conn.execute("SELECT spotify_artist_id FROM artists WHERE artist_id=7").fetchone()
    assert row["spotify_artist_id"] == "artist-a"


def test_backfill_album_links_uses_existing_track_metadata():
    from backend.domains.metadata.spotify_refresh import (
        backfill_album_links_from_existing_metadata,
    )

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'track-a')")
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, duration_ms, spotify_album_id)
           VALUES ('track-a', 'Track A', 180000, 'album-a')"""
    )
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date) "
        "VALUES (1, 1, 10, '2026-06-01')"
    )

    changed = backfill_album_links_from_existing_metadata(conn)

    assert changed >= 1
    play = conn.execute(
        "SELECT spotify_track_id_at_play, spotify_album_id_at_play FROM plays"
    ).fetchone()
    assert play["spotify_track_id_at_play"] == "track-a"
    assert play["spotify_album_id_at_play"] == "album-a"
    link = conn.execute("SELECT * FROM album_spotify_links").fetchone()
    assert link["album_id"] == 10
    assert link["spotify_album_id"] == "album-a"
    assert link["evidence"] == "play_track_meta"


def test_upsert_album_batch_preserves_existing_image_when_provider_omits_images():
    from backend.domains.metadata.spotify_refresh import upsert_album_batch

    conn = _conn()
    conn.execute(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date, image_url)
           VALUES ('album-a', 'Old Name', 'single', '2026-01-01', 'old.jpg')"""
    )

    updated = upsert_album_batch(
        conn,
        [
            {
                "id": "album-a",
                "name": "Album A",
                "album_type": "album",
                "release_date": "2026-06-01",
                "popularity": 80,
                "label": "Fixture",
                "genres": [],
                "images": [],
                "artists": [{"name": "Artist A"}],
                "total_tracks": 11,
                "tracks": {"items": [{"id": "track-a"}]},
            }
        ],
    )

    assert updated == 1
    row = conn.execute(
        "SELECT * FROM spotify_album_meta WHERE spotify_album_id = 'album-a'"
    ).fetchone()
    assert row["album_name"] == "Album A"
    assert row["album_type"] == "album"
    assert row["image_url"] == "old.jpg"
    assert row["total_tracks"] == 11
    assert row["track_list"] == '["track-a"]'


def test_artist_batch_and_cover_source_sync_fill_local_entities():
    from backend.domains.metadata.spotify_refresh import (
        sync_local_cover_urls,
        upsert_artist_batch,
    )

    conn = _conn()
    conn.execute(
        "INSERT INTO artists(artist_id, artist_name, spotify_artist_id) "
        "VALUES (7, 'Artist A', 'artist-a')"
    )
    updated = upsert_artist_batch(
        conn,
        [
            {
                "id": "artist-a",
                "name": "Artist A",
                "images": [{"url": "artist.jpg"}],
                "followers": {"total": 12},
                "genres": ["pop"],
            }
        ],
    )

    assert updated == 1
    sync_local_cover_urls(conn)
    row = conn.execute("SELECT image_url, followers FROM artists WHERE artist_id=7").fetchone()
    assert row["image_url"] == "artist.jpg"
    assert row["followers"] == 12


def test_refresh_missing_spotify_metadata_without_token_returns_partial_report():
    from backend.domains.metadata.spotify_refresh import refresh_missing_spotify_metadata

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'track-a')")
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, duration_ms, spotify_album_id)
           VALUES ('track-a', 'Track A', 180000, 'album-a')"""
    )
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date) "
        "VALUES (1, 1, 10, '2026-06-01')"
    )

    report = refresh_missing_spotify_metadata(conn, provider=object(), access_token=None)

    assert report.provider_available is False
    assert report.errors == ("spotify_credentials_missing",)
    assert report.album_links_backfilled >= 1
    assert report.local_album_ids_relinked == frozenset({10})
    assert report.impact_scope_exact is False
    link = conn.execute("SELECT * FROM album_spotify_links").fetchone()
    assert link["album_id"] == 10


def test_scoped_refresh_reports_exact_provider_and_backlog_impact_ids():
    from backend.domains.metadata.spotify_refresh import (
        MetadataRefreshScope,
        refresh_missing_spotify_metadata,
    )

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (2, 'track-backlog')")
    conn.execute(
        """INSERT INTO plays(
               play_id, track_id, source_album_id, ts_date,
               spotify_track_id_at_play, import_generation_id
           ) VALUES (2, 2, 20, '2026-08-20', 'track-backlog', 'generation-old')"""
    )

    class Provider:
        def get_tracks(self, ids, token):
            return {
                "tracks": [
                    {
                        "id": spotify_track_id,
                        "name": spotify_track_id,
                        "artists": [],
                        "album": {"id": f"album-for-{spotify_track_id}"},
                    }
                    for spotify_track_id in ids
                ]
            }

        def get_albums(self, ids, token):
            return {
                "albums": [
                    {
                        "id": spotify_album_id,
                        "name": spotify_album_id,
                        "images": [],
                        "artists": [],
                        "tracks": {"items": []},
                        "total_tracks": 1,
                    }
                    for spotify_album_id in ids
                ]
            }

        def get_artists_by_ids(self, ids, token):
            return {"artists": []}

    report = refresh_missing_spotify_metadata(
        conn,
        provider=Provider(),
        access_token="token",
        scope=MetadataRefreshScope(
            generation_id="generation-new",
            spotify_track_ids=frozenset({"track-scoped"}),
            spotify_album_ids=frozenset({"album-scoped"}),
        ),
    )

    assert report.spotify_track_ids_updated == frozenset({"track-backlog", "track-scoped"})
    assert report.spotify_album_ids_updated == frozenset(
        {
            "album-for-track-backlog",
            "album-for-track-scoped",
            "album-scoped",
        }
    )
    assert report.local_album_ids_relinked == frozenset({20})
    assert report.impact_scope_exact is True


def test_refresh_batch_failure_marks_impact_scope_inexact():
    from backend.domains.metadata.spotify_refresh import (
        MetadataRefreshScope,
        refresh_missing_spotify_metadata,
    )

    conn = _conn()

    class Provider:
        def get_tracks(self, ids, token):
            return None

        def get_albums(self, ids, token):
            return {"albums": []}

        def get_artists_by_ids(self, ids, token):
            return {"artists": []}

    report = refresh_missing_spotify_metadata(
        conn,
        provider=Provider(),
        access_token="token",
        scope=MetadataRefreshScope(
            generation_id="generation-new",
            spotify_track_ids=frozenset({"track-failed"}),
        ),
    )

    assert report.errors == ("tracks_batch_failed",)
    assert report.spotify_track_ids_updated == frozenset()
    assert report.impact_scope_exact is False


def test_scoped_refresh_does_not_request_unrelated_missing_tracks():
    from backend.domains.metadata.spotify_refresh import (
        MetadataRefreshScope,
        refresh_missing_spotify_metadata,
    )

    conn = _conn()
    conn.executemany(
        "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
        [(1, "Scoped"), (2, "Unrelated")],
    )
    conn.executemany(
        "INSERT INTO tracks(track_id, artist_id, spotify_track_id) VALUES (?, ?, ?)",
        [(1, 1, "track-scoped"), (2, 2, "track-unrelated")],
    )
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, spotify_album_id
           ) VALUES ('track-unrelated', 'Unrelated', NULL)"""
    )
    conn.execute(
        """INSERT INTO plays(
               play_id, track_id, ts_date, spotify_track_id_at_play,
               import_generation_id
           ) VALUES (1, 1, '2026-08-23', 'track-scoped', 'generation-new')"""
    )

    class Provider:
        requested: list[str] = []

        def get_tracks(self, ids, token):
            self.requested.extend(ids)
            return {
                "tracks": [
                    {"id": value, "name": value, "artists": [], "album": {}} for value in ids
                ]
            }

        def get_albums(self, ids, token):
            return {"albums": []}

        def get_artists_by_ids(self, ids, token):
            return {"artists": []}

    provider = Provider()
    report = refresh_missing_spotify_metadata(
        conn,
        provider=provider,
        access_token="token",
        scope=MetadataRefreshScope(
            generation_id="generation-new",
            track_ids=frozenset({1}),
            artist_ids=frozenset({1}),
        ),
    )

    assert provider.requested == ["track-scoped"]
    assert report.tracks_requested == 1


def test_scoped_track_candidates_union_play_time_and_canonical_ids_and_link_artist():
    from backend.domains.metadata.spotify_refresh import (
        MetadataRefreshScope,
        refresh_missing_spotify_metadata,
    )

    conn = _conn()
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Exact Artist')")
    conn.execute(
        """INSERT INTO tracks(track_id, artist_id, spotify_track_id)
           VALUES (1, 1, 'canonical-track')"""
    )
    conn.executemany(
        """INSERT INTO plays(
               play_id, track_id, ts_date, spotify_track_id_at_play,
               import_generation_id
           ) VALUES (?, ?, '2026-08-23', ?, 'generation-new')""",
        [(1, 1, "play-time-track"), (2, None, "play-only-track")],
    )

    class Provider:
        requested: list[str] = []

        def get_tracks(self, ids, token):
            self.requested.extend(ids)
            return {
                "tracks": [
                    {
                        "id": value,
                        "name": value,
                        "artists": (
                            [{"id": "artist-exact", "name": "Exact Artist"}]
                            if value == "play-time-track"
                            else []
                        ),
                        "album": {},
                    }
                    for value in ids
                ]
            }

        def get_albums(self, ids, token):
            return {"albums": []}

        def get_artists_by_ids(self, ids, token):
            return {"artists": []}

    provider = Provider()
    refresh_missing_spotify_metadata(
        conn,
        provider=provider,
        access_token="token",
        scope=MetadataRefreshScope(
            generation_id="generation-new",
            track_ids=frozenset({1}),
            artist_ids=frozenset({1}),
        ),
    )

    assert provider.requested == ["canonical-track", "play-only-track", "play-time-track"]
    artist = conn.execute("SELECT spotify_artist_id FROM artists WHERE artist_id=1").fetchone()
    assert artist[0] == "artist-exact"


def test_scoped_album_candidates_union_generation_play_track_meta_and_links():
    from backend.domains.metadata.spotify_refresh import (
        MetadataRefreshScope,
        _scoped_album_candidates,
    )

    conn = _conn()
    conn.execute(
        "INSERT INTO tracks(track_id, artist_id, spotify_track_id) VALUES (1, 1, 'track-a')"
    )
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, spotify_album_id
           ) VALUES ('track-a', 'Track A', 'album-from-track')"""
    )
    conn.execute(
        """INSERT INTO plays(
               play_id, track_id, source_album_id, ts_date,
               spotify_album_id_at_play, import_generation_id
           ) VALUES (1, 1, NULL, '2026-08-23', 'album-at-play', 'generation-new')"""
    )
    conn.execute(
        """INSERT INTO album_spotify_links(
               album_id, spotify_album_id, evidence
           ) VALUES (10, 'album-from-link', 'fixture')"""
    )

    candidates = _scoped_album_candidates(
        conn,
        MetadataRefreshScope(
            generation_id="generation-new",
            track_ids=frozenset({1}),
            album_ids=frozenset({10}),
        ),
    )

    assert candidates == ["album-at-play", "album-from-link", "album-from-track"]


def test_scoped_refresh_retries_global_missing_metadata_and_artist_cover_backlog():
    from backend.domains.metadata.spotify_refresh import (
        MetadataRefreshScope,
        refresh_missing_spotify_metadata,
    )

    conn = _conn()
    conn.executemany(
        """INSERT INTO artists(
               artist_id, artist_name, spotify_artist_id, image_url
           ) VALUES (?, ?, ?, ?)""",
        [
            (1, "Current Artist", "artist-current", "current.jpg"),
            (2, "Retry Artist", "artist-retry", None),
            (3, "Search Retry Artist", None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO tracks(track_id, artist_id, spotify_track_id) VALUES (?, ?, ?)",
        [(1, 1, "track-current"), (2, 2, "track-retry"), (3, 3, "track-search")],
    )
    conn.executemany(
        "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
        [(1, 1), (2, 2), (3, 3)],
    )
    conn.executemany(
        """INSERT INTO plays(
               play_id, track_id, source_album_id, ts_date,
               spotify_track_id_at_play, import_generation_id
           ) VALUES (?, ?, ?, '2026-08-23', ?, ?)""",
        [
            (1, 1, 10, "track-current", "generation-new"),
            (2, 2, 20, "track-retry", "generation-failed"),
            (3, 3, 30, "track-search", "generation-failed"),
        ],
    )
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, spotify_album_id
           ) VALUES ('track-current', 'Current', 'album-current')"""
    )
    conn.execute(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, image_url, total_tracks
           ) VALUES ('album-current', 'Current', 'current.jpg', 1)"""
    )

    class FailingProvider:
        def get_tracks(self, ids, token):
            return None

        def get_albums(self, ids, token):
            return None

        def get_artists_by_ids(self, ids, token):
            return None

    failed = refresh_missing_spotify_metadata(
        conn,
        provider=FailingProvider(),
        access_token="token",
        scope=MetadataRefreshScope(
            generation_id="generation-failed",
            track_ids=frozenset({2, 3}),
            album_ids=frozenset({20, 30}),
            artist_ids=frozenset({2, 3}),
        ),
    )
    assert "tracks_batch_failed" in failed.errors
    assert "artists_batch_failed" in failed.errors

    class Provider:
        tracks_requested: list[str] = []
        albums_requested: list[str] = []
        artists_requested: list[str] = []
        searches: list[str] = []

        def get_tracks(self, ids, token):
            self.tracks_requested.extend(ids)
            return {
                "tracks": [
                    {
                        "id": value,
                        "name": value,
                        "artists": [],
                        "album": {"id": f"album-{value}"},
                    }
                    for value in ids
                ]
            }

        def get_albums(self, ids, token):
            self.albums_requested.extend(ids)
            return {
                "albums": [
                    {
                        "id": value,
                        "name": value,
                        "images": [{"url": f"{value}.jpg"}],
                        "total_tracks": 1,
                    }
                    for value in ids
                ]
            }

        def get_artists_by_ids(self, ids, token):
            self.artists_requested.extend(ids)
            return {
                "artists": [
                    {
                        "id": value,
                        "name": "Retry Artist",
                        "images": [{"url": f"{value}.jpg"}],
                    }
                    for value in ids
                ]
            }

        def search_artist(self, name, token):
            self.searches.append(name)
            return {
                "id": "artist-search-retry",
                "name": name,
                "images": [{"url": "search-retry.jpg"}],
            }

    provider = Provider()
    refresh_missing_spotify_metadata(
        conn,
        provider=provider,
        access_token="token",
        scope=MetadataRefreshScope(
            generation_id="generation-new",
            track_ids=frozenset({1}),
            album_ids=frozenset({10}),
            artist_ids=frozenset({1}),
        ),
    )

    assert "track-retry" in provider.tracks_requested
    assert "album-track-retry" in provider.albums_requested
    assert "artist-retry" in provider.artists_requested
    assert "Search Retry Artist" in provider.searches
