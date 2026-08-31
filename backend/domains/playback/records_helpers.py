"""Shared helpers for playback records computation."""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.logical_timeline import (
    attach_listening_duration_frame,
    explode_listening_slices,
    get_listening_duration_frame,
)

TOP_RECORD_LIMIT = 50


def records_duration_frame(
    event_frame: pd.DataFrame,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Return the attached all-listening duration rows scoped for Records.

    A filtered pandas frame may retain an attrs reference to the complete
    history.  Records callers must therefore pass their resolved period bounds
    when establishing a scope.  Once the scoped frame is attached, downstream
    record functions call this helper without bounds and cannot see rows from
    another period.

    Frames created directly by tests or legacy callers have no attached
    duration track; those retain the previous event-duration fallback.
    """
    attached = get_listening_duration_frame(event_frame)
    source = attached if attached is not None else event_frame
    if attached is not None and "slice_start_at" not in source.columns:
        source = explode_listening_slices(source, granularity="hour")
    if source.empty:
        return source.copy()

    scoped = source
    if (start_date or end_date) and "ts_date" in scoped.columns:
        dates = scoped["ts_date"].astype(str)
        mask = pd.Series(True, index=scoped.index)
        if start_date:
            mask &= dates >= start_date
        if end_date:
            mask &= dates <= end_date
        scoped = scoped.loc[mask]
    return scoped.copy()


def attach_scoped_records_duration(
    event_frame: pd.DataFrame,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Attach a period-scoped duration track to an event frame in place."""
    duration = records_duration_frame(
        event_frame,
        start_date=start_date,
        end_date=end_date,
    )
    return attach_listening_duration_frame(event_frame, duration)


def grouped_records_duration(
    event_frame: pd.DataFrame,
    group_cols: list[str],
    *,
    value_name: str = "total_ms",
) -> pd.DataFrame:
    """Aggregate the Records duration track without changing event counts."""
    duration = records_duration_frame(event_frame)
    if duration.empty or any(column not in duration.columns for column in group_cols):
        duration = event_frame
    if duration.empty or "ms_played" not in duration.columns:
        return pd.DataFrame(columns=[*group_cols, value_name])
    return (
        duration.groupby(group_cols, dropna=False)["ms_played"].sum().reset_index(name=value_name)
    )


def unique_cols(*cols):
    """Return deduplicated column list — first occurrence wins."""
    seen = set()
    result = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def safe_groupby_cols(base_cols, group_col, name_col, artist_col):
    """Build groupby column list, avoiding duplicates when group/name/artist overlap."""
    cols = list(base_cols)
    if group_col not in cols:
        cols.append(group_col)
    if name_col not in cols and name_col != group_col:
        cols.append(name_col)
    if artist_col not in cols and artist_col != group_col and artist_col != name_col:
        cols.append(artist_col)
    return cols


def safe_rename(df, name_col, artist_col):
    """Rename name_col/artist_col to standard 'name'/'artist_name' columns.

    When name_col == artist_col (e.g. artist records where both are "artist_name"),
    the column is renamed to "name" and then copied back to "artist_name" so that
    downstream cover-URL lookup can find the artist name in either column.
    """
    if name_col != "name" and name_col in df.columns:
        df = df.rename(columns={name_col: "name"})
    if "name" not in df.columns:
        df["name"] = ""
    if artist_col != "artist_name" and artist_col in df.columns:
        df = df.rename(columns={artist_col: "artist_name"})
    if "artist_name" not in df.columns:
        # When name_col == artist_col the original column was renamed to "name"
        # above; copy it back so artist cover lookup works.
        df["artist_name"] = df["name"] if name_col == artist_col else ""
    return df
