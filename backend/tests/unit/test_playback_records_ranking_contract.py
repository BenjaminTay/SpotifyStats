from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_behavior import compute_behavior_records
from backend.domains.playback.records_discovery import _feat_lover_artist, _no_repeat_streak
from backend.domains.playback.records_longevity import _longest_streak_days
from backend.domains.playback.records_obsession import (
    _consecutive_marathon,
    _daily_binge,
    _daily_total_record,
)
from backend.domains.playback.records_reigns import _daily_champion
from backend.domains.playback.records_sorting import sort_and_limit
from backend.domains.playback.records_time import _weekday_preference


def _event_rows(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if "play_id" not in frame.columns:
        frame["play_id"] = range(1, len(frame) + 1)
    if "ms_played" not in frame.columns:
        frame["ms_played"] = 180_000
    return frame


def test_sort_and_limit_is_independent_of_input_order() -> None:
    original = pd.DataFrame(
        [
            {"id": "b", "metric": 10, "secondary": 2},
            {"id": "a", "metric": 10, "secondary": 2},
            {"id": "c", "metric": 9, "secondary": 9},
        ]
    )

    first = sort_and_limit(original, ["metric", "secondary", "id"], [False, False, True])
    second = sort_and_limit(
        original.sample(frac=1, random_state=7).reset_index(drop=True),
        ["metric", "secondary", "id"],
        [False, False, True],
    )

    assert first["id"].tolist() == ["a", "b", "c"]
    assert second["id"].tolist() == first["id"].tolist()
    assert first["rank"].tolist() == [1, 2, 3]


def test_daily_binge_uses_duration_and_entity_id_as_tie_breakers() -> None:
    rows = []
    for play_id, track_id, duration in [
        (1, "b", 200_000),
        (2, "b", 200_000),
        (3, "a", 300_000),
        (4, "a", 300_000),
    ]:
        rows.append(
            {
                "play_id": play_id,
                "track_id": track_id,
                "track_name": track_id.upper(),
                "artist_name": "Artist",
                "ts_date": "2026-01-01",
                "ms_played": duration,
            }
        )

    result = _daily_binge(pd.DataFrame(rows), "track_id", "track_name", "artist_name")

    assert result.iloc[0]["entity_id"] == "a"
    assert result.iloc[0]["total_ms"] == 600_000


def test_daily_champion_uses_duration_and_entity_id_as_tie_breakers() -> None:
    frame = _event_rows(
        [
            {
                "play_id": 1,
                "track_id": "b",
                "track_name": "B",
                "artist_name": "Artist",
                "ts_date": "2026-01-01",
                "ms_played": 100_000,
            },
            {
                "play_id": 2,
                "track_id": "b",
                "track_name": "B",
                "artist_name": "Artist",
                "ts_date": "2026-01-01",
                "ms_played": 100_000,
            },
            {
                "play_id": 3,
                "track_id": "a",
                "track_name": "A",
                "artist_name": "Artist",
                "ts_date": "2026-01-01",
                "ms_played": 150_000,
            },
            {
                "play_id": 4,
                "track_id": "a",
                "track_name": "A",
                "artist_name": "Artist",
                "ts_date": "2026-01-01",
                "ms_played": 150_000,
            },
        ]
    )

    result = _daily_champion(frame, "track_id", "track_name", "artist_name")

    assert result.iloc[0]["entity_id"] == "a"
    assert result.iloc[0]["total_plays"] == 2
    assert result.iloc[0]["total_ms"] == 300_000


def test_daily_total_record_keeps_exact_duration_for_rank_and_payload() -> None:
    frame = _event_rows(
        [
            {"play_id": 1, "ts_date": "2026-01-01", "track_id": 1, "ms_played": 180_000},
            {"play_id": 2, "ts_date": "2026-01-02", "track_id": 2, "ms_played": 181_000},
        ]
    )
    frame["track_name"] = frame["track_id"].map({1: "A", 2: "B"})
    frame["album_name"] = frame["track_id"].map({1: "Album A", 2: "Album B"})
    frame["artist_name"] = "Artist"

    result = _daily_total_record(frame, frame, frame, frame)
    day_two = result[result["date"] == "2026-01-02"].iloc[0]

    assert day_two["hours_rank"] == 1
    assert day_two["total_ms"] == 181_000
    assert day_two["total_hours"] == 0.1


def test_single_day_longest_streak_reports_actual_duration() -> None:
    frame = _event_rows(
        [
            {
                "play_id": 1,
                "track_id": 1,
                "track_name": "One",
                "artist_name": "Artist",
                "ts_date": "2026-01-01",
                "ms_played": 180_000,
            }
        ]
    )

    result = _longest_streak_days(frame, "track_id", "track_name", "artist_name")

    assert result.iloc[0]["total_ms"] == 180_000
    assert result.iloc[0]["secondary_value"] == 0.1


def test_consecutive_marathon_uses_duration_before_stable_entity_id() -> None:
    frame = _event_rows(
        [
            {
                "play_id": 1,
                "track_id": "b",
                "track_name": "B",
                "artist_name": "Artist",
                "ts": "2026-01-01T00:00:00",
                "ms_played": 100_000,
            },
            {
                "play_id": 2,
                "track_id": "b",
                "track_name": "B",
                "artist_name": "Artist",
                "ts": "2026-01-01T00:03:00",
                "ms_played": 100_000,
            },
            {
                "play_id": 3,
                "track_id": "a",
                "track_name": "A",
                "artist_name": "Artist",
                "ts": "2026-01-01T00:06:00",
                "ms_played": 200_000,
            },
            {
                "play_id": 4,
                "track_id": "a",
                "track_name": "A",
                "artist_name": "Artist",
                "ts": "2026-01-01T00:09:00",
                "ms_played": 200_000,
            },
        ]
    )

    result = _consecutive_marathon(frame, "track_id", "track_name", "artist_name")

    assert result.iloc[0]["entity_id"] == "a"
    assert result.iloc[0]["total_ms"] == 400_000


def test_weekday_rank_is_assigned_after_sorting() -> None:
    frame = _event_rows(
        [
            {"play_id": 1, "ts_dow": 0, "ts_date": "2026-01-05"},
            {"play_id": 2, "ts_dow": 1, "ts_date": "2026-01-06"},
            {"play_id": 3, "ts_dow": 1, "ts_date": "2026-01-13"},
        ]
    )

    result = _weekday_preference(frame)

    assert result.iloc[0]["name"] == "周二"
    assert result.iloc[0]["rank"] == 1
    assert result.iloc[1]["rank"] == 2


def test_featured_artist_ranking_excludes_primary_credit() -> None:
    frame = _event_rows(
        [
            {
                "play_id": 1,
                "track_name": "Song (feat. Guest)",
                "artist_name": "Primary",
                "role": "primary",
            },
            {
                "play_id": 2,
                "track_name": "Song (feat. Guest)",
                "artist_name": "Primary",
                "role": "primary",
            },
            {
                "play_id": 3,
                "track_name": "Song (feat. Guest)",
                "artist_name": "Guest",
                "role": "featured",
            },
            {
                "play_id": 4,
                "track_name": "Song (feat. Guest)",
                "artist_name": "Guest",
                "role": "featured",
            },
        ]
    )

    result = _feat_lover_artist(frame)

    assert result["name"].tolist() == ["Guest"]
    assert result.iloc[0]["value"] == 2


def test_milestones_can_use_full_history_when_display_period_is_scoped() -> None:
    lifetime = _event_rows(
        [
            {
                "play_id": index,
                "ts": pd.Timestamp("2025-01-01") + pd.Timedelta(minutes=index),
                "ts_date": "2025-01-01",
                "track_id": index,
                "track_name": f"Track {index}",
                "artist_name": "Artist",
            }
            for index in range(500)
        ]
    )
    period = lifetime.iloc[:3].copy()
    records: dict = {}

    compute_behavior_records(
        records,
        period,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        milestone_event_frame=lifetime,
    )

    milestone = records["behavior_playback_milestones"].iloc[0]
    assert milestone["value"] == 500
    assert milestone["total_plays"] == 500
    assert milestone["scope"] == "lifetime"


def test_no_repeat_uses_play_id_when_timestamps_are_equal() -> None:
    frame = _event_rows(
        [
            {"play_id": 2, "ts": "2026-01-01T00:00:00", "track_id": "a"},
            {"play_id": 1, "ts": "2026-01-01T00:00:00", "track_id": "b"},
            {"play_id": 3, "ts": "2026-01-01T00:01:00", "track_id": "c"},
        ]
    )

    result = _no_repeat_streak(frame, "track_id", "track")

    assert result.iloc[0]["value"] == 3
