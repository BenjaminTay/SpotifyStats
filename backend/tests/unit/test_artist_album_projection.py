"""Artist album subcharts retain facts with bounded temporary frame ownership."""

import weakref
from itertools import product

import pandas as pd
import pytest

from backend.core import db
from backend.domains.playback import album_projects, track_groups
from backend.domains.playback.logical_timeline import LISTENING_INTERVALS_COLUMN
from backend.services import analysis_stats_service as analysis
from backend.services import entity_rank_context_service as ranks
from backend.services import entity_stats_service as stats
from backend.services.analysis_snapshot_service import default_params
from backend.tests.unit import test_analysis_snapshots

isolated = test_analysis_snapshots.isolated
pytestmark = pytest.mark.unit


@pytest.mark.parametrize("merge,dynamic", product((False, True), repeat=2))
@pytest.mark.parametrize("period", ["lifetime", "last_4_weeks", "custom"])
def test_complete_artist_payload_matches_full_width_album_subchart(
    isolated, monkeypatch, merge, dynamic, period
):
    conn = db.get_db(readonly=True)
    try:
        params = default_params(conn, "analysis_stats")
        params.update(merge_enabled=merge, dynamic_threshold=dynamic)
        ranks.ensure(conn, params)
        params["period"] = period
        if period == "custom":
            params.update(start_date="2020-01-01", end_date="2030-01-01")
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        with monkeypatch.context() as legacy:
            legacy.setattr(stats, "_artist_album_chart_input", lambda frame, **_: frame)
            expected = stats._build_artist_stats(conn, "Fixture Artist Alpha", **params)
        assert expected["found"]
        source_before = isolated[0].read_bytes()
        publication_before = (isolated[1] / "analysis.db").read_bytes()
        assert stats._build_artist_stats(conn, "Fixture Artist Alpha", **params) == expected
        assert isolated[0].read_bytes() == source_before
        assert (isolated[1] / "analysis.db").read_bytes() == publication_before
    finally:
        conn.close()


@pytest.mark.parametrize("has_events,has_duration", [(True, True), (True, False), (False, True)])
@pytest.mark.parametrize("with_intervals", [False, True])
def test_owned_album_boundary_facts_and_temporary_lifecycle(
    isolated, monkeypatch, has_events, has_duration, with_intervals
):
    conn = db.get_db(readonly=True)
    try:
        start = pd.Timestamp("2026-06-30T23:50:00+08:00")
        end = pd.Timestamp("2026-07-01T00:10:00+08:00")
        events = pd.DataFrame(
            [
                {
                    "track_id": track_id,
                    "track_name": str(track_id),
                    "artist_name": "Artist",
                    "album_name": "Source compilation",
                    "source_album_id": 999,
                    "ts": str(end),
                    "ts_date": "2026-07-01",
                    "ms_played": 1200000,
                    "unused_context": tuple(range(30)),
                }
                for track_id in (1, 2)
            ]
        )
        durations = events.copy()
        if with_intervals:
            durations[LISTENING_INTERVALS_COLUMN] = [((start.value, end.value),)] * 2
        events.attrs["unrelated_history"] = object()
        durations.attrs["unrelated_history"] = object()
        if not has_events:
            events = events.iloc[:0].copy()
        if not has_duration:
            durations = durations.iloc[:0].copy()
        event_attrs, duration_attrs = events.attrs.copy(), durations.attrs.copy()
        original_events, original_durations = events.copy(), durations.copy()
        member = pd.DataFrame(
            [
                {
                    "project_id": track_id,
                    "album_project_name": "Owned" if track_id == 1 else "Guest only",
                    "artist_name": "Artist" if track_id == 1 else "Other artist",
                    "release_date": "2020-01-01",
                    "canonical_song_key": str(track_id),
                }
                for track_id in (1, 2)
            ]
        )
        monkeypatch.setattr(
            album_projects, "load_album_project_membership", lambda *_, **__: member
        )
        monkeypatch.setattr(track_groups, "load_track_group_keys", lambda *_, **__: pd.DataFrame())
        monkeypatch.setattr(analysis, "_album_cover_lookup", lambda _: {})
        monkeypatch.setattr(analysis, "_resolve_album_category", lambda *_: "album")
        resolved = {"start_date": "2026-07-01", "end_date": "2026-07-01"}
        with monkeypatch.context() as legacy:
            legacy.setattr(stats, "_artist_album_chart_input", lambda frame, **_: frame)
            expected = stats._artist_top_albums(conn, events, durations, resolved, "Artist")

        temporary = []
        original_filter = stats._filter_artist_owned_album_events
        original_duration = stats.build_duration_frame

        def scoped(connection, frame, *args, **kwargs):
            assert not frame.attrs
            assert "unused_context" not in frame
            assert "source_album_id" not in frame
            assert len(frame.columns) <= 8
            result = original_filter(connection, frame, *args, **kwargs)
            temporary.append(weakref.ref(result))
            return result

        def duration(frame, *args, duration_source=None, **kwargs):
            assert duration_source is not None
            result = original_duration(frame, *args, duration_source=duration_source, **kwargs)
            temporary.append(weakref.ref(result))
            return result

        monkeypatch.setattr(stats, "_filter_artist_owned_album_events", scoped)
        monkeypatch.setattr(stats, "build_duration_frame", duration)
        actual = stats._artist_top_albums(conn, events, durations, resolved, "Artist")
        assert actual == expected
        assert temporary and all(ref() is None for ref in temporary)
        pd.testing.assert_frame_equal(events, original_events)
        pd.testing.assert_frame_equal(durations, original_durations)
        assert events.attrs == event_attrs and durations.attrs == duration_attrs
        if has_events:
            assert len(actual) == 1 and actual[0]["album_name"] == "Owned"
            assert actual[0]["plays"] == 1
            expected_hours = 0.17 if has_duration and with_intervals else 0.33
            assert actual[0]["hours"] == expected_hours
        else:
            assert actual == []
    finally:
        conn.close()
