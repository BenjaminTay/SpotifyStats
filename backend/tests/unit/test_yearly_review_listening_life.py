from __future__ import annotations

import pandas as pd

from backend.domains.yearly_review.listening_life import build_listening_life
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReviewCoverage,
    YearlyTasteCoverage,
)


def _coverage() -> YearlyReviewCoverage:
    return YearlyReviewCoverage(
        status="complete",
        play=YearlyPlayCoverage(
            status="complete",
            observed_start="2025-01-01",
            observed_end="2025-12-31",
            natural_days_span=365,
            import_coverage_status="unknown",
            internal_gap_status="unknown",
        ),
        billboard=YearlyBillboardCoverage(status="complete", source_status="complete"),
        comparison=YearlyComparisonCoverage(comparable=True, baseline_year=2024),
        taste=YearlyTasteCoverage(),
    )


def _stats(total: int = 1000) -> dict:
    hourly = [{"hour": hour, "plays": 20, "hours": 1} for hour in range(24)]
    hourly[22]["plays"] = 120
    for hour in range(0, 6):
        hourly[hour]["plays"] = 30
    return {
        "summary": {"total_plays": total},
        "hourly_distribution": hourly,
        "weekday_distribution": [
            {"day": str(day), "plays": value, "hours": 1}
            for day, value in enumerate([100, 100, 100, 100, 100, 150, 150])
        ],
        "behavior_summary": {"primary_platform": "ios", "primary_platform_rate": 80},
    }


def test_listening_life_uses_normalized_baselines_and_never_infers_gap() -> None:
    frame = pd.DataFrame(
        {
            "track_id": list(range(100)) * 10,
            "ts_date": ["2025-01-01"] * 1000,
        }
    )
    result = build_listening_life(
        _stats(),
        _coverage(),
        baseline_stats=_stats(800),
        play_rankings={
            "charts": {
                "artist": {"by_plays": [{"artist_name": "A", "plays": 400, "share_pct": 40}]}
            }
        },
        event_frame=frame,
    )

    ids = {item.headline_id for item in result.observations}
    assert "weekday_weekend_pattern" in ids
    assert "late_night_listening" in ids
    assert "artist_concentration" in ids
    assert "replay_pattern" in ids
    assert not any("空窗" in item.title or "空窗" in item.statement for item in result.observations)
    weekend = next(
        item for item in result.observations if item.headline_id == "weekday_weekend_pattern"
    )
    weekday_metric = next(
        metric for metric in result.metrics if metric.key == "weekday_daily_plays"
    )
    weekend_metric = next(
        metric for metric in result.metrics if metric.key == "weekend_daily_plays"
    )
    assert weekday_metric.value == 1.9
    assert weekend_metric.value == 2.9
    assert "周末每天平均播放 2.9 次" in weekend.statement
    assert "工作日为 1.9 次" in weekend.statement


def test_partial_window_uses_inclusive_calendar_denominators() -> None:
    coverage = _coverage()
    coverage.status = "observed_range"
    coverage.play.status = "observed_range"
    coverage.play.observed_start = "2025-01-01"
    coverage.play.observed_end = "2025-01-07"
    result = build_listening_life(_stats(), coverage)

    metrics = {metric.key: metric.value for metric in result.metrics}
    assert metrics["weekday_daily_plays"] == 100.0
    assert metrics["weekend_daily_plays"] == 150.0


def test_listening_life_uses_canonical_tracks_and_logical_artist_share() -> None:
    event_frame = pd.DataFrame(
        {
            "play_id": [1, 2, 3],
            "track_id": [1, 2, 3],
            "ts_date": ["2025-01-01", "2025-01-02", "2025-01-03"],
        }
    )
    annual_tracks = event_frame.assign(
        canonical_track_id=[100, 100, 200],
        canonical_track_name=["Known", "Known", "New"],
    )
    history_tracks = pd.concat(
        [
            pd.DataFrame(
                {
                    "play_id": [0],
                    "track_id": [9],
                    "canonical_track_id": [100],
                    "canonical_track_name": ["Known"],
                    "ts_date": ["2024-12-31"],
                }
            ),
            annual_tracks,
        ],
        ignore_index=True,
    )
    result = build_listening_life(
        _stats(3),
        _coverage(),
        play_rankings={
            "charts": {
                "artist": {"by_plays": [{"artist_name": "A", "plays": 2, "share_pct": 50.0}]}
            }
        },
        event_frame=event_frame,
        history_frame=event_frame,
        track_frame=annual_tracks,
        history_track_frame=history_tracks,
    )

    metrics = {metric.key: metric.value for metric in result.metrics}
    artist = next(
        item for item in result.observations if item.headline_id == "artist_concentration"
    )

    assert metrics["unique_tracks"] == 2
    assert metrics["new_tracks"] == 1
    assert metrics["new_track_rate_pct"] == 50.0
    assert metrics["top_artist_share_pct"] == 66.7
    assert "66.7% 的播放包含 A" in artist.statement
