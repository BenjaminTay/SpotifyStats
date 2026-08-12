from __future__ import annotations

from backend.domains.yearly_review.passport import build_passport_and_headlines
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReviewCoverage,
    YearlyTasteCoverage,
)


def _coverage(*, comparable: bool) -> YearlyReviewCoverage:
    return YearlyReviewCoverage(
        status="complete",
        play=YearlyPlayCoverage(
            status="complete", observed_start="2025-01-01", observed_end="2025-12-31"
        ),
        billboard=YearlyBillboardCoverage(status="complete", source_status="complete"),
        comparison=YearlyComparisonCoverage(
            baseline_year=2024 if comparable else None,
            comparable=comparable,
            reason=None if comparable else "baseline_unavailable",
        ),
        taste=YearlyTasteCoverage(),
    )


def _stats(hours: float = 100) -> dict:
    return {
        "summary": {
            "total_plays": 1000,
            "total_hours": hours,
            "active_days": 300,
            "unique_tracks": 200,
            "unique_albums": 40,
            "unique_artists": 30,
        },
        "monthly_distribution": [
            {"month": month, "plays": 10 * month, "hours": float(month), "active_days": 10}
            for month in range(1, 13)
        ],
    }


def test_passport_uses_real_baseline_and_selects_three_distinct_headlines() -> None:
    rankings = {
        "charts": {
            "artist": {
                "by_plays": [
                    {
                        "artist_name": "Artist",
                        "plays": 400,
                        "hours": 40,
                        "share_pct": 40,
                        "deep_link": "/music/artists/Artist",
                    }
                ]
            }
        }
    }
    passport, headlines = build_passport_and_headlines(
        2025,
        _coverage(comparable=True),
        _stats(100),
        baseline_stats=_stats(80),
        play_rankings=rankings,
        baseline_entity_counts={"track": 180, "album": 35, "artist": 28},
    )

    assert passport.status == "complete"
    assert (
        next(metric for metric in passport.metrics if metric.key == "total_hours").comparison_value
        == 80
    )
    assert [headline.headline_id for headline in headlines] == [
        "listening_time_change",
        "most_played_artist",
        "peak_listening_month",
    ]
    assert headlines[0].primary_metric.value == 25.0


def test_passport_uses_canonical_ranking_counts_instead_of_raw_summary_counts() -> None:
    rankings = {
        "charts": {
            "track": {"available_count": 2754, "by_plays": []},
            "album": {"available_count": 623, "by_plays": []},
            "artist": {"available_count": 440, "by_plays": []},
        }
    }

    passport, _ = build_passport_and_headlines(
        2025,
        _coverage(comparable=False),
        _stats(),
        play_rankings=rankings,
    )

    metrics = {metric.key: metric for metric in passport.metrics}
    assert metrics["unique_tracks"].value == 2754
    assert metrics["unique_tracks"].label == "年度播放曲目"
    assert metrics["unique_albums"].value == 623
    assert metrics["unique_albums"].label == "年度播放专辑"
    assert metrics["unique_artists"].value == 440
    assert metrics["unique_artists"].label == "年度播放艺人"


def test_no_baseline_never_invents_default_percentage() -> None:
    passport, headlines = build_passport_and_headlines(
        2025,
        _coverage(comparable=False),
        _stats(),
    )

    assert all(metric.comparison_value is None for metric in passport.metrics)
    assert "listening_time_change" not in {headline.headline_id for headline in headlines}


def test_failed_ranking_does_not_replace_nonempty_raw_counts_with_zero() -> None:
    passport, _ = build_passport_and_headlines(
        2025,
        _coverage(comparable=False),
        _stats(),
        play_rankings={
            "empty": True,
            "charts": {
                entity: {"available_count": 0, "by_plays": []}
                for entity in ("track", "album", "artist")
            },
        },
    )

    values = {metric.key: metric.value for metric in passport.metrics}
    assert values["unique_tracks"] == 200
    assert values["unique_albums"] == 40
    assert values["unique_artists"] == 30
