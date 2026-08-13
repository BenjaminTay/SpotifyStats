from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import account
from backend.dependencies import get_conn


def test_archive_overview_endpoint_uses_strict_response_contract(monkeypatch) -> None:
    payload = {
        "schema_version": "account_archive_v1",
        "content_version": "account_archive_v1_0",
        "data_revision": "revision",
        "status": "empty",
        "counts": {
            "saved_tracks": 0,
            "saved_albums": 0,
            "saved_artists": 0,
            "saved_shows": 0,
            "playlists": 0,
            "playlist_items": 0,
        },
        "coverage": {
            "saved_tracks_with_date": 0,
            "saved_tracks_with_date_pct": 0,
            "saved_tracks_linked_to_history": 0,
            "saved_tracks_linked_to_history_pct": 0,
            "saved_tracks_with_known_duration": 0,
            "saved_tracks_with_known_duration_pct": 0,
            "known_duration_ms": 0,
        },
        "period": {
            "first_saved_at": None,
            "latest_saved_at": None,
            "first_play_date": None,
            "latest_play_date": None,
        },
        "date_provenance": {"oauth": 0, "manual": 0, "legacy": 0, "missing": 0},
        "capabilities": {
            "collection_browse": "unavailable",
            "collection_timeline": "unavailable",
            "playback_cross_analysis": "unavailable",
        },
        "featured_items": [],
    }
    monkeypatch.setattr(account, "get_archive_overview", lambda _conn: payload)
    test_app = FastAPI()
    test_app.include_router(account.router, prefix="/api")
    test_app.dependency_overrides[get_conn] = lambda: object()

    response = TestClient(test_app).get("/api/account/archive-overview")

    assert response.status_code == 200
    assert response.json() == payload
    route_schema = test_app.openapi()["paths"]["/api/account/archive-overview"]["get"]
    assert "schema" in route_schema["responses"]["200"]["content"]["application/json"]
