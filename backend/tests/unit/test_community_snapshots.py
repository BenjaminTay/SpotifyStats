"""Community read boundary, indexed projections and publication recovery."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Event

import pytest

from backend.domains.community import snapshot_store as store
from backend.domains.community.post_types import CommunityPost
from backend.services import community_snapshot_service as service

pytestmark = pytest.mark.unit


@pytest.fixture
def snapshot(monkeypatch, tmp_path):
    from backend.core import config

    monkeypatch.setattr(
        config, "SPOTIFY_STATS_COMMUNITY_CACHE_PATH", str(tmp_path / "community.db")
    )
    posts = [
        CommunityPost(
            str(i),
            "@a" if i % 2 == 0 else "@b",
            f"2024-01-{30 - i // 4:02d}T12:00:00",
            f"Song {i} 中文",
            "no1_announcement" if i % 3 == 0 else "debut",
            linked_entities=[
                {"type": "artist", "name": "Artist"},
                {"type": "track", "name": "Song", "id": 42},
            ],
            tags=["weekly", str(i % 2)],
            significance=i / 100,
        )
        for i in range(100)
    ]
    store.publish("key", "r1", posts, lambda: None)
    return posts


def test_indexed_filters_and_totals(snapshot):
    cases = [
        {},
        {"accounts": "@b"},
        {
            "tags": "1",
            "accounts": "@b",
            "date_from": "2024-01-12",
            "date_to": "2024-01-28",
            "search": "中文",
            "post_types": "debut",
        },
        {"highlights_only": True, "significance_min": 0.4},
        {"search": "%_"},
        {"search": "SONG"},
    ]
    with store.reader("key") as (conn, row):
        for filters in cases:
            base = [
                p
                for p in snapshot
                if (
                    not filters.get("accounts")
                    or p.account_handle in filters["accounts"].split(",")
                )
                and (not filters.get("tags") or bool(set(p.tags) & set(filters["tags"].split(","))))
                and (not filters.get("date_from") or p.posted_at >= filters["date_from"])
                and (not filters.get("date_to") or p.posted_at <= filters["date_to"])
                and (
                    not filters.get("post_types") or p.post_type in filters["post_types"].split(",")
                )
                and p.significance >= filters.get("significance_min", 0)
                and (not filters.get("search") or filters["search"].lower() in p.content.lower())
            ]
            selected = [
                p
                for p in base
                if not filters.get("highlights_only") or p.post_type == "no1_announcement"
            ]
            result = store.feed(conn, row["generation"], limit=7, offset=7, **filters)
            assert result["meta"]["total_all"] == len(base)
            assert result["meta"]["total"] == len(selected)
            assert [p["id"] for p in result["posts"]] == [p.id for p in selected[7:14]]


def test_trending_and_reply_projections(snapshot):
    with store.reader("key") as (conn, row):
        g = row["generation"]
        trend = store.trending(conn, g)
        assert trend["artists"] == [{"name": "Artist", "count": 100, "entity_id": None}]
        assert trend["tracks"] == [{"name": "Song", "count": 100, "entity_id": 42}]
        assert trend["latest_no1"]["post_id"] == "0"
        assert trend["latest_debut"]["post_id"] == "1"
        detail = store.detail(conn, g, "0")
        assert [p["id"] for p in detail["replies"]] == ["1"]
        assert store.detail(conn, g, "missing") is None


def test_atomic_failure_previous_and_pruning(snapshot):
    def fail():
        raise RuntimeError("source drift")

    with pytest.raises(RuntimeError):
        store.publish("key", "r2", snapshot, fail)
    with store.reader("key") as (_, row):
        assert row["revision"] == "r1"
    store.publish("key", "r2", snapshot, lambda: None)
    store.publish("key", "r3", snapshot, lambda: None)
    with store.reader("key") as (conn, row):
        assert row["revision"] == "r3"
        assert [
            r[0] for r in conn.execute("SELECT revision FROM generations ORDER BY generation")
        ] == ["r2", "r3"]
    with store.reader("other") as (_, row):
        assert row is None


def test_public_reader_zero_writes_and_page_enrichment(snapshot, monkeypatch):
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )

    monkeypatch.setattr(service, "context", lambda *a: ({}, "key", "r2"))
    enriched = []

    def enrich(conn, posts):
        enriched.extend(posts)
        return posts

    monkeypatch.setattr(service, "enrich", enrich)
    writes = []
    original = store.connect

    def connect(**kwargs):
        conn = original(**kwargs)

        def authorizer(action, *args):
            if action in {23, 18, 9, 2, 1}:
                writes.append(action)
                return 1
            return 0

        conn.set_authorizer(authorizer)
        return conn

    monkeypatch.setattr(store, "connect", connect)
    token = set_public_readonly_db_guard(True)
    try:
        result = service.read(None, "feed", {}, limit=50, offset=50)
        assert len(enriched) == 50
        assert result["snapshot"]["freshness"] == "last_known_good"
        enriched.clear()
        service.read(None, "trending", {})
        assert enriched == []
        service.read(None, "post", {}, post_id="0")
        assert len(enriched) == 2
        with pytest.raises(PermissionError):
            service.ensure(None)
        assert service.enqueue_defaults("public") == []
        assert writes == []
    finally:
        reset_public_readonly_db_guard(token)


def test_missing_does_not_create_or_build(monkeypatch, tmp_path):
    from fastapi import HTTPException

    from backend.core import config

    monkeypatch.setattr(
        config, "SPOTIFY_STATS_COMMUNITY_CACHE_PATH", str(tmp_path / "missing" / "community.db")
    )
    monkeypatch.setattr(service, "context", lambda *a: pytest.fail("missing must not hash source"))
    with pytest.raises(HTTPException) as exc:
        service.read(None, "feed", {}, limit=50, offset=0)
    assert exc.value.status_code == 503
    assert not (tmp_path / "missing").exists()


def test_four_ensure_calls_build_once_and_public_reads_lkg(snapshot, monkeypatch):
    from backend.domains.community import feed_generator

    class Conn:
        def close(self):
            pass

    monkeypatch.setattr(service, "get_db", lambda **k: Conn())
    monkeypatch.setattr(service, "context", lambda *a: ({}, "key", "r2"))
    monkeypatch.setattr(service, "configured_billboard_filters", lambda c: {})
    entered, release = Event(), Event()
    calls = []

    def builder(*a, **k):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return snapshot

    monkeypatch.setattr(feed_generator, "build_publication_posts", builder)
    with ThreadPoolExecutor(4) as pool:
        jobs = [pool.submit(service.ensure, Conn()) for _ in range(4)]
        assert entered.wait(5)
        with store.reader("key") as (_, row):
            assert row["revision"] == "r1"
        release.set()
        results = [j.result() for j in jobs]
    assert len(calls) == 1
    assert sum(r["published"] for r in results) == 1


def test_failed_status_keeps_core(snapshot, monkeypatch):
    store.mark_failed("key", "r2")
    monkeypatch.setattr(service, "context", lambda *a: ({}, "key", "r2"))
    result = service.read(None, "trending", {})
    assert result["snapshot"]["build_status"] == "failed"
    assert result["artists"][0]["count"] == 100
    with store.reader("key") as (_, row):
        assert row["revision"] == "r1"


def test_published_content_is_stable(snapshot):
    assert store.publish("key", "r1", [], lambda: None) is False
    with store.reader("key") as (conn, row):
        posts = store.feed(conn, row["generation"], limit=50, offset=0)["posts"]
    for actual, expected in zip(posts, snapshot):
        facts = asdict(expected)
        facts.pop("metrics")
        facts.pop("images")
        assert json.loads(json.dumps(actual)) == facts


@pytest.mark.parametrize("dependency", ["source", "identity", "collection", "config"])
def test_drift_rejects_publication_and_next_ensure_recovers(snapshot, monkeypatch, dependency):
    from backend.domains.community import feed_generator

    state = {"revision": "r2", "settings": {}}

    class Conn:
        def close(self):
            pass

    monkeypatch.setattr(service, "get_db", lambda **k: Conn())
    monkeypatch.setattr(service, "context", lambda *a: ({}, "key", state["revision"]))
    monkeypatch.setattr(service, "configured_billboard_filters", lambda c: dict(state["settings"]))

    def builder(*a, **k):
        if dependency == "config":
            state["settings"] = {"min_ms": 45000}
        else:
            state["revision"] = "r3"
        return snapshot

    monkeypatch.setattr(feed_generator, "build_publication_posts", builder)
    with pytest.raises(ValueError, match="changed"):
        service.ensure(Conn())
    with store.reader("key") as (_, row):
        assert row["revision"] == "r1"
    monkeypatch.setattr(feed_generator, "build_publication_posts", lambda *a, **k: snapshot)
    assert service.ensure(Conn())["published"]


def test_core_sql_failure_rolls_back(snapshot, monkeypatch):
    original = store.connect

    def connect(**kwargs):
        conn = original(**kwargs)
        if kwargs.get("write"):
            conn.execute(
                "CREATE TEMP TRIGGER fail_core BEFORE INSERT ON posts WHEN NEW.ordinal=2 BEGIN SELECT RAISE(ABORT,'core failure'); END"
            )
        return conn

    monkeypatch.setattr(store, "connect", connect)
    with pytest.raises(store.sqlite3.IntegrityError):
        store.publish("key", "r2", snapshot, lambda: None)
    with store.reader("key") as (_, row):
        assert row["revision"] == "r1"


def test_display_failure_does_not_destroy_publication(snapshot, monkeypatch):
    monkeypatch.setattr(service, "context", lambda *a: ({}, "key", "r1"))
    monkeypatch.setattr(
        service, "enrich", lambda *a: (_ for _ in ()).throw(ValueError("cover failure"))
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        service.read(None, "feed", {}, limit=50, offset=0)
    assert service.read(None, "trending", {})["artists"][0]["count"] == 100
    with store.reader("key") as (_, row):
        assert row["revision"] == "r1"


def test_exact_revision_reacts_to_facts_but_not_cover(monkeypatch, tmp_path):
    from backend.core import db
    from backend.domains.community.snapshot_revision import source_revision

    target = tmp_path / "source.db"
    with db.get_db(readonly=True) as source, store.sqlite3.connect(target) as destination:
        source.backup(destination)
        destination.execute("PRAGMA journal_mode=DELETE")
    source.close()
    destination.close()
    with store.sqlite3.connect(target) as conn:
        initial = source_revision(conn)
        row = conn.execute("SELECT spotify_album_id FROM spotify_album_meta LIMIT 1").fetchone()
        conn.execute(
            "UPDATE spotify_album_meta SET image_url='display-only' WHERE spotify_album_id=?",
            (row[0],),
        )
        conn.commit()
        assert source_revision(conn) == initial
        conn.execute(
            "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT min(play_id) FROM plays)"
        )
        conn.commit()
        assert source_revision(conn) != initial
        second = source_revision(conn)
        conn.execute("UPDATE saved_tracks SET track_name=track_name||' changed'")
        conn.commit()
        if conn.execute("SELECT count(*) FROM saved_tracks").fetchone()[0]:
            assert source_revision(conn) != second


def test_late_week_boundary_never_posts_before_completion():
    from backend.domains.community.feed_helpers import _week_end_date

    assert _week_end_date("2026-08-14", week_start_hour=23) == "2026-08-21T23:00:00"
    assert _week_end_date("2026-08-14", week_start_hour=0) == "2026-08-21T12:00:00"


def test_failed_job_can_requeue_and_handler_uses_latest_defaults(snapshot, monkeypatch):
    from backend.core.job_queue import Job, JobQueue

    class Conn:
        def close(self):
            pass

    monkeypatch.setattr(service, "get_db", lambda **k: Conn())
    monkeypatch.setattr(service, "queue_targets_connection", lambda *a: True)
    monkeypatch.setattr(service, "context", lambda *a: ({"min_ms": 30000}, "key", "r2"))
    queue = JobQueue(max_workers=0)
    queue._db_path = str(store.path())
    with store.sqlite3.connect(queue._db_path) as conn:
        conn.execute("CREATE TABLE background_jobs(job_type,entity_type,entity_id,status)")
        conn.execute(
            "INSERT INTO background_jobs VALUES(?,?,?,?)",
            (service.JOB_TYPE, "community", "key", "failed"),
        )
    jobs = []
    monkeypatch.setattr(queue, "enqueue", lambda job: jobs.append(job) or job.job_id)
    assert len(service.enqueue_defaults("retry", queue=queue)) == 1
    assert jobs[0].payload["default"] is True
    monkeypatch.setattr(service, "configured_billboard_filters", lambda c: {"min_ms": 45000})
    calls = []
    monkeypatch.setattr(service, "ensure", lambda conn, params: calls.append(params))
    service.handle_rebuild(
        Job.create(
            service.JOB_TYPE, "community", "key", default=True, params_json='{"min_ms": 30000}'
        )
    )
    assert calls == [{"min_ms": 45000}]


@pytest.mark.parametrize("path", ["/api/settings", "/api/spotify/auth/sync"])
def test_committed_mutations_schedule_community_independently(monkeypatch, path):
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    from backend.main import public_readonly_surface_middleware
    from backend.services import analysis_snapshot_service

    calls = []
    monkeypatch.setattr(
        analysis_snapshot_service,
        "enqueue_defaults",
        lambda *a: (_ for _ in ()).throw(RuntimeError("analysis failed")),
    )
    monkeypatch.setattr(service, "enqueue_defaults", lambda reason: calls.append(reason))

    async def committed(request):
        return Response(status_code=200)

    request = Request({"type": "http", "method": "POST", "path": path, "headers": []})
    result = asyncio.run(public_readonly_surface_middleware(request, committed))
    assert result.status_code == 200
    assert calls == ["committed " + path]
