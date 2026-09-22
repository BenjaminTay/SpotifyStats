from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.access_surface import PUBLIC_SAFE_GET_TEMPLATES, SURFACE_HEADER
from backend.core.cache_manager import invalidate_all
from backend.core.job_queue import JobQueue
from backend.domains.billboard import persistent_cache as cache
from backend.main import app
from backend.services import billboard_snapshot_service as maintenance
from backend.services import home_service as home

pytestmark = pytest.mark.contract
PUBLIC = {SURFACE_HEADER: "public-readonly"}


@pytest.fixture
def isolated(use_seed_db, tmp_path, monkeypatch):
    from backend.core.migrations import run_migrations
    from backend.domains.yearly_review import artifact_cache

    monkeypatch.setattr(cache, "BILLBOARD_CACHE_PATH", str(tmp_path / "billboard.db"))
    monkeypatch.setattr(home, "DB_PATH", use_seed_db)
    monkeypatch.setattr(home, "_HOME_SNAPSHOT_DIR", tmp_path / "home")
    monkeypatch.setattr(artifact_cache, "YEARLY_REVIEW_CACHE_PATH", str(tmp_path / "yearly.db"))
    run_migrations()
    invalidate_all()
    # No lifespan: no startup queue, recovery or unrelated background work.
    client = TestClient(app)
    yield client, Path(use_seed_db), tmp_path
    client.close()
    invalidate_all()


def _state(db_path, files):
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        tables = "\n".join(conn.iterdump())
    disk = {
        str(p.relative_to(files)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in files.rglob("*")
        if p.is_file()
        and not p.name.endswith("-shm")
        # SQLite may leave an empty WAL sidecar after a read-only connection is
        # opened on Linux. It contains no committed frames, so it is not a
        # published-state mutation. Non-empty WAL files remain byte-exact here.
        and not (p.name.endswith("-wal") and p.stat().st_size == 0)
    }
    return tables, disk


def _forbid(*_args, **_kwargs):
    pytest.fail("public GET entered an expensive builder, writer or JobQueue")


def _sentinels(monkeypatch):
    from backend.api.billboard import release_cycle
    from backend.domains.billboard import (
        chart_compute,
        chart_staged_api,
        chart_year_end_cache,
        detail_views,
    )

    for name in (
        "_compute_weekly_data_cached",
        "_compute_records_cached",
        "_compute_power_scores_cached",
        "_compute_summaries_cached",
    ):
        monkeypatch.setattr(chart_staged_api, name, _forbid)
    monkeypatch.setattr(chart_compute, "_compute_billboard_data_cached", _forbid)
    monkeypatch.setattr(chart_year_end_cache, "_compute_year_end_cached", _forbid)
    for name in (
        "_track_detail_cached",
        "_artist_detail_cached",
        "_album_detail_cached",
        "_album_project_detail_cached",
        "build_track_detail_summary",
        "build_album_detail_summary",
        "build_artist_detail_summary",
    ):
        monkeypatch.setattr(detail_views, name, _forbid)
    monkeypatch.setattr(release_cycle, "load_billboard_raw", _forbid)
    monkeypatch.setattr(release_cycle, "load_billboard_raw_for_artists", _forbid)
    monkeypatch.setattr(home, "build_home_overview", _forbid)
    monkeypatch.setattr(home, "_start_snapshot_rebuild", _forbid)
    monkeypatch.setattr(home, "_write_snapshot", _forbid)
    monkeypatch.setattr(cache, "store_persisted_snapshot", _forbid)
    monkeypatch.setattr(JobQueue, "enqueue", _forbid)
    monkeypatch.setattr(JobQueue, "enqueue_if_not_pending", _forbid)


@pytest.mark.parametrize("key_error", [False, True])
def test_all_public_billboard_gets_fail_closed_without_publications(
    isolated, monkeypatch, key_error
):
    client, db_path, files = isolated
    if key_error:

        def broken(*_args):
            raise ValueError("source revision unavailable")

        monkeypatch.setattr(cache, "build_cache_context", broken)
    _sentinels(monkeypatch)
    before = _state(db_path, files)
    for template in sorted(PUBLIC_SAFE_GET_TEMPLATES):
        if not template.startswith("/api/billboard/"):
            continue
        path = re.sub(r"\{[^{}]+\}", "1", template)
        response = client.get(path, headers=PUBLIC)
        assert response.status_code == 503, (path, response.text)
        assert response.json()["detail"]["error"] == "snapshot_unavailable"
    assert _state(db_path, files) == before


def test_private_maintenance_publishes_records_and_public_exact_lkg_are_read_only(
    isolated, monkeypatch
):
    client, db_path, files = isolated
    result = maintenance.rebuild_default_billboard_snapshots()
    assert "records" in result["families"]
    assert maintenance.billboard_default_snapshots_ready()
    filters = maintenance.configured_billboard_filters()
    old = cache.build_cache_context("records", filters)
    payload = cache.load_persisted_snapshot(old, allow_lkg=False)
    assert payload is not None
    _sentinels(monkeypatch)
    before = _state(db_path, files)
    exact = client.get("/api/billboard/records", headers=PUBLIC)
    assert exact.status_code == 200, exact.text
    assert exact.json()["records"] == payload["records"]
    assert exact.json()["snapshot"]["freshness"] == "current"
    build_key = cache.build_cache_context

    def stale_key(family, params):
        return {
            **build_key(family, params),
            "cache_key": "new-key",
            "source_revision": "new-source",
        }

    monkeypatch.setattr(cache, "build_cache_context", stale_key)
    stale = client.get("/api/billboard/records", headers=PUBLIC)
    assert stale.status_code == 200
    assert stale.json()["records"] == payload["records"]
    assert stale.json()["snapshot"] == {
        "status": "warming",
        "freshness": "last_known_good",
        "source_revision": old["source_revision"],
        "target_revision": "new-source",
    }
    incompatible = client.get("/api/billboard/records?bb_top_n=31", headers=PUBLIC)
    assert incompatible.status_code == 503
    assert _state(db_path, files) == before


def test_home_publication_contract_and_read_only_transition(isolated, monkeypatch):
    client, db_path, files = isolated
    missing = client.get("/api/home/overview", headers=PUBLIC)
    assert missing.status_code == 503
    # Private-admin publishes using the existing controlled default warmup.
    published = home.prewarm_default_home_overview()
    assert list((files / "home").glob("*.json"))
    _sentinels(monkeypatch)
    before = _state(db_path, files)
    exact = client.get("/api/home/overview", headers=PUBLIC)
    assert exact.status_code == 200, exact.text
    assert exact.json()["archive"] == published.archive.model_dump()
    assert exact.json()["snapshot"]["freshness"] == "current"
    original = home.database_revision
    monkeypatch.setattr(home, "database_revision", lambda: original() + "-new")
    stale = client.get("/api/home/overview", headers=PUBLIC)
    assert stale.status_code == 200, stale.text
    assert stale.json()["cache_state"] == "warming"
    assert stale.json()["snapshot"]["freshness"] == "last_known_good"
    assert (
        stale.json()["snapshot"]["source_revision"] != stale.json()["snapshot"]["target_revision"]
    )
    assert stale.json()["archive"] == exact.json()["archive"]
    assert client.get("/api/home/overview?bb_top_n=31", headers=PUBLIC).status_code == 503
    assert _state(db_path, files) == before


def test_album_name_and_project_public_private_contract(isolated):
    client, _db_path, _files = isolated
    maintenance.rebuild_default_billboard_snapshots()
    params = {"artist_name": "Alpha", "view": "summary"}
    named = client.get("/api/billboard/album/Alpha%20Debut", params=params)
    assert named.status_code == 200, named.text
    project_id = named.json()["album_project_id"]
    for path, params in [
        (f"/api/billboard/album-project/{project_id}", {"view": "summary"}),
        (f"/api/billboard/album-project/{project_id}", {"view": "project"}),
        (f"/api/music/album-projects/{project_id}/stats", {"include_rank_context": False}),
        (f"/api/music/album-projects/{project_id}/rankings", {}),
        (f"/api/music/album-projects/{project_id}/plays", {}),
        (f"/api/music/album-projects/{project_id}/play-dates", {}),
    ]:
        private = client.get(path, params=params)
        public = client.get(path, params=params, headers=PUBLIC)
        assert private.status_code == public.status_code == 200, (path, private.text, public.text)
        assert private.json() == public.json()
