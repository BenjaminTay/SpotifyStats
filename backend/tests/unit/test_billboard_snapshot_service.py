from __future__ import annotations

import sqlite3

import pytest

from backend.core.job_queue import JobQueue
from backend.services import billboard_snapshot_service as snapshot_service

pytestmark = pytest.mark.unit


def _init_jobs_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE background_jobs(
               job_id TEXT PRIMARY KEY,
               job_type TEXT NOT NULL,
               entity_type TEXT,
               entity_id TEXT,
               payload_json TEXT,
               status TEXT NOT NULL DEFAULT 'pending',
               created_at TEXT,
               updated_at TEXT,
               attempts INTEGER DEFAULT 0,
               error TEXT
           )"""
    )
    conn.commit()
    conn.close()


def test_enqueue_snapshot_rebuild_is_deduplicated(tmp_path):
    db_path = tmp_path / "spotify_stats.db"
    _init_jobs_db(db_path)
    queue = JobQueue(max_workers=1)
    queue.prepare(str(db_path))

    first = snapshot_service.enqueue_billboard_snapshot_rebuild(
        "import complete",
        queue=queue,
    )
    second = snapshot_service.enqueue_billboard_snapshot_rebuild(
        "settings changed",
        queue=queue,
    )

    assert first is not None
    assert second is None
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT job_type, entity_id, status FROM background_jobs WHERE job_id=?",
        (first,),
    ).fetchone()
    conn.close()
    assert row == ("billboard_snapshot_rebuild", "default", "pending")


def test_startup_snapshot_rebuild_skips_when_all_default_rows_are_current(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "spotify_stats.db"
    _init_jobs_db(db_path)
    queue = JobQueue(max_workers=1)
    queue.prepare(str(db_path))
    filters = {
        "min_ms": 30_000,
        "music_only": True,
        "merge_enabled": True,
        "bb_top_n": 30,
        "bb_album_top_n": 20,
        "bb_artist_top_n": 20,
        "bb_week_start_dow": 4,
        "bb_week_start_hour": 0,
        "year_start": None,
        "year_end": None,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 5,
        "merge_level": 2,
        "include_compilations": False,
    }
    monkeypatch.setattr(snapshot_service, "configured_billboard_filters", lambda: filters)
    monkeypatch.setattr(
        "backend.domains.billboard.chart_load_rank.billboard_revision_state",
        lambda: (1, 1, 1, 1, "ready:ready"),
    )

    def fake_context(family, params):
        return {
            "cache_key": f"{family}:{params.get('year')}",
            "request_key": family,
            "family": family,
            "source_revision": "current",
            "builder_version": "test",
            "params": params,
        }

    def fake_load(context, *, allow_lkg=True, cache_path=None):
        if context["family"] == "year_end" and context["params"]["year"] is None:
            return {"meta": {"available_years": [2025, 2026]}}
        return {"meta": {}}

    monkeypatch.setattr(
        "backend.domains.billboard.persistent_cache.build_cache_context",
        fake_context,
    )
    monkeypatch.setattr(
        "backend.domains.billboard.persistent_cache.load_persisted_snapshot",
        fake_load,
    )

    assert (
        snapshot_service.enqueue_billboard_snapshot_rebuild(
            "application startup",
            queue=queue,
        )
        is None
    )
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM background_jobs").fetchone()[0] == 0


def test_rebuild_default_snapshots_builds_latest_and_each_year(monkeypatch):
    filters = {"merge_level": 2, "include_compilations": False}
    calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(snapshot_service, "configured_billboard_filters", lambda: filters)
    monkeypatch.setattr(
        "backend.services.billboard_service.compute_weekly_data",
        lambda **kwargs: calls.append(("weekly", kwargs)) or {"weekly": []},
    )
    monkeypatch.setattr(
        "backend.services.billboard_service.compute_all_time_staged",
        lambda **kwargs: calls.append(("all_time", kwargs)) or {"weekly": []},
    )
    monkeypatch.setattr(
        "backend.services.billboard_service.compute_billboard_data",
        lambda **kwargs: calls.append(("full_data", kwargs)) or {"meta": {}},
    )
    monkeypatch.setattr(
        "backend.services.billboard_service.compute_year_end_staged",
        lambda **kwargs: calls.append(("year_end", kwargs))
        or {"meta": {"available_years": [2025, 2026]}},
    )

    result = snapshot_service.rebuild_default_billboard_snapshots()

    assert result["years"] == [2025, 2026]
    assert [name for name, _kwargs in calls] == [
        "weekly",
        "all_time",
        "full_data",
        "year_end",
        "year_end",
        "year_end",
    ]
    assert all(kwargs["force_rebuild"] is True for _name, kwargs in calls)
