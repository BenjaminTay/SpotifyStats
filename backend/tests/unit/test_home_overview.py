from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.domains.home import overview
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

    def fake_chart_rows(*args):
        calls.append(args)
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
    result = overview._recent_album_leader(
        sqlite3.connect(":memory:"),
        pd.DataFrame([{"play_id": 1}]),
        SimpleNamespace(merge_level=1, include_compilations=False),
    )

    assert calls[0][6] == 1
    assert calls[0][7] is False
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

    payload, _current_tracks, _previous_tracks, _current = overview._recent_payload(
        sqlite3.connect(":memory:"),
        frame,
        frame,
        SimpleNamespace(merge_level=1, include_compilations=False),
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
