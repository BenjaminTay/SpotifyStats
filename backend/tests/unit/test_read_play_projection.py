"""Narrow SQL inputs preserve public facts and reuse scoped artist frames."""

from contextlib import closing
from functools import partial
from itertools import product

import pytest

from backend.core import db
from backend.core.cache_manager import invalidate_all
from backend.services import analysis_stats_service as analysis
from backend.services import entity_rank_context_service as ranks
from backend.services import entity_stats_service as stats
from backend.services.analysis_snapshot_service import default_params
from backend.tests.unit import test_analysis_snapshots

isolated = test_analysis_snapshots.isolated
pytestmark = pytest.mark.unit


def test_projected_charts_match_full_width_for_counts_duration_and_album_identity(
    isolated, monkeypatch
):
    from backend.domains.playback.l3_album_attribution import apply_l3_album_attribution_plan

    with closing(db.get_db(readonly=False)) as writer:
        apply_l3_album_attribution_plan(writer)
    conn = db.get_db(readonly=True)
    original = analysis.load_period_plays

    def wide(*args, **kwargs):
        loader = kwargs["_loader"].func
        kwargs["_loader"] = partial(loader, columns="*")
        return original(*args, **kwargs)

    try:
        source_before = isolated[0].read_bytes()
        for entity, level, merge, dynamic, period in (
            ("track", 1, False, False, "lifetime"),
            ("track", 2, True, True, "custom"),
            ("track", 3, True, False, "lifetime"),
            ("album", 1, True, True, "lifetime"),
            ("album", 2, False, True, "custom"),
            ("album", 3, True, False, "lifetime"),
            ("artist", 2, False, False, "lifetime"),
            ("artist", 2, True, True, "custom"),
        ):
            for metric in ("plays", "hours"):
                params = dict(
                    min_ms=30000,
                    music_only=True,
                    merge_enabled=merge,
                    dynamic_threshold=dynamic,
                    entity=entity,
                    merge_level=level,
                    metric=metric,
                    period=period,
                    start_date="2026-01-01",
                    end_date="2026-03-31",
                    include_compilations=True,
                )
                with monkeypatch.context() as legacy:
                    legacy.setattr(analysis, "load_period_plays", wide)
                    expected = analysis._build_analysis_charts(conn, **params)
                assert expected["total"] > 0
                assert analysis._build_analysis_charts(conn, **params) == expected
        assert isolated[0].read_bytes() == source_before
    finally:
        conn.close()


@pytest.mark.parametrize("merge,dynamic", product((False, True), repeat=2))
def test_artist_stats_and_rankings_preserve_facts_and_share_credited_input(
    isolated, monkeypatch, merge, dynamic
):
    conn = db.get_db(readonly=True)
    try:
        params = default_params(conn, "analysis_stats")
        params.update(merge_enabled=merge, dynamic_threshold=dynamic)
        ranks.ensure(conn, params)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        artist = "Fixture Artist Alpha"

        def payloads():
            return [
                stats._build_artist_stats(conn, artist, include_rank_context=rank, **params)
                for rank in (False, True)
            ] + [
                stats.get_artist_personal_ranking(conn, artist, entity, metric, 20, 0, **params)
                for entity, metric in product(("track", "album"), ("plays", "hours"))
            ]

        for period in ("lifetime", "custom"):
            params.update(period=period, start_date="2020-01-01", end_date="2030-01-01")
            with monkeypatch.context() as legacy:

                def wide(loader):
                    def read(*args, **kwargs):
                        kwargs["columns"] = "*"
                        return loader(*args, **kwargs)

                    return read

                legacy.setattr(stats, "load_plays", wide(db.load_plays))
                legacy.setattr(stats, "load_plays_for_artists", wide(db.load_plays_for_artists))
                expected = payloads()
            invalidate_all()
            assert payloads() == expected
            if period == "lifetime":
                # First-screen stats use primary-credit rows. The published
                # stats and four rankings share one other, credited input.
                assert db._load_plays_for_artists_cached.cache_info().misses == 1
                assert expected[0]["found"]
    finally:
        conn.close()
