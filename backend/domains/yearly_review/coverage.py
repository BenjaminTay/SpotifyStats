"""Coverage Passport builders for Yearly Review V2."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

import pandas as pd

from backend.models.yearly_review import (
    ImportCoverageStatus,
    InternalGapStatus,
    TasteCoverageLevel,
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReportStatus,
    YearlyReviewCoverage,
    YearlyTasteAxisCoverage,
    YearlyTasteCoverage,
)

MIN_REPORT_DAYS = 90
MIN_BILLBOARD_WEEKS = 4
TASTE_CORE_THRESHOLD = 70.0
TASTE_SECONDARY_THRESHOLD = 40.0


def _date_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="object")
    column = next((name for name in ("ts_date", "ts") if name in frame.columns), None)
    if column is None:
        return pd.Series(dtype="object")
    parsed = pd.to_datetime(frame[column], errors="coerce", utc=True).dropna()
    if parsed.empty:
        return pd.Series(dtype="object")
    return parsed.dt.date


def build_play_coverage(
    frame: pd.DataFrame,
    *,
    year: int,
    today: date | None = None,
    import_coverage_status: ImportCoverageStatus = "unknown",
    internal_gap_status: InternalGapStatus = "unknown",
    minimum_report_days: int = MIN_REPORT_DAYS,
) -> YearlyPlayCoverage:
    """Describe observed dates without inventing import completeness."""
    dates = _date_series(frame)
    if dates.empty:
        return YearlyPlayCoverage(
            status="empty",
            import_coverage_status=import_coverage_status,
            internal_gap_status=internal_gap_status,
            reason="no_effective_plays",
        )

    observed_start = min(dates)
    observed_end = max(dates)
    natural_days_span = (observed_end - observed_start).days + 1
    calendar_start = date(year, 1, 1)
    calendar_end = date(year, 12, 31)
    as_of = today or date.today()
    starts_at_boundary = observed_start <= calendar_start
    ends_at_boundary = observed_end >= calendar_end

    status: YearlyReportStatus
    reason: str | None = None
    if natural_days_span < minimum_report_days:
        status = "insufficient"
        reason = "observed_span_below_minimum"
    elif (
        starts_at_boundary
        and ends_at_boundary
        and import_coverage_status != "verified_partial"
        and internal_gap_status != "verified_gaps"
    ):
        status = "complete"
    elif year == as_of.year and starts_at_boundary and observed_end <= as_of:
        status = "year_to_date"
        reason = "current_year_observed_to_latest_data"
    else:
        status = "observed_range"
        reason = "calendar_boundary_not_fully_observed"

    return YearlyPlayCoverage(
        status=status,
        observed_start=observed_start.isoformat(),
        observed_end=observed_end.isoformat(),
        active_days=int(dates.nunique()),
        natural_days_span=natural_days_span,
        import_coverage_status=import_coverage_status,
        internal_gap_status=internal_gap_status,
        is_calendar_start_observed=starts_at_boundary,
        is_calendar_end_observed=ends_at_boundary,
        latest_data_date=observed_end.isoformat(),
        reason=reason,
    )


def build_billboard_coverage(meta: dict[str, Any] | None) -> YearlyBillboardCoverage:
    """Adapt the existing Year-End coverage contract without reinterpreting weeks."""
    source = meta or {}
    source_status = str(source.get("coverage_status") or "empty")
    observed_weeks = int(source.get("observed_weeks") or 0)
    expected_weeks = int(source.get("expected_weeks") or 0)

    if source_status == "empty" or observed_weeks == 0:
        status: YearlyReportStatus = "empty"
        reason = "no_billboard_weeks"
    elif observed_weeks < MIN_BILLBOARD_WEEKS:
        status = "insufficient"
        reason = "billboard_weeks_below_minimum"
    elif source_status == "complete":
        status = "complete"
        reason = None
    elif source_status == "year_to_date":
        status = "year_to_date"
        reason = "billboard_year_to_date"
    else:
        status = "observed_range"
        reason = f"billboard_{source_status}"

    return YearlyBillboardCoverage(
        status=status,
        source_status=source_status,
        observed_weeks=observed_weeks,
        expected_weeks=expected_weeks,
        has_internal_gaps=source.get("has_internal_gaps"),
        first_billboard_week=source.get("first_billboard_week"),
        last_billboard_week=source.get("last_billboard_week"),
        reason=reason,
    )


def _previous_year_date(value: date, baseline_year: int) -> date:
    day = min(value.day, calendar.monthrange(baseline_year, value.month)[1])
    return date(baseline_year, value.month, day)


def _next_year_date(value: date, current_year: int) -> date:
    day = min(value.day, calendar.monthrange(current_year, value.month)[1])
    return date(current_year, value.month, day)


def build_comparison_coverage(
    *,
    report_year: int,
    current: YearlyPlayCoverage,
    baseline: YearlyPlayCoverage | None,
) -> YearlyComparisonCoverage:
    """Resolve the largest trustworthy calendar window shared by both years.

    A complete current year may have a partial first year in the local archive.
    In that case, comparing the full current year with the partial baseline would
    mix different observation lengths.  We first keep the historical exact
    aligned-window behavior, then fall back to the largest common period when it
    is at least the minimum report length.
    """
    baseline_year = report_year - 1
    if baseline is None or baseline.status == "empty":
        return YearlyComparisonCoverage(
            baseline_year=baseline_year,
            comparable=False,
            reason="baseline_unavailable",
        )
    if current.status in {"empty", "insufficient"}:
        return YearlyComparisonCoverage(
            baseline_year=baseline_year,
            comparable=False,
            reason="current_period_insufficient",
        )
    if not current.observed_start or not current.observed_end:
        return YearlyComparisonCoverage(
            baseline_year=baseline_year,
            comparable=False,
            reason="current_bounds_unavailable",
        )

    current_start = date.fromisoformat(current.observed_start)
    current_end = date.fromisoformat(current.observed_end)
    aligned_start = _previous_year_date(current_start, baseline_year)
    aligned_end = _previous_year_date(current_end, baseline_year)
    if not baseline.observed_start or not baseline.observed_end:
        return YearlyComparisonCoverage(
            baseline_year=baseline_year,
            aligned_start=aligned_start.isoformat(),
            aligned_end=aligned_end.isoformat(),
            comparable=False,
            reason="baseline_bounds_unavailable",
        )

    baseline_start = date.fromisoformat(baseline.observed_start)
    baseline_end = date.fromisoformat(baseline.observed_end)
    aligned_covered = baseline_start <= aligned_start and baseline_end >= aligned_end
    if aligned_covered:
        mode = (
            "full_year"
            if current.status == "complete" and baseline.status == "complete"
            else "same_period"
        )
        return YearlyComparisonCoverage(
            baseline_year=baseline_year,
            mode=mode,
            current_start=current_start.isoformat(),
            current_end=current_end.isoformat(),
            baseline_start=aligned_start.isoformat(),
            baseline_end=aligned_end.isoformat(),
            aligned_start=aligned_start.isoformat(),
            aligned_end=aligned_end.isoformat(),
            comparable=True,
        )

    # Map the partial baseline interval into the current year and intersect it
    # with the current observed interval.  This gives a same-length, same-month
    # comparison without treating missing historical months as zero playback.
    baseline_start_in_current = _next_year_date(baseline_start, report_year)
    baseline_end_in_current = _next_year_date(baseline_end, report_year)
    common_current_start = max(current_start, baseline_start_in_current)
    common_current_end = min(current_end, baseline_end_in_current)
    common_days = (common_current_end - common_current_start).days + 1
    if common_current_start > common_current_end or common_days < MIN_REPORT_DAYS:
        return YearlyComparisonCoverage(
            baseline_year=baseline_year,
            mode="unavailable",
            aligned_start=aligned_start.isoformat(),
            aligned_end=aligned_end.isoformat(),
            comparable=False,
            reason="no_sufficient_common_period",
        )

    common_baseline_start = _previous_year_date(common_current_start, baseline_year)
    common_baseline_end = _previous_year_date(common_current_end, baseline_year)
    return YearlyComparisonCoverage(
        baseline_year=baseline_year,
        mode="common_period",
        current_start=common_current_start.isoformat(),
        current_end=common_current_end.isoformat(),
        baseline_start=common_baseline_start.isoformat(),
        baseline_end=common_baseline_end.isoformat(),
        aligned_start=common_baseline_start.isoformat(),
        aligned_end=common_baseline_end.isoformat(),
        comparable=True,
    )


def _axis_coverage(known_pct: float, unknown_hours: float = 0) -> YearlyTasteAxisCoverage:
    known = min(max(float(known_pct), 0.0), 100.0)
    level: TasteCoverageLevel
    if known >= TASTE_CORE_THRESHOLD:
        level = "core"
        conclusion_allowed = True
        caveat_required = False
    elif known >= TASTE_SECONDARY_THRESHOLD:
        level = "secondary"
        conclusion_allowed = False
        caveat_required = True
    elif known > 0 or unknown_hours > 0:
        level = "insufficient"
        conclusion_allowed = False
        caveat_required = True
    else:
        level = "unavailable"
        conclusion_allowed = False
        caveat_required = True
    return YearlyTasteAxisCoverage(
        known_pct=round(known, 2),
        unknown_hours=max(float(unknown_hours), 0.0),
        level=level,
        conclusion_allowed=conclusion_allowed,
        caveat_required=caveat_required,
    )


def _known_pct(axis: dict[str, Any] | None) -> tuple[float, float]:
    values = axis or {}
    total = float(values.get("total_hours") or values.get("eligible_hours") or 0)
    known = float(values.get("known_hours") or values.get("classified_hours") or 0)
    unknown = float(values.get("unknown_hours") or 0)
    if "classified_pct" in values:
        return float(values["classified_pct"]), unknown
    return (known / total * 100 if total > 0 else 0.0), unknown


def build_taste_coverage(
    taste_profile: dict[str, Any] | None,
    *,
    release_era: dict[str, Any] | None = None,
) -> YearlyTasteCoverage:
    profile = taste_profile or {}
    style_pct, style_unknown = _known_pct(profile.get("primary_styles"))
    scene_pct, scene_unknown = _known_pct(profile.get("regional_pop"))
    language_pct, language_unknown = _known_pct(profile.get("language_dist"))
    era = release_era or {}
    era_pct = float(era.get("known_pct") or 0)
    era_unknown = float(era.get("unknown_hours") or 0)
    return YearlyTasteCoverage(
        style=_axis_coverage(style_pct, style_unknown),
        scene=_axis_coverage(scene_pct, scene_unknown),
        language=_axis_coverage(language_pct, language_unknown),
        release_era=_axis_coverage(era_pct, era_unknown),
    )


def build_yearly_review_coverage(
    *,
    play: YearlyPlayCoverage,
    billboard: YearlyBillboardCoverage,
    comparison: YearlyComparisonCoverage,
    taste: YearlyTasteCoverage,
) -> YearlyReviewCoverage:
    """Assemble the passport; top-level status follows observable play coverage."""
    return YearlyReviewCoverage(
        status=play.status,
        play=play,
        billboard=billboard,
        comparison=comparison,
        taste=taste,
    )
