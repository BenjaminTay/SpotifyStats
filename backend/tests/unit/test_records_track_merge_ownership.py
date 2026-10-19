"""Track canonical merges preserve full rows while avoiding pre-merge copies."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.domains.playback.logical_timeline import (
    attach_listening_duration_frame,
    get_listening_duration_frame,
)
from backend.services import analysis_records_service as service

pytestmark = pytest.mark.unit


def track_sources(mode):
    events = pd.DataFrame(
        {
            "play_id": [7, 8, 9],
            "track_id": pd.array([1, 1, 2], dtype="Int64"),
            "track_name": ["A live", "A alternate", "B"],
            "representative_track_id": [101, 102, 103],
            "ms_played": [40000, 50000, 60000],
        }
    )
    duration = pd.concat(
        [events, events.iloc[:1].assign(play_id=10, track_id=3, ms_played=9000)], ignore_index=True
    )
    duration["slice_start_at"] = ["2026-01-01T00:00:00"] * 4
    events.index = pd.Index([4, 4, 8], name="source_row")
    duration.index = pd.Index([4, 4, 8, 9], name="source_row")
    for frame in (events, duration):
        frame["source_payload"] = pd.array(["keep"] * len(frame), dtype="string")
        frame.attrs["sentinel"] = "source metadata"
    groups = pd.DataFrame(
        {
            "track_id": pd.array([1, 2], dtype="Int64"),
            "track_agg_id": [100, 200],
            "track_agg_name": ["A", "B group"],
            "representative_track_id": [999, 998],
        }
    )
    if mode == "duplicates":
        groups = pd.concat(
            [groups.iloc[:1], groups.iloc[:1].assign(track_agg_id=101), groups.iloc[1:]],
            ignore_index=True,
        )
    elif mode == "partial":
        groups = groups.iloc[:1].assign(track_agg_name=None)
    elif mode == "null_keys":
        events.loc[8, "track_id"] = pd.NA
        duration.loc[8, "track_id"] = pd.NA
        groups.loc[1, "track_id"] = pd.NA
        groups.loc[1, "track_agg_id"] = 500
    elif mode == "empty_groups":
        groups = pd.DataFrame()
    if mode in {"events_empty", "both_empty"}:
        events = events.iloc[:0].copy()
    if mode in {"duration_empty", "both_empty"}:
        duration = duration.iloc[:0].copy()
    attach_listening_duration_frame(events, duration)
    return events, duration, groups


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "duplicates",
        "partial",
        "null_keys",
        "empty_groups",
        "events_empty",
        "duration_empty",
        "both_empty",
    ],
)
def test_track_merge_preserves_rows_credits_and_independent_duration(monkeypatch, level, mode):
    events, duration, groups = track_sources(mode)
    before_events, before_duration = events.copy(), duration.copy()
    loads = []

    def load(*args):
        loads.append(args[1])
        return groups

    monkeypatch.setattr(service, "load_track_group_keys", load)
    with sqlite3.connect(":memory:") as conn:
        track = service._build_records_track_frame(events, duration, conn, level)
    projected_duration = get_listening_duration_frame(track)
    assert projected_duration is not None and projected_duration is not duration
    for source, actual in [(events, track), (duration, projected_duration)]:
        assert set(source.columns) <= set(actual.columns)
        expected_ids = source.play_id.tolist()
        if level >= 2 and mode == "duplicates":
            expected_ids = (
                [7, 7, 8, 8, 9] + ([10] if source is duration else []) if len(source) else []
            )
        assert actual.play_id.tolist() == expected_ids
        if not actual.empty:
            assert actual.representative_track_id.tolist() == [
                {7: 101, 8: 102, 9: 103, 10: 101}[key] for key in expected_ids
            ]
            if level >= 2 and not groups.empty:
                mapping = {7: 100, 8: 100, 9: 200, 10: 3}
                if mode == "null_keys":
                    mapping[9] = 500
                if mode == "partial":
                    mapping[9] = 2
                if mode == "duplicates":
                    expected_keys = [100, 101, 100, 101, 200] + ([3] if source is duration else [])
                else:
                    expected_keys = [mapping[key] for key in expected_ids]
                assert actual.canonical_track_id.tolist() == expected_keys
            else:
                pd.testing.assert_series_equal(
                    actual.canonical_track_id, source.track_id, check_names=False
                )
            if mode == "partial":
                assert actual.canonical_track_name.tolist() == source.track_name.tolist()
            actual.loc[:, "track_name"] = "changed"
            actual.loc[:, "ms_played"] = -1
    pd.testing.assert_frame_equal(events, before_events)
    pd.testing.assert_frame_equal(duration, before_duration)
    assert get_listening_duration_frame(events) is duration
    assert loads == ([level] if level >= 2 and (len(events) or len(duration)) else [])


def test_merges_receive_original_sources_without_preallocated_wide_copies(monkeypatch):
    events, duration, groups = track_sources("normal")
    inputs = []
    native_merge = pd.DataFrame.merge

    def observe_merge(frame, *args, **kwargs):
        inputs.append(frame is events or frame is duration)
        return native_merge(frame, *args, **kwargs)

    monkeypatch.setattr(service, "load_track_group_keys", lambda *args: groups)
    monkeypatch.setattr(pd.DataFrame, "merge", observe_merge)
    with sqlite3.connect(":memory:") as conn:
        service._build_records_track_frame(events, duration, conn, 2)
    assert inputs == [True, True]
