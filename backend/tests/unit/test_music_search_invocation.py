from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from backend.domains.music_search import invocation
from backend.domains.playback.logical_timeline import (
    attach_listening_duration_frame,
    get_listening_duration_frame,
)
from backend.services import music_search_maintenance_service as maintenance
from backend.tests.unit.test_music_search_maintenance import (
    _conn,
    _seed_ready_candidate_and_statistics,
)

pytestmark = pytest.mark.unit


def test_exact_ready_skips_planner_only_with_current_attribution(monkeypatch):
    conn = _conn()
    _seed_ready_candidate_and_statistics(conn)
    monkeypatch.setattr(invocation, "attribution_dependencies_ready", lambda _: True)
    monkeypatch.setattr(
        "backend.domains.playback.l3_album_attribution.reconcile_l3_album_attribution_dependencies",
        lambda _: pytest.fail("exact ready repeated attribution planning"),
    )
    assert maintenance.rebuild_current_music_search_derived_data(conn)["status"] == "ready"
    monkeypatch.setattr(invocation, "attribution_dependencies_ready", lambda _: False)
    with pytest.raises(pytest.fail.Exception, match="repeated attribution"):
        maintenance.rebuild_current_music_search_derived_data(conn)


def test_compaction_preserves_unqualified_duration_and_logical_intervals(tmp_path, monkeypatch):
    path = tmp_path / "source.db"
    conn = sqlite3.connect(path)
    context = type(
        "Context",
        (),
        dict(
            min_ms=30000,
            music_only=True,
            merge_enabled=True,
            dynamic_threshold=True,
            max_merge_gap_minutes=5,
        ),
    )()
    frame = pd.DataFrame(
        {
            "track_id": [1],
            "ms_played": [60000],
            "_logical_event_id": ["event"],
            "_listening_intervals_ns": [((1, 2),)],
            "platform": ["unused"],
        }
    )
    duration = pd.DataFrame(
        {
            "track_id": [1, 2],
            "ms_played": [60000, 10000],
            "_listening_intervals_ns": [((1, 2),), ((3, 4),)],
        }
    )
    attach_listening_duration_frame(frame, duration)
    monkeypatch.setattr(invocation.db, "DB_PATH", str(path))
    monkeypatch.setattr(invocation, "get_track_identity_revision", lambda _: 0)
    calls = []

    def load(**options):
        calls.append(options)
        return frame

    monkeypatch.setattr(invocation.db, "_load_plays_cached", load)
    result, empty = invocation.load_invocation_frames(conn, (context,), ("track", "album"))[True]
    assert len(calls) == 1 and "p.play_id" in calls[0]["columns"]
    assert empty.empty
    assert result["_logical_event_id"].tolist() == ["event"]
    assert result["_listening_intervals_ns"].tolist() == [((1, 2),)]
    assert "platform" not in result
    pd.testing.assert_frame_equal(get_listening_duration_frame(result), duration)
    monkeypatch.setattr(invocation.db, "DB_PATH", str(tmp_path / "other.db"))
    with pytest.raises(RuntimeError, match="namespace changed"):
        invocation.load_invocation_frames(conn, (context,), ("track", "album"))
    assert len(calls) == 1
    conn.close()


def test_waiters_recheck_ready_and_failed_owner_releases_lock(tmp_path, monkeypatch):
    path = tmp_path / "owners.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE result (ready INTEGER)")
    barrier = threading.Barrier(4)
    builds = []

    def rebuild(conn, **_):
        if not conn.execute("SELECT 1 FROM result").fetchone():
            builds.append(1)
            conn.execute("INSERT INTO result VALUES (1)")
            conn.commit()
        return {"status": "ready"}

    monkeypatch.setattr(maintenance, "_rebuild_current_music_search_derived_data", rebuild)

    def worker(_):
        conn = sqlite3.connect(path)
        try:
            barrier.wait()
            return maintenance.rebuild_current_music_search_derived_data(conn)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(row["status"] == "ready" for row in pool.map(worker, range(4)))
    assert builds == [1]
    assert not invocation._owners

    with sqlite3.connect(path) as conn:
        with pytest.raises(RuntimeError):
            with invocation.maintenance_owner(conn):
                raise RuntimeError("failed build")
        with invocation.maintenance_owner(conn):
            pass
    assert not invocation._owners


def test_album_compaction_keeps_release_day_and_duration_only_rows():
    frame = pd.DataFrame(
        {
            "track_id": [1, 1, 1],
            "track_name": ["Track"] * 3,
            "artist_name": ["Artist"] * 3,
            "billboard_week": ["2026-01-02"] * 3,
            "ts_date": ["2026-01-02", "2026-01-02", "2026-01-03"],
            "play_count": [1, 0, 0],
            "total_ms": [0, 60000, 10000],
        }
    )
    result = invocation.compact_album_facts(frame, weekly=True)
    assert result["ts_date"].tolist() == ["2026-01-02", "2026-01-03"]
    assert result["play_count"].tolist() == [1, 0]
    assert result["total_ms"].tolist() == [60000, 10000]
    lifetime = invocation.compact_album_facts(frame)
    assert lifetime["play_count"].tolist() == [1]
    assert lifetime["total_ms"].tolist() == [70000]


def test_superseded_job_enqueues_current_base_without_failing_new_year_end(monkeypatch):
    from backend.core.job_queue import Job
    from backend.domains.music_search.revisions import bump_music_search_revisions

    conn = _conn()
    old_contexts = _seed_ready_candidate_and_statistics(conn)
    queued = []
    monkeypatch.setattr(maintenance, "get_db", lambda **_: conn)

    def superseded(*args, **kwargs):
        bump_music_search_revisions(conn, "settings")
        conn.commit()
        raise RuntimeError("semantic base changed during build")

    def enqueue(**kwargs):
        contexts = maintenance.build_music_search_variant_contexts(
            conn, maintenance._current_filter_values(conn)
        )
        queued.append(contexts[0].semantic_base_key)

    monkeypatch.setattr(maintenance, "rebuild_current_music_search_derived_data", superseded)
    monkeypatch.setattr(maintenance, "enqueue_music_search_snapshot_rebuild", enqueue)
    monkeypatch.setattr(
        maintenance,
        "fail_pending_year_end_projection_set",
        lambda *args, **kwargs: pytest.fail("old job marked new Year-End target failed"),
    )
    job = Job.create(
        maintenance.MUSIC_SEARCH_SNAPSHOT_JOB_TYPE,
        "music_search_snapshot",
        f"snapshot-set:{old_contexts[0].semantic_base_key}",
    )
    with pytest.raises(RuntimeError, match="semantic base changed"):
        maintenance.handle_music_search_snapshot_rebuild(job)
    assert len(queued) == 1 and queued[0] != old_contexts[0].semantic_base_key
