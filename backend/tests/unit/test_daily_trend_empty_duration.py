from __future__ import annotations

import pandas as pd
import pytest

from backend.services.analysis_stats_service import _daily_trend, _year_distribution
from backend.services.entity_stats_service import _entity_base

pytestmark = pytest.mark.unit


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.DataFrame(
        {
            "ts_date": ["2026-01-02", "2025-12-31", "2026-01-02"],
            "ts_year": [2026, 2025, 2026],
            "ts_month": [1, 12, 1],
            "ts_dow": [4, 2, 4],
            "ts_hour": [12, 12, 12],
            "track_id": [1, 1, 1],
            "artist_name": ["Featured Guest"] * 3,
            "ms_played": [180_000] * 3,
        }
    )
    durations = pd.DataFrame(
        {
            "ts_date": ["2026-01-03", "2026-01-02"],
            "ts_year": [2026, 2026],
            "ms_played": [1_800_000, 3_600_000],
        }
    )
    return events, durations


@pytest.mark.parametrize(
    "has_events,has_duration,daily,yearly",
    [
        (
            True,
            False,
            [
                {"date": "2025-12-31", "plays": 1, "hours": 0.0},
                {"date": "2026-01-02", "plays": 2, "hours": 0.0},
            ],
            [
                {"year": 2025, "plays": 1, "hours": 0.0},
                {"year": 2026, "plays": 2, "hours": 0.0},
            ],
        ),
        (
            False,
            True,
            [
                {"date": "2026-01-02", "plays": 0, "hours": 1.0},
                {"date": "2026-01-03", "plays": 0, "hours": 0.5},
            ],
            [{"year": 2026, "plays": 0, "hours": 1.5}],
        ),
        (False, False, [], []),
        (
            True,
            True,
            [
                {"date": "2025-12-31", "plays": 1, "hours": 0.0},
                {"date": "2026-01-02", "plays": 2, "hours": 1.0},
                {"date": "2026-01-03", "plays": 0, "hours": 0.5},
            ],
            [
                {"year": 2025, "plays": 1, "hours": 0.0},
                {"year": 2026, "plays": 2, "hours": 1.5},
            ],
        ),
    ],
    ids=["counts-only", "duration-only", "both-empty", "both-populated"],
)
def test_trends_keep_period_keys_for_independent_count_and_duration_tracks(
    has_events, has_duration, daily, yearly
):
    events, durations = _frames()
    if not has_events:
        events = events.iloc[0:0]
    if not has_duration:
        durations = durations.iloc[0:0]
    assert _daily_trend(events, durations) == daily
    assert _year_distribution(events, durations) == yearly


def test_featured_entity_without_duration_keeps_count_trends():
    events, _ = _frames()
    result = _entity_base(events, events, {}, events.iloc[0:0])
    assert result["summary"]["total_plays"] == 3
    assert result["summary"]["total_hours"] == 0.0
    assert result["daily_trend"] == [
        {"date": "2025-12-31", "plays": 1, "hours": 0.0},
        {"date": "2026-01-02", "plays": 2, "hours": 0.0},
    ]
    assert result["year_distribution"] == [
        {"year": 2025, "plays": 1, "hours": 0.0},
        {"year": 2026, "plays": 2, "hours": 0.0},
    ]
    assert result["cumulative_trend"][-1] == {
        "date": "2026-01-02",
        "cumulative_plays": 3,
        "cumulative_hours": 0.0,
    }
