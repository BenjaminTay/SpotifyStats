"""Independent listening-duration helpers for yearly report consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from backend.domains.playback.logical_timeline import (
    explode_listening_slices,
    get_listening_duration_frame,
)


@dataclass(eq=False)
class ListeningDurationSlicesRef:
    """Identity reference for scoped duration slices stored in pandas attrs."""

    frame: pd.DataFrame

    def __eq__(self, other: object) -> bool:
        return self is other

    def __deepcopy__(self, memo: dict[int, object]) -> ListeningDurationSlicesRef:
        return self

    def __getitem__(self, key):
        """Keep the historical attrs payload's read-only column access."""
        return self.frame[key]


def listening_duration_slices(
    frame: pd.DataFrame,
    *,
    source_frame: pd.DataFrame | None = None,
    year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    granularity: Literal["hour", "day"] = "hour",
) -> pd.DataFrame:
    """Return unthresholded listening slices scoped to a yearly-report window.

    Logical event rows remain the source of play counts.  This helper reads the
    independently attached duration timeline, explodes it at local boundaries,
    and only then applies the requested calendar window.  Falling back to the
    supplied frame keeps older fixtures and pre-dual-track callers compatible.
    """
    owner = source_frame if source_frame is not None else frame
    scoped = owner.attrs.get("listening_duration_slices")
    if isinstance(scoped, ListeningDurationSlicesRef):
        slices = scoped.frame.copy()
    elif isinstance(scoped, pd.DataFrame):
        slices = scoped.copy()
    else:
        duration_source = get_listening_duration_frame(owner)
        slices = explode_listening_slices(
            duration_source if duration_source is not None else owner,
            granularity=granularity,
        )

    if slices.empty:
        return slices.reset_index(drop=True)
    if year is not None:
        if "ts_year" in slices.columns:
            years = pd.to_numeric(slices["ts_year"], errors="coerce")
        else:
            years = pd.to_datetime(slices["ts_date"], errors="coerce").dt.year
        slices = slices[years == int(year)]
    if start_date is not None:
        slices = slices[slices["ts_date"].astype(str).str[:10] >= str(start_date)]
    if end_date is not None:
        slices = slices[slices["ts_date"].astype(str).str[:10] <= str(end_date)]
    return slices.copy().reset_index(drop=True)


def with_listening_duration_slices(
    events: pd.DataFrame,
    duration_slices: pd.DataFrame,
) -> pd.DataFrame:
    """Attach already-scoped duration slices without changing event rows."""
    result = events.copy()
    result.attrs["listening_duration_slices"] = ListeningDurationSlicesRef(
        duration_slices.reset_index(drop=True)
    )
    return result


def count_duration_frame(
    events: pd.DataFrame,
    duration_slices: pd.DataFrame,
) -> pd.DataFrame:
    """Combine count and duration facts while retaining independent weights."""
    count_rows = events.copy()
    count_rows["play_count"] = 1
    count_rows["total_ms"] = 0
    time_rows = duration_slices.copy()
    time_rows["play_count"] = 0
    time_rows["total_ms"] = pd.to_numeric(
        time_rows.get("ms_played", pd.Series(index=time_rows.index, dtype="float64")),
        errors="coerce",
    ).fillna(0)
    if count_rows.empty:
        return time_rows.reset_index(drop=True)
    if time_rows.empty:
        return count_rows.reset_index(drop=True)
    return pd.concat([count_rows, time_rows], ignore_index=True, sort=False)
