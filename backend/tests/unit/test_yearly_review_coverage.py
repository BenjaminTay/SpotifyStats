from __future__ import annotations

from datetime import date

import pandas as pd

from backend.domains.yearly_review.coverage import (
    build_billboard_coverage,
    build_comparison_coverage,
    build_play_coverage,
    build_taste_coverage,
    build_yearly_review_coverage,
)


def _frame(*dates: str) -> pd.DataFrame:
    return pd.DataFrame({"ts_date": list(dates)})


def test_complete_year_keeps_unknown_internal_gap_separate() -> None:
    result = build_play_coverage(
        _frame("2025-01-01", "2025-06-01", "2025-12-31"),
        year=2025,
        today=date(2026, 8, 12),
    )

    assert result.status == "complete"
    assert result.natural_days_span == 365
    assert result.active_days == 3
    assert result.internal_gap_status == "unknown"
    assert result.import_coverage_status == "unknown"


def test_current_year_from_january_is_year_to_date() -> None:
    result = build_play_coverage(
        _frame("2026-01-01", "2026-04-15"),
        year=2026,
        today=date(2026, 4, 20),
    )

    assert result.status == "year_to_date"
    assert result.latest_data_date == "2026-04-15"


def test_missing_year_start_is_observed_range() -> None:
    result = build_play_coverage(
        _frame("2025-03-01", "2025-12-31"),
        year=2025,
        today=date(2026, 1, 1),
    )

    assert result.status == "observed_range"
    assert result.is_calendar_start_observed is False
    assert result.is_calendar_end_observed is True


def test_short_observed_range_is_insufficient_and_empty_is_distinct() -> None:
    insufficient = build_play_coverage(
        _frame("2025-05-01", "2025-05-20"),
        year=2025,
    )
    empty = build_play_coverage(pd.DataFrame(), year=2025)

    assert insufficient.status == "insufficient"
    assert insufficient.reason == "observed_span_below_minimum"
    assert empty.status == "empty"
    assert empty.reason == "no_effective_plays"


def test_verified_internal_gap_prevents_complete_claim() -> None:
    result = build_play_coverage(
        _frame("2025-01-01", "2025-12-31"),
        year=2025,
        internal_gap_status="verified_gaps",
    )

    assert result.status == "observed_range"
    assert result.internal_gap_status == "verified_gaps"


def test_verified_partial_import_prevents_complete_claim() -> None:
    result = build_play_coverage(
        _frame("2025-01-01", "2025-12-31"),
        year=2025,
        import_coverage_status="verified_partial",
    )

    assert result.status == "observed_range"
    assert result.import_coverage_status == "verified_partial"


def test_billboard_adapter_handles_complete_partial_and_missing_weeks() -> None:
    complete = build_billboard_coverage(
        {
            "coverage_status": "complete",
            "observed_weeks": 52,
            "expected_weeks": 52,
            "has_internal_gaps": False,
            "first_billboard_week": "2025-01-03T00:00:00",
            "last_billboard_week": "2025-12-26T00:00:00",
        }
    )
    partial = build_billboard_coverage(
        {"coverage_status": "partial_start", "observed_weeks": 40, "expected_weeks": 52}
    )
    empty = build_billboard_coverage(None)

    assert complete.status == "complete"
    assert complete.has_internal_gaps is False
    assert partial.status == "observed_range"
    assert partial.reason == "billboard_partial_start"
    assert empty.status == "empty"
    assert empty.reason == "no_billboard_weeks"


def test_comparison_requires_prior_year_aligned_window() -> None:
    current = build_play_coverage(
        _frame("2026-01-01", "2026-04-15"),
        year=2026,
        today=date(2026, 4, 20),
    )
    baseline = build_play_coverage(
        _frame("2025-01-01", "2025-12-31"),
        year=2025,
    )
    comparable = build_comparison_coverage(
        report_year=2026,
        current=current,
        baseline=baseline,
    )
    unavailable = build_comparison_coverage(
        report_year=2026,
        current=current,
        baseline=None,
    )

    assert comparable.comparable is True
    assert comparable.aligned_end == "2025-04-15"
    assert unavailable.comparable is False
    assert unavailable.reason == "baseline_unavailable"


def test_taste_coverage_applies_frozen_thresholds_and_keeps_unknown() -> None:
    result = build_taste_coverage(
        {
            "primary_styles": {"total_hours": 100, "known_hours": 92, "unknown_hours": 8},
            "regional_pop": {"total_hours": 100, "known_hours": 48, "unknown_hours": 52},
            "language_dist": {
                "eligible_hours": 100,
                "classified_hours": 30,
                "unknown_hours": 70,
                "classified_pct": 30,
            },
        },
        release_era={"known_pct": 99.5, "unknown_hours": 0.5},
    )

    assert result.style.level == "core"
    assert result.style.conclusion_allowed is True
    assert result.scene.level == "secondary"
    assert result.scene.conclusion_allowed is False
    assert result.language.level == "insufficient"
    assert result.language.unknown_hours == 70
    assert result.release_era.level == "core"


def test_aggregate_status_follows_play_coverage_without_hiding_subcoverage() -> None:
    play = build_play_coverage(_frame("2025-01-01", "2025-12-31"), year=2025)
    billboard = build_billboard_coverage(None)
    comparison = build_comparison_coverage(
        report_year=2025,
        current=play,
        baseline=None,
    )
    taste = build_taste_coverage(None)

    result = build_yearly_review_coverage(
        play=play,
        billboard=billboard,
        comparison=comparison,
        taste=taste,
    )

    assert result.status == "complete"
    assert result.billboard.status == "empty"
    assert result.comparison.comparable is False
    assert result.taste.style.level == "unavailable"
