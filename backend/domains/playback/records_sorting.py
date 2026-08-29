"""Deterministic sorting helpers for Playback Records.

Every record list must sort the complete candidate set before applying its
display limit.  The helpers in this module keep that rule in one place and
make the final rank independent of pandas' input order.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from backend.domains.playback.records_helpers import TOP_RECORD_LIMIT


def sort_and_limit(
    frame: pd.DataFrame,
    columns: Sequence[str],
    ascending: Sequence[bool],
    *,
    limit: int = TOP_RECORD_LIMIT,
    assign_rank: bool = True,
) -> pd.DataFrame:
    """Sort all rows, apply the display limit, and assign final row ranks."""

    if frame.empty:
        return frame.copy()
    if len(columns) != len(ascending):
        raise ValueError("sort columns and ascending flags must have the same length")
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise KeyError(f"missing playback record sort columns: {missing}")

    result = frame.sort_values(
        list(columns),
        ascending=list(ascending),
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)
    if limit is not None:
        result = result.head(limit).copy()
    if assign_rank:
        result["rank"] = range(1, len(result) + 1)
    return result


def select_period_winners(
    frame: pd.DataFrame,
    period_column: str,
    primary_column: str,
    stable_column: str,
    *,
    secondary_column: str | None = None,
) -> pd.DataFrame:
    """Select one deterministic winner for each period.

    Periods are ordered chronologically for the winner selection only.  The
    caller controls the final presentation order afterwards.
    """

    columns = [period_column, primary_column]
    ascending = [True, False]
    if secondary_column is not None:
        columns.append(secondary_column)
        ascending.append(False)
    columns.append(stable_column)
    ascending.append(True)
    ordered = sort_and_limit(frame, columns, ascending, limit=None, assign_rank=False)
    return ordered.drop_duplicates(period_column, keep="first").copy()
