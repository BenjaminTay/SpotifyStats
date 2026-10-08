"""Release comparisons reuse exact weekly ranks and preserve playback windows."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.api.billboard import release_cycle as api
from backend.core.json_helpers import df_to_json
from backend.dependencies import BillboardFilters
from backend.domains.billboard import persistent_cache as cache
from backend.domains.billboard.week_coverage import (
    current_open_billboard_week,
    keep_complete_billboard_weeks,
)
from backend.services import release_cycle_comparison_service as service
from backend.services import release_cycle_service as cycles
from backend.services.billboard_snapshot_service import configured_billboard_filters
from backend.tests.unit import test_versus_rank_context

base_isolated = test_versus_rank_context.base_isolated
rank_isolated = test_versus_rank_context.isolated
pytestmark = pytest.mark.unit


@pytest.fixture
def isolated(rank_isolated, monkeypatch):
    monkeypatch.setattr(cache, "BILLBOARD_CACHE_PATH", str(rank_isolated[1] / "billboard.db"))
    service._weekly_projection.cache_clear()
    service._daily_projection.cache_clear()
    yield rank_isolated
    service._weekly_projection.cache_clear()
    service._daily_projection.cache_clear()


def _filters(**changes):
    params = configured_billboard_filters()
    params.pop("merge_level")
    params.pop("include_compilations")
    return BillboardFilters(**{**params, **changes})


def _publish_oracle(filters, level=2, compilations=False):
    raw, _, _, _ = api._get_weekly_data(filters, level, compilations)
    artists = api.load_billboard_raw_for_artists(
        filters.min_ms,
        filters.music_only,
        filters.bb_week_start_dow,
        filters.bb_week_start_hour,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_enabled=filters.merge_enabled,
    )
    artists = api._filter_billboard_years(artists, filters)
    edge = current_open_billboard_week(
        week_start_dow=filters.bb_week_start_dow,
        week_start_hour=filters.bb_week_start_hour,
    )
    weekly_artist = api.compute_artist_weekly_rankings(
        keep_complete_billboard_weeks(artists, open_week=edge), filters.bb_artist_top_n
    )
    weekly_album = api.compute_album_weekly_rankings(
        keep_complete_billboard_weeks(raw, open_week=edge),
        filters.bb_album_top_n,
        merge_level=level,
        include_compilations=compilations,
    )
    _, params = service._resolve(
        (), {**vars(filters), "merge_level": level, "include_compilations": compilations}
    )
    context = cache.build_cache_context("weekly", params)
    cache.store_persisted_snapshot(
        context,
        {
            "weekly_artist": df_to_json(weekly_artist, ["billboard_week"]),
            "weekly_album": df_to_json(weekly_album, ["billboard_week"]),
        },
    )
    return raw, weekly_artist, weekly_album


@pytest.mark.parametrize(
    "changes,level,compilations",
    [
        ({}, 2, False),
        ({"dynamic_threshold": False}, 3, True),
        ({"year_start": 2026, "year_end": 2026, "bb_week_start_hour": 23}, 2, False),
        ({"dynamic_threshold": False, "year_start": 2026, "bb_week_start_hour": 8}, 3, False),
        ({"merge_enabled": False, "bb_week_start_hour": 23}, 2, True),
    ],
)
def test_comparison_preserves_full_timelines_metrics_and_complete_week_ranks(
    isolated, monkeypatch, changes, level, compilations
):
    filters = _filters(**changes)
    raw, weekly_artist, weekly_album = _publish_oracle(filters, level, compilations)
    if "ts_date_dt" not in raw.columns:
        # Unmerged raw rows retain source dates; derive the date primitive
        # needed by the unchanged release-cycle algorithm on the oracle copy.
        raw = pd.DataFrame(raw, copy=False).copy()
        raw["ts_date_dt"] = pd.to_datetime(raw["ts_date"])
    names = list(raw["artist_name"].dropna().unique())[:2]
    selected, artist_ranks, album_ranks, daily = service.prepare_comparison_data(
        filters, names, level, compilations
    )
    assert not selected.attrs
    assert len(selected.columns) <= 8
    assert set(selected["artist_name"]) <= set(names)
    # The existing algorithm can use its precomputed daily baseline without
    # changing release-anchored windows, medians, half-life or impact metrics.
    monkeypatch.setattr(cycles, "get_advance_singles", lambda *_: [])
    for name in names:
        albums = raw.loc[raw["artist_name"] == name, "album_name"].dropna().unique()[:2]
        for album in albums:
            kwargs = dict(
                artist_name=name,
                album_name=album,
                release_date=pd.Timestamp("2026-01-01"),
                weeks_before=12,
                weeks_after=24,
            )
            legacy = cycles.compute_release_cycle(
                raw, weekly_artist=weekly_artist, weekly_album=weekly_album, **kwargs
            )
            current = cycles.compute_release_cycle(
                selected,
                weekly_artist=artist_ranks,
                weekly_album=album_ranks,
                total_daily=daily,
                **kwargs,
            )
            for field in (
                "artist_timeline",
                "album_timeline",
                "track_timelines",
                "artist_ranks",
                "album_ranks",
            ):
                pd.testing.assert_frame_equal(
                    legacy[field].reset_index(drop=True),
                    current[field].reset_index(drop=True),
                    check_dtype=False,
                )
            if not legacy["total_timeline"].empty:
                pd.testing.assert_frame_equal(
                    legacy["total_timeline"][["week_offset", "play_count"]],
                    current["total_timeline"],
                    check_dtype=False,
                )
            assert cycles.compute_release_metrics(legacy) == cycles.compute_release_metrics(current)


def test_compare_missing_wrong_filters_or_drift_never_builds_charts(isolated, monkeypatch):
    filters = _filters()
    original_counts = service._count_events

    def forbid(*args, **kwargs):
        pytest.fail("comparison entered chart building or raw preparation without exact ranks")

    monkeypatch.setattr(service, "_count_events", forbid)
    with pytest.raises(HTTPException) as unavailable:
        service.prepare_comparison_data(filters, ["Fixture Artist"])
    assert unavailable.value.status_code == 503
    assert unavailable.value.detail["error"] == "snapshot_unavailable"
    assert not (isolated[1] / "billboard.db").exists()
    monkeypatch.setattr(service, "_count_events", original_counts)
    raw, _, _ = _publish_oracle(filters)
    monkeypatch.setattr(service, "_count_events", forbid)
    with pytest.raises(HTTPException) as mismatch:
        service.prepare_comparison_data(_filters(dynamic_threshold=False), ["Fixture Artist"])
    assert mismatch.value.status_code == 503
    original_context = cache.build_cache_context
    calls = []

    def drifting(family, params):
        context = original_context(family, params)
        calls.append(1)
        return context if len(calls) == 1 else {**context, "source_revision": "changed"}

    monkeypatch.setattr(cache, "build_cache_context", drifting)
    monkeypatch.setattr(service, "_count_events", original_counts)
    with pytest.raises(HTTPException) as drift:
        service.prepare_comparison_data(filters, list(raw["artist_name"].unique()))
    assert drift.value.status_code == 503


def test_concurrent_comparisons_decode_exact_projection_once_and_never_rank(isolated, monkeypatch):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)
    names = list(raw["artist_name"].unique())[:2]
    original_read = cache.load_persisted_snapshot
    reads = []
    count_builds = []
    original_counts = service._count_events

    def count(*args, **kwargs):
        count_builds.append(1)
        return original_counts(*args, **kwargs)

    monkeypatch.setattr(service, "_count_events", count)

    def read(*args, **kwargs):
        reads.append(kwargs)
        return original_read(*args, **kwargs)

    monkeypatch.setattr(cache, "load_persisted_snapshot", read)
    for name in (
        "compute_weekly_rankings",
        "compute_artist_weekly_rankings",
        "compute_album_weekly_rankings",
    ):
        monkeypatch.setattr(
            api, name, lambda *a, **kw: pytest.fail("comparison recomputed weekly ranks")
        )
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(
            pool.map(lambda _: service.prepare_comparison_data(filters, names), range(3))
        )
    assert len(reads) == 1 and reads[0]["allow_lkg"] is False
    assert len(count_builds) == 1
    assert service._daily_projection.cache_info().currsize == 1
    assert all(result[0].equals(results[0][0]) for result in results)
    assert service._weekly_projection.cache_info().currsize == 1
    # Only scalar tuples survive caching; the full raw weighted attrs and
    # DataFrames never enter this result cache.
    _, params = service._resolve(
        (), {**vars(filters), "merge_level": 2, "include_compilations": False}
    )
    projected = service._weekly_projection(
        json.dumps(cache.build_cache_context("weekly", params), sort_keys=True),
        service._publication_state(),
    )
    assert all(isinstance(rows, tuple) for rows in projected)
    assert all(isinstance(row, tuple) for rows in projected for row in rows)


def test_coverage_edge_retains_playback_but_only_complete_week_ranks(isolated):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)
    names = list(raw["artist_name"].unique())
    selected, artists, albums, daily = service.prepare_comparison_data(filters, names)
    edge = current_open_billboard_week(
        week_start_dow=filters.bb_week_start_dow,
        week_start_hour=filters.bb_week_start_hour,
    )
    assert (pd.to_datetime(selected["billboard_week"]).dt.date == edge).any()
    assert int(daily.sum()) == len(raw)
    for ranked in (artists, albums):
        assert (pd.to_datetime(ranked["billboard_week"]).dt.date < edge).all()


def test_actual_source_drift_during_raw_read_refuses_comparison(isolated, monkeypatch):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)

    original_target = service._load_target_timeline

    def drift(*args, **kwargs):
        result = original_target(*args, **kwargs)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        return result

    monkeypatch.setattr(service, "_load_target_timeline", drift)
    with pytest.raises(HTTPException) as rejected:
        service.prepare_comparison_data(filters, list(raw["artist_name"].unique()))
    assert rejected.value.status_code == 503


def test_one_artist_multiple_releases_uses_primary_scope_without_credit_fanout(
    isolated, monkeypatch
):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)
    name = raw["artist_name"].dropna().iloc[0]
    from backend.services import versus_personal_context

    monkeypatch.setattr(
        versus_personal_context,
        "get_effective_track_credits",
        lambda *_: pytest.fail("Billboard primary timeline entered featured-credit expansion"),
    )
    selected, _, _, daily = service.prepare_comparison_data(filters, [name, name])
    expected = pd.DataFrame(raw, copy=False).loc[
        raw["artist_name"] == name, list(service.PLAY_COLUMNS)
    ]
    pd.testing.assert_frame_equal(
        selected.reset_index(drop=True), expected.reset_index(drop=True), check_dtype=False
    )
    assert int(daily.sum()) == len(raw)
    with pytest.raises(ValueError, match="2至4"):
        conn = sqlite3.connect(isolated[0])
        try:
            versus_personal_context.resolve_selection(conn, "artist", [name])
        finally:
            conn.close()
