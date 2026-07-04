"""Wikidata artist genre provider client."""

from __future__ import annotations

from urllib.parse import urlencode

from backend.infrastructure.http.client import HttpClient
from backend.providers.base import BaseProvider, ProviderConfig


class WikidataProvider(BaseProvider):
    """Read artist genre evidence from Wikidata SPARQL bindings."""

    BASE_URL = "https://query.wikidata.org/sparql"
    USER_AGENT = "SpotifyStats/1.0 (artist-genre-resolution)"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        http_client: HttpClient | None = None,
    ):
        if config is None:
            config = ProviderConfig(
                name="wikidata",
                base_url=self.BASE_URL,
                timeout=10,
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
        return {"provider": "wikidata", "base_url": self.config.base_url}

    def get_artist_genres(self, artist_name: str, limit: int = 20) -> list[dict]:
        """Query Wikidata for artist genre labels and simple contextual hints."""
        if not artist_name.strip():
            return []

        query = _build_artist_genre_query(artist_name, limit)
        try:
            resp = self._http.get(
                f"{self.config.base_url}?{urlencode({'query': query, 'format': 'json'})}",
                headers={"Accept": "application/sparql-results+json"},
            )
            if resp.status != 200:
                return []
            payload = resp.json()
            bindings = payload.get("results", {}).get("bindings", [])
        except Exception:
            return []

        if not isinstance(bindings, list):
            return []
        return _parse_bindings(bindings, fallback_artist_name=artist_name)


def _build_artist_genre_query(artist_name: str, limit: int) -> str:
    escaped_artist = artist_name.replace("\\", "\\\\").replace('"', '\\"')
    return f"""
SELECT ?artist ?artistLabel ?genreLabel ?countryLabel ?languageLabel WHERE {{
  ?artist rdfs:label "{escaped_artist}"@en.
  {{
    ?artist wdt:P31 ?artistType.
    VALUES ?artistType {{ wd:Q639669 wd:Q215380 wd:Q2088357 wd:Q5741069 }}
  }}
  UNION
  {{
    ?artist wdt:P31 wd:Q5;
            wdt:P106 ?occupation.
    VALUES ?occupation {{ wd:Q177220 wd:Q36834 wd:Q639669 wd:Q753110 wd:Q488205 }}
  }}
  OPTIONAL {{ ?artist wdt:P136 ?genre. }}
  OPTIONAL {{ ?artist wdt:P27|wdt:P495 ?country. }}
  OPTIONAL {{ ?artist wdt:P1412 ?language. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
""".strip()


def _parse_bindings(bindings: list[dict], fallback_artist_name: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        source_key = _extract_entity_id(_binding_value(binding, "artist"))
        genre = _binding_value(binding, "genreLabel")
        if not source_key or not genre:
            continue
        record = grouped.setdefault(
            source_key,
            {
                "artist_name": _binding_value(binding, "artistLabel") or fallback_artist_name,
                "raw_genres": [],
                "countries": [],
                "languages": [],
            },
        )
        _append_unique(record["raw_genres"], {"name": genre})
        _append_unique(record["countries"], _binding_value(binding, "countryLabel"))
        _append_unique(record["languages"], _binding_value(binding, "languageLabel"))

    evidence = []
    for source_key, record in grouped.items():
        raw_genres = record["raw_genres"]
        normalized_genres = _dedupe_normalized([item["name"] for item in raw_genres])
        if not normalized_genres:
            continue
        evidence.append(
            {
                "source": "wikidata",
                "source_key": source_key,
                "raw_genres": raw_genres,
                "normalized_genres": normalized_genres,
                "primary_genre": normalized_genres[0],
                "confidence": 0.75,
                "evidence_url": f"https://www.wikidata.org/wiki/{source_key}",
                "evidence_summary": _summary(
                    str(record["artist_name"]),
                    raw_genres,
                    source_key,
                ),
                "hints": {
                    "countries": record["countries"],
                    "languages": record["languages"],
                },
            }
        )
    return evidence


def _binding_value(binding: dict, key: str) -> str:
    value = binding.get(key, {})
    if not isinstance(value, dict):
        return ""
    return str(value.get("value", "")).strip()


def _extract_entity_id(value: str) -> str:
    if not value:
        return ""
    return value.rsplit("/", maxsplit=1)[-1]


def _append_unique(items: list, value):
    if value and value not in items:
        items.append(value)


def _dedupe_normalized(names: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for name in names:
        value = " ".join(name.lower().strip().split())
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def _summary(artist_name: str, raw_genres: list[dict], source_key: str) -> str:
    tags = ", ".join(item["name"] for item in raw_genres[:5])
    return f"Wikidata genres for {artist_name} ({source_key}): {tags}"
