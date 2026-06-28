from __future__ import annotations

from typing import Any

import pytest

from backend.services import wikipedia_service

pytestmark = pytest.mark.unit


def test_artist_wiki_reports_progress_for_external_fetch(monkeypatch: pytest.MonkeyPatch):
    events: list[tuple[str, str]] = []
    saved: dict[str, Any] = {}

    monkeypatch.setattr(wikipedia_service, "_cache_lookup", lambda key: (False, None))
    monkeypatch.setattr(
        wikipedia_service, "_cache_set", lambda key, data: saved.update({key: data})
    )
    monkeypatch.setattr(
        wikipedia_service,
        "find_artist_page",
        lambda artist_name: ("Example Artist", "en"),
    )
    monkeypatch.setattr(
        wikipedia_service,
        "_fetch_page_data",
        lambda title, lang: {
            "extract": "Example Artist is a singer.",
            "description": "singer",
            "thumbnail": "https://example.test/artist.jpg",
        },
    )
    monkeypatch.setattr(wikipedia_service, "_fetch_full_extract", lambda title, lang: "")
    monkeypatch.setattr(
        wikipedia_service,
        "_wiki_page_url",
        lambda title, lang: f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
    )
    monkeypatch.setattr(wikipedia_service, "_add_translations", lambda result: result)

    result = wikipedia_service.get_artist_wiki(
        "Example Artist",
        progress_callback=lambda stage, message: events.append((stage, message)),
    )

    assert result is not None
    assert result["title"] == "Example Artist"
    assert result["summary"] == "Example Artist is a singer."
    assert [stage for stage, _message in events] == [
        "checking_cache",
        "fetching_external_data",
        "calling_llm",
        "saving_cache",
    ]
    assert saved["artist:Example Artist"]["title"] == "Example Artist"


def test_album_wiki_reports_cache_hit_for_cached_null(monkeypatch: pytest.MonkeyPatch):
    events: list[tuple[str, str]] = []

    monkeypatch.setattr(wikipedia_service, "_cache_lookup", lambda key: (True, None))
    monkeypatch.setattr(
        wikipedia_service,
        "find_album_page",
        lambda album_name, artist_name: pytest.fail("cached null must not fetch Wikipedia"),
    )
    monkeypatch.setattr(
        wikipedia_service,
        "_cache_set",
        lambda key, data: pytest.fail("cache hit must not rewrite cache"),
    )

    result = wikipedia_service.get_album_wiki(
        "Missing Album",
        "Missing Artist",
        progress_callback=lambda stage, message: events.append((stage, message)),
    )

    assert result is None
    assert [stage for stage, _message in events] == ["checking_cache", "checking_cache"]
    assert "命中" in events[-1][1]


def test_artist_wiki_skips_cache_write_when_cancelled_before_save(
    monkeypatch: pytest.MonkeyPatch,
):
    events: list[tuple[str, str]] = []

    monkeypatch.setattr(wikipedia_service, "_cache_lookup", lambda key: (False, None))
    monkeypatch.setattr(
        wikipedia_service,
        "_cache_set",
        lambda key, data: pytest.fail("cancelled enrichment must not write wiki cache"),
    )
    monkeypatch.setattr(
        wikipedia_service,
        "find_artist_page",
        lambda artist_name: ("Example Artist", "en"),
    )
    monkeypatch.setattr(
        wikipedia_service,
        "_fetch_page_data",
        lambda title, lang: {
            "extract": "Example Artist is a singer.",
            "description": "singer",
            "thumbnail": "",
        },
    )
    monkeypatch.setattr(wikipedia_service, "_fetch_full_extract", lambda title, lang: "")
    monkeypatch.setattr(
        wikipedia_service, "_wiki_page_url", lambda title, lang: "https://example.test"
    )
    monkeypatch.setattr(wikipedia_service, "_add_translations", lambda result: result)

    result = wikipedia_service.get_artist_wiki(
        "Example Artist",
        progress_callback=lambda stage, message: events.append((stage, message)),
        should_continue=lambda: False,
    )

    assert result is not None
    assert result["title"] == "Example Artist"
    assert [stage for stage, _message in events] == [
        "checking_cache",
        "fetching_external_data",
        "calling_llm",
    ]
