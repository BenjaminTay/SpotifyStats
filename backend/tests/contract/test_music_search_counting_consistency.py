from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_music_search_uses_track_detail_counting_filters(client):
    params = {
        "q": "Fixture Long Track",
        "kind": "track",
        "limit_per_type": 5,
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
    }

    static_search = client.get(
        "/api/music/search",
        params={**params, "dynamic_threshold": False},
    ).json()
    static_detail = client.get(
        "/api/music/tracks/902/stats",
        params={**params, "dynamic_threshold": False},
    ).json()
    dynamic_search = client.get(
        "/api/music/search",
        params={**params, "dynamic_threshold": True},
    ).json()
    dynamic_detail = client.get(
        "/api/music/tracks/902/stats",
        params={**params, "dynamic_threshold": True},
    ).json()

    assert static_detail["summary"]["total_plays"] == 1
    assert static_search["tracks"][0]["play_events"] == static_detail["summary"]["total_plays"]
    assert dynamic_detail["found"] is False
    assert dynamic_search["total"] == 0
    assert dynamic_search["tracks"] == []


def test_music_search_artist_count_matches_detail_stats(client):
    params = {
        "q": "Fixture Artist Alpha",
        "kind": "artist",
        "limit_per_type": 5,
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": True,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get("/api/music/artists/Fixture Artist Alpha/stats", params=params).json()

    assert detail["found"] is True
    assert search["artists"][0]["play_events"] == detail["summary"]["total_plays"]


def test_music_search_album_count_matches_detail_stats(client):
    params = {
        "q": "Fixture Future LP",
        "kind": "album",
        "limit_per_type": 5,
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": True,
        "merge_level": 2,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get(
        "/api/music/albums/Fixture Future LP/stats",
        params={**params, "artist": "Fixture Artist Alpha"},
    ).json()

    assert detail["found"] is True
    assert search["albums"][0]["play_events"] == detail["summary"]["total_plays"]


def test_music_search_track_chart_matches_billboard_detail(client):
    params = {
        "q": "Fixture Long Track",
        "kind": "track",
        "limit_per_type": 5,
        "include_chart": True,
        "min_ms": 30000,
        "music_only": True,
        "dynamic_threshold": False,
        "merge_level": 2,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get("/api/billboard/track/902", params=params).json()

    assert detail["found"] is True
    chart = search["tracks"][0]["chart"]
    assert chart["peak_position"] == detail["summary"]["peak_position"]
    assert chart["peak_weeks"] == detail["summary"]["weeks_at_peak"]
    assert chart["weeks_on_chart"] == detail["summary"]["weeks_on_chart"]
    assert chart["weeks_at_no1"] == detail["summary"]["weeks_at_no1"]
    assert chart["power_score"] == detail["summary"]["power_score"]
    assert chart["power_rank"] == detail["summary"]["power_rank"]
    assert chart["first_week"] == detail["summary"]["first_week"]
    assert chart["latest_week"] == detail["summary"]["last_week"]
    assert chart["first_peak_week"] == detail["summary"]["first_peak_week"]


@pytest.mark.parametrize("merge_level", [1, 2, 3])
def test_music_search_album_chart_matches_billboard_detail(client, merge_level):
    params = {
        "q": "Fixture Future LP",
        "kind": "album",
        "limit_per_type": 5,
        "include_chart": True,
        "min_ms": 30000,
        "music_only": True,
        "dynamic_threshold": True,
        "merge_level": merge_level,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get(
        "/api/billboard/album/Fixture Future LP",
        params={**params, "artist_name": "Fixture Artist Alpha"},
    ).json()

    assert detail["found"] is True
    chart = search["albums"][0]["chart"]
    assert chart["peak_position"] == detail["chart_summary"]["peak_position"]
    assert chart["peak_weeks"] == detail["chart_summary"]["peak_weeks"]
    assert chart["weeks_on_chart"] == detail["chart_summary"]["weeks_on_chart"]
    assert chart["weeks_at_no1"] == detail["chart_summary"]["no1_weeks"]
    assert chart["power_score"] == detail["chart_summary"]["power_score"]
    assert chart["power_rank"] == detail["chart_summary"]["power_rank"]
    assert chart["first_week"] == detail["chart_summary"]["first_week"]
    assert chart["latest_week"] == detail["chart_summary"]["latest_week"]
    assert chart["first_peak_week"] == detail["chart_summary"]["first_peak_week"]


@pytest.mark.parametrize("merge_level", [1, 2, 3])
def test_music_search_artist_chart_matches_billboard_detail(client, merge_level):
    params = {
        "q": "Fixture Artist Alpha",
        "kind": "artist",
        "limit_per_type": 5,
        "include_chart": True,
        "min_ms": 30000,
        "music_only": True,
        "dynamic_threshold": True,
        "merge_level": merge_level,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get("/api/billboard/artist/Fixture Artist Alpha", params=params).json()

    assert detail["found"] is True
    chart = search["artists"][0]["chart"]
    assert chart["peak_position"] == detail["chart_summary"]["peak_position"]
    assert chart["peak_weeks"] == detail["chart_summary"]["peak_weeks"]
    assert chart["weeks_on_chart"] == detail["chart_summary"]["weeks_on_chart"]
    assert chart["weeks_at_no1"] == detail["chart_summary"]["no1_weeks"]
    assert chart["power_score"] == detail["chart_summary"]["power_score"]
    assert chart["power_rank"] == detail["chart_summary"]["power_rank"]
    assert chart["first_week"] == detail["chart_summary"]["first_week"]
    assert chart["latest_week"] == detail["chart_summary"]["latest_week"]
    assert chart["first_peak_week"] == detail["chart_summary"]["first_peak_week"]
