"""Hour-slice geometry shared only within one Records builder invocation."""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.logical_timeline import (
    LISTENING_INTERVALS_COLUMN,
    explode_listening_slices,
)

_SLICE_COLUMNS = (
    "slice_start_at",
    "slice_end_at",
    "ms_played",
    "ts_date",
    "ts_date_dt",
    "ts_year",
    "ts_month",
    "ts_week",
    "ts_dow",
    "ts_hour",
)


class RecordsDurationFacts:
    """Reuse interval geometry, never entity rows, counts or fan-out totals.

    The original timeline splitter remains the sole authority for boundaries
    and per-slice millisecond rounding. Keys contain every ordered interval;
    entity identity/credit is deliberately absent because each output row is
    copied from its own source frame. No facts survive the builder invocation.
    """

    def __init__(self) -> None:
        self._positions: dict[tuple, list[int]] = {}
        self._geometry = pd.DataFrame()

    def hour_slices(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or LISTENING_INTERVALS_COLUMN not in frame:
            return frame.copy()
        keys = [
            tuple((int(start), int(end)) for start, end in intervals) if intervals else ()
            for intervals in frame[LISTENING_INTERVALS_COLUMN]
        ]
        missing = list(dict.fromkeys(key for key in keys if key not in self._positions))
        if missing:
            slices = explode_listening_slices(
                pd.DataFrame(
                    {LISTENING_INTERVALS_COLUMN: missing, "_interval_id": range(len(missing))}
                ),
                granularity="hour",
            )
            offset = len(self._geometry)
            for key in missing:
                self._positions[key] = []
            for position, interval_id in enumerate(slices["_interval_id"]):
                self._positions[missing[interval_id]].append(offset + position)
            if not slices.empty:
                geometry = slices[list(_SLICE_COLUMNS)]
                self._geometry = (
                    pd.concat([self._geometry, geometry], ignore_index=True)
                    if not self._geometry.empty
                    else geometry.reset_index(drop=True)
                )

        source_positions = []
        slice_positions = []
        for position, key in enumerate(keys):
            positions = self._positions[key]
            source_positions.extend([position] * len(positions))
            slice_positions.extend(positions)
        if not source_positions:
            return frame.iloc[0:0].copy()
        result = frame.iloc[source_positions].copy().reset_index(drop=True)
        geometry = self._geometry.iloc[slice_positions]
        for column in _SLICE_COLUMNS:
            result[column] = geometry[column].to_numpy()
        return result
