from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.contract


def _find_year_end_route() -> APIRoute:
    for route in app.routes:
        if (
            isinstance(route, APIRoute)
            and route.path == "/api/billboard/year-end"
            and "GET" in route.methods
        ):
            return route
    raise AssertionError("GET /api/billboard/year-end route not found")


def test_year_end_route_declares_response_model():
    route = _find_year_end_route()

    assert route.response_model is not None


def test_year_end_route_publishes_openapi_schema():
    schema = app.openapi()
    response = schema["paths"]["/api/billboard/year-end"]["get"]["responses"]["200"]

    assert "application/json" in response["content"]
    assert "schema" in response["content"]["application/json"]


def test_year_end_endpoint_returns_response_shape(monkeypatch):
    from backend.api.billboard import year_end as api_year_end

    captured_kwargs = {}

    def fake_compute_year_end_staged(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "meta": {
                "year": 2025,
                "available_years": [2025],
                "total_weeks": 1,
                "top_n": kwargs["bb_top_n"],
                "album_top_n": kwargs["bb_album_top_n"],
                "artist_top_n": kwargs["bb_artist_top_n"],
                "week_start_dow": 4,
                "week_start_hour": 0,
                "score_label": "Year-End Score",
            },
            "tracks": [
                {
                    "track_id": 1,
                    "track_name": "Annual Winner",
                    "artist_name": "Artist A",
                    "artist_names": ["Artist A"],
                    "album_name": "Album A",
                    "cover_url": None,
                    "year_end_score": 1000,
                    "year_end_rank": 1,
                    "peak_position": 1,
                    "weeks_on_chart": 1,
                    "weeks_at_peak": 1,
                    "weeks_at_no1": 1,
                    "weeks_top5": 1,
                    "weeks_top10": 1,
                    "chart_plays": 100,
                    "first_week": "2025-01-03T00:00:00",
                    "last_week": "2025-01-03T00:00:00",
                    "true_first_week": "2025-01-03T00:00:00",
                    "is_true_debut_no1": True,
                }
            ],
            "albums": [],
            "artists": [],
            "honors": {"year_end_no1_track": None},
        }

    monkeypatch.setattr(api_year_end, "compute_year_end_staged", fake_compute_year_end_staged)

    response = TestClient(app).get("/api/billboard/year-end?year=2025")

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["year"] == 2025
    assert data["meta"]["top_n"] == 50
    assert data["meta"]["album_top_n"] == 30
    assert data["meta"]["artist_top_n"] == 30
    assert data["tracks"][0]["year_end_rank"] == 1
    assert captured_kwargs["bb_top_n"] == 50
    assert captured_kwargs["bb_album_top_n"] == 30
    assert captured_kwargs["bb_artist_top_n"] == 30


def test_year_end_invalid_year_returns_422_and_request_id(monkeypatch):
    from backend.api.billboard import year_end as api_year_end

    def fake_compute_year_end_staged(**_kwargs):
        raise ValueError("Year 1900 is outside available Billboard years: [2025]")

    monkeypatch.setattr(api_year_end, "compute_year_end_staged", fake_compute_year_end_staged)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/billboard/year-end?year=1900",
        headers={"X-Request-ID": "year-end-invalid"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Year 1900 is outside available Billboard years: [2025]"
    assert response.headers["X-Request-ID"] == "year-end-invalid"
