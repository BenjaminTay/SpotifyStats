"""Aligned calendar windows shared by every annual comparison consumer."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class AlignedComparisonFrames:
    current: pd.DataFrame
    baseline: pd.DataFrame
    current_start: str
    current_end: str
    baseline_start: str
    baseline_end: str


def previous_year_date(value: str | date) -> str:
    current = date.fromisoformat(value) if isinstance(value, str) else value
    target_year = current.year - 1
    day = min(current.day, calendar.monthrange(target_year, current.month)[1])
    return date(target_year, current.month, day).isoformat()


def filter_date_range(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if frame.empty or "ts_date" not in frame.columns:
        return frame.copy()
    dates = frame["ts_date"].astype(str).str[:10]
    return frame[(dates >= start) & (dates <= end)].copy()


def aligned_comparison_frames(
    frame: pd.DataFrame,
    *,
    report_year: int,
    observed_start: str,
    observed_end: str,
) -> AlignedComparisonFrames:
    current_start = observed_start
    current_end = observed_end
    if not current_start.startswith(f"{report_year:04d}-") or not current_end.startswith(
        f"{report_year:04d}-"
    ):
        raise ValueError("observed comparison bounds must belong to the report year")
    baseline_start = previous_year_date(current_start)
    baseline_end = previous_year_date(current_end)
    return AlignedComparisonFrames(
        current=filter_date_range(frame, current_start, current_end),
        baseline=filter_date_range(frame, baseline_start, baseline_end),
        current_start=current_start,
        current_end=current_end,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
    )
