"""Genius provider — unified interface for Genius API.

Wraps the existing GeniusClient behind the BaseProvider interface.
"""

from __future__ import annotations

from backend.core.config import GENIUS_ACCESS_TOKEN, GENIUS_PROXY, HTTPS_PROXY
from backend.core.genius.client import GeniusClient
from backend.providers.base import BaseProvider, ProviderConfig


class GeniusProvider(BaseProvider):
    """Provider for Genius API (lyrics, song metadata, artist info)."""

    def __init__(self, config: ProviderConfig | None = None):
        if config is None:
            config = ProviderConfig(
                name="genius",
                base_url="https://api.genius.com",
                timeout=30,
                retries=3,
                rate_limit_rps=5.0,
                https_proxy=GENIUS_PROXY or HTTPS_PROXY or "",
            )
        super().__init__(config)
        self._client: GeniusClient | None = None

    def _get_client(self) -> GeniusClient | None:
        if self._client is None:
            if not GENIUS_ACCESS_TOKEN:
                return None
            proxy_url = GENIUS_PROXY or HTTPS_PROXY
            proxy = {"https": proxy_url} if proxy_url else None
            self._client = GeniusClient(access_token=GENIUS_ACCESS_TOKEN, proxy=proxy)
        return self._client

    def health_check(self) -> bool:
        try:
            client = self._get_client()
            if client is None:
                return False
            result = client.get_song(title="test", artist="test")
            return result is not None or True  # search returns None for fake songs, ok
        except Exception:
            return False

    def redact(self) -> dict:
        return {
            "provider": "genius",
            "access_token": GENIUS_ACCESS_TOKEN[:6] + "***" if GENIUS_ACCESS_TOKEN else "unset",
        }

    def get_song(self, title: str, artist: str):
        client = self._get_client()
        if client is None:
            return None
        return client.get_song(title=title, artist=artist)

    def get_artist(self, artist_id: int):
        client = self._get_client()
        if client is None:
            return None
        return client.get_artist(artist_id)  # type: ignore[attr-defined]

    def search(self, query: str):
        client = self._get_client()
        if client is None:
            return None
        return client.search(query)
