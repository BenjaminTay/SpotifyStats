"""Track charts retain complete facts while weighting only consumed columns."""

import pandas as pd
import pytest

from backend.core import db
from backend.domains.playback import logical_timeline
from backend.domains.playback.logical_timeline import (
    LISTENING_INTERVALS_COLUMN,
    attach_listening_duration_frame,
    get_listening_duration_frame,
)
from backend.services import analysis_stats_service as analysis
from backend.services import entity_stats_service as stats
from backend.services import versus_rank_context_service as ranks
from backend.tests.unit import test_album_published_rank_context as album_tests

base_isolated = album_tests.base_isolated
isolated = album_tests.isolated
pytestmark = pytest.mark.unit


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
@pytest.mark.parametrize("period", ["lifetime", "last_6_months", "last_4_weeks"])
def test_complete_track_rows_match_full_width_weighting(
    isolated, monkeypatch, level, dynamic, period
):
    conn = db.get_db(readonly=True)
    try:
        events, current, resolved = analysis.load_period_plays(
            conn,
            30000,
            True,
            True,
            period,
            dynamic_threshold=dynamic,
            attach_duration_slices=False,
        )
        duration = analysis.build_duration_frame(events, resolved)
        current["unused_context"] = [tuple(range(20))] * len(current)
        duration["unused_context"] = [tuple(range(20))] * len(duration)
        event_attrs = current.attrs.copy()
        duration_attrs = duration.attrs.copy()
        expected = {}
        # Disable only projection: the original full-width weighting,
        # canonicalization, sorting and serialization form the reference path.
        with monkeypatch.context() as legacy:
            legacy.setattr(analysis, "_track_chart_input", lambda frame: frame)
            for metric in ("plays", "hours"):
                expected[metric] = analysis.chart_rows(
                    conn,
                    current,
                    "track",
                    metric,
                    20,
                    1,
                    merge_level=level,
                    duration_frame=duration,
                )
        for metric in ("plays", "hours"):
            assert (
                analysis.chart_rows(
                    conn,
                    current,
                    "track",
                    metric,
                    20,
                    1,
                    merge_level=level,
                    duration_frame=duration,
                )
                == expected[metric]
            )
        assert current.attrs == event_attrs
        assert duration.attrs == duration_attrs
        assert "unused_context" in current and "unused_context" in duration
    finally:
        conn.close()


@pytest.mark.parametrize("empty_counts", [False, True])
def test_implicit_duration_is_resolved_before_projection(monkeypatch, empty_counts):
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
                "ms_played": 1200000,
                LISTENING_INTERVALS_COLUMN: ((begin.value, finish.value),),
                "unused_context": tuple(range(20)),
            }
        ]
    )
    counts = source.iloc[: 0 if empty_counts else 1].copy()
    attach_listening_duration_frame(counts, source)
    original_weighting = analysis._analysis_weighted_frame
    seen = []
    allowed = {"track_id", "track_name", "artist_name", "album_name", "ts", "ms_played"}

    def bounded(events, *, duration_frame=None):
        observed_duration = (
            duration_frame
            if duration_frame is not None
            else analysis._duration_frame(events, granularity="hour")
        )
        seen.append((tuple(events.columns), tuple(observed_duration.columns)))
        assert set(events.columns) <= allowed
        assert set(observed_duration.columns) <= allowed
        assert not events.attrs and not observed_duration.attrs
        return original_weighting(events, duration_frame=duration_frame)

    monkeypatch.setattr(analysis, "_analysis_weighted_frame", bounded)
    result = analysis._chart_agg(counts, "track", conn=None, merge_level=1)
    assert len(seen) == 1
    assert all(set(columns) <= allowed for columns in seen[0])
    assert result["plays"].tolist() == [0 if empty_counts else 1]
    assert result["hours"].tolist() == [1 / 3]
    assert get_listening_duration_frame(counts) is source
    assert LISTENING_INTERVALS_COLUMN in source and "unused_context" in source


def test_top250_duration_expansion_uses_only_consumed_columns(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(conn)
        ranks.ensure(conn, filters)
        context, _ = ranks.read(conn, filters)
        album, artist = album_tests.sample(conn)
        album_names = stats._resolve_album_project_album_names(conn, album, artist, 2)
        build = stats.build_duration_frame
        with monkeypatch.context() as legacy:
            legacy.setattr(stats, "build_duration_frame", lambda frame, **kwargs: build(frame))
            expected = stats._published_album_top250_counts(
                conn, context, filters, album_names, artist
            )
        explode = logical_timeline.explode_listening_slices
        seen = []

        def bounded(frame, **kwargs):
            seen.append(tuple(frame.columns))
            assert set(frame.columns) <= {
                "track_id",
                "track_name",
                "artist_name",
                "album_name",
                "ts",
                "ts_date",
                "ms_played",
                LISTENING_INTERVALS_COLUMN,
            }
            return explode(frame, **kwargs)

        monkeypatch.setattr(logical_timeline, "explode_listening_slices", bounded)
        assert (
            stats._published_album_top250_counts(conn, context, filters, album_names, artist)
            == expected
        )
        assert len(seen) == 1
    finally:
        conn.close()
