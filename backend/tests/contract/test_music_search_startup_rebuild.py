from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.core import db as db_mod
from backend.core import job_queue as job_queue_module
from backend.core.job_queue import JobQueue
from backend.core.migrations import run_migrations
from backend.main import app
from backend.services.music_search_maintenance_service import (
    rebuild_current_music_search_derived_data,
)

pytestmark = pytest.mark.contract

SEARCH_JOB_TYPE = "music_search_snapshot_rebuild"


def _prepare_database() -> None:
    db_mod.init_db()
    run_migrations()
    with sqlite3.connect(db_mod.DB_PATH) as conn:
        conn.execute("DELETE FROM background_jobs WHERE job_type=?", (SEARCH_JOB_TYPE,))


def _search_jobs() -> list[sqlite3.Row]:
    with sqlite3.connect(db_mod.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """SELECT job_id, status, entity_id
               FROM background_jobs WHERE job_type=? ORDER BY created_at""",
            (SEARCH_JOB_TYPE,),
        ).fetchall()


def _install_non_processing_queue(monkeypatch) -> JobQueue:
    queue = JobQueue(max_workers=0)
    monkeypatch.setattr(job_queue_module, "_queue", queue)
    return queue


def _run_startup() -> None:
    with TestClient(app):
        pass


def test_disabled_search_startup_rebuild_enqueues_no_search_job(
    use_seed_db,
    monkeypatch,
) -> None:
    _prepare_database()
    _install_non_processing_queue(monkeypatch)
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "0")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    _run_startup()

    assert _search_jobs() == []


def test_enabled_search_startup_rebuild_enqueues_at_most_one_missing_job(
    use_seed_db,
    monkeypatch,
) -> None:
    _prepare_database()
    _install_non_processing_queue(monkeypatch)
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    _run_startup()
    _run_startup()

    jobs = _search_jobs()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "pending"


def test_enabled_search_startup_rebuild_skips_when_six_variants_are_ready(
    use_seed_db,
    monkeypatch,
) -> None:
    _prepare_database()
    with db_mod.get_db(readonly=False) as conn:
        report = rebuild_current_music_search_derived_data(conn, rebuild_documents=True)
    assert report["snapshot_set"]["ready_count"] == 6
    assert report["snapshot_set"]["failed_count"] == 0

    _install_non_processing_queue(monkeypatch)
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    _run_startup()
    _run_startup()

    assert _search_jobs() == []
