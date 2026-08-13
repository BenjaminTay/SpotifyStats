from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.access_surface import (
    PUBLIC_READONLY_SURFACE,
    SURFACE_HEADER,
    public_policy_decision,
)
from backend.main import app

pytestmark = pytest.mark.unit


def test_public_policy_keeps_only_explicit_analytical_posts() -> None:
    assert public_policy_decision("GET", "/api/home/overview") == "allow"
    assert public_policy_decision("POST", "/api/billboard/versus/track") == "allow"
    assert public_policy_decision("POST", "/api/billboard/versus/artist") == "allow"
    assert public_policy_decision("POST", "/api/yearly-review/prewarm") == "readonly"
    assert public_policy_decision("POST", "/api/settings/rebuild-agg") == "readonly"
    assert public_policy_decision("PATCH", "/api/metadata/artist-genres/reviews/1") == "disabled"
    assert public_policy_decision("GET", "/api/ai/tasks/example") == "disabled"
    assert public_policy_decision("GET", "/docs") == "disabled"


def test_runtime_capabilities_are_surface_specific() -> None:
    with TestClient(app) as client:
        private_response = client.get("/api/runtime/capabilities")
        public_response = client.get(
            "/api/runtime/capabilities",
            headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
        )

    assert private_response.status_code == 200
    assert private_response.json() == {
        "surface": "private-admin",
        "settings": True,
        "editing": True,
        "imports": True,
        "ai": True,
        "spotify_oauth": True,
        "lyrics": True,
    }
    assert public_response.status_code == 200
    assert public_response.json() == {
        "surface": "public-readonly",
        "settings": False,
        "editing": False,
        "imports": False,
        "ai": False,
        "spotify_oauth": False,
        "lyrics": False,
    }


def test_public_surface_rejects_writes_and_hides_disabled_features() -> None:
    headers = {SURFACE_HEADER: PUBLIC_READONLY_SURFACE}
    with TestClient(app) as client:
        write_response = client.put("/api/settings", headers=headers, json={})
        ai_response = client.get("/api/ai/tasks/not-a-real-task", headers=headers)
        settings_response = client.get("/api/settings", headers=headers)

    assert write_response.status_code == 403
    assert write_response.json()["detail"]["error"] == "public_readonly"
    assert ai_response.status_code == 404
    assert settings_response.status_code == 200
    settings = settings_response.json()
    assert settings["spotify_connected"] is False
    assert settings["spotify_profile"] is None
    assert settings["llm_enabled"] is False
    assert settings["has_llm_key"] is False
