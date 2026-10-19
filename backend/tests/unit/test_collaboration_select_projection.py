"""Filter collaboration rows before materializing their full-width projection."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.playback import records_collaboration as collaboration
from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.tests.unit.test_playback_records_collaboration import _frames
from backend.tests.unit.test_playback_records_collaboration import (
    credit_conn as _credit_conn_fixture,
)

credit_conn = _credit_conn_fixture

pytestmark = pytest.mark.unit
MODES = [
    "integer",
    "mixed_string",
    "nullable_int",
    "nullable_uint",
    "nullable_int32",
    "float",
    "numeric_strings",
    "all",
    "none",
    "missing_rep",
    "legacy",
    "legacy_blocked",
    "existing_key",
    "membership_duplicate",
    "empty",
]
COOPERATING = {101, 102, 104, 106, 107}


def select_sources(mode, duplicate_index):
    events, tracks, albums = _frames([101, 103, 104, 106])
    extra = _frames([102])[0].assign(play_id=9, ms_played=9000, _logical_event_id="duration-only:9")
    duration = pd.concat([events, extra], ignore_index=True)
    duration["slice_start_at"] = [f"2026-01-01T0{i}:00:00" for i in range(5)]
    durations = [
        duration,
        duration.assign(
            canonical_track_id=duration.track_id, canonical_track_name=duration.track_name
        ),
        duration.assign(album_project_id=50, album_project_name="Album Project"),
    ]
    frames = [events, tracks, albums]
    for frame in [*frames, *durations]:
        n = len(frame)
        values = [101, 103, 104, 106] + ([102] if n == 5 else [])
        if mode == "mixed_string":
            values[1] = "invalid"
        if mode in {"nullable_int", "nullable_uint", "nullable_int32", "float"}:
            values[1] = None
        if mode == "numeric_strings":
            values = [str(v) for v in values]
        if mode == "all":
            values = [101, 102, 104, 106] + ([102] if n == 5 else [])
        if mode == "none":
            values = [103, 105, 999, None] + ([103] if n == 5 else [])
        dtype = {
            "nullable_int": "Int64",
            "nullable_uint": "UInt64",
            "nullable_int32": "Int32",
            "float": "float64",
        }.get(mode)
        frame["representative_track_id"] = pd.array(values, dtype=dtype) if dtype else values
        if mode in {"legacy", "legacy_blocked"}:
            frame["track_id"] = frame["representative_track_id"]
        if mode in {"missing_rep", "legacy", "legacy_blocked"}:
            frame.drop(columns="representative_track_id", inplace=True)
        if mode == "legacy":
            frame.drop(columns="l1_id", inplace=True)
        if mode == "existing_key":
            frame["_credit_track_id"] = "wrong"
        frame["source_payload"] = pd.array(["keep"] * n, dtype="string")
        frame.attrs["source_metadata"] = "unchanged"
        if duplicate_index:
            frame.index = pd.Index([4, 4, 8, 8] + ([9] if n == 5 else []), name="source_row")
    if mode == "empty":
        frames = [f.iloc[:0].copy() for f in frames]
        durations = [f.iloc[:0].copy() for f in durations]
    if mode == "membership_duplicate":
        frames[2] = pd.concat([frames[2], frames[2].iloc[:1]])
    for frame, slices in zip(frames, durations):
        attach_listening_duration_frame(frame, slices)
    return frames, durations


@pytest.mark.parametrize("duplicate_index", [False, True])
@pytest.mark.parametrize("mode", MODES)
def test_select_preserves_full_conversion_dtype_indices_and_duration(
    credit_conn, mode, duplicate_index
):
    frames, durations = select_sources(mode, duplicate_index)
    if mode in {"legacy", "legacy_blocked"}:
        credit_conn.execute("DROP TABLE track_l1_identities")
    sources = [*frames, *durations]
    originals = [frame.copy() for frame in sources]
    expected = []
    for frame in sources:
        if "representative_track_id" in frame:
            keys = pd.to_numeric(frame["representative_track_id"], errors="coerce")
        elif mode == "legacy":
            keys = pd.to_numeric(frame["track_id"], errors="coerce")
        else:
            keys = pd.to_numeric(pd.Series(None, index=frame.index, dtype=object), errors="coerce")
        expected.append(keys.loc[keys.isin(COOPERATING)].rename("_credit_track_id"))
    if mode in {"missing_rep", "legacy_blocked"}:
        # With no usable credit IDs the existing builder fails its later merge.
        # Preserve that boundary; this projection change does not repair it.
        with pytest.raises(ValueError, match="merge on float64 and object columns"):
            collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
        for actual, original in zip(sources, originals):
            pd.testing.assert_frame_equal(actual, original)
            assert actual.attrs["source_metadata"] == "unchanged"
        return
    facts = collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
    outputs = [
        facts.events,
        facts.tracks,
        facts.albums,
        facts.artist_duration,
        facts.track_duration,
        facts.album_duration,
    ]
    for index in [0, 1, 2, 4, 5]:
        pd.testing.assert_series_equal(outputs[index]["_credit_track_id"], expected[index])
        assert set(sources[index].columns) <= set(outputs[index].columns)
        assert outputs[index].attrs == {}
    assert facts.total_events == len(frames[0])
    for actual, original in zip(sources, originals):
        pd.testing.assert_frame_equal(actual, original)
        assert actual.attrs["source_metadata"] == "unchanged"
    if mode == "mixed_string":
        # Invalid rows remain relevant to conversion dtype even after exclusion.
        assert facts.tracks["_credit_track_id"].dtype == "float64"
    if mode not in {"none", "missing_rep", "legacy_blocked", "empty"}:
        assert 9 in set(facts.track_duration.play_id)  # Below-threshold duration survives.


def test_select_copies_matching_rows_without_copying_full_sources(monkeypatch, credit_conn):
    frames, durations = select_sources("integer", True)
    source_ids = {id(frame) for frame in [*frames, *durations]}
    full_copies_after_lookup = []
    lookup_complete = False
    native_lookup = collaboration.get_effective_track_credit_frame
    native_copy = pd.DataFrame.copy

    def lookup(*args):
        nonlocal lookup_complete
        result = native_lookup(*args)
        lookup_complete = True
        return result

    def copy(frame, *args, **kwargs):
        if lookup_complete and id(frame) in source_ids:
            full_copies_after_lookup.append((len(frame), len(frame.columns)))
        return native_copy(frame, *args, **kwargs)

    monkeypatch.setattr(collaboration, "get_effective_track_credit_frame", lookup)
    monkeypatch.setattr(pd.DataFrame, "copy", copy)
    facts = collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
    assert facts.events.play_id.tolist() == [1, 3, 4]
    assert facts.track_duration.play_id.tolist() == [1, 3, 4, 9]
    assert full_copies_after_lookup == []
