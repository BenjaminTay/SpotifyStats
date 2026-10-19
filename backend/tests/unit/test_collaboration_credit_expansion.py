"""Narrow credit joins retain full owned payloads and release consumed hours."""

from __future__ import annotations

import weakref

import pandas as pd
import pytest

from backend.domains.playback import records_collaboration as collaboration
from backend.tests.unit.test_collaboration_select_projection import select_sources
from backend.tests.unit.test_playback_records_collaboration import (
    credit_conn as _credit_conn_fixture,
)

credit_conn = _credit_conn_fixture

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("deduplicate", [False, True])
@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "empty",
        "both_empty",
        "nullable",
        "null_key",
        "logical_duplicates",
        "duplicate_index",
        "named_axes",
        "metadata_overlap",
        "position_name",
    ],
)
def test_credit_expansion_matches_full_merge_and_owns_result(mode, deduplicate):
    frames, _ = select_sources("integer", mode == "duplicate_index")
    frame = frames[0].copy()
    frame.attrs = {"source": "unchanged"}
    frame["_credit_track_id"] = frame["representative_track_id"]
    frame["artist_id"] = 999
    frame["role"] = "old-role"
    frame["extra_number"] = pd.array([1, None, 3, 4], dtype="Int32")
    credits = pd.DataFrame(
        {
            "_credit_track_id": [101, 101, 101, 104, 106],
            "artist_id": [1, 2, 2, 3, 4],
            "artist_name": ["A", "B", "B", "C", "D"],
            "role": ["primary", "featured", "featured", "primary", "featured"],
            "_role_order": [0, 1, 1, 0, 1],
        }
    )
    if mode == "empty":
        frame = frame.iloc[:0]
    if mode == "both_empty":
        frame = frame.iloc[:0]
        credits = pd.DataFrame(columns=credits.columns)
    if mode == "nullable":
        frame["_credit_track_id"] = frame["_credit_track_id"].astype("Int64")
        credits["artist_id"] = credits["artist_id"].astype("Int32")
        credits["role"] = credits["role"].astype("string")
    if mode == "null_key":
        frame["_credit_track_id"] = frame["_credit_track_id"].astype("Int64")
        credits["_credit_track_id"] = credits["_credit_track_id"].astype("Int64")
        frame.loc[1, "_credit_track_id"] = pd.NA
        credits.loc[4, "_credit_track_id"] = pd.NA
    if mode == "logical_duplicates":
        frame["_logical_event_id"] = "shared-logical-event"
        credits.loc[3, "artist_id"] = 1
    if mode == "named_axes":
        frame.index.name = "source_row"
        frame.columns.name = "source_field"
    if mode == "metadata_overlap":
        frame["_role_order"] = 99
    if mode == "position_name":
        frame["_collaboration_row"] = "preserve"
    before, cbefore = frame.copy(), credits.copy()
    expected = frame.drop(columns=["artist_id", "artist_name", "role"], errors="ignore").merge(
        credits, on="_credit_track_id", how="inner"
    )
    if deduplicate:
        expected = expected.drop_duplicates(["_logical_event_id", "artist_id"])
    actual = collaboration._expand_artist_credits(frame, credits, deduplicate_events=deduplicate)
    pd.testing.assert_frame_equal(actual, expected)
    assert actual.attrs == expected.attrs
    assert actual is not frame and actual is not credits
    actual["source_payload"] = "result-only"
    actual["artist_name"] = "result-only"
    actual.attrs["result"] = "only"
    pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(credits, cbefore)
    assert frame.attrs == before.attrs and credits.attrs == cbefore.attrs


def test_builder_credit_merges_receive_only_identity_keys(monkeypatch, credit_conn):
    frames, durations = select_sources("integer", True)
    originals = [f.copy() for f in [*frames, *durations]]
    native = pd.DataFrame.merge
    observed = []

    def merge(frame, *args, **kwargs):
        if kwargs.get("on") == "_credit_track_id" and kwargs.get("how") == "inner":
            observed.append(list(frame.columns))
            assert "source_payload" not in frame
            assert set(frame.columns) <= {
                "_credit_track_id",
                "_logical_event_id",
                "_collaboration_row",
            }
        return native(frame, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "merge", merge)
    facts = collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
    assert len(observed) == 2
    assert [len(c) for c in observed] == [3, 2]
    assert "source_payload" in facts.artists and "source_payload" in facts.artist_duration
    for actual, expected in zip([*frames, *durations], originals):
        pd.testing.assert_frame_equal(actual, expected)


@pytest.mark.parametrize("attached", [False, True])
def test_consumed_duration_tables_follow_ownership(monkeypatch, credit_conn, attached):
    frames, durations = select_sources("integer", True)
    for slices in durations:
        slices.drop(columns="slice_start_at", inplace=True)
    if not attached:
        for frame in frames:
            frame.attrs.pop("listening_duration_frame")
    native_duration = collaboration.records_duration_frame
    native_merge = pd.DataFrame.merge
    refs, checks = [], []

    def duration(*args, **kwargs):
        result = native_duration(*args, **kwargs)
        refs.append(weakref.ref(result))
        return result

    def merge(frame, *args, **kwargs):
        if kwargs.get("on") == "_credit_track_id" and kwargs.get("how") == "inner":
            checks.append([ref() is not None for ref in refs])
            if len(checks) == 2:
                assert checks[-1] == ([False] * 3 if attached else [True] * 3)
        return native_merge(frame, *args, **kwargs)

    monkeypatch.setattr(collaboration, "records_duration_frame", duration)
    monkeypatch.setattr(pd.DataFrame, "merge", merge)
    facts = collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
    assert len(checks) == 2 and len(refs) == 3
    assert not facts.artist_duration.empty


def test_selected_duration_source_released_before_names(monkeypatch, credit_conn):
    frames, _ = select_sources("integer", True)
    native_expand = collaboration._expand_artist_credits
    native_map = pd.Series.map
    duration_ref, observed = [], []

    def expand(frame, credits, *, deduplicate_events):
        if not deduplicate_events:
            duration_ref.append(weakref.ref(frame))
        return native_expand(frame, credits, deduplicate_events=deduplicate_events)

    def names(series, mapper, *args, **kwargs):
        if duration_ref and isinstance(mapper, pd.Series) and mapper.name == "artist_name":
            observed.append(duration_ref[0]() is not None)
            assert not observed[-1]
        return native_map(series, mapper, *args, **kwargs)

    monkeypatch.setattr(collaboration, "_expand_artist_credits", expand)
    monkeypatch.setattr(pd.Series, "map", names)
    collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
    assert observed == [False]
