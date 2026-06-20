import pytest
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.contract

SPOTIFY_AUTH_JSON_ROUTES = (
    ("GET", "/api/spotify/auth/login"),
    ("GET", "/api/spotify/auth/status"),
    ("DELETE", "/api/spotify/auth/disconnect"),
    ("POST", "/api/spotify/auth/sync"),
    ("GET", "/api/spotify/auth/data"),
    ("GET", "/api/spotify/auth/playing"),
    ("POST", "/api/spotify/auth/sync-all"),
)


def _find_route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_spotify_auth_json_routes_declare_response_models():
    for method, path in SPOTIFY_AUTH_JSON_ROUTES:
        route = _find_route(method, path)

        assert route.response_model is not None, f"{method} {path} missing response_model"


def test_spotify_auth_json_routes_publish_openapi_response_schema():
    schema = app.openapi()
    for method, path in SPOTIFY_AUTH_JSON_ROUTES:
        operation = schema["paths"][path][method.lower()]
        response = operation["responses"]["200"]

        assert "application/json" in response["content"], f"{method} {path} missing JSON content"
        assert "schema" in response["content"]["application/json"], (
            f"{method} {path} missing response schema"
        )


def test_spotify_callback_declares_redirect_response_class():
    route = _find_route("GET", "/api/spotify/auth/callback")

    assert route.response_class is RedirectResponse


def test_spotify_callback_origin_follows_ngrok_redirect_uri_when_frontend_origin_is_default(
    monkeypatch,
):
    from backend.api import spotify_auth as spotify_auth_api
    from backend.core import config

    monkeypatch.setattr(config, "FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setattr(
        config,
        "SPOTIFY_REDIRECT_URI",
        "https://stuffing-nebula-tamer.ngrok-free.dev/api/spotify/auth/callback",
    )

    assert spotify_auth_api._get_frontend_origin() == "https://stuffing-nebula-tamer.ngrok-free.dev"


@pytest.fixture(autouse=True)
def clear_pkce_store():
    from backend.services import spotify_auth

    spotify_auth._pkce_store.clear()
    yield
    spotify_auth._pkce_store.clear()


def test_spotify_login_reports_configuration_error_without_500(monkeypatch, use_seed_db):
    from backend.core import spotify_utils

    monkeypatch.setattr(spotify_utils, "get_client_id", lambda: None)

    with TestClient(app, raise_server_exceptions=False) as local_client:
        response = local_client.get("/api/spotify/auth/login")

    assert response.status_code == 503
    assert response.json() == {"detail": "spotify_client_not_configured"}


def test_spotify_login_creates_pkce_state(monkeypatch, client):
    from backend.services import spotify_auth

    monkeypatch.setattr(
        spotify_auth,
        "generate_pkce_pair",
        lambda: ("verifier-contract", "challenge-contract"),
    )
    monkeypatch.setattr(spotify_auth.secrets, "token_hex", lambda n: "state-contract")

    def fake_build_auth_url(code_challenge, state):
        assert code_challenge == "challenge-contract"
        assert state == "state-contract"
        return "https://spotify.test/auth?state=state-contract"

    monkeypatch.setattr(spotify_auth, "build_auth_url", fake_build_auth_url)

    response = client.get("/api/spotify/auth/login")

    assert response.status_code == 200
    assert response.json() == {
        "auth_url": "https://spotify.test/auth?state=state-contract",
        "state": "state-contract",
    }
    assert spotify_auth._pkce_store == {"state-contract": "verifier-contract"}


def test_spotify_callback_exchanges_code_stores_token_and_redirects(
    monkeypatch,
    client,
    use_seed_db,
):
    from backend.api import spotify_auth as spotify_auth_api
    from backend.core import crypto, spotify_utils
    from backend.core.db import get_db
    from backend.services import spotify_auth

    spotify_auth._pkce_store["state-ok"] = "verifier-ok"
    exchange_calls = []
    sync_calls = []

    def fake_exchange_code_for_tokens(code, code_verifier):
        exchange_calls.append((code, code_verifier))
        return {
            "access_token": "access-contract",
            "refresh_token": "refresh-contract",
            "expires_in": 3600,
            "scope": "user-read-private",
        }

    def fake_sync_all_spotify_data(conn, access_token):
        sync_calls.append(access_token)
        return {"saved_tracks": {"total": 0}}

    monkeypatch.setattr(spotify_auth_api, "_get_frontend_origin", lambda: "http://frontend.test")
    monkeypatch.setattr(spotify_auth, "exchange_code_for_tokens", fake_exchange_code_for_tokens)
    monkeypatch.setattr(spotify_auth, "sync_all_spotify_data", fake_sync_all_spotify_data)

    response = client.get(
        "/api/spotify/auth/callback?code=code-ok&state=state-ok",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://frontend.test/settings?spotify_connected=true"
    assert exchange_calls == [("code-ok", "verifier-ok")]
    assert sync_calls == ["access-contract"]
    assert "state-ok" not in spotify_auth._pkce_store

    conn = get_db(readonly=True)
    try:
        raw_token = conn.execute(
            "SELECT value FROM settings WHERE key = 'spotify_user_token'"
        ).fetchone()[0]
        assert crypto.is_encrypted(raw_token)

        token = spotify_utils._load_user_token_json(conn)
        assert token["access_token"] == "access-contract"
        assert token["refresh_token"] == "refresh-contract"
        assert token["scope"] == "user-read-private"
    finally:
        conn.close()


def test_spotify_callback_invalid_state_redirects_without_exchange(monkeypatch, client):
    from backend.api import spotify_auth as spotify_auth_api
    from backend.services import spotify_auth

    exchange_calls = []

    def fake_exchange_code_for_tokens(code, code_verifier):
        exchange_calls.append((code, code_verifier))
        return {"access_token": "unexpected"}

    monkeypatch.setattr(spotify_auth_api, "_get_frontend_origin", lambda: "http://frontend.test")
    monkeypatch.setattr(spotify_auth, "exchange_code_for_tokens", fake_exchange_code_for_tokens)

    response = client.get(
        "/api/spotify/auth/callback?code=code-bad&state=missing",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"] == "http://frontend.test/settings?spotify_error=invalid_state"
    )
    assert exchange_calls == []
