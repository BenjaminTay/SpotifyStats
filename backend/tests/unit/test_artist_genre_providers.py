"""Unit tests for external artist genre provider clients."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, error: Exception | None = None):
        self.status = status
        self._payload = payload or {}
        self._error = error

    def json(self):
        if self._error:
            raise self._error
        return self._payload


class FakeHttpClient:
    def __init__(self, *responses: FakeResponse):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def get(self, url: str, headers: dict | None = None):
        self.requests.append({"url": url, "headers": headers or {}})
        return self.responses.pop(0)


def test_lastfm_without_api_key_is_disabled():
    from backend.providers.base import BaseProvider
    from backend.providers.lastfm.client import LastFMProvider

    provider = LastFMProvider(api_key="", http_client=FakeHttpClient())

    assert isinstance(provider, BaseProvider)
    assert provider.health_check() is False
    assert provider.get_artist_genres("Radiohead") == []


def test_lastfm_parses_top_tags_into_genre_evidence():
    from backend.providers.lastfm.client import LastFMProvider

    http = FakeHttpClient(
        FakeResponse(
            200,
            {
                "toptags": {
                    "tag": [
                        {"name": "Rock", "count": "100"},
                        {"name": "Alternative Rock", "count": 64},
                        {"name": "rock", "count": 7},
                    ]
                }
            },
        )
    )

    result = LastFMProvider(api_key="lfm-secret-123", http_client=http).get_artist_genres(
        "Radiohead"
    )

    assert len(result) == 1
    evidence = result[0]
    assert evidence["source"] == "lastfm"
    assert evidence["source_key"] == "Radiohead"
    assert evidence["primary_genre"] == "rock"
    assert evidence["normalized_genres"] == ["rock", "alternative rock"]
    assert evidence["raw_genres"][0] == {"name": "Rock", "count": 100}
    assert evidence["confidence"] > 0
    assert "last.fm" in evidence["evidence_url"].lower()
    assert "Rock" in evidence["evidence_summary"]
    assert "artist.getTopTags" in http.requests[0]["url"]


def test_lastfm_filters_non_genre_tags_and_encodes_evidence_url():
    from backend.providers.lastfm.client import LastFMProvider

    http = FakeHttpClient(
        FakeResponse(
            200,
            {
                "toptags": {
                    "tag": [
                        {"name": "seen live", "count": 1000},
                        {"name": "2010s", "count": 900},
                        {"name": "Australian", "count": 800},
                        {"name": "Hard Rock", "count": 700},
                        {"name": "Blues", "count": 650},
                    ]
                }
            },
        )
    )

    result = LastFMProvider(api_key="lfm-secret-123", http_client=http).get_artist_genres("AC/DC")

    assert result[0]["normalized_genres"] == ["hard rock", "blues"]
    assert result[0]["raw_genres"][0]["name"] == "Hard Rock"
    assert result[0]["evidence_url"].endswith("/AC%2FDC")


def test_lastfm_redact_does_not_leak_api_key():
    from backend.providers.lastfm.client import LastFMProvider

    redacted = LastFMProvider(api_key="lfm-secret-123").redact()

    assert "lfm-secret-123" not in str(redacted)
    assert redacted["api_key"].endswith("***")


def test_musicbrainz_prioritizes_genres_before_folksonomy_tags():
    from backend.providers.musicbrainz.client import MusicBrainzProvider

    http = FakeHttpClient(
        FakeResponse(
            200,
            {
                "artists": [
                    {
                        "id": "mbid-radiohead",
                        "name": "Radiohead",
                        "score": "100",
                        "country": "GB",
                        "tags": [
                            {"name": "Alternative Rock", "count": 42},
                            {"name": "art rock", "count": 9},
                        ],
                        "genres": [{"name": "Experimental Rock", "count": 5}],
                    },
                    {
                        "id": "mbid-empty",
                        "name": "Radio Head",
                        "score": "80",
                        "tags": [],
                        "genres": [],
                    },
                ]
            },
        )
    )

    result = MusicBrainzProvider(http_client=http).get_artist_genres("Radiohead")

    assert len(result) == 1
    evidence = result[0]
    assert evidence["source"] == "musicbrainz"
    assert evidence["source_key"] == "mbid-radiohead"
    assert evidence["primary_genre"] == "experimental rock"
    assert evidence["normalized_genres"] == [
        "experimental rock",
        "alternative rock",
        "art rock",
    ]
    assert evidence["hints"]["country"] == "GB"
    assert "MusicBrainz" in evidence["evidence_summary"]
    assert "fmt=json" in http.requests[0]["url"]


def test_musicbrainz_falls_back_to_tags_when_genres_are_absent():
    from backend.providers.musicbrainz.client import MusicBrainzProvider

    http = FakeHttpClient(
        FakeResponse(
            200,
            {
                "artists": [
                    {
                        "id": "mbid-tag-only",
                        "name": "Tag Only",
                        "score": "90",
                        "tags": [{"name": "Indie Rock", "count": 10}],
                        "genres": [],
                    }
                ]
            },
        )
    )

    result = MusicBrainzProvider(http_client=http).get_artist_genres("Tag Only")

    assert result[0]["primary_genre"] == "indie rock"
    assert result[0]["normalized_genres"] == ["indie rock"]


def test_musicbrainz_tag_only_evidence_is_below_auto_approval_threshold():
    from backend.providers.musicbrainz.client import MusicBrainzProvider
    from backend.services.artist_genre_backfill_service import EXTERNAL_APPROVAL_MIN_CONFIDENCE

    http = FakeHttpClient(
        FakeResponse(
            200,
            {
                "artists": [
                    {
                        "id": "mbid-tag-only",
                        "name": "Tag Only",
                        "score": "100",
                        "tags": [{"name": "Pop", "count": 10}],
                        "genres": [],
                    }
                ]
            },
        )
    )

    result = MusicBrainzProvider(http_client=http).get_artist_genres("Tag Only")

    assert result[0]["confidence"] < EXTERNAL_APPROVAL_MIN_CONFIDENCE


def test_wikidata_parses_sparql_bindings_into_genre_evidence():
    from backend.providers.wikidata.client import WikidataProvider

    http = FakeHttpClient(
        FakeResponse(
            200,
            {
                "results": {
                    "bindings": [
                        {
                            "artist": {"value": "http://www.wikidata.org/entity/Q123"},
                            "artistLabel": {"value": "Radiohead"},
                            "genreLabel": {"value": "Alternative Rock"},
                            "countryLabel": {"value": "United Kingdom"},
                            "languageLabel": {"value": "English"},
                        },
                        {
                            "artist": {"value": "http://www.wikidata.org/entity/Q123"},
                            "artistLabel": {"value": "Radiohead"},
                            "genreLabel": {"value": "Art Rock"},
                            "countryLabel": {"value": "United Kingdom"},
                            "languageLabel": {"value": "English"},
                        },
                    ]
                }
            },
        )
    )

    result = WikidataProvider(http_client=http).get_artist_genres("Radiohead")

    assert len(result) == 1
    evidence = result[0]
    assert evidence["source"] == "wikidata"
    assert evidence["source_key"] == "Q123"
    assert evidence["primary_genre"] == "alternative rock"
    assert evidence["normalized_genres"] == ["alternative rock", "art rock"]
    assert evidence["hints"]["countries"] == ["United Kingdom"]
    assert evidence["hints"]["languages"] == ["English"]
    assert evidence["evidence_url"] == "https://www.wikidata.org/wiki/Q123"
    assert "query.wikidata.org" in http.requests[0]["url"]


def test_wikidata_query_restricts_results_to_music_artist_entities():
    from backend.providers.wikidata.client import WikidataProvider

    http = FakeHttpClient(FakeResponse(200, {"results": {"bindings": []}}))

    WikidataProvider(http_client=http).get_artist_genres("Radiohead")

    query = parse_qs(urlparse(http.requests[0]["url"]).query)["query"][0]
    assert "wdt:P31 ?artistType" in query
    assert "wdt:P106 ?occupation" in query
    assert "Q639669" in query
    assert "Q177220" in query
    assert "Q36834" in query


@pytest.mark.parametrize(
    ("import_path", "class_name", "kwargs"),
    [
        (
            "backend.providers.lastfm.client",
            "LastFMProvider",
            {"api_key": "key"},  # pragma: allowlist secret
        ),
        ("backend.providers.musicbrainz.client", "MusicBrainzProvider", {}),
        ("backend.providers.wikidata.client", "WikidataProvider", {}),
    ],
)
def test_provider_non_200_returns_empty(import_path, class_name, kwargs):
    module = __import__(import_path, fromlist=[class_name])
    provider_cls = getattr(module, class_name)
    provider = provider_cls(http_client=FakeHttpClient(FakeResponse(503)), **kwargs)

    assert provider.get_artist_genres("Radiohead") == []


@pytest.mark.parametrize(
    ("import_path", "class_name", "kwargs"),
    [
        (
            "backend.providers.lastfm.client",
            "LastFMProvider",
            {"api_key": "key"},  # pragma: allowlist secret
        ),
        ("backend.providers.musicbrainz.client", "MusicBrainzProvider", {}),
        ("backend.providers.wikidata.client", "WikidataProvider", {}),
    ],
)
def test_provider_bad_json_returns_empty(import_path, class_name, kwargs):
    module = __import__(import_path, fromlist=[class_name])
    provider_cls = getattr(module, class_name)
    provider = provider_cls(
        http_client=FakeHttpClient(FakeResponse(200, error=ValueError("bad json"))),
        **kwargs,
    )

    assert provider.get_artist_genres("Radiohead") == []
