"""Skip-storm temporary columns must not copy unrelated event fields."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.playback import records_behavior as behavior
from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.domains.playback.records_helpers import safe_groupby_cols, unique_cols

pytestmark = pytest.mark.unit


def make_skip_frame(entity_type, mode="normal"):
    identities = [2] * 12 + [1] * 12 + [3] * 9
    names = {1: "甲", 2: "乙", 3: "不足"}
    frame = pd.DataFrame(
        {
            "canonical_track_id": identities,
            "canonical_track_name": [names[v] for v in identities],
            "album_project_id": identities,
            "album_project_name": [names[v] for v in identities],
            "artist_name": [names[v] for v in identities],
            "play_id": range(len(identities)),
            "ms_played": [1000] * len(identities),
            "reason_end": ["fwdbtn"] * 6 + ["trackdone"] * 6 + ["fwdbtn"] * 6 + ["trackdone"] * 15,
            "_forward": [99] * len(identities),
            **{f"unused_{i}": [f"payload-{i}"] * len(identities) for i in range(30)},
        }
    )
    if mode == "nullable":
        frame["play_id"] = frame["play_id"].astype("Int64")
        frame["ms_played"] = frame["ms_played"].astype("Int64")
        frame["reason_end"] = frame["reason_end"].astype("string")
        frame.loc[0, ["play_id", "ms_played", "reason_end"]] = pd.NA
    elif mode == "categorical":
        for col in ["canonical_track_name", "album_project_name", "artist_name"]:
            frame[col] = pd.Categorical(frame[col], categories=["不足", "乙", "甲", "unused"])
    elif mode == "duplicate_index":
        frame.index = [4] * len(frame)
    elif mode == "null_groups":
        frame.loc[:2, ["canonical_track_id", "album_project_id", "artist_name"]] = None
    elif mode == "below_threshold":
        frame = frame.iloc[:9].copy()
    elif mode == "empty":
        frame = frame.iloc[:0].copy()
    elif mode == "missing_reason":
        frame = frame.drop(columns="reason_end")
    elif mode == "shuffled":
        frame = frame.sample(frac=1, random_state=7)
    elif mode == "float_ms":
        frame["ms_played"] = frame["ms_played"].astype(float) + 0.5
    elif mode == "null_reason":
        frame.loc[[0, 1], "reason_end"] = None
    elif mode == "all_null_reason":
        frame["reason_end"] = pd.Series(pd.NA, index=frame.index, dtype="string")
    elif mode == "all_null_ms":
        frame["ms_played"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    elif mode == "all_null_play_id":
        frame["play_id"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    duration = frame.copy()
    attach_listening_duration_frame(frame, duration)
    frame.attrs["sentinel"] = "preserve source"
    return frame, duration, (*behavior._group_col_for(frame, entity_type), entity_type)


@pytest.mark.parametrize("entity_type", ["track", "album", "artist"])
@pytest.mark.parametrize("mode", ["normal", "duplicate_index", "shuffled", "float_ms"])
def test_skip_storm_keeps_counts_threshold_ties_and_source(entity_type, mode):
    frame, duration, args = make_skip_frame(entity_type, mode)
    before, duration_before = frame.copy(), duration.copy()
    attrs = frame.attrs.copy()
    result = behavior._skip_storm(frame, *args)
    expected_names = ["乙", "甲"] if entity_type == "artist" else ["甲", "乙"]
    assert result["name"].astype(str).tolist() == expected_names
    assert result["rank"].tolist() == [1, 2]
    assert result["total_plays"].tolist() == [12, 12]
    assert result["fwd_plays"].tolist() == [6, 6]
    assert result["value"].tolist() == [50.0, 50.0]
    expected_ms = [12006, 12006] if mode == "float_ms" else [12000, 12000]
    assert result["total_ms"].tolist() == expected_ms
    result.iat[0, result.columns.get_loc("name")] = "changed"
    pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(duration, duration_before)
    assert frame.attrs == attrs


@pytest.mark.parametrize("entity_type", ["track", "album", "artist"])
def test_skip_assign_receives_only_required_columns(monkeypatch, entity_type):
    frame, duration, args = make_skip_frame(entity_type)
    before, duration_before = frame.copy(), duration.copy()
    expected = unique_cols(*safe_groupby_cols([], *args[:3]), "play_id", "ms_played")
    original = pd.DataFrame.assign
    observed = []

    def assign(source, **kwargs):
        observed.append(list(source.columns))
        assert list(source.columns) == expected
        return original(source, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "assign", assign)
    result = behavior._skip_storm(frame, *args)
    assert observed == [expected]
    assert not result.empty
    pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(duration, duration_before)


@pytest.mark.parametrize("mode", ["empty", "missing_reason", "below_threshold"])
def test_skip_storm_empty_guards(mode):
    frame, _, args = make_skip_frame("track", mode)
    assert behavior._skip_storm(frame, *args).empty


def test_skip_storm_counts_nonnull_ids_but_all_forward_flags():
    frame, _, args = make_skip_frame("track", "nullable")
    result = behavior._skip_storm(frame, *args)
    assert result["name"].tolist() == ["甲", "乙"]
    assert result["total_plays"].tolist() == [12, 11]
    assert result["fwd_plays"].tolist() == [6, 5]
    assert result["total_ms"].tolist() == [12000, 11000]
    assert result["value"].tolist() == [50.0, 45.5]
