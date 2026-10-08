"""Complete compact ranks, source fences, read-only access and bounded retention."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException

from backend.core import db
from backend.services import analysis_snapshot_store as store
from backend.services import analysis_stats_service as analysis
from backend.services import versus_rank_context_service as ranks
from backend.tests.unit import test_analysis_snapshots

base_isolated = test_analysis_snapshots.isolated


@pytest.fixture
def isolated(base_isolated):
    from backend.domains.playback.l3_album_attribution import apply_l3_album_attribution_plan

    conn = db.get_db(readonly=False)
    try:
        apply_l3_album_attribution_plan(conn, ensure_schema=False)
    finally:
        conn.close()
    yield base_isolated
    ranks._read_cached.cache_clear()


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
def test_compact_full_collection_matches_public_chart_oracle(isolated, level, dynamic):
    conn = db.get_db(readonly=True)
    try:
        params, _, metadata, _ = ranks.request_context(
            conn, {"merge_level": level, "dynamic_threshold": dynamic}
        )
        payload = ranks.build_payload(conn, params)
        assert all(payload[k] == v for k, v in metadata.items())
        load = {k: params[k] for k in ranks.LOAD_FILTERS}
        for kind in ranks.KINDS:
            loader = db.load_plays_for_artists if kind == "artist" else db.load_plays
            frame, _, _ = analysis.load_period_plays(
                conn, **load, _loader=loader, attach_duration_slices=False
            )
            for period in ranks.PERIODS:
                resolved = analysis.resolve_period(frame, period, None, None)
                duration = analysis.build_duration_frame(
                    frame, None if period == "lifetime" else resolved
                )
                _, rows = analysis.chart_rows(
                    conn,
                    analysis.filter_period_events(frame, resolved),
                    kind,
                    "plays",
                    None,
                    0,
                    level,
                    params["include_compilations"],
                    duration,
                )
                expected = {}
                for row in rows:
                    key = (
                        str(row["track_id"])
                        if kind == "track"
                        else str(row["album_project_id"])
                        if kind == "album"
                        else row["artist_name"]
                    )
                    expected.setdefault(key, row["rank"])
                assert payload["ranks"][kind][period] == expected
    finally:
        conn.close()


def test_compact_builder_never_generates_display_rows_and_slices_once_per_loader(
    isolated, monkeypatch
):
    conn = db.get_db(readonly=True)
    calls = []
    original = analysis.build_duration_frame

    def duration(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(analysis, "build_duration_frame", duration)
    monkeypatch.setattr(analysis, "chart_rows", lambda *a, **kw: pytest.fail("display rows built"))
    monkeypatch.setattr(analysis, "_album_cover_lookup", lambda *a: pytest.fail("covers loaded"))
    monkeypatch.setattr(analysis, "_artist_cover_lookup", lambda *a: pytest.fail("covers loaded"))
    try:
        payload = ranks.build_payload(conn)
        assert payload["ranks"]["track"]["lifetime"]
        assert len(calls) == 2
    finally:
        conn.close()


def test_maintenance_owned_frames_preserve_interactive_cache_and_source_connection(
    isolated, monkeypatch
):
    conn = db.get_db(readonly=True)
    try:
        # Existing consumers retain their cached frames and still obtain
        # isolated copies through the normal GET loader path.
        interactive = db.load_plays(conn)
        artists = db.load_plays_for_artists(conn)
        cached = (
            db._load_plays_cached.cache_info(),
            db._load_plays_for_artists_cached.cache_info(),
        )
        db.load_plays(conn)
        assert db._load_plays_cached.cache_info().hits == cached[0].hits + 1
        cached = (
            db._load_plays_cached.cache_info(),
            db._load_plays_for_artists_cached.cache_info(),
        )

        def no_new_connection(*args, **kwargs):
            pytest.fail("maintenance opened a second source connection")

        monkeypatch.setattr(db, "get_db", no_new_connection)
        monkeypatch.setattr(ranks, "get_db", no_new_connection)
        for params in ranks.default_configurations(conn):
            assert ranks.ensure(conn, params)["published"]
        assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] > 0
        assert (
            db._load_plays_cached.cache_info(),
            db._load_plays_for_artists_cached.cache_info(),
        ) == cached
        assert not interactive.empty and not artists.empty
    finally:
        conn.close()


def test_exact_publication_singleflight_source_drift_and_restart_read(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        with pytest.raises(HTTPException) as missing:
            ranks.read(conn)
        assert missing.value.status_code == 503

        def build(_):
            owned = db.get_db(readonly=True)
            try:
                return ranks.ensure(owned)
            finally:
                owned.close()

        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(build, range(4)))
        assert sum(result["published"] for result in results) == 1
        before = ranks.read(conn)
        ranks._read_cached.cache_clear()
        monkeypatch.setattr(ranks, "build_payload", lambda *a: pytest.fail("read built ranks"))
        assert ranks.read(conn) == before
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        with pytest.raises(HTTPException) as drift:
            ranks.read(conn)
        assert drift.value.status_code == 503
    finally:
        conn.close()


def test_invalid_or_corrupt_payload_refused_with_no_lkg_fallback(isolated):
    conn = db.get_db(readonly=True)
    try:
        ranks.ensure(conn)
        params, key, metadata, family = ranks.request_context(conn)
        payload, _ = ranks.read(conn)
        bad = {**payload, "ranks": {}}
        store.publish(family, key, metadata["source_revision"], ranks.VERSION, bad)
        with pytest.raises(HTTPException):
            ranks.read(conn)
        ranks.ensure(conn)
        with sqlite3.connect(store.path()) as writer:
            writer.execute("UPDATE analysis_snapshots SET sha256='bad' WHERE family=?", (family,))
        with pytest.raises(HTTPException):
            ranks.read(conn)
    finally:
        conn.close()


def test_source_fence_refuses_partial_publication(isolated, monkeypatch):
    original = ranks.build_payload

    def drifting(conn, params):
        value = original(conn, params)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        return value

    monkeypatch.setattr(ranks, "build_payload", drifting)
    conn = db.get_db(readonly=True)
    try:
        with pytest.raises(ValueError, match="changed during"):
            ranks.ensure(conn)
        assert not store.path().exists()
    finally:
        conn.close()


def test_rank_store_default_custom_and_existing_budgets_are_independent(isolated):
    for i in range(store.MAX_KEYS):
        store.publish("analysis_records", str(i), "r", "v", {})
    for i in range(4):
        store.publish(ranks.FAMILY, f"default{i}", "r", "v", {})
    for i in range(9):
        store.publish(ranks.CUSTOM_FAMILY, f"custom{i}", "r", "v", {})
    with sqlite3.connect(store.path()) as conn:
        rows = dict(
            conn.execute(
                "SELECT family,COUNT(DISTINCT request_key) FROM analysis_snapshots GROUP BY family"
            )
        )
    assert rows == {"analysis_records": 16, ranks.FAMILY: 4, ranks.CUSTOM_FAMILY: 4}
    assert all(store.read(ranks.FAMILY, f"default{i}", "r", "v") for i in range(4))
    store.publish("analysis_stats", "extra", "r", "v", {})
    assert all(store.read(ranks.FAMILY, f"default{i}", "r", "v") for i in range(4))
    assert store.read(ranks.CUSTOM_FAMILY, "custom0", "r", "v") is None


def test_export_manifest_does_not_require_origin_lineage(isolated):
    conn = db.get_db(readonly=True)
    try:
        ranks.ensure(conn)
        manifest = ranks.export_publication(conn)
        assert manifest["source_revision"] == manifest["payload"]["source_revision"]
        assert manifest["payload_digest"] == store.digest(manifest["payload"])
        assert manifest["builder_version"] == ranks.VERSION
    finally:
        conn.close()


def test_lifetime_duration_outside_count_coverage_preserves_hour_tiebreak(monkeypatch):
    import pandas as pd

    from backend.services.versus_personal_context import STATISTICS_CONTRACT_VERSION

    events = pd.DataFrame(
        [
            {
                "track_id": 500001,
                "track_name": "A",
                "artist_name": "Artist",
                "album_name": "Album",
                "ts": "2026-02-02T12:00:00",
                "ts_date": "2026-02-02",
                "ms_played": 30000,
            },
            {
                "track_id": 500002,
                "track_name": "B",
                "artist_name": "Artist",
                "album_name": "Album",
                "ts": "2026-02-02T12:05:00",
                "ts_date": "2026-02-02",
                "ms_played": 30000,
            },
        ]
    )
    durations = events.copy()
    durations.loc[0, "ms_played"] = 40000
    durations.loc[1, "ms_played"] = 30000
    edge = events.iloc[[1]].copy()
    edge["ts_date"] = "2026-02-01"
    edge["ms_played"] = 20000
    durations = pd.concat([durations, edge], ignore_index=True)
    metadata = {
        "filter_fingerprint": "fixture",
        "source_revision": "revision",
        "statistics_contract_version": STATISTICS_CONTRACT_VERSION,
    }
    params = {
        "merge_level": 2,
        "include_compilations": False,
        **{k: True for k in ranks.LOAD_FILTERS},
    }
    monkeypatch.setattr(
        ranks, "request_context", lambda *_: (params, "key", metadata, ranks.FAMILY)
    )
    monkeypatch.setattr(
        analysis, "load_period_plays", lambda *_args, **_kwargs: (events, events, {})
    )
    monkeypatch.setattr(analysis, "build_duration_frame", lambda *_args, **_kwargs: durations)
    rank_map = ranks._rank_map
    monkeypatch.setattr(
        ranks,
        "_rank_map",
        lambda c, e, d, kind, p: rank_map(None, e, d, kind, p) if kind == "track" else {},
    )
    payload = ranks.build_payload(None)
    assert payload["ranks"]["track"]["lifetime"] == {"500002": 1, "500001": 2}
    # The prior lifetime clipping loses the extra listening-only boundary day,
    # reversing an equal-count tie. Recent windows still apply their boundaries.
    clipped = analysis.resolve_period(events, "lifetime", None, None)
    assert rank_map(None, events, ranks._filter_slices(durations, clipped), "track", params) == {
        "500001": 1,
        "500002": 2,
    }


def test_default_maintenance_enqueues_four_unique_contexts_and_reuses_ready(isolated):
    from backend.core.job_queue import JobQueue

    queue = JobQueue()
    queue.prepare(str(isolated[0]))
    jobs = ranks.enqueue_defaults("fixture", queue=queue)
    assert len(jobs) == 4
    assert ranks.enqueue_defaults("duplicate", queue=queue) == []
    conn = db.get_db(readonly=True)
    try:
        for params in ranks.default_configurations(conn):
            ranks.ensure(conn, params)
        assert ranks.enqueue_defaults("all ready", queue=queue) == []
        custom = {"min_ms": 45000}
        assert ranks.prepare_snapshot(custom, queue=queue)["job_id"]
        for params in ranks.default_configurations(conn):
            assert ranks.read(conn, params)[1]["status"] == "ready"
    finally:
        conn.close()


def test_custom_maintenance_capacity_counts_running_and_existing_targets(isolated):
    from backend.core.job_queue import Job, JobQueue

    queue = JobQueue(max_workers=0)
    queue.prepare(str(isolated[0]))
    filters = [{"min_ms": value} for value in (40000, 45000, 50000, 55000)]
    claimed = [ranks.prepare_snapshot(params, queue=queue) for params in filters]
    assert all(result["job_id"] for result in claimed)
    second = JobQueue(max_workers=0)
    second.prepare(str(isolated[0]))
    second._active_targets.clear()
    with sqlite3.connect(isolated[0]) as writer:
        writer.execute(
            "UPDATE background_jobs SET status='running' WHERE job_id=?",
            (claimed[0]["job_id"],),
        )
    # A separate queue must consult durable pending/running targets, including
    # the existing target whose status changed to running.
    assert ranks.prepare_snapshot(filters[0], queue=second) == {
        "status": "queued",
        "request_key": claimed[0]["request_key"],
        "job_id": None,
    }
    refused = ranks.prepare_snapshot({"min_ms": 60000}, queue=second)
    assert refused["status"] == "deferred" and refused["job_id"] is None
    # Default and unrelated maintenance families retain their own contracts.
    assert len(ranks.enqueue_defaults("custom quota full", queue=second)) == 4
    assert second.enqueue_if_not_pending(Job.create("fixture_maintenance", "other", "new"))
    with sqlite3.connect(isolated[0]) as writer:
        count = writer.execute(
            "SELECT COUNT(*) FROM background_jobs WHERE job_type=? AND entity_type=?",
            (ranks.JOB_TYPE, ranks.CUSTOM_FAMILY),
        ).fetchone()[0]
        assert count == 4
        writer.execute(
            "UPDATE background_jobs SET status='done' WHERE job_id=?",
            (claimed[1]["job_id"],),
        )
    assert ranks.prepare_snapshot({"min_ms": 60000}, queue=second)["job_id"]


def test_custom_maintenance_capacity_is_atomic_across_concurrent_queues(isolated):
    from backend.core.job_queue import JobQueue

    first, second = JobQueue(max_workers=0), JobQueue(max_workers=0)
    for queue in (first, second):
        queue.prepare(str(isolated[0]))
    for value in (40000, 45000, 50000):
        assert ranks.prepare_snapshot({"min_ms": value}, queue=first)["job_id"]
    barrier = Barrier(2)

    def claim(queue, value):
        barrier.wait()
        return ranks.prepare_snapshot({"min_ms": value}, queue=queue)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, first, 55000), pool.submit(claim, second, 60000)]
        results = [future.result() for future in futures]
    assert sorted(result["status"] for result in results) == ["deferred", "queued"]
    assert sum(bool(result["job_id"]) for result in results) == 1
    with sqlite3.connect(isolated[0]) as reader:
        assert (
            reader.execute(
                "SELECT COUNT(*) FROM background_jobs WHERE job_type=? AND entity_type=? "
                "AND status IN ('pending','running')",
                (ranks.JOB_TYPE, ranks.CUSTOM_FAMILY),
            ).fetchone()[0]
            == 4
        )


def test_custom_capacity_cannot_fall_back_to_unbounded_memory_queue(isolated, monkeypatch):
    from backend.core import job_queue

    queue = job_queue.JobQueue(max_workers=0)
    queue.prepare(str(isolated[0]))

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(job_queue, "connect_sqlite_path", unavailable)
    result = ranks.prepare_snapshot({"min_ms": 45000}, queue=queue)
    assert result["status"] == "deferred" and result["job_id"] is None
    assert not queue._active_targets
    assert not queue._startup_jobs


def test_public_guard_blocks_prepare_build_publish(isolated):
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )

    conn = db.get_db(readonly=True)
    try:
        token = set_public_readonly_db_guard(True)
        try:
            assert ranks.enqueue_defaults("public") == []
            with pytest.raises(PermissionError):
                ranks.ensure(conn)
            with pytest.raises(PermissionError):
                ranks.prepare_snapshot()
        finally:
            reset_public_readonly_db_guard(token)
    finally:
        conn.close()


def test_personal_rank_jobs_share_gate_with_other_heavy_families(isolated):
    import threading
    import time

    from backend.core.job_queue import Job, JobQueue

    queue = JobQueue(max_workers=0)
    queue.prepare(str(isolated[0]))
    active = peak = 0
    lock = threading.Lock()

    def handler(_job):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1

    queue.register(ranks.JOB_TYPE, handler)
    queue.register("analysis_snapshot_rebuild", handler)
    jobs = [
        Job.create(ranks.JOB_TYPE, ranks.FAMILY, "one"),
        Job.create("analysis_snapshot_rebuild", "analysis", "two"),
    ]
    for job in jobs:
        queue._insert_db_job(job)
    with ThreadPoolExecutor(2) as executor:
        assert all(executor.map(queue._process_job, jobs))
    assert peak == 1


def test_import_job_completion_schedules_rank_maintenance(isolated, monkeypatch):
    from backend.core.job_queue import Job, JobQueue
    from backend.services import analysis_snapshot_service, entity_rank_context_service

    queue = JobQueue(max_workers=0)
    queue.prepare(str(isolated[0]))
    scheduled = []
    monkeypatch.setattr(analysis_snapshot_service, "enqueue_defaults", lambda *a, **kw: [])
    monkeypatch.setattr(entity_rank_context_service, "enqueue_default", lambda *a, **kw: [])
    monkeypatch.setattr(
        ranks, "enqueue_defaults", lambda reason, queue: scheduled.append((reason, queue))
    )
    queue.register("playback_import_maintenance", lambda _job: None)
    job = Job.create("playback_import_maintenance", "import", "fixture")
    queue._insert_db_job(job)
    assert queue._process_job(job)
    assert scheduled == [("playback_import_maintenance", queue)]


def test_missing_revision_tracking_is_snapshot_unavailable(isolated):
    conn = db.get_db(readonly=True)
    try:
        ranks.ensure(conn)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute("DROP TRIGGER analysis_rev_plays_update")
        with pytest.raises(HTTPException) as unavailable:
            ranks.read(conn)
        assert unavailable.value.status_code == 503
        assert unavailable.value.detail["error"] == "snapshot_unavailable"
    finally:
        conn.close()


def test_rank_read_fences_identity_selection_before_and_after_source_change(isolated, monkeypatch):
    from backend.services import versus_personal_context as personal_context

    conn = db.get_db(readonly=True)
    try:
        ranks.ensure(conn)
        track = conn.execute(
            "SELECT l1_id FROM track_l1_identities ORDER BY l1_id LIMIT 1"
        ).fetchone()[0]
        params, _, _, family = ranks.request_context(conn)
        original = personal_context.resolve_selection

        def drift_then_return(*args, **kwargs):
            selected = original(*args, **kwargs)
            with sqlite3.connect(isolated[0]) as writer:
                writer.execute(
                    "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
                )
            # Simulate a concurrent maintenance publication becoming ready for
            # the newer revision immediately after identity resolution.
            _, new_key, new_metadata, _ = ranks.request_context(conn, params)
            payload = ranks.build_payload(conn, params)
            store.publish(family, new_key, new_metadata["source_revision"], ranks.VERSION, payload)
            return selected

        monkeypatch.setattr(personal_context, "resolve_selection", drift_then_return)
        with pytest.raises(HTTPException) as unavailable:
            ranks.read_personal_ranks(conn, "track", [track, 999999999], params)
        assert unavailable.value.status_code == 503
    finally:
        conn.close()


def test_candidate_only_drift_keeps_exact_rank_but_metadata_change_refuses(isolated):
    conn = db.get_db(readonly=True)
    try:
        ranks.ensure(conn)
        before = ranks.read(conn)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE music_search_revision_state SET candidate_revision=candidate_revision+1"
            )
        assert ranks.read(conn) == before
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE music_search_revision_state SET metadata_revision=metadata_revision+1"
            )
        with pytest.raises(HTTPException) as unavailable:
            ranks.read(conn)
        assert unavailable.value.status_code == 503
    finally:
        conn.close()


def test_revision_collection_retries_bounded_unrelated_queue_write(isolated, monkeypatch):
    from backend.services import versus_personal_context as personal_context

    conn = db.get_db(readonly=True)
    try:
        before = personal_context.context(conn)
        original = personal_context._revision_vector
        calls = []

        def unrelated_write(connection, tables):
            value = original(connection, tables)
            calls.append(1)
            if len(calls) == 1:
                with sqlite3.connect(isolated[0]) as writer:
                    writer.execute(
                        "INSERT INTO background_jobs(job_id,job_type,entity_type,entity_id,status) VALUES('background-write','fixture','fixture','fixture','done')"
                    )
            return value

        monkeypatch.setattr(personal_context, "_revision_vector", unrelated_write)
        assert personal_context.context(conn) == before
        assert len(calls) == 2
    finally:
        conn.close()
