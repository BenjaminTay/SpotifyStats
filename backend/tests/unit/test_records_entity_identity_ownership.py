"""Reuse identified Records input without borrowing mutable result tables."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.domains.playback.records_helpers import records_duration_frame
from backend.services import analysis_records_service as service
from backend.tests.unit.test_records_projection_lifetime import (
    records_sources as _records_sources_fixture,
)

records_sources = _records_sources_fixture

pytestmark = pytest.mark.unit
MODES = [
    "success",
    "empty_membership",
    "key_error",
    "load_error",
    "join_error",
    "fill_error",
    "events_empty",
    "duration_empty",
    "both_empty",
    "artist_error",
    "period",
]


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("mode", MODES)
def test_identified_source_and_independent_entity_results(records_sources, level, mode):
    events, duration, *_ = records_sources(mode)
    events["_logical_event_id"] = pd.array(["annual-A", "annual-B"][: len(events)], dtype="string")
    events["_artist_event_id"] = pd.array([41, 42][: len(events)], dtype="Int64")
    original, original_duration = events.copy(), duration.copy()
    source_attrs = events.attrs.copy()
    with sqlite3.connect(":memory:") as conn:
        results = service._build_entity_frames(
            events, conn, level, period_start="2026-01-02" if mode == "period" else None
        )
    pd.testing.assert_frame_equal(events, original)
    pd.testing.assert_frame_equal(duration, original_duration)
    assert events.attrs == source_attrs
    assert len({id(result) for result in results}) == 3
    for index, result in enumerate(results):
        assert result is not events
        assert set(events.columns) <= set(result.columns)
        assert result["_logical_event_id"].isin(["annual-A", "annual-B"]).all()
        before_others = [other.copy() for other in results]
        before_other_attrs = [other.attrs.copy() for other in results]
        if not result.empty:
            result.iat[0, result.columns.get_loc("track_name")] = f"changed-{index}"
            result.iat[0, result.columns.get_loc("ms_played")] = -100 - index
        result.attrs["sentinel"] = f"changed-result-{index}"
        # Duration consumers request an owned table through the existing helper.
        consumed_duration = records_duration_frame(result)
        assert consumed_duration is not duration
        if not consumed_duration.empty:
            consumed_duration.iat[0, consumed_duration.columns.get_loc("ms_played")] = -999
        for other_index, other in enumerate(results):
            if other_index != index:
                pd.testing.assert_frame_equal(other, before_others[other_index])
                assert other.attrs == before_other_attrs[other_index]
        pd.testing.assert_frame_equal(events, original)
        pd.testing.assert_frame_equal(duration, original_duration)
        assert events.attrs == source_attrs


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("identified", [True, False], ids=["existing", "missing"])
def test_identity_source_is_reused_readonly(monkeypatch, records_sources, level, identified):
    events, *_ = records_sources("success")
    if identified:
        events["_logical_event_id"] = ["annual-A", "annual-B"]
    original = events.copy()
    native_assign = service.assign_logical_event_id
    native_album = service._build_records_album_frame
    native_track = service._build_records_track_frame
    assigned = []
    album_inputs = []
    track_inputs = []

    def assign(frame, **kwargs):
        assigned.append(id(frame))
        return native_assign(frame, **kwargs)

    def album(frame, *args, **kwargs):
        if not kwargs.get("duration"):
            album_inputs.append(id(frame))
        return native_album(frame, *args, **kwargs)

    def track(frame, *args, **kwargs):
        track_inputs.append(id(frame))
        return native_track(frame, *args, **kwargs)

    monkeypatch.setattr(service, "assign_logical_event_id", assign)
    monkeypatch.setattr(service, "_build_records_album_frame", album)
    monkeypatch.setattr(service, "_build_records_track_frame", track)
    with sqlite3.connect(":memory:") as conn:
        results = service._build_entity_frames(events, conn, level)
    assert assigned == ([] if identified else [id(events)])
    assert len(album_inputs) == len(track_inputs) == 1
    assert album_inputs == track_inputs
    assert (track_inputs[0] == id(events)) is identified
    assert all(result is not events for result in results)
    pd.testing.assert_frame_equal(events, original)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_identified_annual_attrs_remain_on_unchanged_source(records_sources, level):
    events, duration, *_ = records_sources("success")
    events["_logical_event_id"] = ["annual-A", "annual-B"]
    annual_slices = duration.copy()
    events.attrs["listening_duration_slices"] = annual_slices
    original = events.copy()
    original_duration = duration.copy()
    original_slices = annual_slices.copy()
    with sqlite3.connect(":memory:") as conn:
        results = service._build_entity_frames(
            events, conn, level, period_start="2026-01-01", period_end="2026-12-31"
        )
    for result in results:
        assert result is not events
        result.iat[0, result.columns.get_loc("ms_played")] = -999
        result.attrs.pop("listening_duration_slices", None)
    pd.testing.assert_frame_equal(events, original)
    pd.testing.assert_frame_equal(duration, original_duration)
    pd.testing.assert_frame_equal(annual_slices, original_slices)
    assert events.attrs["listening_duration_slices"] is annual_slices
