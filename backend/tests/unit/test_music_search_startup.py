from __future__ import annotations

import pytest

from backend.main import _music_search_startup_rebuild_enabled

pytestmark = pytest.mark.unit


def test_music_search_startup_rebuild_flag_defaults_enabled(monkeypatch) -> None:
    monkeypatch.delenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", raising=False)

    assert _music_search_startup_rebuild_enabled() is True


def test_music_search_startup_rebuild_flag_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "0")

    assert _music_search_startup_rebuild_enabled() is False


def test_music_search_startup_rebuild_flag_is_independent_from_cache_warmup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SPOTIFY_STATS_WARMUP", "0")
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "1")

    assert _music_search_startup_rebuild_enabled() is True
