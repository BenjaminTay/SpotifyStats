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
    response_ref = response["content"]["application/json"]["schema"]["$ref"]
    response_schema = schema["components"]["schemas"][response_ref.rsplit("/", 1)[-1]]
    assert response_schema["properties"]["tracks"]["items"]["$ref"].endswith(
        "/BillboardYearEndTrackRow"
    )
    assert response_schema["properties"]["albums"]["items"]["$ref"].endswith(
        "/BillboardYearEndAlbumRow"
    )
    assert response_schema["properties"]["artists"]["items"]["$ref"].endswith(
        "/BillboardYearEndArtistRow"
    )
    track_row = schema["components"]["schemas"]["BillboardYearEndTrackRow"]
    assert "annual_plays" in track_row["properties"]
    assert "chart_plays" in track_row["properties"]


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
                "top_n": kwargs["year_end_top_n"],
                "album_top_n": kwargs["year_end_album_top_n"],
                "artist_top_n": kwargs["year_end_artist_top_n"],
                "year_end_top_n": kwargs["year_end_top_n"],
                "year_end_album_top_n": kwargs["year_end_album_top_n"],
                "year_end_artist_top_n": kwargs["year_end_artist_top_n"],
                "weekly_top_n": kwargs["bb_top_n"],
                "weekly_album_top_n": kwargs["bb_album_top_n"],
                "weekly_artist_top_n": kwargs["bb_artist_top_n"],
                "week_start_dow": 4,
                "week_start_hour": 0,
                "score_label": "Year-End Score",
                "semantics_version": "year_end_v3",
                "coverage_status": "year_to_date",
                "is_complete_year": False,
                "period_start": "2025-01-03T00:00:00",
                "period_end": "2025-01-03T00:00:00",
                "first_billboard_week": "2025-01-03T00:00:00",
                "last_billboard_week": "2025-01-03T00:00:00",
                "observed_weeks": 1,
                "expected_weeks": 52,
                "has_internal_gaps": False,
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
                    "annual_plays": 110,
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

    response = TestClient(app).get(
        "/api/billboard/year-end?year=2025&merge_enabled=false&include_compilations=true"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["year"] == 2025
    assert data["meta"]["top_n"] == 50
    assert data["meta"]["album_top_n"] == 30
    assert data["meta"]["artist_top_n"] == 30
    assert data["meta"]["weekly_top_n"] == captured_kwargs["bb_top_n"]
    assert data["meta"]["weekly_album_top_n"] == captured_kwargs["bb_album_top_n"]
    assert data["meta"]["weekly_artist_top_n"] == captured_kwargs["bb_artist_top_n"]
    assert data["tracks"][0]["year_end_rank"] == 1
    assert data["tracks"][0]["annual_plays"] == 110
    assert captured_kwargs["year_end_top_n"] == 50
    assert captured_kwargs["year_end_album_top_n"] == 30
    assert captured_kwargs["year_end_artist_top_n"] == 30
    assert captured_kwargs["merge_enabled"] is False
    assert captured_kwargs["include_compilations"] is True


def test_year_end_query_cutoffs_do_not_change_output_limits(monkeypatch):
    from backend.api.billboard import year_end as api_year_end

    captured_kwargs = {}

    def fake_compute_year_end_staged(**kwargs):
        captured_kwargs.update(kwargs)
        raise ValueError("stop after parameter capture")

    monkeypatch.setattr(api_year_end, "compute_year_end_staged", fake_compute_year_end_staged)

    response = TestClient(app).get(
        "/api/billboard/year-end?year=2025&bb_top_n=10&bb_album_top_n=8&bb_artist_top_n=6"
    )

    assert response.status_code == 422
    assert captured_kwargs["bb_top_n"] == 10
    assert captured_kwargs["bb_album_top_n"] == 8
    assert captured_kwargs["bb_artist_top_n"] == 6
    assert captured_kwargs["year_end_top_n"] == 50
    assert captured_kwargs["year_end_album_top_n"] == 30
    assert captured_kwargs["year_end_artist_top_n"] == 30


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
