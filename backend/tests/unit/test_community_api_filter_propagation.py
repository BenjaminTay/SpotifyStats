"""Community API filter propagation tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_community_feed_uses_saved_billboard_settings_when_query_params_omitted(
    client, monkeypatch
):
    import backend.api.community as community_api
    import backend.dependencies as dependencies

    captured = {}
    saved_settings = {
        "min_ms": 45000,
        "music_only": True,
        "bb_top_n": 77,
        "bb_album_top_n": 66,
        "bb_artist_top_n": 55,
        "bb_week_start_dow": 2,
        "bb_week_start_hour": 12,
    }

    def fake_generate_all_posts(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(dependencies, "_load_filter_settings", lambda: saved_settings)
    monkeypatch.setattr(community_api, "generate_all_posts", fake_generate_all_posts)

    response = client.get("/api/community/feed", params={"limit": 1})

    assert response.status_code == 200
    assert captured["min_ms"] == 45000
    assert captured["music_only"] is True
    assert captured["bb_top_n"] == 77
    assert captured["bb_album_top_n"] == 66
    assert captured["bb_artist_top_n"] == 55
    assert captured["bb_week_start_dow"] == 2
    assert captured["bb_week_start_hour"] == 12


def test_community_feed_forwards_explicit_billboard_and_merge_query_params(client, monkeypatch):
    import backend.api.community as community_api

    captured = {}

    def fake_generate_all_posts(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(community_api, "generate_all_posts", fake_generate_all_posts)

    response = client.get(
        "/api/community/feed",
        params={
            "limit": 1,
            "bb_top_n": 88,
            "bb_album_top_n": 44,
            "bb_artist_top_n": 33,
            "bb_week_start_dow": 5,
            "bb_week_start_hour": 12,
            "year_start": 2026,
            "year_end": 2026,
            "merge_level": 3,
            "include_compilations": True,
            "dynamic_threshold": False,
            "max_merge_gap_minutes": 45,
        },
    )

    assert response.status_code == 200
    assert captured["bb_top_n"] == 88
    assert captured["bb_album_top_n"] == 44
    assert captured["bb_artist_top_n"] == 33
    assert captured["bb_week_start_dow"] == 5
    assert captured["bb_week_start_hour"] == 12
    assert captured["year_start"] == 2026
    assert captured["year_end"] == 2026
    assert captured["merge_level"] == 3
    assert captured["include_compilations"] is True
    assert captured["dynamic_threshold"] is False
    assert captured["max_merge_gap_minutes"] == 45
