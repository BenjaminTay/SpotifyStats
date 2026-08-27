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

    static_billboard_detail = client.get(
        "/api/billboard/track/902",
        params={**params, "dynamic_threshold": False, "bb_top_n": 5},
    )
    dynamic_billboard_detail = client.get(
        "/api/billboard/track/902",
        params={**params, "dynamic_threshold": True, "bb_top_n": 5},
    )
    assert static_billboard_detail.status_code == 200
    assert dynamic_billboard_detail.status_code == 404


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


def test_artist_personal_rankings_are_server_paginated_and_stable(client):
    params = {
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": False,
        "entity": "track",
        "metric": "plays",
        "limit": 1,
    }
    first = client.get(
        "/api/music/artists/Fixture Artist Alpha/rankings",
        params={**params, "offset": 0},
    )
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["found"] is True
    assert first_data["total"] >= 2
    assert len(first_data["rows"]) == 1
    assert first_data["rows"][0]["rank"] == 1

    second = client.get(
        "/api/music/artists/Fixture Artist Alpha/rankings",
        params={**params, "offset": 1},
    ).json()
    assert second["total"] == first_data["total"]
    assert second["rows"][0]["rank"] == 2


def test_artist_album_rankings_keep_album_specific_play_dates(client):
    data = client.get(
        "/api/music/artists/Fixture Artist Alpha/rankings",
        params={
            "entity": "album",
            "metric": "plays",
            "limit": 20,
            "offset": 0,
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": False,
        },
    ).json()

    future_lp = next(row for row in data["rows"] if row["album_name"] == "Fixture Future LP")
    assert future_lp["first_played"] == "2026-01-10T02:00:00Z"
    assert future_lp["last_played"] == "2026-03-02T02:00:00Z"


def test_artist_album_ranking_excludes_albums_owned_by_collaboration_partners(client):
    base_params = {
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": False,
        "metric": "plays",
        "limit": 20,
        "offset": 0,
    }

    tracks = client.get(
        "/api/music/artists/Fixture Artist Beta/rankings",
        params={**base_params, "entity": "track"},
    ).json()
    albums = client.get(
        "/api/music/artists/Fixture Artist Beta/rankings",
        params={**base_params, "entity": "album"},
    ).json()
    stats = client.get(
        "/api/music/artists/Fixture Artist Beta/stats",
        params=base_params,
    ).json()

    assert tracks["found"] is True
    assert {row["track_name"] for row in tracks["rows"]} >= {
        "Fixture Shared Credit",
        "Fixture Lead Single Remix",
    }
    assert albums["found"] is True
    assert albums["total"] == 0
    assert albums["rows"] == []
    assert stats["top_tracks"]
    assert stats["top_albums"] == []


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


def test_album_personal_rankings_are_server_paginated_and_project_scoped(client):
    params = {
        "artist": "Fixture Artist Alpha",
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": False,
        "merge_level": 2,
        "metric": "plays",
        "limit": 1,
    }
    first = client.get(
        "/api/music/albums/Fixture Future LP/rankings",
        params={**params, "offset": 0},
    )
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["found"] is True
    assert first_data["entity"] == "track"
    assert first_data["total"] >= 2
    assert len(first_data["rows"]) == 1
    assert first_data["rows"][0]["rank"] == 1
    assert first_data["rows"][0]["artist_names"]

    second = client.get(
        "/api/music/albums/Fixture Future LP/rankings",
        params={**params, "offset": 1},
    ).json()
    assert second["total"] == first_data["total"]
    assert second["rows"][0]["rank"] == 2


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


def test_music_search_and_billboard_detail_share_merge_disabled_semantics(client):
    params = {
        "q": "Fixture Fragment Song",
        "kind": "track",
        "limit_per_type": 5,
        "include_chart": True,
        "min_ms": 30000,
        "music_only": True,
        "dynamic_threshold": False,
        "merge_level": 2,
        "bb_top_n": 100,
    }

    merged_search = client.get("/api/music/search", params={**params, "merge_enabled": True}).json()
    merged_detail = client.get("/api/billboard/track/901", params={**params, "merge_enabled": True})
    unmerged_search = client.get(
        "/api/music/search", params={**params, "merge_enabled": False}
    ).json()
    unmerged_detail = client.get(
        "/api/billboard/track/901", params={**params, "merge_enabled": False}
    )

    assert merged_detail.status_code == 200
    assert (
        merged_search["tracks"][0]["chart"]["peak_position"]
        == merged_detail.json()["summary"]["peak_position"]
    )
    assert unmerged_search["tracks"] == []
    assert unmerged_detail.status_code == 404


def test_search_chart_lookup_respects_compilation_semantics(client):
    from backend.services.music_search_service import _build_chart_lookup

    chart_params = {
        "min_ms": 30000,
        "music_only": True,
        "bb_top_n": 100,
        "bb_album_top_n": 100,
        "bb_artist_top_n": 100,
        "bb_week_start_dow": 4,
        "bb_week_start_hour": 0,
        "year_start": None,
        "year_end": None,
        "merge_level": 2,
        "dynamic_threshold": False,
        "max_merge_gap_minutes": 5,
        "merge_enabled": True,
    }
    album_key = ("Fixture Compilation Plus", "Fixture Artist Alpha")

    excluded = _build_chart_lookup(**chart_params, include_compilations=False)
    included = _build_chart_lookup(**chart_params, include_compilations=True)
    detail_params = {
        **{key: value for key, value in chart_params.items() if value is not None},
        "artist_name": "Fixture Artist Alpha",
    }
    excluded_detail = client.get(
        "/api/billboard/album/Fixture Compilation Plus",
        params={**detail_params, "include_compilations": False},
    )
    included_detail = client.get(
        "/api/billboard/album/Fixture Compilation Plus",
        params={**detail_params, "include_compilations": True},
    )

    assert album_key not in excluded["album"]
    assert album_key in included["album"]
    assert excluded_detail.status_code == 200
    assert excluded_detail.json()["chart_summary"] is None
    assert included_detail.status_code == 200
    detail_chart = included_detail.json()["chart_summary"]
    assert included["album"][album_key].peak_position == detail_chart["peak_position"]
    assert included["album"][album_key].weeks_on_chart == detail_chart["weeks_on_chart"]


@pytest.mark.parametrize("merge_level", [2, 3])
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


@pytest.mark.parametrize("merge_level", [2, 3])
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
