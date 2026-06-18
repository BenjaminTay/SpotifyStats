from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class _FakeConn:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_spotify_playing_uses_writable_connection_for_token_refresh(monkeypatch):
    """Live playback can refresh and persist an expired Spotify token."""
    from backend.api import spotify_auth

    conn = _FakeConn()
    readonly_flags = []

    def fake_get_db(readonly=True):
        readonly_flags.append(readonly)
        return conn

    def fake_get_live_playback(received_conn):
        assert received_conn is conn
        return {"is_playing": False}

    monkeypatch.setattr(spotify_auth, "get_db", fake_get_db, raising=False)
    monkeypatch.setattr(spotify_auth, "get_live_playback", fake_get_live_playback)

    assert spotify_auth.spotify_playing() == {"is_playing": False}
    assert readonly_flags == [False]
    assert conn.closed is True
