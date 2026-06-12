"""Playback counting policy helpers.

Extracted from backend.core.db to give the counting boundary a clear name
and make it independently testable.

effective_threshold() — compute the minimum ms_played for a valid play given
                         a track's duration. Implements R1 (dynamic threshold).

filter_effective_plays() — apply the threshold to a DataFrame. Supports
                           legacy static threshold and future dynamic mode.
"""

from __future__ import annotations

import pandas as pd


def effective_threshold(
    duration_ms: int | float | None,
    min_ms: int = 30_000,
    ratio: float = 0.1,
) -> int:
    """Return the minimum ms_played for a play to count as valid.

    R1: ms_played >= max(min_ms, duration_ms * ratio)

    Falls back to min_ms when duration_ms is unavailable (NULL, 0, NaN).
    """
    if duration_ms is None:
        return int(min_ms)
    try:
        dur = int(duration_ms)
    except (ValueError, TypeError):
        return int(min_ms)
    if dur <= 0:
        return int(min_ms)
    if pd.isna(duration_ms):
        return int(min_ms)
    return int(max(min_ms, dur * ratio))


def filter_effective_plays(
    df: pd.DataFrame,
    min_ms: int = 30_000,
    dynamic_threshold: bool = False,
    ratio: float = 0.1,
) -> pd.DataFrame:
    """Filter a DataFrame to only rows whose ms_played meets the threshold.

    When dynamic_threshold=False (default, legacy):
        ms_played >= min_ms

    When dynamic_threshold=True (R1):
        ms_played >= max(min_ms, duration_ms * ratio)

    Returns a copy of the filtered DataFrame.
    """
    if df.empty or min_ms <= 0:
        return df.copy()

    if not dynamic_threshold:
        return df[df["ms_played"] >= min_ms].copy()

    thresholds = df["duration_ms"].apply(
        lambda d: effective_threshold(d, min_ms=min_ms, ratio=ratio)
    )
    return df[df["ms_played"] >= thresholds].copy()
