"""Deterministic logical-play timeline reconstruction.

Spotify Extended Streaming History records the instant at which playback
stopped (``ts``) and the amount listened (``ms_played``), but it does not
record an exact start/pause/resume timeline.  This module reconstructs the
highest-fidelity deterministic timeline available from those fields:

* infer one listened interval per raw row;
* group adjacent same-track/source rows by *idle* time;
* emit one row per logical play with its own ``counted_at``;
* retain the credited listened intervals for duration attribution.

The raw ``plays`` table remains untouched.  All derived timestamps are UTC;
the familiar ``ts_*`` columns are rebuilt in Asia/Shanghai for consumers.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

PLAYBACK_EVENT_POLICY_VERSION = "logical_event_time_v2"
PLAYBACK_TIMEZONE = "Asia/Shanghai"
DEFAULT_MAX_MERGE_GAP_MINUTES = 5
OVERLAP_TOLERANCE_SECONDS = 2

LISTENING_INTERVALS_COLUMN = "_listening_intervals_ns"


@dataclass(eq=False)
class BillboardWeightedFrameRef:
    """Pandas-attrs-safe reference to a weighted Billboard frame.

    Pandas compares ``DataFrame.attrs`` while finalising derived objects. A
    bare DataFrame returns another DataFrame from equality and can therefore
    raise an ambiguous-truth-value error. Identity equality keeps the payload
    available without interfering with unrelated groupby/concat operations.
    """

    frame: pd.DataFrame

    def __eq__(self, other: object) -> bool:
        return self is other


def attach_billboard_weighted_frame(events: pd.DataFrame, weighted: pd.DataFrame) -> pd.DataFrame:
    """Attach weighted duration/count rows without unsafe attrs equality."""
    events.attrs["billboard_weighted_frame"] = BillboardWeightedFrameRef(weighted)
    return events


def get_billboard_weighted_frame(events: pd.DataFrame) -> pd.DataFrame | None:
    """Return an attached weighted frame, including the pre-V2 raw form."""
    payload = events.attrs.get("billboard_weighted_frame")
    if isinstance(payload, BillboardWeightedFrameRef):
        return payload.frame
    if isinstance(payload, pd.DataFrame):
        return payload
    return None


@dataclass(frozen=True)
class _Segment:
    """One inferred, monotonic listened interval inside a merge run."""

    start_ns: int
    end_ns: int
    cumulative_start_ms: int
    cumulative_end_ms: int


def _iso_utc(value_ns: int) -> str:
    return pd.Timestamp(value_ns, unit="ns", tz="UTC").isoformat().replace("+00:00", "Z")


def _iso_utc_array(values_ns: Sequence[int]) -> list[str]:
    values = np.asarray(values_ns, dtype="int64").astype("datetime64[ns]")
    rendered = np.datetime_as_string(values, unit="ms", timezone="UTC")
    return [value[:-5] + "Z" if value.endswith(".000Z") else value for value in rendered.tolist()]


def _timestamp_ns(values: pd.Series) -> np.ndarray:
    if isinstance(values.dtype, pd.DatetimeTZDtype):
        return values.astype("int64", copy=False).to_numpy()
    if pd.api.types.is_datetime64_ns_dtype(values.dtype):
        # Extended-history timestamps are UTC. A native datetime64 column can
        # therefore bypass the much slower mixed-string parser.
        return values.to_numpy(dtype="datetime64[ns]", copy=False).astype("int64")
    parsed = pd.to_datetime(values, errors="coerce", utc=True, format="mixed")
    # ``astype`` represents NaT as int64.min, which is convenient for a
    # vectorised validity check below.
    return parsed.astype("int64", copy=False).to_numpy()


def _normalise_boundary_columns(boundary_column: str | Sequence[str] | None) -> list[str]:
    if not boundary_column:
        return []
    if isinstance(boundary_column, str):
        return [boundary_column]
    return list(boundary_column)


def _changed_rows(values: pd.Series) -> np.ndarray:
    """Vectorised adjacent-value comparison with nulls treated as equal."""
    raw = values.to_numpy(copy=False)
    changed = np.ones(len(raw), dtype=bool)
    if len(raw) <= 1:
        return changed
    if pd.api.types.is_numeric_dtype(values.dtype):
        left = raw[1:]
        right = raw[:-1]
        changed[1:] = left != right
        if pd.api.types.is_float_dtype(values.dtype):
            changed[1:] &= ~(np.isnan(left) & np.isnan(right))
        return changed
    normalised = values.astype(object).where(values.notna(), "__missing__").to_numpy()
    changed[1:] = normalised[1:] != normalised[:-1]
    return changed


def _local_time_parts(
    timestamp_ns: Sequence[int], *, rendered_utc: Sequence[str] | None = None
) -> pd.DataFrame:
    utc = pd.to_datetime(pd.Series(timestamp_ns), unit="ns", utc=True)
    local = utc.dt.tz_convert(PLAYBACK_TIMEZONE)
    iso_week = local.dt.isocalendar().week.astype("int64")
    if rendered_utc is None:
        rendered_utc = _iso_utc_array(timestamp_ns)
    return pd.DataFrame(
        {
            "ts": rendered_utc,
            "counted_at": rendered_utc,
            "ts_date": local.dt.date.astype(str),
            "ts_date_dt": local.dt.tz_localize(None).dt.normalize(),
            "ts_year": local.dt.year.astype("int64"),
            "ts_month": local.dt.month.astype("int64"),
            "ts_week": iso_week,
            "ts_dow": local.dt.dayofweek.astype("int64"),
            "ts_hour": local.dt.hour.astype("int64"),
        }
    )


def _map_position_ns(segments: list[_Segment], position_ms: int) -> int:
    """Map a positive cumulative listened position to UTC nanoseconds."""
    if not segments:
        raise ValueError("cannot map a position without segments")
    if position_ms <= 0:
        return segments[0].start_ns
    ends = [segment.cumulative_end_ms for segment in segments]
    index = int(np.searchsorted(ends, position_ms, side="left"))
    index = min(index, len(segments) - 1)
    segment = segments[index]
    offset_ms = max(0, min(position_ms, segment.cumulative_end_ms) - segment.cumulative_start_ms)
    return segment.start_ns + offset_ms * 1_000_000


def _intervals_for_range(
    segments: list[_Segment], start_ms: int, end_ms: int
) -> tuple[tuple[int, int], ...]:
    intervals: list[tuple[int, int]] = []
    if end_ms <= start_ms:
        return ()
    for segment in segments:
        overlap_start = max(start_ms, segment.cumulative_start_ms)
        overlap_end = min(end_ms, segment.cumulative_end_ms)
        if overlap_end <= overlap_start:
            continue
        start_ns = segment.start_ns + (overlap_start - segment.cumulative_start_ms) * 1_000_000
        end_ns = segment.start_ns + (overlap_end - segment.cumulative_start_ms) * 1_000_000
        intervals.append((int(start_ns), int(end_ns)))
    return tuple(intervals)


def _build_segments(
    row_indices: Iterable[int],
    *,
    start_ns: np.ndarray,
    end_ns: np.ndarray,
    played_ms: np.ndarray,
) -> tuple[list[_Segment], bool]:
    """Build non-overlapping inferred intervals while preserving listened ms."""
    segments: list[_Segment] = []
    cumulative_ms = 0
    adjusted = False
    previous_effective_end: int | None = None
    for index in row_indices:
        duration_ms = int(max(played_ms[index], 0))
        if duration_ms <= 0:
            continue
        effective_start = int(start_ns[index])
        if previous_effective_end is not None and effective_start < previous_effective_end:
            # Grouping already split overlaps larger than the allowed clock
            # tolerance.  Remaining overlaps are timestamp rounding noise.
            effective_start = previous_effective_end
            adjusted = True
        effective_end = effective_start + duration_ms * 1_000_000
        segments.append(
            _Segment(
                start_ns=effective_start,
                end_ns=effective_end,
                cumulative_start_ms=cumulative_ms,
                cumulative_end_ms=cumulative_ms + duration_ms,
            )
        )
        cumulative_ms += duration_ms
        previous_effective_end = effective_end
    return segments, adjusted


def reconstruct_logical_plays(
    frame: pd.DataFrame,
    min_ms: int,
    *,
    identity_column: str = "track_id",
    dynamic_threshold: bool = False,
    max_gap_minutes: int | None = DEFAULT_MAX_MERGE_GAP_MINUTES,
    boundary_column: str | Sequence[str] | None = None,
    overlap_tolerance_seconds: int = OVERLAP_TOLERANCE_SECONDS,
) -> pd.DataFrame:
    """Reconstruct logical play events from ordered raw playback rows.

    ``max_gap_minutes`` is the maximum *idle* time between the previous stop
    and the next inferred start.  ``None`` is supported only for legacy
    compatibility; resolved application policies always provide an integer.

    The returned frame remains compatible with existing consumers: ``ts`` and
    all ``ts_*`` columns describe ``counted_at`` and ``ms_played`` is the
    credited duration of that logical event.  Internal listened intervals are
    retained in :data:`LISTENING_INTERVALS_COLUMN` for exact time slicing.
    """
    if frame.empty:
        result = frame.copy()
        if LISTENING_INTERVALS_COLUMN not in result.columns:
            result[LISTENING_INTERVALS_COLUMN] = pd.Series(dtype=object)
        return result

    required = {identity_column, "ms_played", "duration_ms", "ts"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"logical playback reconstruction missing columns: {sorted(missing)}")

    df = frame.copy().reset_index(drop=True)
    end_ns = _timestamp_ns(df["ts"])
    nat_ns = np.iinfo("int64").min
    played_ms = pd.to_numeric(df["ms_played"], errors="coerce").fillna(0).clip(lower=0)
    played_ms_np = played_ms.astype("int64").to_numpy()
    start_ns = end_ns.copy()
    valid_timestamp = end_ns != nat_ns
    start_ns[valid_timestamp] = end_ns[valid_timestamp] - played_ms_np[valid_timestamp] * 1_000_000

    track_changed = _changed_rows(df[identity_column])
    boundary_changed = np.zeros(len(df), dtype=bool)
    for column in _normalise_boundary_columns(boundary_column):
        if column not in df.columns:
            continue
        boundary_changed |= _changed_rows(df[column])

    gap_changed = np.zeros(len(df), dtype=bool)
    overlap_split = np.zeros(len(df), dtype=bool)
    if len(df) > 1:
        previous_end = np.roll(end_ns, 1)
        gap_ns = start_ns - previous_end
        valid_pair = valid_timestamp & np.roll(valid_timestamp, 1)
        valid_pair[0] = False
        if max_gap_minutes is not None:
            gap_changed |= valid_pair & (gap_ns > int(max_gap_minutes) * 60 * 1_000_000_000)
        severe_overlap = valid_pair & (gap_ns < -int(overlap_tolerance_seconds) * 1_000_000_000)
        gap_changed |= severe_overlap
        overlap_split |= severe_overlap
        # Invalid timestamps cannot be safely merged or attributed.
        gap_changed |= ~valid_timestamp

    starts_group = track_changed | boundary_changed | gap_changed
    starts_group[0] = True
    group_ids = np.cumsum(starts_group) - 1

    template_indices: list[int] = []
    output_ms: list[int] = []
    counted_ns: list[int] = []
    event_start_ns: list[int] = []
    event_end_ns: list[int] = []
    intervals_output: list[tuple[tuple[int, int], ...]] = []
    event_ids: list[str] = []
    run_ids: list[str] = []
    event_ordinals: list[int] = []
    qualities: list[str] = []

    group_starts = np.flatnonzero(starts_group)
    group_ends = np.r_[group_starts[1:], len(df)]
    group_sizes = group_ends - group_starts
    group_totals = np.add.reduceat(played_ms_np, group_starts)
    group_offsets = np.r_[0, np.cumsum(group_totals, dtype="int64")[:-1]]
    row_group_offsets = np.repeat(group_offsets, group_sizes)
    global_cumulative = np.cumsum(played_ms_np, dtype="int64")
    row_cumulative_end = global_cumulative - row_group_offsets
    row_cumulative_start = row_cumulative_end - played_ms_np

    # Reconstruct a monotonic wall-clock axis in vectorised form.  The
    # group-wise cumulative maximum shifts only sub-two-second overlap noise;
    # larger overlaps already started a new group above.
    base_candidates = start_ns - row_cumulative_start * 1_000_000
    effective_bases = (
        pd.Series(base_candidates).groupby(group_ids, sort=False).cummax().to_numpy(dtype="int64")
    )
    effective_start_ns = effective_bases + row_cumulative_start * 1_000_000
    effective_end_ns = effective_start_ns + played_ms_np * 1_000_000

    duration_np = (
        pd.to_numeric(df["duration_ms"], errors="coerce").fillna(0).astype("int64").to_numpy()
    )
    group_durations = duration_np[group_starts]
    group_valid_timestamps = valid_timestamp[group_starts]

    if "play_id" in df.columns:
        play_ids = df["play_id"].astype(object).to_numpy()
    else:
        play_ids = np.arange(len(df), dtype=object)
    anchor_values = [
        play_ids[position] if pd.notna(play_ids[position]) else int(position)
        for position in group_starts
    ]
    group_run_ids = [f"{PLAYBACK_EVENT_POLICY_VERSION}:{value}" for value in anchor_values]

    # Main vectorised path for groups with a known track duration.
    valid_duration_groups = (group_durations > 0) & group_valid_timestamps & (group_totals > 0)
    thresholds = np.full(len(group_starts), max(int(min_ms), 0), dtype="int64")
    if dynamic_threshold:
        thresholds = np.maximum(thresholds, (group_durations * 0.1).astype("int64"))
    full_plays = np.zeros(len(group_starts), dtype="int64")
    remainders = np.zeros(len(group_starts), dtype="int64")
    full_plays[valid_duration_groups] = (
        group_totals[valid_duration_groups] // group_durations[valid_duration_groups]
    )
    remainders[valid_duration_groups] = (
        group_totals[valid_duration_groups] % group_durations[valid_duration_groups]
    )
    has_remainder_event = valid_duration_groups & (remainders > 0) & (remainders >= thresholds)
    output_counts = full_plays + has_remainder_event.astype("int64")

    event_groups = np.repeat(np.arange(len(group_starts)), output_counts)
    if len(event_groups):
        event_offsets = np.repeat(np.cumsum(output_counts) - output_counts, output_counts)
        event_sequence = np.arange(len(event_groups), dtype="int64") - event_offsets
        event_duration = group_durations[event_groups]
        event_full_count = full_plays[event_groups]
        is_full_event = event_sequence < event_full_count
        range_start = event_sequence * event_duration
        range_end = np.where(
            is_full_event,
            (event_sequence + 1) * event_duration,
            group_totals[event_groups],
        ).astype("int64")
        qualification = np.where(
            is_full_event,
            range_end,
            event_full_count * event_duration + thresholds[event_groups],
        ).astype("int64")
        global_qualification = group_offsets[event_groups] + qualification
        qualification_rows = np.searchsorted(global_cumulative, global_qualification, side="left")
        zero_qualification = qualification <= 0
        qualification_rows[zero_qualification] = group_starts[event_groups[zero_qualification]]
        qualification_offsets = qualification - row_cumulative_start[qualification_rows]
        mapped_counted_ns = (
            effective_start_ns[qualification_rows] + qualification_offsets * 1_000_000
        )

        global_range_start = group_offsets[event_groups] + range_start
        global_range_end = group_offsets[event_groups] + range_end
        range_start_rows = np.searchsorted(global_cumulative, global_range_start, side="right")
        range_end_rows = np.searchsorted(global_cumulative, global_range_end, side="left")

        raw_gap_ns = start_ns - np.roll(end_ns, 1)
        rounding_overlap = (
            valid_timestamp
            & np.roll(valid_timestamp, 1)
            & (raw_gap_ns < 0)
            & (raw_gap_ns >= -int(overlap_tolerance_seconds) * 1_000_000_000)
            & ~starts_group
        )
        rounding_overlap[0] = False
        group_adjusted = np.maximum.reduceat(rounding_overlap.astype("int8"), group_starts) > 0

        first_interval_start = (
            effective_start_ns[range_start_rows]
            + (range_start - row_cumulative_start[range_start_rows]) * 1_000_000
        ).astype("int64")
        first_interval_end = (
            effective_start_ns[range_start_rows]
            + (
                np.minimum(range_end, row_cumulative_end[range_start_rows])
                - row_cumulative_start[range_start_rows]
            )
            * 1_000_000
        ).astype("int64")
        last_interval_start = (
            effective_start_ns[range_end_rows]
            + (
                np.maximum(range_start, row_cumulative_start[range_end_rows])
                - row_cumulative_start[range_end_rows]
            )
            * 1_000_000
        ).astype("int64")
        last_interval_end = (
            effective_start_ns[range_end_rows]
            + (range_end - row_cumulative_start[range_end_rows]) * 1_000_000
        ).astype("int64")

        event_intervals: list[tuple[tuple[int, int], ...]] = []
        for index, (first_row, last_row) in enumerate(
            zip(range_start_rows.tolist(), range_end_rows.tolist())
        ):
            if first_row == last_row:
                event_intervals.append(
                    ((int(first_interval_start[index]), int(last_interval_end[index])),)
                )
                continue
            pieces: list[tuple[int, int]] = [
                (int(first_interval_start[index]), int(first_interval_end[index]))
            ]
            if last_row > first_row + 1:
                pieces.extend(
                    (int(effective_start_ns[row]), int(effective_end_ns[row]))
                    for row in range(first_row + 1, last_row)
                    if effective_end_ns[row] > effective_start_ns[row]
                )
            pieces.append((int(last_interval_start[index]), int(last_interval_end[index])))
            event_intervals.append(tuple(pieces))

        event_anchor_positions = group_starts[event_groups]
        event_run_ids = [group_run_ids[index] for index in event_groups]
        group_qualities = np.where(group_adjusted, "rounding_adjusted", "inferred").astype(object)
        group_qualities[overlap_split[group_starts]] = "overlap_split"
        template_indices.extend(event_anchor_positions.astype(int).tolist())
        output_ms.extend((range_end - range_start).astype(int).tolist())
        counted_ns.extend(mapped_counted_ns.astype(int).tolist())
        event_start_ns.extend([intervals[0][0] for intervals in event_intervals])
        event_end_ns.extend([intervals[-1][1] for intervals in event_intervals])
        intervals_output.extend(event_intervals)
        event_ids.extend(
            f"{run_id}:{int(sequence)}" for run_id, sequence in zip(event_run_ids, event_sequence)
        )
        run_ids.extend(event_run_ids)
        event_ordinals.extend(event_sequence.astype(int).tolist())
        qualities.extend(group_qualities[event_groups].tolist())

    # Duration-missing rows cannot be expanded. Preserve one candidate per
    # raw row and let the standard effective filter apply the fallback min_ms.
    invalid_duration_group_ids = np.flatnonzero((group_durations <= 0) & group_valid_timestamps)
    threshold_ms = max(int(min_ms), 0)
    for group_index in invalid_duration_group_ids.tolist():
        run_id = group_run_ids[group_index]
        for ordinal, position in enumerate(
            range(int(group_starts[group_index]), int(group_ends[group_index]))
        ):
            value_ms = int(played_ms_np[position])
            if value_ms <= 0 or not valid_timestamp[position]:
                continue
            row_start = int(start_ns[position])
            row_end = int(end_ns[position])
            counted = (
                row_end if threshold_ms <= 0 else min(row_end, row_start + threshold_ms * 1_000_000)
            )
            template_indices.append(position)
            output_ms.append(value_ms)
            counted_ns.append(counted)
            event_start_ns.append(row_start)
            event_end_ns.append(row_end)
            intervals_output.append(((row_start, row_end),))
            event_ids.append(f"{run_id}:{ordinal}")
            run_ids.append(run_id)
            event_ordinals.append(ordinal)
            qualities.append("duration_fallback")

    if not template_indices:
        empty = df.iloc[0:0].copy()
        empty[LISTENING_INTERVALS_COLUMN] = pd.Series(dtype=object)
        return empty.reset_index(drop=True)

    order = np.lexsort(
        (np.asarray(event_ordinals, dtype="int64"), np.asarray(template_indices, dtype="int64"))
    )
    template_indices = [template_indices[index] for index in order]
    output_ms = [output_ms[index] for index in order]
    counted_ns = [counted_ns[index] for index in order]
    event_start_ns = [event_start_ns[index] for index in order]
    event_end_ns = [event_end_ns[index] for index in order]
    intervals_output = [intervals_output[index] for index in order]
    event_ids = [event_ids[index] for index in order]
    run_ids = [run_ids[index] for index in order]
    event_ordinals = [event_ordinals[index] for index in order]
    qualities = [qualities[index] for index in order]

    result = df.iloc[template_indices].copy().reset_index(drop=True)
    result["ms_played"] = pd.Series(output_ms, dtype="int64")
    counted_rendered = _iso_utc_array(counted_ns)
    parts = _local_time_parts(counted_ns, rendered_utc=counted_rendered)
    for column in parts.columns:
        result[column] = parts[column].to_numpy()
    # These auxiliary fields intentionally remain timezone-aware timestamps.
    # Unlike the compatibility ``ts`` string they are internal timeline data;
    # keeping the native dtype avoids two costly full-column string renders.
    result["event_start_at"] = pd.to_datetime(event_start_ns, unit="ns", utc=True)
    result["event_end_at"] = pd.to_datetime(event_end_ns, unit="ns", utc=True)
    result["_logical_event_id"] = event_ids
    result["_merge_run_id"] = run_ids
    result["_logical_event_ordinal"] = pd.Series(event_ordinals, dtype="int64")
    result["time_quality"] = qualities
    result["playback_event_policy_version"] = PLAYBACK_EVENT_POLICY_VERSION
    result[LISTENING_INTERVALS_COLUMN] = intervals_output
    return result


def _next_boundary(
    local: pd.Timestamp,
    granularity: Literal["hour", "day"],
) -> pd.Timestamp:
    if granularity == "hour":
        return local.floor("h") + pd.Timedelta(hours=1)
    return local.normalize() + pd.Timedelta(days=1)


def explode_listening_slices(
    frame: pd.DataFrame,
    *,
    granularity: Literal["hour", "day"] = "day",
) -> pd.DataFrame:
    """Explode credited listened intervals at local hour/day boundaries.

    Every output row retains the source logical-event columns, while
    ``ms_played`` and ``ts_*`` describe the slice.  Play counts must continue
    to come from the event frame, never from the exploded slice row count.
    """
    if frame.empty:
        return frame.copy()
    if LISTENING_INTERVALS_COLUMN not in frame.columns:
        return frame.copy()

    source_positions: list[int] = []
    slice_start_ns: list[int] = []
    slice_end_ns: list[int] = []
    for position, intervals in enumerate(frame[LISTENING_INTERVALS_COLUMN].tolist()):
        if not intervals:
            continue
        for raw_start_ns, raw_end_ns in intervals:
            cursor_ns = int(raw_start_ns)
            end_ns = int(raw_end_ns)
            while cursor_ns < end_ns:
                cursor_utc = pd.Timestamp(cursor_ns, unit="ns", tz="UTC")
                cursor_local = cursor_utc.tz_convert(PLAYBACK_TIMEZONE)
                boundary_local = _next_boundary(cursor_local, granularity)
                boundary_ns = int(boundary_local.tz_convert("UTC").value)
                part_end_ns = min(end_ns, boundary_ns)
                source_positions.append(position)
                slice_start_ns.append(cursor_ns)
                slice_end_ns.append(part_end_ns)
                cursor_ns = part_end_ns

    if not source_positions:
        return frame.iloc[0:0].copy()
    result = frame.iloc[source_positions].copy().reset_index(drop=True)
    result["slice_start_at"] = [_iso_utc(value) for value in slice_start_ns]
    result["slice_end_at"] = [_iso_utc(value) for value in slice_end_ns]
    result["ms_played"] = pd.Series(
        [(end - start) // 1_000_000 for start, end in zip(slice_start_ns, slice_end_ns)],
        dtype="int64",
    )
    parts = _local_time_parts(slice_start_ns)
    for column in (
        "ts_date",
        "ts_date_dt",
        "ts_year",
        "ts_month",
        "ts_week",
        "ts_dow",
        "ts_hour",
    ):
        result[column] = parts[column].to_numpy()
    return result


def billboard_week_for_timestamps(
    timestamps: pd.Series,
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> pd.Series:
    """Return the local half-open Billboard week key for UTC timestamps."""
    utc = pd.to_datetime(timestamps, errors="coerce", utc=True, format="mixed")
    local = utc.dt.tz_convert(PLAYBACK_TIMEZONE)
    shifted = local - pd.to_timedelta(week_start_hour, unit="h")
    days_back = (shifted.dt.dayofweek - int(week_start_dow)) % 7
    starts = shifted.dt.normalize() - pd.to_timedelta(days_back, unit="D")
    return starts.dt.date


def listening_slices_for_billboard(
    frame: pd.DataFrame,
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> pd.DataFrame:
    """Split listened intervals at custom Billboard week boundaries."""
    # Day slices are sufficient because the only intra-day chart boundary is
    # the configured start hour. Split each interval again at that hour.
    if frame.empty or LISTENING_INTERVALS_COLUMN not in frame.columns:
        result = frame.copy()
        if not result.empty:
            result["billboard_week"] = billboard_week_for_timestamps(
                result["ts"],
                week_start_dow=week_start_dow,
                week_start_hour=week_start_hour,
            )
        return result

    source_positions: list[int] = []
    starts_ns: list[int] = []
    ends_ns: list[int] = []
    for position, intervals in enumerate(frame[LISTENING_INTERVALS_COLUMN].tolist()):
        for raw_start_ns, raw_end_ns in intervals or ():
            cursor_ns = int(raw_start_ns)
            end_ns = int(raw_end_ns)
            while cursor_ns < end_ns:
                cursor = pd.Timestamp(cursor_ns, unit="ns", tz="UTC")
                local = cursor.tz_convert(PLAYBACK_TIMEZONE)
                candidate = local.normalize() + pd.Timedelta(hours=week_start_hour)
                if candidate <= local:
                    candidate += pd.Timedelta(days=1)
                boundary_ns = int(candidate.tz_convert("UTC").value)
                part_end = min(end_ns, boundary_ns)
                source_positions.append(position)
                starts_ns.append(cursor_ns)
                ends_ns.append(part_end)
                cursor_ns = part_end

    if not source_positions:
        return frame.iloc[0:0].copy()
    result = frame.iloc[source_positions].copy().reset_index(drop=True)
    result["slice_start_at"] = [_iso_utc(value) for value in starts_ns]
    result["slice_end_at"] = [_iso_utc(value) for value in ends_ns]
    result["ms_played"] = pd.Series(
        [(end - start) // 1_000_000 for start, end in zip(starts_ns, ends_ns)],
        dtype="int64",
    )
    local_parts = _local_time_parts(starts_ns)
    result["ts_date"] = local_parts["ts_date"].to_numpy()
    result["ts_date_dt"] = local_parts["ts_date_dt"].to_numpy()
    result["billboard_week"] = billboard_week_for_timestamps(
        result["slice_start_at"],
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    return result


def build_billboard_weighted_frame(
    events: pd.DataFrame,
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> pd.DataFrame:
    """Return a frame with independent play-count and duration weights.

    Event rows contribute one play at ``counted_at`` and zero duration. Slice
    rows contribute zero plays and their exact duration in the week where the
    listening occurred. Downstream groupers must sum ``play_count`` and
    ``total_ms`` when these columns are present.
    """
    if events.empty:
        result = events.copy()
        result["play_count"] = pd.Series(dtype="int64")
        result["total_ms"] = pd.Series(dtype="int64")
        result["billboard_week"] = pd.Series(dtype=object)
        return result

    event_rows = events.copy()
    event_rows["billboard_week"] = billboard_week_for_timestamps(
        event_rows["counted_at"] if "counted_at" in event_rows.columns else event_rows["ts"],
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    event_rows["play_count"] = 1
    event_rows["total_ms"] = 0

    slices = listening_slices_for_billboard(
        events,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    if slices.empty:
        return event_rows.reset_index(drop=True)
    slices = slices.copy()
    slices["play_count"] = 0
    slices["total_ms"] = (
        pd.to_numeric(slices["ms_played"], errors="coerce").fillna(0).astype("int64")
    )
    return pd.concat([event_rows, slices], ignore_index=True, sort=False)
