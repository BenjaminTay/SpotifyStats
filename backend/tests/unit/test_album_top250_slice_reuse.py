"""A single unfiltered duration slice frame preserves all three Top250 windows."""

import pandas as pd
import pytest

from backend.core import db
from backend.services import analysis_stats_service as analysis
from backend.services import entity_stats_service as stats
from backend.services import versus_rank_context_service as ranks
from backend.tests.unit import test_album_published_rank_context as album_tests

base_isolated = album_tests.base_isolated
isolated = album_tests.isolated
pytestmark = pytest.mark.unit


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
def test_unfiltered_slice_reuse_matches_legacy_top250_for_all_windows(
    isolated, monkeypatch, level, dynamic
):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(
            conn, {"merge_level": 2, "dynamic_threshold": dynamic}
        )
        ranks.ensure(conn, filters)
        context, _ = ranks.read(conn, filters)
        album, artist = album_tests.sample(conn)
        album_names = stats._resolve_album_project_album_names(conn, album, artist, level)
        parent_frames = []
        duration_calls = []
        event_filter = stats.filter_period_events
        duration_builder = stats.build_duration_frame
        load = stats.load_plays
        count = stats._top250_count

        # Independent legacy oracle: full-width rows and per-window slicing.
        def wide_load(*args, **kwargs):
            kwargs.pop("columns", None)
            return load(*args, **kwargs)

        def legacy_count(*args, **kwargs):
            kwargs.pop("duration_frame", None)
            return count(*args, **kwargs)

        with monkeypatch.context() as old:
            old.setattr(stats, "load_plays", wide_load)
            old.setattr(stats, "_top250_count", legacy_count)
            expected = stats._published_album_top250_counts(
                conn, context, filters, album_names, artist
            )

        def collect_parent(frame, resolved):
            if "slice_start_at" not in frame.columns:
                parent_frames.append(frame)
            return event_filter(frame, resolved)

        def collect_duration(*args, **kwargs):
            duration_calls.append(1)
            return duration_builder(*args, **kwargs)

        with monkeypatch.context() as current:
            current.setattr(stats, "filter_period_events", collect_parent)
            current.setattr(stats, "build_duration_frame", collect_duration)
            actual = stats._published_album_top250_counts(
                conn, context, filters, album_names, artist
            )
        assert actual == expected
        assert duration_calls == [1]
        assert len(parent_frames) == 3
        assert all(frame is parent_frames[0] for frame in parent_frames)
        shared = analysis.build_duration_frame(parent_frames[0])
        for resolved in context["periods"].values():
            original = analysis.build_duration_frame(
                analysis.filter_period_events(parent_frames[0], resolved), resolved
            )
            reused = analysis.filter_period_events(shared, resolved).reset_index(drop=True)
            pd.testing.assert_frame_equal(reused, original)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-06-30", "2026-06-30"),
        ("2026-07-01", "2026-07-01"),
        ("2026-07-02", "2026-07-02"),
        (None, "2026-06-30"),
        ("2026-07-01", None),
        (None, None),
    ],
)
def test_slice_reuse_preserves_cross_midnight_and_empty_count_window(start, end):
    from backend.domains.playback.logical_timeline import (
        LISTENING_INTERVALS_COLUMN,
        attach_listening_duration_frame,
    )

    begin = pd.Timestamp("2026-06-30T23:50:00+08:00")
    finish = pd.Timestamp("2026-07-01T00:10:00+08:00")
    source = pd.DataFrame(
        [
            {
                "track_id": 1,
                "track_name": "Boundary",
                "artist_name": "Artist",
                "album_name": "Album",
                "ts": finish,
                "ts_date": "2026-07-01",
                "ms_played": 1_200_000,
                LISTENING_INTERVALS_COLUMN: ((begin.value, finish.value),),
            }
        ]
    )
    counts = source.copy()
    attach_listening_duration_frame(counts, source)
    bounds = {"start_date": start, "end_date": end}
    period_counts = analysis.filter_period_events(counts, bounds)
    expected = analysis.build_duration_frame(period_counts, bounds)
    shared = analysis.build_duration_frame(counts)
    actual = analysis.filter_period_events(shared, bounds).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)
    if start == end == "2026-06-30":
        assert period_counts.empty
        assert actual["ms_played"].sum() == 600_000
