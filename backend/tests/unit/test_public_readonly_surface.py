from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.core.access_surface import (
    ACCESS_POLICY_VERSION,
    GATEWAY_TOKEN_HEADER,
    PRIVATE_ADMIN_SURFACE,
    PUBLIC_READONLY_SURFACE,
    PUBLIC_SAFE_GET_TEMPLATES,
    PUBLIC_SAFE_POST_PATHS,
    RELEASE_SHA_ENV,
    SURFACE_HEADER,
    TRUSTED_GATEWAY_REQUIRED_ENV,
    public_policy_decision,
    reset_public_readonly_db_guard,
    set_public_readonly_db_guard,
)
from backend.main import app

pytestmark = pytest.mark.unit


def test_public_allowlist_only_references_registered_routes() -> None:
    registered_gets = {
        route.path for route in app.routes if "GET" in (getattr(route, "methods", None) or set())
    }
    registered_posts = {
        route.path for route in app.routes if "POST" in (getattr(route, "methods", None) or set())
    }

    assert PUBLIC_SAFE_GET_TEMPLATES <= registered_gets
    assert PUBLIC_SAFE_POST_PATHS <= registered_posts


def test_public_policy_keeps_only_explicit_analytical_posts() -> None:
    assert public_policy_decision("GET", "/api/home/overview") == "allow"
    assert public_policy_decision("GET", "/api/music/tracks/42/stats") == "allow"
    assert public_policy_decision("GET", "/api/billboard/artist/A/B") == "allow"
    assert public_policy_decision("POST", "/api/billboard/versus/track") == "allow"
    assert public_policy_decision("POST", "/api/billboard/versus/artist") == "allow"
    assert public_policy_decision("POST", "/api/yearly-review/prewarm") == "readonly"
    assert public_policy_decision("POST", "/api/settings/rebuild-agg") == "readonly"
    assert public_policy_decision("PATCH", "/api/metadata/artist-genres/reviews/1") == "disabled"
    assert public_policy_decision("GET", "/api/ai/tasks/example") == "disabled"
    assert public_policy_decision("GET", "/docs") == "disabled"
    assert public_policy_decision("GET", "/api/yearly-review/generation-status") == "disabled"
    # A newly added GET is private until it is explicitly added to the policy.
    assert public_policy_decision("GET", "/api/future-feature") == "disabled"
    assert public_policy_decision("OPTIONS", "/api/future-feature") == "disabled"


def test_runtime_capabilities_are_surface_specific(monkeypatch) -> None:
    monkeypatch.setenv(RELEASE_SHA_ENV, "test-release-sha")
    with TestClient(app) as client:
        private_response = client.get("/api/runtime/capabilities")
        public_response = client.get(
            "/api/runtime/capabilities",
            headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
        )

    assert private_response.status_code == 200
    assert private_response.json() == {
        "surface": "private-admin",
        "profile": "full",
        "policy_version": ACCESS_POLICY_VERSION,
        "release_sha": "test-release-sha",
        "settings": True,
        "editing": True,
        "imports": True,
        "ai": True,
        "spotify_oauth": True,
        "lyrics": True,
        "metadata_governance": True,
        "data_rebuild": True,
        "yearly_generation": True,
        "community_write": True,
        "cover_enrichment": True,
        "account_connection": True,
    }
    assert public_response.status_code == 200
    assert public_response.json() == {
        "surface": "public-readonly",
        "profile": "showcase",
        "policy_version": ACCESS_POLICY_VERSION,
        "release_sha": "test-release-sha",
        "settings": False,
        "editing": False,
        "imports": False,
        "ai": False,
        "spotify_oauth": False,
        "lyrics": False,
        "metadata_governance": False,
        "data_rebuild": False,
        "yearly_generation": False,
        "community_write": False,
        "cover_enrichment": False,
        "account_connection": False,
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


def test_required_gateway_fails_closed_except_health(monkeypatch) -> None:
    monkeypatch.setenv(TRUSTED_GATEWAY_REQUIRED_ENV, "1")
    monkeypatch.setenv("SPOTIFY_STATS_GATEWAY_TOKEN", "server-only-token")
    trusted_public = {
        SURFACE_HEADER: PUBLIC_READONLY_SURFACE,
        GATEWAY_TOKEN_HEADER: "server-only-token",
    }
    trusted_private = {
        SURFACE_HEADER: PRIVATE_ADMIN_SURFACE,
        GATEWAY_TOKEN_HEADER: "server-only-token",
    }

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        missing = client.get("/api/runtime/capabilities")
        invalid = client.get(
            "/api/runtime/capabilities",
            headers={
                SURFACE_HEADER: PRIVATE_ADMIN_SURFACE,
                GATEWAY_TOKEN_HEADER: "forged-token",
            },
        )
        unknown = client.get(
            "/api/runtime/capabilities",
            headers={
                SURFACE_HEADER: "unknown-admin",
                GATEWAY_TOKEN_HEADER: "server-only-token",
            },
        )
        public = client.get("/api/runtime/capabilities", headers=trusted_public)
        private = client.get("/api/runtime/capabilities", headers=trusted_private)

    for response in (missing, invalid, unknown):
        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "untrusted_gateway"
    assert public.status_code == 200
    assert public.json()["surface"] == PUBLIC_READONLY_SURFACE
    assert private.status_code == 200
    assert private.json()["surface"] == PRIVATE_ADMIN_SURFACE


def test_public_db_guard_overrides_explicit_write_connection(monkeypatch, tmp_path) -> None:
    from backend.core import db as db_mod

    db_path = tmp_path / "surface-guard.db"
    setup_conn = sqlite3.connect(db_path)
    setup_conn.execute("CREATE TABLE guard_probe (value TEXT NOT NULL)")
    setup_conn.commit()
    setup_conn.close()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    token = set_public_readonly_db_guard(True)
    public_conn = None
    try:
        public_conn = db_mod.get_db(readonly=False)
        assert public_conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            public_conn.execute("INSERT INTO guard_probe(value) VALUES ('public')")
    finally:
        if public_conn is not None:
            public_conn.close()
        reset_public_readonly_db_guard(token)

    private_conn = db_mod.get_db(readonly=False)
    try:
        private_conn.execute("INSERT INTO guard_probe(value) VALUES ('private')")
        private_conn.commit()
        rows = private_conn.execute("SELECT value FROM guard_probe").fetchall()
        assert [row[0] for row in rows] == ["private"]
    finally:
        private_conn.close()


def test_public_cover_miss_never_triggers_spotify_lookup(monkeypatch) -> None:
    import backend.main as main_module

    called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("public cover miss attempted external enrichment")

    monkeypatch.setattr(main_module, "_get_cover_cdn_url", lambda *_args: None)
    monkeypatch.setattr(main_module, "_search_spotify_cover", fail_if_called)
    with TestClient(app) as client:
        response = client.get(
            "/covers/albums/2147483647.jpg",
            headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
        )

    assert response.status_code == 404
    assert called is False
