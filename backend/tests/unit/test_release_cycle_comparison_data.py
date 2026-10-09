"""Release comparisons reuse exact weekly ranks and preserve playback windows."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Event

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.api.billboard import release_cycle as api
from backend.core import db
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


def test_empty_wal_metadata_race_does_not_split_readonly_projection_singleflight(
    isolated, monkeypatch
):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)
    names = list(raw["artist_name"].unique())[:2]
    path = isolated[1] / "billboard.db"
    wal = path.with_name(path.name + "-wal")
    # Finish private fixture maintenance before holding only real RO readers.
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    finally:
        conn.close()
    before = path.read_bytes()
    reader_open = Event()
    second_sampled = Event()
    original_read = cache.load_persisted_snapshot
    original_state = service._publication_state
    reads = []
    states = []

    def state():
        observed = original_state()
        states.append(observed)
        if len(states) == 2:
            second_sampled.set()
        return observed

    def read(*args, **kwargs):
        reads.append(kwargs)
        if len(reads) == 1:
            conn = cache._connect()  # Real mode=ro under the service's public guard.
            try:
                conn.execute("SELECT COUNT(*) FROM billboard_snapshots").fetchall()
                assert wal.exists() and wal.stat().st_size == 0
                # VFS sidecar lifecycle differs by platform. Coordinate its
                # irrelevant empty-file mtime change, never publication data.
                stat = wal.stat()
                os.utime(wal, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
                reader_open.set()
                assert second_sampled.wait(5)
                return original_read(*args, **kwargs)
            finally:
                conn.close()
        return original_read(*args, **kwargs)

    monkeypatch.setattr(service, "_publication_state", state)
    monkeypatch.setattr(cache, "load_persisted_snapshot", read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.prepare_comparison_data, filters, names)
        if not reader_open.wait(5):
            first.result(timeout=1)
            pytest.fail("first reader must open the real read-only database")
        second = pool.submit(service.prepare_comparison_data, filters, names)
        results = [first.result(timeout=10), second.result(timeout=10)]
    assert len(reads) == 1, states
    assert reads[0]["allow_lkg"] is False
    assert states[0] == states[1]
    assert path.read_bytes() == before
    assert results[0][0].equals(results[1][0])
    assert service._weekly_projection.cache_info().currsize == 1


@pytest.mark.parametrize("resolve_stats", [False, True])
def test_empty_wal_deleted_during_state_sampling_retains_main_identity(
    isolated, monkeypatch, resolve_stats
):
    filters = _filters()
    _publish_oracle(filters)
    path = isolated[1] / "billboard.db"
    wal = path.with_name(path.name + "-wal")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        assert wal.exists() and wal.stat().st_size == 0
        main = path.stat()
        before = path.read_bytes()
        original_stat = Path.stat
        original_exists = Path.exists
        sampled_exists = wal.exists()
        deleted = []

        def exists(self):
            # This was a real successful exists sample before the coordinated
            # unlink; it models the old exists->stat window without fake facts.
            return sampled_exists if self == wal else original_exists(self)

        def stat(self, *args, **kwargs):
            if self == wal and not deleted:
                deleted.append(True)
                wal.unlink()
            return original_stat(self, *args, **kwargs)

        if resolve_stats:
            from backend.tests import path_safety

            original_resolved_path = path_safety.resolved_path

            def resolved_path(value):
                resolved = original_resolved_path(value)
                if resolved is not None:
                    # Linux Python 3.9 Path.resolve performs this final stat.
                    # Preserve the actual guard and tolerate only disappearance.
                    try:
                        resolved.stat()
                    except FileNotFoundError:
                        pass
                return resolved

            monkeypatch.setattr(path_safety, "resolved_path", resolved_path)

        monkeypatch.setattr(Path, "exists", exists)
        monkeypatch.setattr(Path, "stat", stat)
        assert service._publication_state() == (
            str(path.resolve()),
            main.st_ino,
            main.st_size,
            main.st_mtime_ns,
            None,
        )
        assert deleted == [True]
        with pytest.raises(FileNotFoundError):
            original_stat(wal)
        assert path.read_bytes() == before
    finally:
        conn.close()


def test_nonempty_wal_publication_invalidates_projection_without_main_change(isolated, monkeypatch):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)
    names = list(raw["artist_name"].unique())
    _, params = service._resolve(
        (), {**vars(filters), "merge_level": 2, "include_compilations": False}
    )
    context = cache.build_cache_context("weekly", params)
    original_read = cache.load_persisted_snapshot
    payload = original_read(context, allow_lkg=False)
    assert payload is not None and payload["weekly_artist"]
    reads = []

    def read(*args, **kwargs):
        reads.append(kwargs)
        return original_read(*args, **kwargs)

    monkeypatch.setattr(cache, "load_persisted_snapshot", read)
    first = service.prepare_comparison_data(filters, names)
    path = isolated[1] / "billboard.db"
    holder = cache._connect()  # Explicit private maintenance, outside the read request.
    try:
        holder.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        before = path.read_bytes()
        before_stat = path.stat()
        # A corrected derived publication, with the same source/context key.
        payload["weekly_artist"][0]["rank"] += 1
        cache.store_persisted_snapshot(context, payload)
        assert path.read_bytes() == before
        after_stat = path.stat()
        assert (after_stat.st_ino, after_stat.st_size, after_stat.st_mtime_ns) == (
            before_stat.st_ino,
            before_stat.st_size,
            before_stat.st_mtime_ns,
        )
        assert path.with_name(path.name + "-wal").stat().st_size > 0
        second = service.prepare_comparison_data(filters, names)
    finally:
        holder.close()
    assert len(reads) == 2
    assert not first[1].equals(second[1])
    expected = pd.DataFrame(payload["weekly_artist"], columns=service.RANK_COLUMNS)
    expected["billboard_week"] = pd.to_datetime(expected["billboard_week"]).dt.date
    expected = expected.loc[expected["artist_name"].isin(names)].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        second[1].drop(columns="album_name"), expected.drop(columns="album_name")
    )


def test_main_cache_replacement_invalidates_projection_with_same_size_and_mtime(
    isolated, monkeypatch
):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)
    names = list(raw["artist_name"].unique())
    original_read = cache.load_persisted_snapshot
    reads = []

    def read(*args, **kwargs):
        reads.append(kwargs)
        return original_read(*args, **kwargs)

    monkeypatch.setattr(cache, "load_persisted_snapshot", read)
    first = service.prepare_comparison_data(filters, names)
    path = isolated[1] / "billboard.db"
    main = path.stat()
    replacement = path.with_name("replacement.db")
    source = sqlite3.connect(path)
    target = sqlite3.connect(replacement)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    assert replacement.stat().st_size == main.st_size
    os.utime(replacement, ns=(main.st_atime_ns, main.st_mtime_ns))
    replacement.replace(path)
    assert path.stat().st_ino != main.st_ino
    assert path.stat().st_mtime_ns == main.st_mtime_ns
    second = service.prepare_comparison_data(filters, names)
    assert len(reads) == 2
    assert first[1].equals(second[1])
    assert first[2].equals(second[2])


def test_real_source_change_rejects_old_projection_before_count_build(isolated, monkeypatch):
    filters = _filters()
    raw, _, _ = _publish_oracle(filters)
    names = list(raw["artist_name"].unique())
    service.prepare_comparison_data(filters, names)
    _, params = service._resolve(
        (), {**vars(filters), "merge_level": 2, "include_compilations": False}
    )
    before = cache.build_cache_context("weekly", params)
    conn = sqlite3.connect(isolated[0])
    try:
        conn.execute(
            "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
        )
        conn.commit()
    finally:
        conn.close()
    assert (
        cache.build_cache_context("weekly", params)["source_revision"] != before["source_revision"]
    )
    monkeypatch.setattr(
        service,
        "_count_events",
        lambda *a, **kw: pytest.fail("old publication triggered count rebuilding"),
    )
    with pytest.raises(HTTPException) as unavailable:
        service.prepare_comparison_data(filters, names)
    assert unavailable.value.status_code == 503


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


def _prepare_daily_aggregate(filters):
    """Publish a real aggregate on the owned seed, with an explicit source ledger."""
    with closing(db.get_db(readonly=False)) as conn, conn:
        digest = hashlib.sha256(
            json.dumps(
                [tuple(row) for row in conn.execute("SELECT * FROM plays ORDER BY play_id")],
                default=str,
            ).encode()
        ).hexdigest()
        conn.execute(
            "UPDATE playback_import_state SET active_generation_id=?,dataset_digest=? "
            "WHERE state_id=1",
            ("release-cycle-aggregate-fixture", digest),
        )
    db.build_aggregations(
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        week_start_dow=filters.bb_week_start_dow,
        week_start_hour=filters.bb_week_start_hour,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    _, resolved = service._resolve((), vars(filters))
    params = {name: resolved[name] for name in service.COUNT_FILTERS}
    return params, cache.build_cache_context("weekly", params)["source_revision"]


def test_exact_daily_aggregate_preserves_cross_year_edge_and_zero_count_slices(
    isolated, monkeypatch
):
    filters = _filters(bb_week_start_hour=12)
    edge = current_open_billboard_week(
        week_start_dow=filters.bb_week_start_dow,
        week_start_hour=filters.bb_week_start_hour,
    )
    with closing(db.get_db(readonly=False)) as conn, conn:
        template = dict(
            conn.execute("SELECT * FROM plays WHERE track_id IS NOT NULL LIMIT 1").fetchone()
        )
        for value in ("2026-01-01T00:00:00Z", f"{edge.isoformat()}T20:00:00Z"):
            row = dict(template)
            row.pop("play_id")
            row["source_fingerprint"] = None
            utc = pd.Timestamp(value)
            local = utc.tz_convert("Asia/Shanghai")
            row.update(
                ts=value,
                ts_date=str(local.date()),
                ts_year=local.year,
                ts_month=local.month,
                ts_week=local.isocalendar().week,
                ts_dow=local.dayofweek,
                ts_hour=local.hour,
                ms_played=180000,
                source_album_id=None,
            )
            conn.execute(
                f"INSERT INTO plays({','.join(row)}) VALUES({','.join('?' for _ in row)})",
                tuple(row.values()),
            )
    params, revision = _prepare_daily_aggregate(filters)
    conn = db.get_db(readonly=True)
    try:
        events = service._count_events(conn, params)
        expected = tuple(
            (int(year), str(day), int(count))
            for (year, day), count in events.groupby(["billboard_year", "ts_date"]).size().items()
        )
        zero_count = conn.execute(
            "SELECT COUNT(*) FROM agg_weekly_track_sources WHERE play_count=0 AND total_ms>0"
        ).fetchone()[0]
        assert zero_count > 0
        assert any(year == 2025 and day == "2026-01-01" for year, day, _ in expected)
        assert any(day >= edge.isoformat() for _, day, _ in expected)
        assert service._try_aggregate_daily_projection(conn, params, revision) == expected
    finally:
        conn.close()
    monkeypatch.setattr(service, "_count_events", lambda *a: pytest.fail("exact aggregate missed"))
    result = service._daily_projection(json.dumps(params, sort_keys=True), revision)
    assert result == expected
    assert all(isinstance(row, tuple) for row in result)
    assert service._daily_projection.cache_info().maxsize == 4


@pytest.mark.parametrize(
    "change",
    [
        "merge_disabled",
        "music_disabled",
        "missing_table",
        "missing_version",
        "version",
        "param_hash",
        "data_generation_id",
        "source_dataset_digest",
        "duration_revision",
        "credit_membership_revision",
        "identity_revision",
        "track_identity_revision",
        "track_credit_revision",
        "track_credit_policy",
        "playback_policy_version",
        "listening_duration_policy_version",
        "source_revision",
    ],
)
def test_daily_aggregate_incomplete_or_wrong_contract_uses_original_counts(
    isolated, monkeypatch, change
):
    params, revision = _prepare_daily_aggregate(_filters())
    if change in ("merge_disabled", "music_disabled"):
        params["merge_enabled" if change == "merge_disabled" else "music_only"] = False
        revision = cache.build_cache_context("weekly", params)["source_revision"]
    elif change == "source_revision":
        revision = "previous-source"
    else:
        with closing(db.get_db(readonly=False)) as conn, conn:
            if change == "missing_table":
                conn.execute("DROP TABLE agg_weekly_track_sources")
            elif change == "missing_version":
                conn.execute("DELETE FROM agg_config WHERE key='builder_version'")
            else:
                key = "builder_version" if change == "version" else change
                conn.execute("UPDATE agg_config SET value='stale' WHERE key=?", (key,))
    counts = []
    original = service._count_events

    def count(*args):
        counts.append(1)
        return original(*args)

    monkeypatch.setattr(service, "_count_events", count)
    service._daily_projection(json.dumps(params, sort_keys=True), revision)
    assert counts == [1]


@pytest.mark.parametrize(
    "key,value",
    [
        ("min_ms", 60000),
        ("dynamic_threshold", False),
        ("max_merge_gap_minutes", 6),
        ("bb_week_start_dow", 0),
        ("bb_week_start_hour", 23),
    ],
)
def test_daily_aggregate_actual_count_parameter_mismatch_preserves_raw_oracle(
    isolated, monkeypatch, key, value
):
    params, _ = _prepare_daily_aggregate(_filters())
    params[key] = value
    revision = cache.build_cache_context("weekly", params)["source_revision"]
    with closing(db.get_db(readonly=True)) as conn:
        events = service._count_events(conn, params)
        expected = tuple(
            (int(year), str(day), int(count))
            for (year, day), count in events.groupby(["billboard_year", "ts_date"]).size().items()
        )
        assert service._try_aggregate_daily_projection(conn, params, revision) is None
    original = service._count_events
    calls = []

    def count(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(service, "_count_events", count)
    assert service._daily_projection(json.dumps(params, sort_keys=True), revision) == expected
    assert calls == [1]


def test_daily_aggregate_real_project_membership_change_keeps_complete_date_counts(isolated):
    from backend.domains.yearly_review.context import _album_project_semantic_revision

    params, _ = _prepare_daily_aggregate(_filters())
    with closing(db.get_db(readonly=True)) as conn:
        events = service._count_events(conn, params)
        expected = tuple(
            (int(year), str(day), int(count))
            for (year, day), count in events.groupby(["billboard_year", "ts_date"]).size().items()
        )
        before = _album_project_semantic_revision(conn)
    with closing(db.get_db(readonly=False)) as conn, conn:
        membership = conn.execute(
            "SELECT project_id,track_id,min_merge_level FROM album_project_tracks LIMIT 1"
        ).fetchone()
        assert membership is not None
        deleted = conn.execute(
            "DELETE FROM album_project_tracks WHERE project_id=? AND track_id=? AND min_merge_level=?",
            tuple(membership),
        )
        assert deleted.rowcount > 0
        assert _album_project_semantic_revision(conn) != before
        assert db._aggregation_config(conn)["album_project_revision"] == before
    revision = cache.build_cache_context("weekly", params)["source_revision"]
    with closing(db.get_db(readonly=True)) as conn:
        assert service._try_aggregate_daily_projection(conn, params, revision) == expected
        current = service._count_events(conn, params)
        assert (
            tuple(
                (int(year), str(day), int(count))
                for (year, day), count in current.groupby(["billboard_year", "ts_date"])
                .size()
                .items()
            )
            == expected
        )


def test_daily_aggregate_nullable_representative_does_not_discard_count_facts(isolated):
    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import get_track_credit_revision
    from backend.domains.metadata.track_identity import get_track_identity_revision

    params, _ = _prepare_daily_aggregate(_filters())
    with closing(db.get_db(readonly=False)) as conn, conn:
        # Presentation can be unresolved without changing logical event owners.
        conn.execute("UPDATE track_l1_identities SET representative_track_id=NULL")
        db.refresh_aggregation_semantic_proof(
            conn,
            min_ms=params["min_ms"],
            music_only=params["music_only"],
            week_start_dow=params["bb_week_start_dow"],
            week_start_hour=params["bb_week_start_hour"],
            dynamic_threshold=params["dynamic_threshold"],
            max_merge_gap_minutes=params["max_merge_gap_minutes"],
            identity_revision=get_identity_revision(conn),
            track_credit_revision=get_track_credit_revision(conn),
            track_identity_revision=get_track_identity_revision(conn),
        )
    revision = cache.build_cache_context("weekly", params)["source_revision"]
    with closing(db.get_db(readonly=True)) as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM track_l1_identities WHERE representative_track_id IS NULL"
            ).fetchone()[0]
            > 0
        )
        events = service._count_events(conn, params)
        expected = tuple(
            (int(year), str(day), int(count))
            for (year, day), count in events.groupby(["billboard_year", "ts_date"]).size().items()
        )
        assert service._try_aggregate_daily_projection(conn, params, revision) == expected


def test_daily_aggregate_actual_source_mutation_during_proof_rejects_projection(
    isolated, monkeypatch
):
    params, revision = _prepare_daily_aggregate(_filters())
    original = db.build_aggregation_semantic_proof

    def mutate(*args, **kwargs):
        proof = original(*args, **kwargs)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        return proof

    monkeypatch.setattr(db, "build_aggregation_semantic_proof", mutate)
    with closing(db.get_db(readonly=True)) as conn:
        assert service._try_aggregate_daily_projection(conn, params, revision) is None


def test_daily_aggregate_unreadable_source_rows_uses_original_counts(isolated, monkeypatch):
    params, revision = _prepare_daily_aggregate(_filters())
    original_db = service.get_db

    def denied(**kwargs):
        conn = original_db(**kwargs)
        conn.set_authorizer(
            lambda operation, table, *_: (
                sqlite3.SQLITE_DENY
                if operation == sqlite3.SQLITE_READ and table == "agg_weekly_track_sources"
                else sqlite3.SQLITE_OK
            )
        )
        return conn

    calls = []
    original = service._count_events

    def count(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(service, "get_db", denied)
    monkeypatch.setattr(service, "_count_events", count)
    assert service._daily_projection(json.dumps(params, sort_keys=True), revision)
    assert calls == [1]


def test_exact_aggregate_preserves_complete_release_cycle_results(isolated, monkeypatch):
    _prepare_daily_aggregate(_filters())
    monkeypatch.setattr(service, "_count_events", lambda *a: pytest.fail("aggregate fell back"))
    test_comparison_preserves_full_timelines_metrics_and_complete_week_ranks(
        isolated, monkeypatch, {}, 2, False
    )
