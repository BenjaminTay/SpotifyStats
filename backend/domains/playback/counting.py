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


def assign_logical_event_id(
    df: pd.DataFrame,
    *,
    preserve_legacy_artist_event_id: bool = False,
) -> pd.DataFrame:
    """Attach one stable ID to each post-merge logical play event.

    The ID is assigned only after merge/filter has produced the final logical
    event rows and before artist fan-out.  It is therefore intentionally a
    frame-local ordinal: the same event keeps its ID across every credited
    artist row, while two expanded events originating from one source play do
    not collapse into one event during artist identity canonicalization.

    ``_artist_event_id`` is retained as a compatibility alias for analysis
    consumers that use it to reason about event continuity.
    """
    result = df.copy()
    if "_logical_event_id" not in result.columns:
        if "play_id" in result.columns:
            fallback_ids = pd.Series(result.index, index=result.index)
            source_ids = result["play_id"].where(result["play_id"].notna(), fallback_ids)
            duplicate_ordinals = source_ids.groupby(source_ids, sort=False).cumcount()
            result["_logical_event_id"] = [
                f"raw_play_v1:{source_id}:{ordinal}"
                for source_id, ordinal in zip(source_ids, duplicate_ordinals)
            ]
        else:
            result["_logical_event_id"] = [f"frame_event_v1:{index}" for index in result.index]
    if preserve_legacy_artist_event_id:
        # Legacy record consumers use numeric adjacency (``diff() == 1``) to
        # detect artist streaks. Keep that compatibility projection while the
        # canonical logical identity remains the stable string above.
        result["_artist_event_id"] = pd.factorize(result["_logical_event_id"], sort=False)[0]
    return result


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
