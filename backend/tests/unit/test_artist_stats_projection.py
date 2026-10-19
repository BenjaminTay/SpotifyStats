"""Artist detail projects before reconstruction without changing complete facts."""

from itertools import product

import pandas as pd
import pytest

from backend.core import db
from backend.domains.playback import logical_timeline
from backend.services import entity_rank_context_service as ranks
from backend.services import entity_stats_service as stats
from backend.services.analysis_snapshot_service import default_params
from backend.tests.unit import test_analysis_snapshots

isolated = test_analysis_snapshots.isolated
pytestmark = pytest.mark.unit


@pytest.mark.parametrize("merge,dynamic,music", product((False, True), repeat=3))
def test_projected_loader_preserves_every_retained_event_and_duration_fact(
    isolated, monkeypatch, merge, dynamic, music
):
    conn = db.get_db(readonly=True)
    try:
        params = dict(merge_enabled=merge, dynamic_threshold=dynamic, music_only=music)
        expected = db.load_plays_for_artists(conn, **params)
        expected_duration = logical_timeline.get_listening_duration_frame(expected)
        reconstruct = logical_timeline.reconstruct_listening_intervals
        seen = []

        def bounded(frame, **kwargs):
            seen.append(tuple(frame.columns))
            assert "source_fingerprint" in frame
            assert "source_album_id" in frame
            assert "platform" in frame
            assert "reason_start" not in frame
            assert "conn_country" not in frame
            assert "import_generation_id" not in frame
            return reconstruct(frame, **kwargs)

        monkeypatch.setattr(logical_timeline, "reconstruct_listening_intervals", bounded)
        actual = db.load_plays_for_artists(conn, columns=stats._ARTIST_STATS_PLAY_COLUMNS, **params)
        actual_duration = logical_timeline.get_listening_duration_frame(actual)
        assert seen and not actual.empty
        assert expected_duration is not None and actual_duration is not None
        pd.testing.assert_frame_equal(actual, expected.loc[:, actual.columns])
        pd.testing.assert_frame_equal(
            actual_duration, expected_duration.loc[:, actual_duration.columns]
        )
    finally:
        conn.close()


@pytest.mark.parametrize("merge,dynamic", product((False, True), repeat=2))
def test_published_artist_complete_payload_matches_full_width_scoped_loader(
    isolated, monkeypatch, merge, dynamic
):
    conn = db.get_db(readonly=True)
    try:
        params = default_params(conn, "analysis_stats")
        params.update(merge_enabled=merge, dynamic_threshold=dynamic)
        ranks.ensure(conn, params)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        with monkeypatch.context() as legacy:
            legacy.setattr(stats, "_ARTIST_STATS_PLAY_COLUMNS", "*")
            expected = stats._build_artist_stats(conn, "Fixture Artist Alpha", **params)
        source_before = isolated[0].read_bytes()
        sidecar = isolated[1] / "analysis.db"
        publication_before = sidecar.read_bytes()
        assert expected["found"]
        assert stats._build_artist_stats(conn, "Fixture Artist Alpha", **params) == expected
        assert isolated[0].read_bytes() == source_before
        assert sidecar.read_bytes() == publication_before
    finally:
        conn.close()
