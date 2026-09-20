"""Invocation-local Records facts preserve slices, entity grains and ties."""

from __future__ import annotations

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from backend.domains.playback import records_duration_facts as duration_module
from backend.domains.playback import records_longevity as longevity
from backend.domains.playback.logical_timeline import (
    LISTENING_INTERVALS_COLUMN,
    attach_listening_duration_frame,
    explode_listening_slices,
)
from backend.domains.playback.records_duration_facts import RecordsDurationFacts
from backend.domains.playback.records_helpers import (
    attach_scoped_records_duration,
    records_duration_frame,
)

pytestmark = pytest.mark.unit


def _interval(start, end):
    return (pd.Timestamp(start).value, pd.Timestamp(end).value)


def test_slice_reuse_preserves_each_source_row_and_artist_credit(monkeypatch):
    midnight = _interval("2024-12-31T15:59:59.999500Z", "2024-12-31T16:00:00.001500Z")
    hour = _interval("2025-01-01T01:59:00Z", "2025-01-01T03:01:00Z")
    new = _interval("2025-02-01T00:00:00Z", "2025-02-01T00:00:03Z")
    event = pd.DataFrame(
        {
            "play_id": [3, 2, 1],
            "artist_name": ["primary"] * 3,
            "ms_played": [0, 7, 8],
            "ts_date": ["original"] * 3,
            LISTENING_INTERVALS_COLUMN: [[], [midnight, hour], [hour]],
        }
    )
    artist = event.iloc[[1, 1, 2]].copy().reset_index(drop=True)
    artist["artist_name"] = ["primary", "featured", "other"]
    artist["role"] = ["main", "featured", "main"]
    artist = pd.concat(
        [
            artist,
            pd.DataFrame(
                {
                    "play_id": [9],
                    "artist_name": ["new"],
                    "role": ["main"],
                    "ms_played": [3],
                    "ts_date": ["other"],
                    LISTENING_INTERVALS_COLUMN: [[new]],
                }
            ),
        ],
        ignore_index=True,
    )
    calls = []
    original = duration_module.explode_listening_slices

    def counted(frame, **kwargs):
        calls.append(len(frame))
        return original(frame, **kwargs)

    monkeypatch.setattr(duration_module, "explode_listening_slices", counted)
    context = RecordsDurationFacts()
    for source in [event, artist, artist]:
        before = source.copy(deep=True)
        assert_frame_equal(
            context.hour_slices(source), explode_listening_slices(source, granularity="hour")
        )
        assert_frame_equal(source, before)
    assert calls == [3, 1]  # No split for a credit-only duplicate or the repeated frame.
    assert_frame_equal(RecordsDurationFacts().hour_slices(artist), context.hour_slices(artist))


@pytest.mark.parametrize("intervals", [[], [(10, 10)], [(20, 10)]])
def test_empty_slice_geometry_preserves_empty_schema(intervals):
    source = pd.DataFrame({"x": [1], LISTENING_INTERVALS_COLUMN: [intervals]})
    context = RecordsDurationFacts()
    assert_frame_equal(
        context.hour_slices(source), explode_listening_slices(source, granularity="hour")
    )
    assert_frame_equal(
        context.hour_slices(source), explode_listening_slices(source, granularity="hour")
    )


def test_scoped_slices_do_not_leak_across_period_or_mutate_preloaded_frame(monkeypatch):
    source = pd.DataFrame(
        {
            "play_id": [1],
            "ms_played": [10000],
            LISTENING_INTERVALS_COLUMN: [
                [_interval("2024-12-31T15:59:55Z", "2024-12-31T16:00:05Z")]
            ],
        }
    )
    events = pd.DataFrame({"play_id": [1], "ts_date": ["2025-01-01"], "ms_played": [10000]})
    attach_listening_duration_frame(events, source)
    context = RecordsDurationFacts()
    scoped = attach_scoped_records_duration(
        events.copy(), start_date="2025-01-01", duration_facts=context
    )
    assert records_duration_frame(scoped)["ms_played"].sum() == 5000
    assert records_duration_frame(events)["ms_played"].sum() == 10000

    def forbidden(*args, **kwargs):
        pytest.fail("preloaded hour slices were exploded again")

    monkeypatch.setattr(context, "hour_slices", forbidden)
    attach_scoped_records_duration(scoped, duration_facts=context)
    assert records_duration_frame(scoped)["ms_played"].sum() == 5000


def test_longevity_keeps_named_grain_ties_and_readonly_facts(monkeypatch):
    # Same entity, two display names: streak totals combine, span/month do not.
    rows = [
        (1, "old", "2025-01-01"),
        (1, "new", "2025-01-02"),
        (1, "new", "2025-01-10"),
        (1, "new", "2025-01-18"),
        (2, "other", "2025-01-01"),
        (2, "other", "2025-01-02"),
    ]
    frame = pd.DataFrame(rows, columns=["id", "name", "ts_date"])
    frame["artist"] = "artist"
    frame["play_id"] = range(len(frame))
    frame["ms_played"] = 1000
    duration = frame.copy()
    duration["ms_played"] = 2000
    duration["slice_start_at"] = "ready"
    attach_listening_duration_frame(frame, duration)
    before = frame.copy()
    duration_before = duration.copy()
    facts = longevity._build_longevity_facts(frame, "id", "name", "artist")
    named_before = facts.named_totals.copy(deep=True)
    methods = (
        longevity._longest_streak_days,
        longevity._longest_span,
        longevity._comeback_after_sleep,
        longevity._most_active_months,
    )
    outputs = [method(frame, "id", "name", "artist", facts=facts) for method in methods]
    streak, span, comeback, active = outputs
    assert streak.iloc[0]["entity_id"] == "1"
    assert streak.iloc[0]["total_plays"] == 4
    assert streak.iloc[0]["total_ms"] == 8000
    assert streak.iloc[0]["start_date"] == "2025-01-01"
    assert comeback.iloc[0]["wake_date"] == "2025-01-10"  # Equal gaps keep the first.
    assert span.loc[span["name"] == "new", "total_plays"].item() == 3
    assert active.loc[active["name"] == "old", "total_ms"].item() == 2000
    assert_frame_equal(facts.named_totals, named_before)
    assert_frame_equal(frame, before)
    assert_frame_equal(duration, duration_before)
    calls = []
    original = longevity._build_longevity_facts

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(longevity, "_build_longevity_facts", counted)
    result = longevity._entity_longevity_records(frame, "id", "name", "artist", "track")
    assert len(calls) == 1
    for actual, expected in zip(result.values(), outputs):
        assert_frame_equal(actual, expected)
