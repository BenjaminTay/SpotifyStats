"""Spotify provider — unified interface for Spotify Web API.

Wraps backend.core.spotify_utils functions behind the BaseProvider interface
and uses the shared HttpClient for HTTP transport.
"""

from __future__ import annotations

import base64
from urllib.parse import quote

from backend.core.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from backend.core.spotify_utils import (
    fetch_current_playback,
    fetch_followed_artists,
    fetch_playlists,
    fetch_recently_played,
    fetch_spotify_profile,
    fetch_top_artists,
    fetch_top_tracks,
)
from backend.infrastructure.http.client import HttpClient
from backend.providers.base import BaseProvider, ProviderConfig


class SpotifyProvider(BaseProvider):
    """Provider for Spotify Web API.

    Wraps existing spotify_utils functions as a cohesive provider instance.
    Uses client credentials flow for server-side requests and supports
    user OAuth tokens for user-specific endpoints.
    """

    def __init__(self, config: ProviderConfig | None = None):
        if config is None:
            config = ProviderConfig(
                name="spotify",
                base_url="https://api.spotify.com/v1",
                timeout=30,
                retries=3,
                rate_limit_rps=10.0,
            )
        super().__init__(config)
        self._http = HttpClient(timeout=config.timeout, retries=config.retries)

    def health_check(self) -> bool:
        try:
            token = self.get_cc_token()
            return token is not None
        except Exception:
            return False

    def redact(self) -> dict:
        return {
            "provider": "spotify",
            "client_id": SPOTIFY_CLIENT_ID[:6] + "***" if SPOTIFY_CLIENT_ID else "unset",
            "client_secret": "***" if SPOTIFY_CLIENT_SECRET else "unset",
        }

    def get_cc_token(self) -> str | None:
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            return None

        auth_b64 = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        resp = self._http.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if resp.status != 200:
            return None
        try:
            return resp.json().get("access_token")
        except Exception:
            return None

    def api_get(self, url: str, access_token: str) -> dict | None:
        resp = self._http.get(url, headers={"Authorization": f"Bearer {access_token}"})
        if resp.status != 200:
            return None
        try:
            return resp.json()
        except Exception:
            return None

    def get_albums(self, album_ids: list[str], access_token: str) -> dict | None:
        if not album_ids:
            return {"albums": []}
        url = f"{self.config.base_url}/albums?ids={','.join(album_ids)}"
        return self.api_get(url, access_token)

    def get_tracks(self, track_ids: list[str], access_token: str) -> dict | None:
        if not track_ids:
            return {"tracks": []}
        url = f"{self.config.base_url}/tracks?ids={','.join(track_ids)}"
        return self.api_get(url, access_token)

    def get_artists_by_ids(self, artist_ids: list[str], access_token: str) -> dict | None:
        if not artist_ids:
            return {"artists": []}
        url = f"{self.config.base_url}/artists?ids={','.join(artist_ids)}"
        return self.api_get(url, access_token)

    def search_albums(
        self, album_name: str, artist_name: str, access_token: str, limit: int = 5
    ) -> dict | None:
        query = quote(f"album:{album_name} artist:{artist_name}")
        url = f"{self.config.base_url}/search?q={query}&type=album&limit={limit}"
        return self.api_get(url, access_token)

    def search_album_cover(
        self, album_name: str, artist_name: str, access_token: str
    ) -> str | None:
        """Search Spotify for an album and return the best cover image URL."""
        result = self.search_albums(album_name, artist_name, access_token, limit=3)
        if not result:
            return None
        items = result.get("albums", {}).get("items", [])
        if not items:
            return None
        # Prefer exact name match, then fall back to first result
        for item in items:
            if item.get("name", "").lower() == album_name.lower():
                images = item.get("images", [])
                if images:
                    return images[0].get("url")
        # Fallback: first result with images
        for item in items:
            images = item.get("images", [])
            if images:
                return images[0].get("url")
        return None

    def search_artist_cover(self, artist_name: str, access_token: str) -> str | None:
        """Search Spotify for an artist and return the best cover image URL."""
        query = quote(artist_name)
        url = f"{self.config.base_url}/search?q={query}&type=artist&limit=3"
        result = self.api_get(url, access_token)
        if not result:
            return None
        items = result.get("artists", {}).get("items", [])
        if not items:
            return None
        # Prefer exact name match
        for item in items:
            if item.get("name", "").lower() == artist_name.lower():
                images = item.get("images", [])
                if images:
                    return images[0].get("url")
        # Fallback
        for item in items:
            images = item.get("images", [])
            if images:
                return images[0].get("url")
        return None

    def get_profile(self, access_token: str) -> dict | None:
        return fetch_spotify_profile(access_token)

    def get_top_artists(
        self, access_token: str, time_range: str = "medium_term", limit: int = 50
    ) -> list[dict] | None:
        return fetch_top_artists(access_token, time_range, limit)

    def get_top_tracks(
        self, access_token: str, time_range: str = "medium_term", limit: int = 50
    ) -> list[dict] | None:
        return fetch_top_tracks(access_token, time_range, limit)

    def get_recently_played(self, access_token: str, limit: int = 50) -> list[dict] | None:
        return fetch_recently_played(access_token, limit)

    def get_playback(self, access_token: str) -> dict | None:
        return fetch_current_playback(access_token)

    def get_followed_artists(self, access_token: str) -> list[dict] | None:
        return fetch_followed_artists(access_token)

    def get_playlists(self, access_token: str) -> list[dict] | None:
        return fetch_playlists(access_token)
