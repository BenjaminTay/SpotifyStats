"""Cancelled album work must not enter the next expensive stage."""

from threading import Event

import pytest

from backend.core import db
from backend.core import request_cancellation as cancellation
from backend.services import entity_stats_service as stats
from backend.services import versus_rank_context_service as ranks
from backend.tests.unit import test_album_published_rank_context as album_tests

base_isolated = album_tests.base_isolated
isolated = album_tests.isolated
pytestmark = pytest.mark.unit


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
@pytest.mark.parametrize("stage", ["source", "duration", "first_window"])
def test_published_top250_stops_at_next_stage(isolated, monkeypatch, level, dynamic, stage):
    conn = db.get_db(readonly=True)
    signal = Event()
    token = cancellation._read_cancelled.set(signal)
    charts = []
    try:
        filters, _, _, _ = ranks.request_context(
            conn, {"merge_level": level, "dynamic_threshold": dynamic}
        )
        ranks.ensure(conn, filters)
        context, _ = ranks.read(conn, filters)
        album, artist = album_tests.sample(conn)
        album_names = stats._resolve_album_project_album_names(conn, album, artist, level)
        original_load = stats.load_period_plays
        original_duration = stats.build_duration_frame
        original_chart = stats.chart_rows

        def load(*args, **kwargs):
            result = original_load(*args, **kwargs)
            if stage == "source":
                signal.set()
            return result

        def duration(*args, **kwargs):
            assert stage != "source", "duration entered after cancelled source stage"
            result = original_duration(*args, **kwargs)
            if stage == "duration":
                signal.set()
            return result

        def chart(*args, **kwargs):
            assert stage == "first_window", "chart entered after earlier cancellation"
            charts.append(1)
            result = original_chart(*args, **kwargs)
            signal.set()
            return result

        monkeypatch.setattr(stats, "load_period_plays", load)
        monkeypatch.setattr(stats, "build_duration_frame", duration)
        monkeypatch.setattr(stats, "chart_rows", chart)
        with pytest.raises(cancellation.RequestReadCancelledError):
            stats._published_album_top250_counts(conn, context, filters, album_names, artist)
        assert charts == ([1] if stage == "first_window" else [])
    finally:
        cancellation._read_cancelled.reset(token)
        conn.close()


@pytest.mark.parametrize("level", [2, 3])
def test_album_read_stops_after_shared_loader_returns(isolated, monkeypatch, level):
    conn = db.get_db(readonly=True)
    signal = Event()
    token = cancellation._read_cancelled.set(signal)
    try:
        album, artist = album_tests.sample(conn)
        original_load = stats.load_period_plays

        def load(*args, **kwargs):
            result = original_load(*args, **kwargs)
            signal.set()
            return result

        monkeypatch.setattr(stats, "load_period_plays", load)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: False)
        monkeypatch.setattr(
            stats, "_duration_source", lambda *_: pytest.fail("owned work continued after loader")
        )
        with pytest.raises(cancellation.RequestReadCancelledError):
            stats._build_album_stats(conn, album, artist, 30000, True, True, merge_level=level)
    finally:
        cancellation._read_cancelled.reset(token)
        conn.close()
