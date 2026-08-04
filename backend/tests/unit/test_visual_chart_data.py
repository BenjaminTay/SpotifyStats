from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.ai_reports.visual_chart_data import build_visual_chart_data, chart_coverage

pytestmark = pytest.mark.unit


def _plays() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_date": "2025-01-01",
                "hour": 9,
                "track_name": "Song A",
                "artist_name": "Taylor Swift",
                "album_name": "The Life of a Showgirl",
                "ms_played": 180000,
            },
            {
                "ts_date": "2025-01-01",
                "hour": 10,
                "track_name": "Song B",
                "artist_name": "Michael Wong",
                "album_name": "光良「回憶裡的瘋狂」巡迴演唱會",
                "ms_played": 200000,
            },
            {
                "ts_date": "2025-02-14",
                "hour": 21,
                "track_name": "15 Minutes",
                "artist_name": "Sabrina Carpenter",
                "album_name": "Single",
                "ms_played": 190000,
            },
            {
                "ts_date": "2025-02-14",
                "hour": 22,
                "track_name": "15 Minutes",
                "artist_name": "Sabrina Carpenter",
                "album_name": "Single",
                "ms_played": 190000,
            },
        ]
    )


def test_visual_chart_data_builds_required_shapes():
    context = {
        "reporting_period": {
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_partial_year": False,
        },
        "top_artists": [{"name": "Taylor Swift"}, {"name": "Michael Wong"}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "weeks_on_chart": 32,
                    "rank": 1,
                }
            ],
            "tracks": [
                {
                    "name": "The Fate of Ophelia",
                    "artist": "Taylor Swift",
                    "plays": 190,
                    "weeks_on_chart": 13,
                    "peak_position": 1,
                }
            ],
        },
        "genre_distribution": {
            "primary_styles": {
                "buckets": [{"key": "mandopop", "label": "mandopop", "share_pct": 16.7}]
            }
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "JOLIN", "first_date": "2025-05-08", "plays": 108}]
        },
        "highlight_day_detail": {"date": "2025-02-14", "plays": 154},
    }
    chart_specs = [
        {"id": "listening_calendar", "chart_type": "listening_calendar_heatmap"},
        {
            "id": "artist_monthly_trend",
            "chart_type": "artist_monthly_trend",
            "entities": ["Taylor Swift", "Michael Wong"],
        },
        {"id": "album_duality_compare", "chart_type": "album_duality_compare"},
        {"id": "highlight_day_timeline", "chart_type": "highlight_day_timeline"},
        {"id": "genre_language_mix", "chart_type": "genre_language_mix"},
        {"id": "discovery_timeline", "chart_type": "discovery_timeline"},
        {"id": "playback_billboard_matrix", "chart_type": "playback_billboard_matrix"},
    ]

    chart_data = build_visual_chart_data(context, chart_specs, plays_df=_plays())

    assert chart_data["listening_calendar"]["active_days"] == 2
    assert chart_data["artist_monthly_trend"]["entities"] == ["Taylor Swift", "Michael Wong"]
    assert (
        chart_data["album_duality_compare"]["playback_leader"]["name"] == "The Life of a Showgirl"
    )
    assert (
        chart_data["album_duality_compare"]["chart_leader"]["name"]
        == "光良「回憶裡的瘋狂」巡迴演唱會"
    )
    assert chart_data["highlight_day_timeline"]["date"] == "2025-02-14"
    assert chart_data["genre_language_mix"]["items"][0]["label"] == "mandopop"
    assert chart_data["discovery_timeline"]["new_artists"][0]["name"] == "JOLIN"
    assert chart_data["playback_billboard_matrix"]["items"][0]["name"] == "The Fate of Ophelia"
    assert chart_data["playback_billboard_matrix"]["items"][0]["peak_rank"] == 1


def test_visual_chart_data_marks_album_duality_aligned_when_leaders_match():
    context = {
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [
                {"name": "The Life of a Showgirl", "artist": "Taylor Swift", "weeks_on_chart": 24}
            ]
        },
    }

    chart_data = build_visual_chart_data(
        context,
        [{"id": "album_duality_compare", "chart_type": "album_duality_compare"}],
        plays_df=_plays(),
    )

    album_data = chart_data["album_duality_compare"]
    assert album_data["relation"] == "aligned"
    assert "同一张专辑" in album_data["interpretation"]
    assert "两种不同" not in album_data["interpretation"]


def test_visual_chart_data_loads_filtered_report_period_with_request_filters(monkeypatch):
    from backend.domains.ai_reports import visual_chart_data as module

    class FakeConn:
        def close(self) -> None:
            pass

    captured: dict[str, object] = {}

    def fake_loader(
        conn,
        *,
        min_ms,
        music_only,
        merge_enabled,
        dynamic_threshold,
        max_merge_gap_minutes,
    ):
        captured.update(
            {
                "conn": conn,
                "min_ms": min_ms,
                "music_only": music_only,
                "merge_enabled": merge_enabled,
                "dynamic_threshold": dynamic_threshold,
                "max_merge_gap_minutes": max_merge_gap_minutes,
            }
        )
        return pd.DataFrame(
            [
                {"ts_date": "2024-12-31", "artist_name": "Taylor Swift", "ms_played": 180000},
                {"ts_date": "2025-01-01", "artist_name": "Taylor Swift", "ms_played": 180000},
                {"ts_date": "2025-02-14", "artist_name": "Taylor Swift", "ms_played": 180000},
                {"ts_date": "2026-01-01", "artist_name": "Taylor Swift", "ms_played": 180000},
            ]
        )

    monkeypatch.setattr(module, "get_db", lambda readonly=True: FakeConn())
    monkeypatch.setattr(module, "_load_yearly_report_plays_frame", fake_loader)

    context = {
        "reporting_period": {
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        },
        "request_filters": {
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 12,
        },
    }

    coverage = chart_coverage(context)
    chart_data = build_visual_chart_data(
        context,
        [{"id": "listening_calendar", "chart_type": "listening_calendar_heatmap"}],
    )

    assert coverage["listening_calendar"] is True
    assert chart_data["listening_calendar"]["active_days"] == 2
    assert chart_data["listening_calendar"]["days"][0]["date"] == "2025-01-01"
    assert captured == {
        "conn": captured["conn"],
        "min_ms": 45000,
        "music_only": False,
        "merge_enabled": False,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 12,
    }


def test_visual_chart_data_adds_artist_trend_observations():
    context = {
        "reporting_period": {"year": 2026, "start_date": "2026-01-01", "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}, {"name": "Olivia Rodrigo"}],
    }
    plays = pd.DataFrame(
        [
            {"month": "2026-01", "Taylor Swift": 337, "Olivia Rodrigo": 60},
            {"month": "2026-06", "Taylor Swift": 114, "Olivia Rodrigo": 366},
        ]
    )
    rows = []
    for row in plays.to_dict("records"):
        for artist in ["Taylor Swift", "Olivia Rodrigo"]:
            rows.extend(
                {
                    "ts_date": f"{row['month']}-01",
                    "artist_name": artist,
                    "track_name": f"{artist} song",
                    "album_name": f"{artist} album",
                    "ms_played": 180000,
                }
                for _ in range(int(row[artist]))
            )

    chart_data = build_visual_chart_data(
        context,
        [
            {
                "id": "artist_monthly_trend",
                "chart_type": "artist_monthly_trend",
                "entities": ["Taylor Swift", "Olivia Rodrigo"],
            }
        ],
        plays_df=pd.DataFrame(rows),
    )

    assert chart_data["artist_monthly_trend"]["observations"] == [
        "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    ]


def test_visual_chart_data_types_playback_billboard_matrix_items():
    context = {
        "personal_billboard_year_end": {
            "tracks": [
                {"name": "Opalite", "plays": 117, "weeks_on_chart": 19, "peak_rank": 1, "rank": 1}
            ],
            "albums": [
                {
                    "name": "The Life of a Showgirl",
                    "plays": 494,
                    "weeks_on_chart": 24,
                    "peak_rank": 1,
                    "rank": 1,
                }
            ],
            "artists": [
                {
                    "name": "Taylor Swift",
                    "plays": 1108,
                    "weeks_on_chart": 25,
                    "peak_rank": 1,
                    "rank": 1,
                }
            ],
        }
    }

    chart_data = build_visual_chart_data(
        context,
        [{"id": "playback_billboard_matrix", "chart_type": "playback_billboard_matrix"}],
        plays_df=pd.DataFrame(),
    )

    matrix = chart_data["playback_billboard_matrix"]
    assert [item["type"] for item in matrix["items"]] == ["track", "album", "artist"]
    assert matrix["observations"] == [
        "Opalite 是单曲里兼具高播放和长在榜的核心作品。",
        "The Life of a Showgirl 是专辑里兼具高播放和长在榜的核心作品。",
        "Taylor Swift 是艺人里兼具高播放和长在榜的核心对象。",
    ]


def test_visual_chart_data_adds_highlight_day_observations():
    rows = [
        {
            "ts_date": "2026-04-03",
            "hour": index % 24,
            "track_name": f"Song {index}",
            "artist_name": "Mixed Artist",
            "album_name": "Mixed Album",
            "ms_played": 180000,
        }
        for index in range(143)
    ]
    context = {"highlight_day_detail": {"date": "2026-04-03", "plays": 143}}

    chart_data = build_visual_chart_data(
        context,
        [{"id": "highlight_day_timeline", "chart_type": "highlight_day_timeline"}],
        plays_df=pd.DataFrame(rows),
    )

    assert chart_data["highlight_day_timeline"]["observations"] == [
        "2026-04-03 有 143 次播放，但最高单曲只有 1 次，更像多曲目密集漫游。"
    ]
