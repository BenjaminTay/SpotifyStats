"""Collaboration aggregates retain event identity and every duration dedupe fact."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.playback import records_collaboration as collaboration

pytestmark = pytest.mark.unit
DURATION_KEYS = [
    "_credit_track_id",
    "_logical_event_id",
    "play_id",
    "ts",
    "slice_start_at",
    "slice_end_at",
    "interval_start_at",
    "interval_end_at",
    "ms_played",
]


def aggregate_sources(entity_type="track", artist_names=True):
    identity, name = {
        "track": ("track_id", "track_name"),
        "artist": ("artist_id", "artist_name"),
        "album": ("album_name", "album_name"),
    }[entity_type]
    frame = pd.DataFrame(
        {
            "play_id": [1, 1, 2, 3, 4],
            "_logical_event_id": ["e1", "e1", "e2", "e3", "e4"],
            "_credit_track_id": [101, 101, 101, 102, 103],
            "artist_name": ["Zed", "Amy", "Zed", "Y", "Other"],
            "ms_played": [60000] * 5,
            "ts": ["2026-01-01T00:00:00"] * 5,
            "_unused_payload": ["unused" * 100] * 5,
            "_unused_integer": pd.array(range(5), dtype="Int32"),
        }
    )
    frame[identity] = ["Album"] * 4 + ["Other"] if entity_type == "album" else [1] * 4 + [2]
    if name not in {identity, "artist_name"}:
        frame[name] = ["Z", "A", "C", "B", "Other"]
    if artist_names:
        frame["artist_names"] = [["Zed", "Amy"], ["Amy", "Zed"], ["Zed", "Amy"], ["Y"], ["Other"]]
    frame.index = pd.Index([8, 8, 2, 2, 5], name="source_row")
    duration = frame.iloc[[0, 0, 0, 2, 3, 3, 4]].copy()
    duration["ms_played"] = [1000, 1000, 1000, 2000, 3000, 500, 4000]
    duration["slice_start_at"] = ["s0", "s0", "s1", "s2", "s3", "s9", "s4"]
    duration["slice_end_at"] = "slice-end"
    duration["interval_start_at"] = "interval-start"
    duration["interval_end_at"] = "interval-end"
    duration.iloc[5, duration.columns.get_loc("play_id")] = 9
    duration.iloc[5, duration.columns.get_loc("_logical_event_id")] = "duration-only:9"
    frame.attrs["source"] = "unchanged-events"
    duration.attrs["source"] = "unchanged-duration"
    return frame, duration, identity, name


@pytest.mark.parametrize("entity_type", ["track", "artist", "album"])
@pytest.mark.parametrize("artist_names", [False, True])
@pytest.mark.parametrize("independent_duration", [False, True])
def test_aggregate_preserves_counts_names_and_independent_duration(
    entity_type, artist_names, independent_duration
):
    frame, duration, identity, name = aggregate_sources(entity_type, artist_names)
    if not independent_duration:
        duration = duration.iloc[:0]
    result = collaboration.aggregate_collaboration(frame, duration, identity, name, entity_type)
    assert result["entity_id"].tolist() == (
        ["Album", "Other"] if entity_type == "album" else ["1", "2"]
    )
    assert result["count"].tolist() == [3, 1]
    assert result["total_ms"].tolist() == (
        [7500, 4000] if independent_duration else [180000, 60000]
    )
    assert result["name"].tolist() == [
        {"track": "A", "artist": "Amy", "album": "Album"}[entity_type],
        "Other",
    ]
    assert result["artist_name"].tolist() == ["Amy", "Other"]
    assert result["value"].tolist() == [3.0, 1.0]
    assert result["entity_type"].tolist() == [entity_type, entity_type]
    if artist_names:
        assert result["artist_names"].tolist() == [["Zed", "Amy", "Y"], ["Other"]]
    else:
        assert "artist_names" not in result


@pytest.mark.parametrize("key", DURATION_KEYS)
def test_each_duration_identity_fact_keeps_separate_slices(key):
    frame, duration, identity, name = aggregate_sources()
    frame = frame.iloc[:1]
    duration = duration.iloc[:2].copy()
    duration.iloc[1, duration.columns.get_loc(key)] = (
        2000
        if key == "ms_played"
        else 999
        if key in {"play_id", "_credit_track_id"}
        else "different"
    )
    result = collaboration.aggregate_collaboration(frame, duration, identity, name, "track")
    assert result["count"].tolist() == [1]
    assert result["total_ms"].tolist() == [3000 if key == "ms_played" else 2000]


def test_aggregate_copies_only_consumed_columns(monkeypatch):
    frame, duration, identity, name = aggregate_sources()
    wide_copies = []
    native_copy = pd.DataFrame.copy

    def copy(value, *args, **kwargs):
        if "_unused_payload" in value.columns:
            wide_copies.append((len(value), len(value.columns)))
        return native_copy(value, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "copy", copy)
    result = collaboration.aggregate_collaboration(frame, duration, identity, name, "track")
    assert result["total_ms"].tolist() == [7500, 4000]
    assert wide_copies == []


def test_aggregate_keeps_source_frames_and_attrs_unchanged():
    frame, duration, identity, name = aggregate_sources()
    originals = [frame.copy(), duration.copy()]
    result = collaboration.aggregate_collaboration(frame, duration, identity, name, "track")
    result["name"] = "changed"
    result.at[0, "artist_names"].append("new-result-only")
    assert frame["artist_names"].iloc[0] == ["Zed", "Amy"]
    assert duration["artist_names"].iloc[0] == ["Zed", "Amy"]
    for actual, original in zip([frame, duration], originals):
        pd.testing.assert_frame_equal(actual, original)
        assert actual.attrs == original.attrs


@pytest.mark.parametrize(
    "guard", ["empty", "missing_identity", "missing_name", "duration_missing_identity"]
)
def test_aggregate_keeps_empty_and_fallback_boundaries(guard):
    frame, duration, identity, name = aggregate_sources()
    if guard == "empty":
        frame = frame.iloc[:0]
    elif guard == "missing_identity":
        frame = frame.drop(columns=identity)
    elif guard == "missing_name":
        frame = frame.drop(columns=name)
    else:
        duration = duration.drop(columns=identity)
    result = collaboration.aggregate_collaboration(frame, duration, identity, name, "track")
    if guard == "duration_missing_identity":
        assert result["total_ms"].tolist() == [180000, 60000]
    else:
        assert result.empty
