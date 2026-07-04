"""Last.fm artist genre provider client."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from backend.core.config import LASTFM_API_KEY
from backend.infrastructure.http.client import HttpClient
from backend.providers.base import BaseProvider, ProviderConfig


class LastFMProvider(BaseProvider):
    """Read artist genre evidence from Last.fm top tags."""

    BASE_URL = "https://ws.audioscrobbler.com/2.0/"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        api_key: str | None = None,
        http_client: HttpClient | None = None,
    ):
        if config is None:
            config = ProviderConfig(
                name="lastfm",
                base_url=self.BASE_URL,
                timeout=10,
                retries=1,
                rate_limit_rps=5.0,
            )
        super().__init__(config)
        self._api_key = LASTFM_API_KEY if api_key is None else api_key
        self._http = http_client or HttpClient(timeout=config.timeout, retries=config.retries)

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            return bool(self.get_artist_genres("Radiohead"))
        except Exception:
            return False

    def redact(self) -> dict:
        return {
            "provider": "lastfm",
            "api_key": self._api_key[:6] + "***" if self._api_key else "unset",
        }

    def get_artist_genres(self, artist_name: str, limit: int = 10) -> list[dict]:
        """Fetch and normalize Last.fm top tags for an artist."""
        if not self._api_key or not artist_name.strip():
            return []

        params = {
            "method": "artist.getTopTags",
            "artist": artist_name,
            "api_key": self._api_key,
            "format": "json",
        }
        try:
            resp = self._http.get(f"{self.config.base_url}?{urlencode(params)}")
            if resp.status != 200:
                return []
            payload = resp.json()
            tags = payload.get("toptags", {}).get("tag", [])
            if isinstance(tags, dict):
                tags = [tags]
            raw_genres = _parse_lastfm_tags(tags, limit=limit)
        except Exception:
            return []

        normalized_genres = _dedupe_normalized([tag["name"] for tag in raw_genres])
        if not normalized_genres:
            return []

        top_count = raw_genres[0].get("count", 0) if raw_genres else 0
        return [
            {
                "source": "lastfm",
                "source_key": artist_name,
                "raw_genres": raw_genres,
                "normalized_genres": normalized_genres,
                "primary_genre": normalized_genres[0],
                "confidence": _confidence_from_count(top_count),
                "evidence_url": f"https://www.last.fm/music/{quote(artist_name, safe='')}",
                "evidence_summary": _summary("Top Last.fm tags", raw_genres),
            }
        ]


_NON_GENRE_TAGS = {
    "seen live",
    "favorite",
    "favourite",
    "favorites",
    "favourites",
    "albums i own",
    "spotify",
}
_NON_GENRE_TOKENS = {
    "australian",
    "british",
    "canadian",
    "american",
    "german",
    "french",
    "swedish",
    "norwegian",
    "danish",
    "female",
    "male",
    "singer",
    "songwriter",
    "beautiful",
    "sad",
    "happy",
    "chill",
    "love",
}
_GENRE_HINTS = {
    "pop",
    "rock",
    "hop",
    "rap",
    "r&b",
    "soul",
    "folk",
    "country",
    "blues",
    "jazz",
    "metal",
    "punk",
    "indie",
    "electronic",
    "dance",
    "house",
    "techno",
    "ambient",
    "classical",
    "reggae",
    "latin",
    "funk",
    "disco",
    "gospel",
    "worship",
    "alternative",
}


def _is_genre_tag(name: str) -> bool:
    value = " ".join(name.lower().strip().split())
    if not value or value in _NON_GENRE_TAGS:
        return False
    if value.endswith("s") and len(value) == 5 and value[:4].isdigit():
        return False
    tokens = set(value.replace("-", " ").split())
    if tokens & _NON_GENRE_TOKENS:
        return False
    return any(hint in value for hint in _GENRE_HINTS)


def _parse_lastfm_tags(tags: Any, limit: int) -> list[dict]:
    parsed: list[dict] = []
    if not isinstance(tags, list):
        return parsed

    for tag in tags:
        if not isinstance(tag, dict):
            continue
        name = str(tag.get("name", "")).strip()
        if not name or not _is_genre_tag(name):
            continue
        parsed.append({"name": name, "count": _to_int(tag.get("count"))})
        if len(parsed) >= limit:
            break
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


def _confidence_from_count(count: int) -> float:
    if count <= 0:
        return 0.5
    return round(min(0.95, 0.55 + (count / (count + 100)) * 0.4), 3)


def _summary(prefix: str, raw_genres: list[dict]) -> str:
    tags = ", ".join(f"{item['name']} ({item['count']})" for item in raw_genres[:5])
    return f"{prefix}: {tags}" if tags else prefix


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
