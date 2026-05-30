"""Unit tests for release cycle service — offline/degraded paths."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSpotifyToken:
    def test_network_failure_returns_none(self, monkeypatch):
        import urllib.error

        import backend.services.release_cycle_service as svc

        monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test-client-secret")

        def raise_url_error(*_args, **_kwargs):
            raise urllib.error.URLError("network disabled")

        monkeypatch.setattr(svc.urllib.request, "urlopen", raise_url_error)
        svc._get_spotify_token.cache_clear()

        result = svc._get_spotify_token()
        assert result is None
