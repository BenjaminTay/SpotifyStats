"""Unit tests for release cycle service — offline/degraded paths."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSpotifyToken:
    def test_network_failure_returns_none(self, monkeypatch):
        import backend.services.release_cycle_service as svc

        monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test-client-secret")

        class FailingSpotifyProvider:
            def get_cc_token(self):
                raise OSError("network disabled")

        monkeypatch.setattr(svc, "SpotifyProvider", FailingSpotifyProvider)
        svc._get_spotify_token.cache_clear()

        result = svc._get_spotify_token()
        assert result is None
