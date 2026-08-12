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
    assert "1.50 倍" in weekend.statement
