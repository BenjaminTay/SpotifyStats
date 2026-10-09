"""Count projections share full timeline facts without its display outputs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.domains.playback import logical_timeline as timeline
from backend.domains.playback.counting import filter_effective_plays

pytestmark = pytest.mark.unit


def frame_for(case):
    if case == "expansion":
        rows = [
            (1, 1, "2026-01-01T15:59:50Z", 20000, 40000, 10),
            (2, 1, "2026-01-01T16:00:10Z", 20000, 40000, 10),
            (3, 2, "2026-01-02T00:08:30.000001Z", 510000, 240000, 11),
        ]
    elif case == "boundaries":
        rows = [
            (1, 1, "2026-01-01T00:00:40Z", 40000, 40000, None),
            (2, 1, "2026-01-01T00:01:20Z", 40000, 40000, None),
            (3, 1, "2026-01-01T00:02:00Z", 40000, 40000, 20),
            (4, 1, "2026-01-01T00:07:40Z", 40000, 40000, 20),
            (5, 1, "2026-01-01T00:13:20.001Z", 40000, 40000, 20),
            (6, 1, "2026-01-01T00:13:21.001Z", 40000, 40000, 20),
            (7, 2, "2026-01-01T00:13:21.001Z", 40000, 40000, 20),
        ]
    else:
        rows = [
            (1, 1, "2026-01-01T15:59:50Z", 20000, None, 10),
            (2, 1, "2026-01-01T16:00:10Z", 30000, 0, 10),
            (3, 2, "not-a-time", 60000, 40000, 11),
            (4, 2, None, 60000, 40000, 11),
            (5, 3, "2026-01-01T16:00:11Z", -1, -100, 12),
            (6, 3, "2026-01-01T16:00:12Z", np.nan, np.nan, 12),
            (7, 4, "2026-01-01T16:00:13Z", 30000, 600000, 13),
        ]
    frame = pd.DataFrame(
        rows, columns=["play_id", "track_id", "ts", "ms_played", "duration_ms", "source_album_id"]
    )
    frame["l1_id"] = frame["track_id"]
    frame["source_track_id"] = frame["track_id"] + 100
    frame["representative_track_id"] = frame["track_id"] + 200
    frame["track_name"] = "source title"
    frame["artist_id"] = frame["track_id"] + 300
    frame["artist_name"] = "raw owner"
    frame["ts_date"] = "intentionally wrong raw date"
    frame.index = pd.Index(range(10, 10 + len(frame)), name="source_index")
    return frame


@pytest.mark.parametrize("case", ["expansion", "boundaries", "fallback"])
@pytest.mark.parametrize("dynamic", [False, True])
@pytest.mark.parametrize("minimum", [0, 30000, 100000])
def test_projection_and_shared_parse_match_full_count_facts(case, dynamic, minimum):
    frame = frame_for(case)
    source = frame.copy(deep=True)
    kwargs = dict(
        identity_column="l1_id",
        dynamic_threshold=dynamic,
        boundary_column="source_album_id",
        max_gap_minutes=5,
    )
    full = timeline.reconstruct_logical_plays(frame, minimum, **kwargs)
    parsed = (
        pd.to_datetime(frame["ts"], errors="coerce", utc=True, format="mixed")
        .astype("int64")
        .to_numpy()
    )
    original_ns = parsed.copy()
    parsed.setflags(write=False)
    explicit_full = timeline.reconstruct_logical_plays(
        frame, minimum, **kwargs, count_only=False, parsed_timestamp_ns=parsed
    )
    pd.testing.assert_frame_equal(explicit_full, full, check_exact=True)
    for provided in (None, parsed):
        projected = timeline.reconstruct_logical_plays(
            frame, minimum, **kwargs, count_only=True, parsed_timestamp_ns=provided
        )
        if not full.empty:
            pd.testing.assert_frame_equal(projected, full[projected.columns], check_exact=True)
            filtered = filter_effective_plays(projected, min_ms=minimum, dynamic_threshold=dynamic)
            expected = filter_effective_plays(full, min_ms=minimum, dynamic_threshold=dynamic)
            pd.testing.assert_frame_equal(filtered, expected[projected.columns], check_exact=True)
        else:
            assert projected.empty
        assert not {
            "ts",
            "counted_at",
            "event_start_at",
            "event_end_at",
            "_merge_run_id",
            "time_quality",
            "playback_event_policy_version",
            timeline.LISTENING_INTERVALS_COLUMN,
        } & set(projected.columns)
    durations = timeline.reconstruct_listening_intervals(
        frame, identity_column="l1_id", boundary_column="source_album_id"
    )
    reused = timeline.reconstruct_listening_intervals(
        frame,
        identity_column="l1_id",
        boundary_column="source_album_id",
        parsed_timestamp_ns=parsed,
    )
    pd.testing.assert_frame_equal(reused, durations, check_exact=True)
    pd.testing.assert_frame_equal(frame, source, check_exact=True)
    np.testing.assert_array_equal(parsed, original_ns)


def test_compact_path_skips_display_time_rendering_and_keeps_counted_day(monkeypatch):
    frame = frame_for("expansion").iloc[:2]
    full = timeline.reconstruct_logical_plays(frame, 30000, identity_column="l1_id")

    def unused(*args, **kwargs):
        pytest.fail("unused full timeline renderer ran")

    monkeypatch.setattr(timeline, "_iso_utc_array", unused)
    monkeypatch.setattr(timeline, "_local_time_parts", unused)
    counts = timeline.reconstruct_logical_plays(
        frame, 30000, identity_column="l1_id", count_only=True
    )
    pd.testing.assert_frame_equal(counts, full[counts.columns], check_exact=True)
    assert counts["ts_date"].tolist() == ["2026-01-02"]
    assert counts["_logical_event_id"].tolist() == ["logical_event_time_v2:1:0"]


@pytest.mark.parametrize("bad", [np.zeros((2, 1), dtype="int64"), np.zeros(1, dtype="int64")])
@pytest.mark.parametrize(
    "function", [timeline.reconstruct_listening_intervals, timeline.reconstruct_logical_plays]
)
def test_preparsed_array_shape_matches_source_rows(function, bad):
    frame = frame_for("expansion").iloc[:2]
    kwargs = {"min_ms": 30000} if function is timeline.reconstruct_logical_plays else {}
    with pytest.raises(ValueError, match="one-dimensional and match"):
        function(frame, parsed_timestamp_ns=bad, **kwargs)


def test_empty_projection_has_stable_count_columns_and_checks_array_length():
    frame = frame_for("expansion").iloc[:0]
    counts = timeline.reconstruct_logical_plays(
        frame, 30000, count_only=True, parsed_timestamp_ns=np.array([], dtype="int64")
    )
    assert counts.empty
    assert counts["ms_played"].dtype == "int64"
    assert counts["_logical_event_id"].dtype == "object"
    assert "ts_date" in counts and "ts" not in counts
    with pytest.raises(ValueError, match="match"):
        timeline.reconstruct_logical_plays(
            frame, 30000, count_only=True, parsed_timestamp_ns=np.zeros(1, dtype="int64")
        )


def test_projection_retains_custom_identity_and_nullable_boundary_columns():
    frame = frame_for("boundaries").rename(
        columns={"l1_id": "owner", "source_album_id": "source_release"}
    )
    full = timeline.reconstruct_logical_plays(
        frame, 30000, identity_column="owner", boundary_column=["source_release"]
    )
    counts = timeline.reconstruct_logical_plays(
        frame, 30000, identity_column="owner", boundary_column=["source_release"], count_only=True
    )
    pd.testing.assert_frame_equal(counts, full[counts.columns], check_exact=True)
    assert "owner" in counts and "source_release" in counts
