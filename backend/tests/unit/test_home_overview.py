from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.domains.home import overview
from backend.domains.playback.logical_timeline import (
    attach_listening_duration_frame,
    reconstruct_listening_intervals,
)
from backend.models.home import HomeOverviewResponse

pytestmark = pytest.mark.unit


def _track_rows(values: list[tuple[int, str, str, int, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "home_track_id": track_id,
                "home_track_name": name,
                "artist_name": artist,
                "play_id": index,
                "ms_played": 180_000,
                "ts_date": played_on,
            }
            for index, (track_id, name, artist, count, played_on) in enumerate(
                row for value in values for row in [value] * value[3]
            )
        ]
    )


def test_headline_prefers_evidenced_comeback(monkeypatch):
    current = _track_rows([(7, "重逢", "艺人", 6, "2026-07-24")])
    previous = _track_rows([(7, "重逢", "艺人", 1, "2026-06-24")])
    history = _track_rows([(7, "重逢", "艺人", 12, "2025-01-01")])
    all_tracks = pd.concat([history, previous, current], ignore_index=True)
    current.index = range(13, 19)
    previous.index = [12]
    all_tracks.index = range(19)
    monkeypatch.setattr(overview, "_track_cover_urls", lambda *_args: {7: "/cover.jpg"})

    result = overview._headline(
        sqlite3.connect(":memory:"),
        current,
        previous,
        all_tracks,
        {"leaders": {"track": None}},
    )

    assert result["kind"] == "comeback"
    assert result["entity"]["entity_id"] == 7
    assert result["entity"]["cover_url"] == "/cover.jpg"
    assert result["statement"] == "最近4周播放了 6 次。"


def test_rediscovery_returns_ranked_candidate_pool(monkeypatch):
    all_tracks = _track_rows(
        [
            (7, "最常重听的久违歌曲", "艺人甲", 15, "2026-01-01"),
            (8, "第二首久违歌曲", "艺人乙", 12, "2026-02-01"),
            (9, "还不够久的歌曲", "艺人丙", 20, "2026-06-01"),
            (10, "播放次数不足", "艺人丁", 9, "2026-01-01"),
        ]
    )
    monkeypatch.setattr(
        overview,
        "_track_cover_urls",
        lambda _conn, track_ids: {track_id: f"/{track_id}.jpg" for track_id in track_ids},
    )

    result = overview._rediscovery_candidates(
        sqlite3.connect(":memory:"), all_tracks, overview.date(2026, 8, 1)
    )

    assert [item["entity"]["entity_id"] for item in result] == [7, 8]
    assert result[0]["days_since_last_play"] == 212
    assert result[1]["entity"]["cover_url"] == "/8.jpg"


def test_billboard_champion_uses_project_identity_and_previous_rank():
    rows = [
        {
            "billboard_week": "2026-07-17",
            "album_project_id": 91,
            "album_name": "专辑",
            "artist_name": "艺人",
            "rank": 1,
            "play_count": 20,
            "total_ms": 3_600_000,
            "cover_url": "/album.jpg",
        },
        {
            "billboard_week": "2026-07-10",
            "album_project_id": 91,
            "album_name": "专辑",
            "artist_name": "艺人",
            "rank": 4,
        },
    ]

    result = overview._champion(rows, "2026-07-17", "2026-07-10", "album")

    assert result["entity"]["entity_id"] == 91
    assert result["previous_rank"] == 4
    assert result["rank_change"] == 3
    assert result["movement"] == "up"
    assert result["hours"] == 1.0


def test_billboard_champion_uses_snapshot_reentry_movement_when_previous_row_is_outside_top_n():
    rows = [
        {
            "billboard_week": "2026-08-14",
            "artist_id": 159,
            "artist_name": "Phoebe Bridgers",
            "rank": 1,
            "play_count": 33,
            "total_ms": 6_541_917,
        }
    ]

    result = overview._champion(
        rows,
        "2026-08-14",
        "2026-08-07",
        "artist",
        {"movement": "re", "previous_rank": None, "rank_change": None},
    )

    assert result["entity"]["entity_id"] == 159
    assert result["movement"] == "re"
    assert result["previous_rank"] is None
    assert result["rank_change"] is None


def test_empty_state_preserves_raw_source_freshness(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE plays(ts_date TEXT, track_id INTEGER)")
    conn.execute("INSERT INTO plays VALUES ('2026-08-12', 1)")
    monkeypatch.setattr(overview, "load_plays", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(overview, "_today", lambda: overview.date(2026, 8, 13))
    context = SimpleNamespace(
        filter_fingerprint="all-filtered-out",
        min_ms=999999,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
    )

    payload = overview.build_home_overview(conn, context)
    result = HomeOverviewResponse.model_validate(payload)

    assert result.state == "limited"
    assert result.recent is None
    assert result.coverage.source_latest_date == "2026-08-12"
    assert result.coverage.latest_effective_play_date is None
    assert result.coverage.freshness == "recent"


def test_track_frame_prefers_composition_scope_at_l3(monkeypatch):
    frame = pd.DataFrame([{"track_id": 9, "track_name": "原曲"}])
    keys = pd.DataFrame(
        [
            {
                "track_id": 9,
                "track_agg_id": 1,
                "track_agg_name": "录音组",
                "track_group_scope": "recording",
            },
            {
                "track_id": 9,
                "track_agg_id": 8,
                "track_agg_name": "作曲组",
                "track_group_scope": "composition",
            },
        ]
    )
    monkeypatch.setattr(overview, "load_track_group_keys", lambda *_args: keys)

    result = overview._track_frame(sqlite3.connect(":memory:"), frame, 3)

    assert result.iloc[0]["home_track_id"] == 8
    assert result.iloc[0]["home_track_name"] == "作曲组"


def test_recent_album_leader_delegates_l1_to_authoritative_chart_rows(monkeypatch):
    calls = []

    def fake_chart_rows(*args, **kwargs):
        calls.append((args, kwargs))
        return 1, [
            {
                "album_project_id": None,
                "album_name": "容器专辑",
                "artist_name": "艺人",
                "cover_url": "/cover.jpg",
                "plays": 12,
                "hours": 1.25,
            }
        ]

    monkeypatch.setattr(overview, "chart_rows", fake_chart_rows)
    duration = pd.DataFrame([{"ms_played": 90_000, "ts_date": "2026-07-24"}])
    result = overview._recent_album_leader(
        sqlite3.connect(":memory:"),
        pd.DataFrame([{"play_id": 1}]),
        SimpleNamespace(merge_level=1, include_compilations=False),
        duration,
    )

    assert calls[0][0][6] == 1
    assert calls[0][0][7] is False
    assert calls[0][1]["duration_frame"] is duration
    assert result["entity"]["name"] == "容器专辑"


def test_recent_windows_are_two_exact_non_overlapping_4_week_ranges(monkeypatch):
    days = pd.date_range("2026-05-30", "2026-07-24", freq="D")
    frame = pd.DataFrame(
        [
            {
                "play_id": index,
                "track_id": 1,
                "track_name": "歌曲",
                "artist_name": "艺人",
                "ts_date": day.date().isoformat(),
                "ts_hour": 12,
                "ts_dow": day.dayofweek,
                "ms_played": 180_000,
            }
            for index, day in enumerate(days)
        ]
    )
    monkeypatch.setattr(overview, "_recent_track_leader", lambda *_args: None)
    monkeypatch.setattr(overview, "_recent_album_leader", lambda *_args: None)
    monkeypatch.setattr(overview, "_recent_artist_leader", lambda *_args: None)

    payload, _current_tracks, _previous_tracks, _current_duration, _previous_duration = (
        overview._recent_payload(
            sqlite3.connect(":memory:"),
            frame,
            frame,
            SimpleNamespace(merge_level=1, include_compilations=False),
        )
    )

    assert payload["period"] == {
        "start_date": "2026-06-27",
        "end_date": "2026-07-24",
        "label": "截至 2026-07-24 的最近4周",
    }
    assert payload["comparison_period"] == {
        "start_date": "2026-05-30",
        "end_date": "2026-06-26",
        "label": "截至 2026-06-26 的最近4周",
    }
    assert payload["comparison_available"] is True
    assert len(payload["trend"]) == 28


def test_period_duration_splits_cross_midnight_listening() -> None:
    raw = pd.DataFrame(
        [
            {
                "play_id": 1,
                "ts": "2026-06-26T16:02:00Z",
                "ts_date": "2026-06-27",
                "track_id": 7,
                "track_name": "跨日歌曲",
                "artist_name": "艺人",
                "album_name": "专辑",
                "ms_played": 240_000,
                "duration_ms": 240_000,
            }
        ]
    )
    duration = reconstruct_listening_intervals(raw)
    events = attach_listening_duration_frame(raw.copy(), duration)

    previous = overview._period_duration(
        events,
        overview.date(2026, 6, 26),
        overview.date(2026, 6, 26),
    )
    current = overview._period_duration(
        events,
        overview.date(2026, 6, 27),
        overview.date(2026, 6, 27),
    )

    assert int(previous["ms_played"].sum()) == 120_000
    assert int(current["ms_played"].sum()) == 120_000


def test_track_activity_keeps_duration_only_rows_without_adding_plays() -> None:
    events = pd.DataFrame(
        [
            {
                "home_track_id": 1,
                "home_track_name": "有时长",
                "artist_name": "艺人甲",
                "play_id": 11,
                "ts_date": "2026-07-24",
            },
            {
                "home_track_id": 2,
                "home_track_name": "只有次数",
                "artist_name": "艺人乙",
                "play_id": 12,
                "ts_date": "2026-07-24",
            },
        ]
    )
    duration = pd.DataFrame(
        [
            {
                "home_track_id": 1,
                "home_track_name": "有时长",
                "artist_name": "艺人甲",
                "ms_played": 40_000,
            },
            {
                "home_track_id": 3,
                "home_track_name": "只有时长",
                "artist_name": "艺人丙",
                "ms_played": 20_000,
            },
        ]
    )

    grouped = overview._aggregate_track_activity(events, duration).set_index("home_track_id")

    assert grouped.loc[1, ["plays", "total_ms"]].tolist() == [1, 40_000]
    assert grouped.loc[2, ["plays", "total_ms"]].tolist() == [1, 0]
    assert grouped.loc[3, ["plays", "total_ms"]].tolist() == [0, 20_000]


def test_recent_uses_attached_duration_for_summary_trend_and_duration_only_day(monkeypatch):
    events = pd.DataFrame(
        [
            {
                "play_id": 1,
                "track_id": 1,
                "track_name": "歌曲",
                "artist_name": "艺人",
                "ts_date": "2026-05-30",
                "ts_hour": 12,
                "ts_dow": 5,
                "ms_played": 9_000_000,
            },
            {
                "play_id": 2,
                "track_id": 1,
                "track_name": "歌曲",
                "artist_name": "艺人",
                "ts_date": "2026-07-24",
                "ts_hour": 12,
                "ts_dow": 4,
                "ms_played": 9_000_000,
            },
        ]
    )
    duration = pd.DataFrame(
        [
            {
                "play_id": 101,
                "track_id": 1,
                "track_name": "歌曲",
                "artist_name": "艺人",
                "ts_date": "2026-05-30",
                "ms_played": 3_600_000,
            },
            {
                "play_id": 102,
                "track_id": 2,
                "track_name": "短时收听",
                "artist_name": "艺人",
                "ts_date": "2026-07-23",
                "ms_played": 720_000,
            },
            {
                "play_id": 103,
                "track_id": 1,
                "track_name": "歌曲",
                "artist_name": "艺人",
                "ts_date": "2026-07-24",
                "ms_played": 1_800_000,
            },
        ]
    )
    attach_listening_duration_frame(events, duration)
    artist_events = events.copy()
    attach_listening_duration_frame(artist_events, duration.copy())
    monkeypatch.setattr(overview, "_recent_track_leader", lambda *_args: None)
    monkeypatch.setattr(overview, "_recent_album_leader", lambda *_args: None)
    monkeypatch.setattr(overview, "_recent_artist_leader", lambda *_args: None)

    payload, _current, _previous, current_duration, _previous_duration = overview._recent_payload(
        sqlite3.connect(":memory:"),
        events,
        artist_events,
        SimpleNamespace(merge_level=1, include_compilations=False),
    )
    trend = {row["date"]: row for row in payload["trend"]}

    assert payload["summary"]["plays"] == 1
    assert payload["summary"]["hours"] == 0.7
    assert payload["summary"]["hours_delta_pct"] == -30.0
    assert trend["2026-07-23"] == {
        "date": "2026-07-23",
        "plays": 0,
        "hours": 0.2,
    }
    assert trend["2026-07-24"] == {
        "date": "2026-07-24",
        "plays": 1,
        "hours": 0.5,
    }
    assert set(current_duration["home_track_id"]) == {1, 2}


def test_empty_qualified_events_keep_attached_archive_duration(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE plays(ts_date TEXT, track_id INTEGER)")
    conn.execute("INSERT INTO plays VALUES ('2026-08-12', 1)")
    events = pd.DataFrame(
        columns=["play_id", "track_id", "track_name", "artist_name", "ts_date", "ms_played"]
    )
    duration = pd.DataFrame([{"ms_played": 3_600_000, "ts_date": "2026-08-12"}])
    attach_listening_duration_frame(events, duration)
    monkeypatch.setattr(overview, "load_plays", lambda *_args, **_kwargs: events)
    monkeypatch.setattr(overview, "_today", lambda: overview.date(2026, 8, 13))
    context = SimpleNamespace(
        filter_fingerprint="duration-only",
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
    )

    payload = overview.build_home_overview(conn, context)

    assert payload["archive"]["total_plays"] == 0
    assert payload["archive"]["total_hours"] == 1.0
    assert payload["recent"] is None
