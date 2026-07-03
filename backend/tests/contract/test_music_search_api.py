from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_conn
from backend.main import app

pytestmark = pytest.mark.contract


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            duration_ms INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER NOT NULL,
            ms_played INTEGER,
            source_album_id INTEGER
        );

        INSERT INTO artists(artist_id, artist_name, image_path, image_url)
        VALUES (1, 'Olivia Rodrigo', NULL, 'https://example.test/olivia.jpg');
        INSERT INTO albums(album_id, album_name, artist_id, image_path, image_url)
        VALUES (10, 'GUTS', 1, NULL, 'https://example.test/guts.jpg');
        INSERT INTO tracks(track_id, track_name, artist_id, album_id, duration_ms) VALUES
            (100, 'vampire', 1, 10, 219724);
        INSERT INTO plays(play_id, track_id, ms_played, source_album_id) VALUES
            (1, 100, 200000, NULL),
            (2, 100, 190000, NULL);
        """
    )
    return conn


@pytest.fixture
def client() -> Iterator[TestClient]:
    conn = _conn()

    def override_get_conn() -> Iterator[sqlite3.Connection]:
        yield conn

    app.dependency_overrides[get_conn] = override_get_conn
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)
        conn.close()


def test_music_search_endpoint_returns_grouped_results(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "vamp"})

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "vamp"
    assert data["limit_per_type"] == 5
    assert data["total"] == 1
    assert data["tracks"][0]["label"] == "vampire"
    assert data["tracks"][0]["href"] == "/music/tracks/100"
    assert data["tracks"][0]["cover_url"] == "/covers/albums/10.jpg"
    assert data["albums"] == []
    assert data["artists"] == []
    assert response.headers["x-request-id"]


def test_music_search_endpoint_accepts_kind_filter(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "guts", "kind": "album"})

    assert response.status_code == 200
    data = response.json()
    assert data["tracks"] == []
    assert data["albums"][0]["href"] == "/music/albums/GUTS?artist=Olivia%20Rodrigo"
    assert data["albums"][0]["cover_url"] == "/covers/albums/10.jpg"
    assert data["artists"] == []


def test_music_search_endpoint_can_include_chart_shape(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "vamp", "kind": "track", "include_chart": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tracks"][0]["label"] == "vampire"
    assert "chart" in data["tracks"][0]


def test_music_search_endpoint_rejects_oversized_limit(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "vamp", "limit_per_type": 50})

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_music_search_endpoint_rejects_invalid_kind(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "vamp", "kind": "playlist"})

    assert response.status_code == 422
    assert response.headers["x-request-id"]
