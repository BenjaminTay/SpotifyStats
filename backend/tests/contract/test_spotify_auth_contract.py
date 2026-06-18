import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.contract


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
