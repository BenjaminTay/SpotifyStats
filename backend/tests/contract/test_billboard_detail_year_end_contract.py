from __future__ import annotations

import pytest

from backend.main import app

pytestmark = pytest.mark.contract


def _response_schema(path: str) -> dict:
    openapi = app.openapi()
    response = openapi["paths"][path]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    name = response["$ref"].rsplit("/", 1)[-1]
    return openapi["components"]["schemas"][name]


@pytest.mark.parametrize(
    "path",
    (
        "/api/billboard/track/{track_id}",
        "/api/billboard/album/{album_name}",
        "/api/billboard/artist/{artist_name}",
    ),
)
def test_detail_openapi_declares_shared_year_end_fields(path: str) -> None:
    properties = _response_schema(path)["properties"]
    assert properties["year_end_status"]["enum"] == ["ready", "warming", "unavailable"]
    assert properties["year_end_summary"]
    assert properties["year_end_history"]["type"] == "array"


def test_detail_response_preserves_ready_year_end_payload(client, monkeypatch) -> None:
    from backend.api.billboard import details

    monkeypatch.setattr(
        details,
        "get_track_detail_view",
        lambda *_args, **_kwargs: {
            "found": True,
            "track_id": 1,
            "track_name": "Track",
            "artist_name": "Artist",
            "cover_url": None,
            "year_end_status": "ready",
            "year_end_summary": {
                "best_year": 2025,
                "best_rank": 2,
                "best_year_is_complete": True,
                "latest_year": 2026,
                "latest_rank": 5,
                "latest_year_is_complete": False,
                "ranked_years": 2,
            },
            "year_end_history": [
                {
                    "year": 2026,
                    "year_end_rank": 5,
                    "coverage_status": "year_to_date",
                    "is_complete_year": False,
                }
            ],
        },
    )

    response = client.get("/api/billboard/track/1", params={"view": "overview"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["year_end_status"] == "ready"
    assert payload["year_end_summary"]["best_rank"] == 2
    assert payload["year_end_history"][0]["coverage_status"] == "year_to_date"


def test_detail_response_defaults_to_unavailable_without_projection_fields(
    client, monkeypatch
) -> None:
    from backend.api.billboard import details

    monkeypatch.setattr(
        details,
        "get_artist_detail_view",
        lambda *_args, **_kwargs: {
            "found": True,
            "artist_name": "Artist",
            "cover_url": None,
        },
    )

    response = client.get("/api/billboard/artist/Artist", params={"view": "summary"})
    assert response.status_code == 200
    assert response.json()["year_end_status"] == "unavailable"
    assert response.json()["year_end_summary"] is None
    assert response.json()["year_end_history"] == []
