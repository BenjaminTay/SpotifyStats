"""MusicBrainz artist genre provider client."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from backend.infrastructure.http.client import HttpClient
from backend.providers.base import BaseProvider, ProviderConfig


class MusicBrainzProvider(BaseProvider):
    """Read artist genre evidence from MusicBrainz search results."""

    BASE_URL = "https://musicbrainz.org/ws/2"
    USER_AGENT = "SpotifyStats/1.0 (artist-genre-resolution)"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        http_client: HttpClient | None = None,
    ):
        if config is None:
            config = ProviderConfig(
                name="musicbrainz",
                base_url=self.BASE_URL,
                timeout=8,
                retries=1,
                rate_limit_rps=1.0,
            )
        super().__init__(config)
        self._http = http_client or HttpClient(
            timeout=config.timeout,
            retries=config.retries,
            user_agent=self.USER_AGENT,
        )

    def health_check(self) -> bool:
        try:
            return bool(self.get_artist_genres("Radiohead"))
        except Exception:
            return False

    def redact(self) -> dict:
        return {"provider": "musicbrainz", "base_url": self.config.base_url}

    def get_artist_genres(self, artist_name: str, limit: int = 3) -> list[dict]:
        """Search MusicBrainz and normalize artist tags/genres."""
        if not artist_name.strip():
            return []

        params = {
            "query": f'artist:"{artist_name}"',
            "fmt": "json",
            "limit": str(limit),
        }
        try:
            resp = self._http.get(
                f"{self.config.base_url}/artist?{urlencode(params)}",
                headers={"Accept": "application/json"},
            )
            if resp.status != 200:
                return []
            payload = resp.json()
            artists = payload.get("artists", [])
        except Exception:
            return []

        if not isinstance(artists, list):
            return []

        evidence = []
        for artist in artists:
            if not isinstance(artist, dict):
                continue
            raw_genres = _parse_musicbrainz_genres(artist)
            normalized_genres = _dedupe_normalized([item["name"] for item in raw_genres])
            if not normalized_genres:
                continue
            source_key = str(artist.get("id") or artist.get("name") or artist_name)
            score = _to_float(artist.get("score"))
            evidence.append(
                {
                    "source": "musicbrainz",
                    "source_key": source_key,
                    "raw_genres": raw_genres,
                    "normalized_genres": normalized_genres,
                    "primary_genre": normalized_genres[0],
                    "confidence": _confidence_from_evidence(score, raw_genres),
                    "evidence_url": f"https://musicbrainz.org/artist/{source_key}",
                    "evidence_summary": _summary(
                        "MusicBrainz tags/genres",
                        str(artist.get("name") or artist_name),
                        raw_genres,
                    ),
                    "hints": {"country": artist.get("country")},
                }
            )
        return evidence


def _parse_musicbrainz_genres(artist: dict) -> list[dict]:
    parsed = []
    for source_type in ("genres", "tags"):
        items = artist.get(source_type, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            parsed.append(
                {
                    "name": name,
                    "count": _to_int(item.get("count")),
                    "type": source_type.rstrip("s"),
                }
            )
    return parsed


def _dedupe_normalized(names: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for name in names:
        value = " ".join(name.lower().strip().split())
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def _confidence_from_evidence(score: float, raw_genres: list[dict]) -> float:
    if score <= 0 or not raw_genres:
        return 0.5
    search_confidence = max(0.2, min(0.82, 0.32 + (score / 100) * 0.5))
    max_count = max((int(item.get("count") or 0) for item in raw_genres), default=0)
    support_adjustment = 0.0
    if max_count >= 25:
        support_adjustment += 0.06
    elif max_count >= 5:
        support_adjustment += 0.03
    elif max_count <= 0:
        support_adjustment -= 0.08
    has_musicbrainz_genre = any(item.get("type") == "genre" for item in raw_genres)
    support_adjustment += 0.04 if has_musicbrainz_genre else -0.12
    return round(max(0.35, min(0.88, search_confidence + support_adjustment)), 3)


def _summary(prefix: str, artist_name: str, raw_genres: list[dict]) -> str:
    tags = ", ".join(f"{item['name']} ({item['count']})" for item in raw_genres[:5])
    return f"{prefix} for {artist_name}: {tags}" if tags else f"{prefix} for {artist_name}"


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
