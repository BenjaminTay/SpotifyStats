"""Bounded logical-play contribution deltas for proven tail appends.

This module deliberately operates on the old/new tail closure produced by
the import change-set proof.  It never loads the lifetime playback frame.
The resulting rows retain the source-album boundary so downstream track,
album-project, and artist projections can apply the same signed contribution
without reconstructing raw history.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import cast

import pandas as pd

TRACK_LOGICAL_DELTA_COLUMNS = (
    "track_id",
    "source_album_id",
    "play_events",
    "total_ms",
)


def build_tail_track_logical_delta(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    min_ms: int,
    music_only: bool,
    dynamic_threshold: bool,
    max_gap_minutes: int,
) -> pd.DataFrame:
    """Return the exact signed track contribution for a proven tail append.

    ``play_events`` and ``total_ms`` are ``new - old`` contributions.  The
    closure reader queries only the appended generation and the immediately
    preceding same-track/source merge run; it raises when the generation is
    not a provable tail append.

    Rows are keyed by both canonical track identity and ``source_album_id``. Keeping the
    source boundary is important even for lifetime metrics: adjacent plays of
    the same track from different source albums are separate logical runs.
    """
    if not generation_id.strip():
        raise ValueError("generation_id must not be empty")
    if min_ms < 0:
        raise ValueError("min_ms must be non-negative")
    if max_gap_minutes < 0:
        raise ValueError("max_gap_minutes must be non-negative")

    # Import locally to keep the playback timeline module independent from
    # import orchestration at module import time.  The Phase D1 helper already
    # owns and tests the exact paginated tail-closure proof.
    from backend.domains.imports.change_set import build_billboard_tail_contribution_frames

    old_events, new_events = build_billboard_tail_contribution_frames(
        conn,
        generation_id=generation_id,
        min_ms=min_ms,
        music_only=music_only,
        dynamic_threshold=dynamic_threshold,
        max_gap_minutes=max_gap_minutes,
    )
    old_contributions = _event_contributions(old_events, sign=-1)
    new_contributions = _event_contributions(new_events, sign=1)
    return _coalesce_signed_contributions(
        pd.concat([old_contributions, new_contributions], ignore_index=True)
    )


def project_track_logical_delta(
    delta: pd.DataFrame,
    *,
    merge_level: int,
    track_group_keys: pd.DataFrame | Mapping[int, int] | None = None,
) -> pd.DataFrame:
    """Project one physical-track delta to an L1/L2/L3 track key space.

    The internal base projection preserves canonical local identities. L2/L3 callers supply the
    corresponding track-group mapping (normally ``load_track_group_keys``).
    Unmapped tracks correctly retain their physical ID.  Conflicting mappings
    fail closed rather than double-counting one contribution.
    """
    if merge_level not in {1, 2, 3}:
        raise ValueError("merge_level must be one of 1, 2, or 3")
    normalised = _normalise_delta(delta)
    if merge_level == 1 or normalised.empty:
        return normalised
    if track_group_keys is None:
        raise ValueError("track_group_keys are required for merge levels 2 and 3")

    mapping = _normalise_track_group_keys(track_group_keys)
    if mapping.empty:
        return normalised
    projected = normalised.merge(mapping, on="track_id", how="left", validate="many_to_one")
    projected["track_id"] = projected["track_agg_id"].fillna(projected["track_id"]).astype("int64")
    return _coalesce_signed_contributions(projected.loc[:, TRACK_LOGICAL_DELTA_COLUMNS])


def project_track_logical_delta_levels(
    delta: pd.DataFrame,
    *,
    track_group_keys: Mapping[int, pd.DataFrame | Mapping[int, int]],
) -> dict[int, pd.DataFrame]:
    """Return L1/L2/L3 projections without rebuilding the tail closure."""
    missing = {2, 3} - set(track_group_keys)
    if missing:
        raise ValueError(f"missing track-group mappings for levels: {sorted(missing)}")
    return {
        1: project_track_logical_delta(delta, merge_level=1),
        2: project_track_logical_delta(
            delta,
            merge_level=2,
            track_group_keys=track_group_keys[2],
        ),
        3: project_track_logical_delta(
            delta,
            merge_level=3,
            track_group_keys=track_group_keys[3],
        ),
    }


def _event_contributions(events: pd.DataFrame, *, sign: int) -> pd.DataFrame:
    if sign not in {-1, 1}:
        raise ValueError("contribution sign must be -1 or 1")
    if events.empty:
        return _empty_track_logical_delta()
    identity_column = "l1_id" if "l1_id" in events.columns else "track_id"
    missing = {identity_column, "ms_played"} - set(events.columns)
    if missing:
        raise ValueError(f"logical event frame missing columns: {sorted(missing)}")

    contribution = pd.DataFrame(index=events.index)
    track_ids = pd.to_numeric(events[identity_column], errors="coerce")
    if track_ids.isna().any():
        raise ValueError("logical event frame contains an invalid track_id")
    contribution["track_id"] = track_ids.astype("int64")
    if "source_album_id" in events.columns:
        contribution["source_album_id"] = pd.to_numeric(
            events["source_album_id"], errors="coerce"
        ).astype("Int64")
    else:
        contribution["source_album_id"] = pd.Series(
            pd.NA,
            index=events.index,
            dtype="Int64",
        )
    durations = pd.to_numeric(events["ms_played"], errors="coerce")
    if durations.isna().any() or (durations < 0).any():
        raise ValueError("logical event frame contains an invalid ms_played")
    contribution["play_events"] = sign
    contribution["total_ms"] = durations.astype("int64") * sign
    return _coalesce_signed_contributions(contribution)


def _normalise_track_group_keys(
    track_group_keys: pd.DataFrame | Mapping[int, int],
) -> pd.DataFrame:
    if isinstance(track_group_keys, Mapping):
        mapping = pd.DataFrame(
            {
                "track_id": list(track_group_keys.keys()),
                "track_agg_id": list(track_group_keys.values()),
            }
        )
    else:
        missing = {"track_id", "track_agg_id"} - set(track_group_keys.columns)
        if missing:
            raise ValueError(f"track-group mapping missing columns: {sorted(missing)}")
        mapping = track_group_keys.loc[:, ["track_id", "track_agg_id"]].copy()
    if mapping.empty:
        return pd.DataFrame(
            {
                "track_id": pd.Series(dtype="int64"),
                "track_agg_id": pd.Series(dtype="int64"),
            }
        )
    mapping["track_id"] = pd.to_numeric(mapping["track_id"], errors="coerce")
    mapping["track_agg_id"] = pd.to_numeric(mapping["track_agg_id"], errors="coerce")
    if mapping[["track_id", "track_agg_id"]].isna().any().any():
        raise ValueError("track-group mapping contains invalid track IDs")
    mapping = mapping.astype({"track_id": "int64", "track_agg_id": "int64"})
    conflicts = mapping.groupby("track_id", sort=False)["track_agg_id"].nunique()
    if (conflicts > 1).any():
        raise ValueError("track-group mapping contains conflicting canonical IDs")
    return mapping.drop_duplicates("track_id").reset_index(drop=True)


def _normalise_delta(delta: pd.DataFrame) -> pd.DataFrame:
    if delta.empty and not set(TRACK_LOGICAL_DELTA_COLUMNS).issubset(delta.columns):
        return _empty_track_logical_delta()
    missing = set(TRACK_LOGICAL_DELTA_COLUMNS) - set(delta.columns)
    if missing:
        raise ValueError(f"track logical delta missing columns: {sorted(missing)}")
    return _coalesce_signed_contributions(delta.loc[:, TRACK_LOGICAL_DELTA_COLUMNS].copy())


def _coalesce_signed_contributions(delta: pd.DataFrame) -> pd.DataFrame:
    if delta.empty:
        return _empty_track_logical_delta()
    frame = delta.loc[:, TRACK_LOGICAL_DELTA_COLUMNS].copy()
    frame["track_id"] = pd.to_numeric(frame["track_id"], errors="coerce")
    frame["source_album_id"] = pd.to_numeric(frame["source_album_id"], errors="coerce").astype(
        "Int64"
    )
    for column in ("play_events", "total_ms"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["track_id", "play_events", "total_ms"]].isna().any().any():
        raise ValueError("track logical delta contains invalid numeric values")
    frame = frame.astype(
        {
            "track_id": "int64",
            "play_events": "int64",
            "total_ms": "int64",
        }
    )
    grouped = (
        frame.groupby(["track_id", "source_album_id"], dropna=False, sort=False)[
            ["play_events", "total_ms"]
        ]
        .sum()
        .reset_index()
    )
    grouped = grouped[(grouped["play_events"] != 0) | (grouped["total_ms"] != 0)]
    if grouped.empty:
        return _empty_track_logical_delta()
    grouped["source_album_id"] = grouped["source_album_id"].astype("Int64")
    grouped = grouped.sort_values(
        ["track_id", "source_album_id"],
        kind="stable",
        na_position="first",
    ).reset_index(drop=True)
    return cast(pd.DataFrame, grouped.loc[:, TRACK_LOGICAL_DELTA_COLUMNS])


def _empty_track_logical_delta() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "track_id": pd.Series(dtype="int64"),
            "source_album_id": pd.Series(dtype="Int64"),
            "play_events": pd.Series(dtype="int64"),
            "total_ms": pd.Series(dtype="int64"),
        }
    )
