from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.main import app

pytestmark = pytest.mark.contract

SETTINGS_MUTATION_ROUTES = (
    ("PUT", "/api/settings"),
    ("POST", "/api/settings/rebuild-agg"),
    ("POST", "/api/settings/clear-translation-cache"),
    ("POST", "/api/settings/llm-profiles"),
    ("POST", "/api/settings/llm-profiles/{profile_id}/apply"),
    ("DELETE", "/api/settings/llm-profiles/{profile_id}"),
)


def _find_route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_settings_mutation_routes_declare_response_models():
    for method, path in SETTINGS_MUTATION_ROUTES:
        route = _find_route(method, path)

        assert route.response_model is not None, f"{method} {path} missing response_model"


def test_settings_mutation_routes_publish_openapi_response_schema():
    schema = app.openapi()
    for method, path in SETTINGS_MUTATION_ROUTES:
        operation = schema["paths"][path][method.lower()]
        response = operation["responses"]["200"]

        assert "application/json" in response["content"], f"{method} {path} missing JSON content"
        assert "schema" in response["content"]["application/json"], (
            f"{method} {path} missing response schema"
        )


def test_settings_update_persists_values_and_redacts_secrets(client):
    response = client.put(
        "/api/settings",
        json={
            "min_ms": 45000,
            "music_only": False,
            "bb_top_n": 40,
            "llm_enabled": True,
            "llm_provider": "openai",
            "llm_model": "gpt-test",
            "llm_api_key": "test-api-key",  # pragma: allowlist secret
            "llm_base_url": "https://llm.example.test/v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["min_ms"] == 45000
    assert body["music_only"] is False
    assert body["bb_top_n"] == 40
    assert body["llm_enabled"] is True
    assert body["llm_provider"] == "openai"
    assert body["llm_model"] == "gpt-test"
    assert body["has_llm_key"] is True
    assert "llm_api_key" not in body
    assert "llm_base_url" not in body

    read_back = client.get("/api/settings").json()
    assert read_back["min_ms"] == 45000
    assert read_back["music_only"] is False
    assert read_back["has_llm_key"] is True
    assert "llm_api_key" not in read_back
    assert "llm_base_url" not in read_back


@pytest.mark.parametrize(
    "payload",
    [
        {"min_ms": -1},
        {"bb_top_n": 4},
        {"bb_album_top_n": 101},
        {"bb_artist_top_n": 4},
        {"bb_week_start_dow": 7},
        {"bb_week_start_hour": 24},
    ],
)
def test_settings_update_rejects_out_of_range_values(client, payload):
    response = client.put("/api/settings", json=payload)

    assert response.status_code == 422


def test_llm_profile_crud_apply_and_secret_redaction(client):
    create_response = client.post(
        "/api/settings/llm-profiles",
        json={
            "profile_name": "Contract Profile",
            "llm_provider": "openai",
            "llm_model": "gpt-contract",
            "llm_api_key": "profile-api-key",  # pragma: allowlist secret
            "llm_base_url": "https://profiles.example.test/v1",
        },
    )
    assert create_response.status_code == 200
    profile_id = create_response.json()["id"]

    duplicate_response = client.post(
        "/api/settings/llm-profiles",
        json={"profile_name": "Contract Profile", "llm_provider": "openai"},
    )
    assert duplicate_response.status_code == 409

    detail_response = client.get(f"/api/settings/llm-profiles/{profile_id}")
    detail = detail_response.json()
    assert detail_response.status_code == 200
    assert detail["profile_name"] == "Contract Profile"
    assert detail["llm_base_url"] == "https://profiles.example.test/v1"
    assert detail["has_llm_key"] is True
    assert "llm_api_key" not in detail

    list_response = client.get("/api/settings/llm-profiles")
    listed = list_response.json()
    assert list_response.status_code == 200
    assert listed[0]["id"] == profile_id
    assert "llm_api_key" not in listed[0]
    assert "llm_base_url" not in listed[0]

    update_response = client.put(
        f"/api/settings/llm-profiles/{profile_id}",
        json={
            "llm_model": "gpt-contract-updated",
            "llm_api_key": "updated-api-key",  # pragma: allowlist secret
        },
    )
    updated = update_response.json()
    assert update_response.status_code == 200
    assert updated["llm_model"] == "gpt-contract-updated"
    assert updated["has_llm_key"] is True
    assert "llm_api_key" not in updated

    apply_response = client.post(f"/api/settings/llm-profiles/{profile_id}/apply")
    assert apply_response.status_code == 200
    assert apply_response.json() == {"status": "applied", "profile_id": profile_id}

    settings = client.get("/api/settings").json()
    assert settings["llm_provider"] == "openai"
    assert settings["llm_model"] == "gpt-contract-updated"
    assert settings["has_llm_key"] is True
    assert "llm_api_key" not in settings

    delete_response = client.delete(f"/api/settings/llm-profiles/{profile_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted"}

    missing_response = client.get(f"/api/settings/llm-profiles/{profile_id}")
    assert missing_response.status_code == 404


def test_clear_translation_cache_returns_deleted_count(client):
    response = client.post("/api/settings/clear-translation-cache")

    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert isinstance(response.json()["deleted_count"], int)
