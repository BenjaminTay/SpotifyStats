from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.contract


@pytest.fixture
def client(use_seed_db: str) -> Iterator[TestClient]:
    del use_seed_db
    with TestClient(app) as test_client:
        yield test_client


def test_music_search_endpoint_returns_grouped_results(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Song 4", "kind": "track"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Alpha Song 4"
    assert data["limit_per_type"] == 5
    assert data["total"] == 1
    assert data["tracks"][0]["label"] == "Alpha Song 4"
    assert data["tracks"][0]["href"] == "/music/tracks/4"
    assert data["tracks"][0]["cover_url"] == "/covers/albums/1.jpg"
    assert data["albums"] == []
    assert data["artists"] == []
    assert response.headers["x-request-id"]


def test_music_search_endpoint_accepts_kind_filter(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Debut", "kind": "album"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tracks"] == []
    assert data["albums"][0]["href"] == "/music/albums/Alpha%20Debut?artist=Alpha"
    assert data["albums"][0]["cover_url"] == "/covers/albums/1.jpg"
    assert data["artists"] == []


def test_music_search_endpoint_can_include_chart_shape(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Song 4", "kind": "track", "include_chart": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tracks"][0]["label"] == "Alpha Song 4"
    assert "chart" in data["tracks"][0]


def test_music_search_endpoint_rejects_oversized_limit(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "Alpha Song 4", "limit_per_type": 50})

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_music_search_endpoint_rejects_invalid_kind(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "Alpha Song 4", "kind": "playlist"})

    assert response.status_code == 422
    assert response.headers["x-request-id"]
