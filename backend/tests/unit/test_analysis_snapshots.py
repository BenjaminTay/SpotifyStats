from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from backend.core import config, db
from backend.core.access_surface import SURFACE_HEADER
from backend.core.cache_manager import invalidate_all
from backend.main import app
from backend.services import analysis_snapshot_service as service
from backend.services import analysis_snapshot_store as store

pytestmark = pytest.mark.unit


@pytest.fixture
def isolated(isolated_test_database, monkeypatch, tmp_path):
    use_seed_db = str(tmp_path / "main.db")
    with sqlite3.connect(isolated_test_database) as src, sqlite3.connect(use_seed_db) as dst:
        src.backup(dst)
    monkeypatch.setattr(db, "DB_PATH", use_seed_db)
    from backend.core.migrations import run_migrations

    run_migrations()
    monkeypatch.setattr(config, "SPOTIFY_STATS_ANALYSIS_CACHE_PATH", str(tmp_path / "analysis.db"))
    invalidate_all()
    yield Path(use_seed_db), tmp_path
    invalidate_all()


def context(family):
    conn = db.get_db(readonly=True)
    try:
        return service.request_context(conn, family, {})
    finally:
        conn.close()


def build(family):
    params, key, revision, version = context(family)
    service.rebuild(family, json.dumps(params, sort_keys=True), key, revision)
    return params, key, revision, version


def forbid(*args, **kwargs):
    pytest.fail("GET crossed publication boundary")


def test_store_integrity_retention_and_rollback(isolated, monkeypatch):
    for i in range(4):
        store.publish("analysis_stats", "key", str(i), "v", {"value": i})
    with sqlite3.connect(store.path()) as conn:
        assert conn.execute("select count(*) from analysis_snapshots").fetchone()[0] == 2
    assert store.read("analysis_stats", "key", "3", "v")[0] == {"value": 3}
    assert store.read("analysis_stats", "other", "3", "v") is None
    with pytest.raises(ValueError):
        store.publish("analysis_stats", "key", "4", "v", {"value": float("nan")})
    assert store.read("analysis_stats", "key", "3", "v")[0] == {"value": 3}
    with sqlite3.connect(store.path()) as conn:
        conn.execute("update analysis_snapshots set sha256='bad' where source_revision='3'")
    assert store.read("analysis_stats", "key", "3", "v")[0] == {"value": 2}
    for i in range(20):
        store.publish("analysis_records", str(i), "r", "v", {})
    with sqlite3.connect(store.path()) as conn:
        assert (
            conn.execute("select count(distinct request_key) from analysis_snapshots").fetchone()[0]
            == store.MAX_KEYS
        )


@pytest.mark.contract
@pytest.mark.parametrize("family", service.VERSIONS)
def test_public_states_no_builder_or_writes(isolated, monkeypatch, family):
    from backend.core.job_queue import JobQueue
    from backend.domains.billboard import persistent_cache
    from backend.services import analysis_records_service, analysis_stats_service

    params, key, revision, version = build(family)
    monkeypatch.setattr(analysis_stats_service, "_build_analysis_stats", forbid)
    monkeypatch.setattr(analysis_records_service, "_get_analysis_records_uncached", forbid)
    monkeypatch.setattr(store, "publish", forbid)
    monkeypatch.setattr(JobQueue, "enqueue_if_not_pending", forbid)
    client = TestClient(app)

    def state():
        with sqlite3.connect(isolated[0]) as c:
            logical = "\n".join(c.iterdump())
        files = {
            str(p): (p.read_bytes(), p.stat().st_mtime_ns)
            for root in {isolated[1], Path(persistent_cache.BILLBOARD_CACHE_PATH).parent}
            for p in root.rglob("*")
            if p.is_file() and not p.name.endswith("-shm")
        }
        return logical, files

    before = state()
    url = "/api/analysis/" + family.removeprefix("analysis_")
    response = client.get(url, params=params, headers={SURFACE_HEADER: "public-readonly"})
    assert response.status_code == 200, response.text
    assert response.json()["snapshot"]["freshness"] == "current"
    assert state() == before
    for period in ("", "unknown-period"):
        fallback = client.get(
            url,
            params={**params, "period": period},
            headers={SURFACE_HEADER: "public-readonly"},
        )
        assert fallback.status_code == 200, fallback.text
        assert fallback.json() == response.json()
        assert state() == before
    with sqlite3.connect(isolated[0]) as c:
        c.execute("update playback_import_state set playback_revision=playback_revision+1")
    before = state()
    assert (
        client.get(url, params=params, headers={SURFACE_HEADER: "public-readonly"}).json()[
            "snapshot"
        ]["freshness"]
        == "last_known_good"
    )
    for change in (
        {"min_ms": 12345},
        {"period": "custom", "start_date": "1900-01-01", "end_date": "1900-01-02"},
    ):
        response = client.get(
            url, params={**params, **change}, headers={SURFACE_HEADER: "public-readonly"}
        )
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "snapshot_unavailable"
    assert state() == before
    store.path().rename(store.path().with_suffix(".saved"))
    before = state()
    assert (
        client.get(url, params=params, headers={SURFACE_HEADER: "public-readonly"}).status_code
        == 503
    )
    assert state() == before
    store.path().with_suffix(".saved").rename(store.path())
    before = state()
    monkeypatch.setattr(
        service, "request_context", lambda *a, **k: (_ for _ in ()).throw(ValueError("key"))
    )
    assert (
        client.get(url, params=params, headers={SURFACE_HEADER: "public-readonly"}).status_code
        == 503
    )
    assert state() == before


@pytest.mark.parametrize("family", service.VERSIONS)
def test_singleflight_semantics_fence_and_failure(isolated, monkeypatch, family):
    from backend.services import analysis_records_service as records
    from backend.services import analysis_stats_service as stats

    module, name = (
        (stats, "_build_analysis_stats")
        if family == "analysis_stats"
        else (records, "_get_analysis_records_uncached")
    )
    original = getattr(module, name)
    params, key, revision, version = context(family)
    calls = []

    def counted(conn, **kwargs):
        calls.append(1)
        return original(conn, **kwargs)

    monkeypatch.setattr(module, name, counted)
    barrier = Barrier(4)

    def worker(_):
        barrier.wait()
        return service.rebuild(
            family, json.dumps(params, sort_keys=bool(_ % 2)) if _ else "{}", key, revision
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(worker, range(4)))
    assert len(calls) == 1
    conn = db.get_db(readonly=True)
    try:
        expected = original(conn, **params)
    finally:
        conn.close()
    actual = store.read(family, key, revision, version)[0]
    # generated_at is the original builder's observation clock, not a statistic.
    if family == "analysis_records":
        expected["meta"]["generated_at"] = actual["meta"]["generated_at"]
    assert actual == expected
    with sqlite3.connect(isolated[0]) as conn:
        conn.execute("update playback_import_state set playback_revision=playback_revision+1")
    _, _, next_revision, _ = context(family)

    def drifting(conn, **kwargs):
        payload = original(conn, **kwargs)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute("update playback_import_state set playback_revision=playback_revision+1")
        return payload

    monkeypatch.setattr(module, name, drifting)
    with pytest.raises(ValueError, match="source fence"):
        service.rebuild(family, json.dumps(params, sort_keys=True), key, next_revision)
    assert store.read(family, key, next_revision, version)[1]["source_revision"] == revision


def test_default_enqueue_exact_and_semantic_invalidation(isolated):
    class Queue:
        database_path = str(isolated[0])

        def __init__(self):
            self.jobs = []

        def enqueue_if_not_pending(self, job):
            if any(j.entity_id == job.entity_id for j in self.jobs):
                return False
            self.jobs.append(job)
            return True

    q = Queue()
    for family in service.VERSIONS:
        build(family)
    assert service.enqueue_defaults("startup", queue=q) == []
    from backend.domains.settings.repository import SettingsRepository

    with sqlite3.connect(isolated[0]) as conn:
        SettingsRepository(conn).update("theme", "dark")
    assert service.enqueue_defaults("unrelated setting", queue=q) == []
    old_keys = {f: context(f)[1] for f in service.VERSIONS}
    with sqlite3.connect(isolated[0]) as conn:
        SettingsRepository(conn).update("min_ms", 45000)
    assert all(context(f)[1] != old_keys[f] for f in service.VERSIONS)
    with sqlite3.connect(isolated[0]) as conn:
        SettingsRepository(conn).update("min_ms", 30000)
    before = {f: context(f)[2] for f in service.VERSIONS}
    with sqlite3.connect(isolated[0]) as c:
        c.execute("update spotify_artist_meta set image_url='different-cover'")
    assert before == {f: context(f)[2] for f in service.VERSIONS}
    with sqlite3.connect(isolated[0]) as c:
        c.execute(
            "update artist_identity_groups set display_name='Display only', revision=revision+1"
        )
        c.execute(
            "update artist_identity_state set current_revision=current_revision+1, active_aggregate_revision=active_aggregate_revision+1"
        )
    assert before == {f: context(f)[2] for f in service.VERSIONS}
    with sqlite3.connect(isolated[0]) as c:
        c.execute("update playback_import_state set playback_revision=playback_revision+1")
    assert len(service.enqueue_defaults("import", queue=q)) == 2
    assert service.enqueue_defaults("again", queue=q) == []


def test_key_canonical_defaults_and_variants(isolated):
    c = db.get_db(readonly=True)
    try:
        for family in service.VERSIONS:
            params, key, _, _ = context(family)
            assert service.request_context(c, family, params)[1] == key
            for name, value in [
                ("min_ms", 1),
                ("dynamic_threshold", False),
                ("merge_enabled", False),
            ]:
                assert service.request_context(c, family, {**params, name: value})[1] != key
            if family == "analysis_records":
                for name, value in [("merge_level", 3), ("include_compilations", True)]:
                    assert service.request_context(c, family, {**params, name: value})[1] != key
    finally:
        c.close()


@pytest.mark.parametrize("family", service.VERSIONS)
@pytest.mark.parametrize(
    "overrides",
    [
        {"period": "last_4_weeks"},
        {"period": "custom", "start_date": "2025-12-31", "end_date": "2026-01-02"},
        {"period": "custom", "start_date": "1900-01-01", "end_date": "1900-01-02"},
        {"merge_level": 3},
        {"include_compilations": True},
        {"dynamic_threshold": False},
        {"merge_enabled": False},
    ],
)
def test_full_payload_roundtrip_all_scopes(isolated, family, overrides):
    from backend.services.analysis_records_service import _get_analysis_records_uncached
    from backend.services.analysis_stats_service import _build_analysis_stats

    if family == "analysis_stats" and (
        "merge_level" in overrides or "include_compilations" in overrides
    ):
        return
    conn = db.get_db(readonly=True)
    try:
        params = service.default_params(conn, family)
        params.update(overrides)
        builder = (
            _build_analysis_stats if family == "analysis_stats" else _get_analysis_records_uncached
        )
        expected = builder(conn, **params)
    finally:
        conn.close()
    # Codec comparisons retain every field, including timestamp, identities,
    # nulls, all section ordering and dual-track facts. Non-lifetime scope is
    # not automatically maintained or advertised as available by GET.
    key = store.digest(params)
    store.publish(family, key, "source", "test", expected)
    assert store.read(family, key, "source", "test")[0] == expected


def test_fact_edits_and_taste_only_invalidation(isolated):
    def revisions():
        return {family: context(family)[2] for family in service.VERSIONS}

    before = revisions()
    with sqlite3.connect(isolated[0]) as conn:
        conn.execute(
            "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
        )
    assert all(revisions()[family] != before[family] for family in before)
    before = revisions()
    with sqlite3.connect(isolated[0]) as conn:
        name = conn.execute(
            "SELECT artist_name FROM artists ORDER BY artist_id LIMIT 1"
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO artist_genre_sources
            (artist_name,source,source_key,normalized_genres_json,primary_genre,status)
            VALUES(?, 'manual', 'stage3a-test', '["pop"]', 'pop', 'approved')""",
            (name,),
        )
    after = revisions()
    assert after["analysis_stats"] != before["analysis_stats"]
    assert after["analysis_records"] == before["analysis_records"]
    before = after
    with sqlite3.connect(isolated[0]) as conn:
        conn.execute(
            "UPDATE artist_genre_sources SET evidence_summary='note only' WHERE source_key='stage3a-test'"
        )
    assert revisions() == before


@pytest.mark.parametrize("family", service.VERSIONS)
def test_boundary_events_and_fanout_payload_roundtrip(isolated, family):
    from datetime import datetime

    from backend.services.analysis_records_service import _get_analysis_records_uncached
    from backend.services.analysis_stats_service import _build_analysis_stats

    with sqlite3.connect(isolated[0]) as conn:
        conn.row_factory = sqlite3.Row
        source = dict(
            conn.execute(
                "SELECT * FROM plays WHERE track_id IS NOT NULL ORDER BY play_id LIMIT 1"
            ).fetchone()
        )
        source.pop("play_id")
        for ts, ms in [
            ("2025-12-31T23:59:50Z", 20000),
            ("2026-01-01T00:00:10Z", 20000),
            ("2026-01-01T00:01:30Z", 80000),
            ("2026-01-04T23:59:50Z", 20000),
            ("2026-01-05T00:00:10Z", 20000),
        ]:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            row = {
                **source,
                "ts": ts,
                "ms_played": ms,
                "ts_year": dt.year,
                "ts_month": dt.month,
                "ts_week": dt.isocalendar()[1],
                "ts_dow": dt.weekday(),
                "ts_hour": dt.hour,
                "ts_date": dt.date().isoformat(),
                "source_fingerprint": None,
            }
            conn.execute(
                "INSERT INTO plays ("
                + ",".join(row)
                + ") VALUES ("
                + ",".join("?" for _ in row)
                + ")",
                list(row.values()),
            )
        artists = [
            r[0] for r in conn.execute("SELECT artist_id FROM artists ORDER BY artist_id LIMIT 2")
        ]
        for artist in artists:
            conn.execute(
                "INSERT OR IGNORE INTO track_artists(track_id,artist_id,role) VALUES(?,?,'primary')",
                (source["track_id"], artist),
            )
    invalidate_all()
    conn = db.get_db(readonly=True)
    try:
        params = service.default_params(conn, family)
        params.update(period="custom", start_date="2026-01-01", end_date="2026-01-05")
        builder = (
            _build_analysis_stats if family == "analysis_stats" else _get_analysis_records_uncached
        )
        expected = builder(conn, **params)
    finally:
        conn.close()
    store.publish(family, "boundary", "facts", "test", expected)
    assert store.read(family, "boundary", "facts", "test")[0] == expected


def test_concurrent_maintenance_has_only_one_pending_job_per_key(isolated):
    from backend.core.job_queue import JobQueue

    queue = JobQueue()
    queue.prepare(str(isolated[0]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: service.enqueue_defaults(str(i), queue=queue), range(4)))
    with sqlite3.connect(isolated[0]) as conn:
        counts = conn.execute(
            "SELECT entity_type,entity_id,COUNT(*) FROM background_jobs WHERE job_type=? AND status IN ('pending','running') GROUP BY entity_type,entity_id",
            (service.JOB_TYPE,),
        ).fetchall()
    assert len(counts) == 2
    assert all(row[2] == 1 for row in counts)


def test_revision_collection_retries_concurrent_commit(isolated, monkeypatch):
    from backend.services import analysis_snapshot_revision as revision

    original = revision._table_digest
    changed = []

    def commit_once(conn, table):
        if not changed:
            changed.append(True)
            with sqlite3.connect(isolated[0]) as writer:
                writer.execute(
                    "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
                )
        return original(conn, table)

    monkeypatch.setattr(revision, "_table_digest", commit_once)
    first = context("analysis_stats")[2]
    assert changed
    assert context("analysis_stats")[2] == first
