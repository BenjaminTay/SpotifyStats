"""One rebuild owns its facts; no caller, scope or later invocation can reuse them."""

from functools import lru_cache

import pandas as pd
import pytest

from backend.domains.billboard import persistent_cache
from backend.domains.billboard.build_context import BillboardBuildContext

pytestmark = pytest.mark.unit


@pytest.fixture
def source(monkeypatch):
    state = {"revision": "a", "namespace": "first"}
    monkeypatch.setattr(persistent_cache, "build_cache_context", lambda *a: dict(state))
    return state


def test_owned_facts_copy_and_release_on_failure(source):
    frame = pd.DataFrame({"rank": [1, 2]})
    context = BillboardBuildContext({})
    calls = []
    with pytest.raises(RuntimeError, match="consumer failure"):
        with context:
            first = context.fact("ranked", lambda: calls.append(1) or (frame, {"nested": [1]}))
            first[0].loc[0, "rank"] = 90
            first[1]["nested"].append(2)
            second = context.fact("ranked", lambda: pytest.fail("duplicate builder"))
            assert second[0]["rank"].tolist() == [1, 2]
            assert second[1] == {"nested": [1]}
            raise RuntimeError("consumer failure")
    assert calls == [1]
    assert context._facts == {}
    with pytest.raises(RuntimeError, match="closed"):
        context.fact("ranked", lambda: frame)
    with BillboardBuildContext({}) as next_context:
        assert next_context.fact("ranked", lambda: 42) == 42


@pytest.mark.parametrize("changed", ["revision", "namespace"])
def test_source_change_rejects_result_before_publication(source, changed):
    @lru_cache
    def builder(*, _facts):
        source[changed] = "changed"
        return {"weekly": []}

    with pytest.raises(RuntimeError, match="source changed"):
        with BillboardBuildContext({}) as context:
            with pytest.raises(RuntimeError, match="source changed"):
                context.compute("weekly", {}, builder)
            # Catching a builder failure cannot turn a changed generation
            # into a successful context exit after publication.
    assert builder.cache_info().currsize == 0


def test_filter_mismatch_is_rejected_and_context_never_enters_lru(source):
    @lru_cache
    def builder(*, merge_level, _facts):
        return {"level": merge_level}

    with BillboardBuildContext({"merge_level": 2}) as context:
        with pytest.raises(ValueError, match="filter mismatch"):
            context.compute("weekly", {"merge_level": 3}, builder)
        assert context.compute("weekly", {"merge_level": 2}, builder) == {"level": 2}
    assert builder.cache_info().currsize == 0


def test_ranked_facts_shared_but_top_n_prefixes_are_separate(source, monkeypatch):
    from backend.domains.billboard import chart_load_rank

    ranks, prefixes = [], []
    monkeypatch.setattr(
        chart_load_rank,
        "_load_and_rank_uncached",
        lambda **kw: (
            ranks.append(kw)
            or (
                pd.DataFrame({"rank": [1]}),
                pd.DataFrame({"rank": [1]}),
                pd.DataFrame({"rank": [1]}),
                [],
                [],
                pd.DataFrame(),
                {},
            )
        ),
    )
    monkeypatch.setattr(
        chart_load_rank,
        "_finish_ranked_facts",
        lambda ranked, *top: prefixes.append(top) or {"top": list(top)},
    )
    base = {"merge_level": 2, "bb_top_n": 30, "bb_album_top_n": 20, "bb_artist_top_n": 20}
    with BillboardBuildContext({}) as context:
        first = context.load_rank(base)
        first["top"][0] = 99
        assert context.load_rank(base)["top"][0] == 30
        annual = {
            **base,
            **dict.fromkeys(("bb_top_n", "bb_album_top_n", "bb_artist_top_n"), 1_000_000),
        }
        assert context.load_rank(annual)["top"][0] == 1_000_000
    assert len(ranks) == 1
    assert len(prefixes) == 2
    assert ranks[0]["_ranking_only"] is True


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"merge_level": 3},
        {"include_compilations": True},
        {"bb_top_n": 1, "bb_album_top_n": 1, "bb_artist_top_n": 1},
        {"dynamic_threshold": False},
        {"merge_enabled": False},
        {"bb_week_start_hour": 13},
        {"bb_week_start_hour": 13, "merge_level": 3},
        {"bb_week_start_hour": 13, "include_compilations": True},
    ],
)
def test_seed_full_payload_parity_with_independent_builders(
    overrides, tmp_path, monkeypatch, request
):
    import sqlite3

    from backend.core import db
    from backend.core.cache_manager import invalidate_all
    from backend.domains.billboard import chart_compute, chart_staged_cache, chart_year_end_cache
    from backend.services.billboard_snapshot_service import (
        _year_end_snapshot_params,
        configured_billboard_filters,
    )

    # Function-owned seed copy, so L3 preparation never changes the session seed.
    database = tmp_path / "seed.db"
    with sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True) as source_db:
        with sqlite3.connect(database) as target:
            source_db.backup(target)
    monkeypatch.setattr(db, "DB_PATH", str(database))
    invalidate_all()
    request.addfinalizer(invalidate_all)
    if overrides.get("merge_level") == 3:
        from backend.core.db import get_db
        from backend.domains.playback.l3_album_attribution import apply_l3_album_attribution_plan

        with get_db(readonly=False) as conn:
            apply_l3_album_attribution_plan(conn)
    params = {**configured_billboard_filters(), **overrides}
    builders = {
        "weekly": chart_staged_cache._compute_weekly_data_cached,
        "power_scores": chart_staged_cache._compute_power_scores_cached,
        "summaries": chart_staged_cache._compute_summaries_cached,
        "full_data": chart_compute._compute_billboard_data_cached,
        "records": chart_staged_cache._compute_records_cached,
    }
    with BillboardBuildContext(params) as context:
        for family, builder in builders.items():
            expected = builder.__wrapped__(**params)
            assert context.compute(family, params, builder) == expected, family
        builder = chart_year_end_cache._compute_year_end_cached
        latest_params = _year_end_snapshot_params(params, None)
        expected = builder.__wrapped__(**latest_params)
        with monkeypatch.context() as annual_guard:
            annual_guard.setattr(
                "backend.domains.billboard.chart_load_rank._add_running_metrics",
                lambda *a: pytest.fail("Year-End must not build unused all-time prefixes"),
            )
            latest = context.compute("year_end", latest_params, builder)
        assert latest == expected
        for year in latest["meta"]["available_years"]:
            year_params = _year_end_snapshot_params(params, year)
            assert context.compute("year_end", year_params, builder) == builder.__wrapped__(
                **year_params
            )


@pytest.mark.parametrize("fail", [False, True])
def test_raw_fallback_owned_once_without_lru_retention(monkeypatch, fail):
    import gc
    import weakref

    from backend.core.cache_manager import invalidate_all
    from backend.domains.billboard import chart_load_rank
    from backend.domains.playback.logical_timeline import get_billboard_weighted_frame
    from backend.services.billboard_snapshot_service import configured_billboard_filters

    invalidate_all()
    calls, owned = [], []
    monkeypatch.setattr(chart_load_rank, "_try_load_from_agg", lambda *a, **kw: (None,) * 3)
    for name in ("load_billboard_raw", "load_billboard_raw_for_artists"):
        loader = getattr(chart_load_rank, name)

        def uncached(*a, _name=name, _loader=loader.__wrapped__, **kw):
            calls.append(_name)
            frame = _loader(*a, **kw)
            owned.extend([weakref.ref(frame), weakref.ref(get_billboard_weighted_frame(frame))])
            return frame

        def forbidden_lru(*a, **kw):
            pytest.fail("invocation raw facts must not enter the legacy LRU")

        forbidden_lru.__wrapped__ = uncached
        monkeypatch.setattr(chart_load_rank, name, forbidden_lru)

    params = {**configured_billboard_filters(), "bb_week_start_hour": 13}
    context = BillboardBuildContext(params)
    try:
        with context:
            first = context.load_rank(params)
            expected = first[0].copy()
            first[0].loc[:, "rank"] = 999
            again = context.load_rank(params)
            pd.testing.assert_frame_equal(again[0], expected)
            annual = context.load_rank(params, year_end=True)
            assert len(annual[0]) >= len(again[0])
            for result in (first, again, annual):
                for index in (0, 1, 2, 5):
                    assert get_billboard_weighted_frame(result[index]) is None
            gc.collect()
            assert all(ref() is None for ref in owned)
            if fail:
                raise RuntimeError("consumer failed after raw ranking")
    except RuntimeError as exc:
        assert fail and str(exc) == "consumer failed after raw ranking"
    assert context._closed and context._facts == {}
    assert calls == ["load_billboard_raw", "load_billboard_raw_for_artists"]
    invalidate_all()


def test_owned_raw_copies_keep_1300_count_duration_boundary(source):
    from backend.domains.billboard.chart_ranking import compute_weekly_rankings
    from backend.domains.billboard.data_loader import _attach_unmerged_listening_intervals
    from backend.domains.playback.logical_timeline import (
        attach_billboard_weighted_frame,
        billboard_week_for_timestamps,
        build_billboard_weighted_frame,
        get_billboard_weighted_frame,
    )

    # Friday 12:59:30–13:00:30 Shanghai: one count in the new week,
    # thirty seconds of listening in each week, including a duration-only row.
    raw = _attach_unmerged_listening_intervals(
        pd.DataFrame(
            {
                "track_id": [1],
                "track_name": ["Boundary"],
                "artist_name": ["Artist"],
                "album_name": ["Album"],
                "ts": ["2026-09-11T05:00:30Z"],
                "ms_played": [60_000],
            }
        )
    )
    weighted = build_billboard_weighted_frame(raw, week_start_dow=4, week_start_hour=13)
    raw["billboard_week"] = billboard_week_for_timestamps(
        raw["counted_at"], week_start_dow=4, week_start_hour=13
    )
    attach_billboard_weighted_frame(raw, weighted)

    @lru_cache
    def loader():
        return raw

    with BillboardBuildContext({}) as context:
        owned = context.load_raw(loader)
        copied = get_billboard_weighted_frame(owned)
        weekly = copied.groupby("billboard_week")[["play_count", "total_ms"]].sum()
        assert weekly["play_count"].tolist() == [0, 1]
        assert weekly["total_ms"].tolist() == [30_000, 30_000]
        assert [str(w) for w in weekly.index] == ["2026-09-04", "2026-09-11"]
        pd.testing.assert_frame_equal(
            compute_weekly_rankings(owned, 30, merge_level=1),
            compute_weekly_rankings(raw, 30, merge_level=1),
        )
        copied.loc[:, "play_count"] = 999
        owned.loc[:, "track_name"] = "changed"
        assert weighted["play_count"].sum() == 1
        assert raw["track_name"].tolist() == ["Boundary"]
    assert loader.cache_info().currsize == 0


@pytest.mark.parametrize("changed", ["revision", "namespace"])
def test_final_publication_source_fence_releases_owned_facts(source, changed):
    context = BillboardBuildContext({})
    with pytest.raises(RuntimeError, match="source changed"):
        with context:
            context.fact("ranked", lambda: pd.DataFrame({"rank": [1]}))
            # Simulate source movement after the last builder has returned and
            # its row has been published. Existing rows remain valid LKG facts.
            source[changed] = "changed after publication"
    assert context._closed and context._facts == {}
