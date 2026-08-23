"""Billboard week coverage rules shared by raw and pre-aggregated charts."""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.domains.playback.logical_timeline import (
    attach_billboard_weighted_frame,
    billboard_week_for_timestamps,
    get_billboard_weighted_frame,
)


def open_billboard_week_for_latest_timestamp(
    latest_timestamp: object,
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> date | None:
    """Return the week that is still incomplete at the data coverage edge.

    Spotify exports do not carry a separate coverage-end timestamp.  The
    latest observed play is therefore the conservative coverage edge: its
    containing Billboard week is never published as a finished chart.
    """
    values = pd.Series([latest_timestamp], dtype=object)
    parsed = pd.to_datetime(values, errors="coerce", utc=True, format="mixed")
    if parsed.isna().all():
        return None
    return billboard_week_for_timestamps(
        parsed,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    ).iloc[0]


def keep_complete_billboard_weeks(
    frame: pd.DataFrame,
    *,
    open_week: date | None,
) -> pd.DataFrame:
    """Drop the coverage-edge week while preserving weighted-frame attrs."""
    if frame.empty or open_week is None or "billboard_week" not in frame.columns:
        return frame.copy()

    week_values = pd.to_datetime(frame["billboard_week"], errors="coerce").dt.date
    result = frame.loc[week_values < open_week].copy()

    weighted = get_billboard_weighted_frame(frame)
    if weighted is not None:
        weighted_weeks = pd.to_datetime(weighted["billboard_week"], errors="coerce").dt.date
        attach_billboard_weighted_frame(
            result,
            weighted.loc[weighted_weeks < open_week].copy(),
        )
    return result


def latest_source_timestamp() -> str | None:
    """Read the latest imported playback timestamp without mutating the DB."""
    from backend.core.db import get_db

    conn = get_db(readonly=True)
    try:
        row = conn.execute("SELECT MAX(ts) FROM plays").fetchone()
        return str(row[0]) if row is not None and row[0] else None
    finally:
        conn.close()


def current_open_billboard_week(
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> date | None:
    """Return the unfinished week at the current imported-data boundary."""
    return open_billboard_week_for_latest_timestamp(
        latest_source_timestamp(),
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
