from __future__ import annotations

import sqlite3
import threading
from unittest.mock import ANY

import pandas as pd
import pytest

from backend.api import track_credits as track_credit_api
from backend.core.job_queue import Job, JobQueue
from backend.services import track_credit_rebuild_service as rebuild

pytestmark = pytest.mark.unit


def _database(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE track_credit_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL,
            active_aggregate_revision INTEGER NOT NULL,
            rebuild_status TEXT NOT NULL,
            last_error TEXT,
            updated_at TEXT
        );
        INSERT INTO track_credit_state VALUES (1, 4, 3, 'pending', NULL, NULL);
        CREATE TABLE artist_identity_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL,
            active_aggregate_revision INTEGER NOT NULL,
            rebuild_status TEXT NOT NULL,
            last_error TEXT,
            updated_at TEXT
        );
        INSERT INTO artist_identity_state VALUES (1, 9, 9, 'ready', NULL, NULL);
        CREATE TABLE agg_weekly_artists (
            billboard_week TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            play_count INTEGER NOT NULL,
            total_ms INTEGER NOT NULL,
            PRIMARY KEY (billboard_week, artist_id)
        );
        INSERT INTO agg_weekly_artists VALUES ('2026-01-02', 99, 7, 7000);
        CREATE TABLE agg_config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE music_search_revision_state (
            state_id INTEGER PRIMARY KEY,
            playback_revision INTEGER NOT NULL DEFAULT 0,
            billboard_revision INTEGER NOT NULL DEFAULT 0,
            metadata_revision INTEGER NOT NULL DEFAULT 0,
            settings_revision INTEGER NOT NULL DEFAULT 0,
            candidate_revision INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT
        );
        INSERT INTO music_search_revision_state VALUES (1, 0, 0, 0, 0, 0, NULL);
        CREATE TABLE music_search_snapshot_meta (
            snapshot_key TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            last_error TEXT
        );
        CREATE TABLE music_search_index_state (
            state_id INTEGER PRIMARY KEY,
            active_generation_id TEXT,
            source_revision TEXT,
            candidate_index_version TEXT,
            updated_at TEXT
        );
        INSERT INTO music_search_index_state VALUES (1, NULL, NULL, NULL, NULL);
        CREATE TABLE background_jobs (
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
        );
        """
    )
    conn.commit()
    conn.close()


def _connection_factory(path):
    def connect(*, readonly=False):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    return connect


class _Settings:
    def __init__(self, _conn):
        pass

    def load_all(self):
        return {
            "min_ms": 30_000,
            "music_only": True,
            "bb_week_start_dow": 4,
            "bb_week_start_hour": 0,
        }


def test_track_credit_shadow_rebuild_atomically_switches_artist_aggregates(tmp_path, monkeypatch):
    path = tmp_path / "track-credit.db"
    _database(path)
    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(rebuild, "SettingsRepository", _Settings)
    monkeypatch.setattr(
        rebuild,
        "load_billboard_raw_for_artists",
        lambda *_args: pd.DataFrame(
            [
                {"billboard_week": "2026-02-06", "artist_id": 53, "ms_played": 1000},
                {"billboard_week": "2026-02-06", "artist_id": 53, "ms_played": 2000},
            ]
        ),
    )

    rebuild.handle_track_credit_rebuild(
        Job.create("track_credit_rebuild", "track_credit", "global", revision=4)
    )

    conn = _connection_factory(path)()
    assert [tuple(row) for row in conn.execute("SELECT * FROM agg_weekly_artists")] == [
        ("2026-02-06", 53, 2, 3000)
    ]
    state = conn.execute("SELECT * FROM track_credit_state").fetchone()
    assert state["active_aggregate_revision"] == 4
    assert state["rebuild_status"] == "ready"
    assert (
        conn.execute("SELECT metadata_revision FROM music_search_revision_state").fetchone()[0] == 1
    )
    conn.close()


def test_track_credit_failed_rebuild_keeps_old_aggregate_and_realtime_revision(
    tmp_path, monkeypatch
):
    path = tmp_path / "track-credit-failure.db"
    _database(path)
    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(rebuild, "SettingsRepository", _Settings)

    def fail(*_args):
        raise RuntimeError("simulated credit rebuild failure")

    monkeypatch.setattr(rebuild, "load_billboard_raw_for_artists", fail)
    with pytest.raises(RuntimeError, match="simulated credit"):
        rebuild.handle_track_credit_rebuild(
            Job.create("track_credit_rebuild", "track_credit", "global", revision=4)
        )

    conn = _connection_factory(path)()
    assert [tuple(row) for row in conn.execute("SELECT * FROM agg_weekly_artists")] == [
        ("2026-01-02", 99, 7, 7000)
    ]
    state = conn.execute("SELECT * FROM track_credit_state").fetchone()
    assert state["active_aggregate_revision"] == 3
    assert state["rebuild_status"] == "failed"
    assert "simulated credit rebuild failure" in state["last_error"]
    assert (
        conn.execute("SELECT metadata_revision FROM music_search_revision_state").fetchone()[0] == 0
    )
    conn.close()


def test_enqueue_uses_revision_specific_identity(tmp_path, monkeypatch):
    path = tmp_path / "track-credit-enqueue.db"
    _database(path)
    queued: list[Job] = []

    class Queue:
        def enqueue_if_not_pending(self, job):
            queued.append(job)
            return job.job_id

    from backend.services import music_search_maintenance_service as maintenance

    monkeypatch.setattr(track_credit_api, "get_db", _connection_factory(path))
    monkeypatch.setattr(track_credit_api, "invalidate_all", lambda: None)
    monkeypatch.setattr(maintenance, "mark_music_search_for_rebuild", lambda **_kwargs: None)
    monkeypatch.setattr(rebuild, "get_job_queue", lambda: Queue())

    first_id = track_credit_api._enqueue_rebuild(34)
    second_id = track_credit_api._enqueue_rebuild(35)

    assert first_id and second_id and first_id != second_id
    assert [job.entity_id for job in queued] == [
        "global:revision:34",
        "global:revision:35",
    ]
    assert [job.payload["revision"] for job in queued] == [34, 35]


def test_role_only_enqueue_does_not_invalidate_statistics(tmp_path, monkeypatch):
    path = tmp_path / "track-credit-role-enqueue.db"
    _database(path)
    with _connection_factory(path)() as conn:
        conn.execute(
            """CREATE TABLE track_credit_change_sets (
                   change_set_id INTEGER PRIMARY KEY,
                   to_revision INTEGER NOT NULL,
                   statistics_membership_changed INTEGER NOT NULL
               )"""
        )
        conn.execute(
            """INSERT INTO track_credit_change_sets(
                   change_set_id, to_revision, statistics_membership_changed
               ) VALUES (1, 4, 0)"""
        )
        conn.commit()
    marks = []

    class Queue:
        def enqueue_if_not_pending(self, job):
            return job.job_id

    from backend.services import music_search_maintenance_service as maintenance

    monkeypatch.setattr(track_credit_api, "get_db", _connection_factory(path))
    monkeypatch.setattr(track_credit_api, "invalidate_all", lambda: None)
    monkeypatch.setattr(
        maintenance,
        "mark_music_search_for_rebuild",
        lambda **kwargs: marks.append(kwargs),
    )
    monkeypatch.setattr(rebuild, "get_job_queue", lambda: Queue())

    assert track_credit_api._enqueue_rebuild(4)
    assert len(marks) == 1
    assert marks[0]["revision_kinds"] == ("candidate",)
    assert marks[0]["statistics"] is False


def test_superseded_rebuild_skips_work_and_ensures_latest_revision(tmp_path, monkeypatch):
    path = tmp_path / "track-credit-superseded.db"
    _database(path)
    with _connection_factory(path)() as conn:
        conn.execute(
            """UPDATE track_credit_state
               SET current_revision=5, rebuild_status='pending' WHERE state_id=1"""
        )
        conn.commit()
    queued: list[Job] = []

    class Queue:
        def enqueue_if_not_pending(self, job):
            queued.append(job)
            return job.job_id

    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(rebuild, "get_job_queue", lambda: Queue())
    monkeypatch.setattr(
        rebuild,
        "load_billboard_raw_for_artists",
        lambda *_args: pytest.fail("superseded rebuild must not load the artist frame"),
    )

    rebuild.handle_track_credit_rebuild(
        Job.create(
            "track_credit_rebuild",
            "track_credit",
            "global:revision:4",
            revision=4,
        )
    )

    assert [(job.entity_id, job.payload["revision"]) for job in queued] == [
        ("global:revision:5", 5)
    ]
    with _connection_factory(path)() as conn:
        state = conn.execute("SELECT * FROM track_credit_state").fetchone()
    assert state["active_aggregate_revision"] == 3
    assert state["rebuild_status"] == "pending"


def test_failure_from_superseded_rebuild_does_not_poison_latest_revision(tmp_path, monkeypatch):
    path = tmp_path / "track-credit-superseded-failure.db"
    _database(path)
    queued: list[Job] = []

    class Queue:
        def enqueue_if_not_pending(self, job):
            queued.append(job)
            return job.job_id

    def mutate_then_fail(*_args):
        with _connection_factory(path)() as conn:
            conn.execute(
                """UPDATE track_credit_state
                   SET current_revision=5, rebuild_status='pending', last_error=NULL
                   WHERE state_id=1"""
            )
            conn.commit()
        raise RuntimeError("obsolete revision failed")

    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(rebuild, "SettingsRepository", _Settings)
    monkeypatch.setattr(rebuild, "get_job_queue", lambda: Queue())
    monkeypatch.setattr(rebuild, "load_billboard_raw_for_artists", mutate_then_fail)

    rebuild.handle_track_credit_rebuild(
        Job.create(
            "track_credit_rebuild",
            "track_credit",
            "global:revision:4",
            revision=4,
        )
    )

    assert [(job.entity_id, job.payload["revision"]) for job in queued] == [
        ("global:revision:5", 5)
    ]
    with _connection_factory(path)() as conn:
        state = conn.execute("SELECT * FROM track_credit_state").fetchone()
    assert state["active_aggregate_revision"] == 3
    assert state["rebuild_status"] == "pending"
    assert state["last_error"] is None


def test_two_rapid_revisions_converge_to_latest_with_persistent_queue(tmp_path, monkeypatch):
    path = tmp_path / "track-credit-rapid-revisions.db"
    _database(path)
    first_started = threading.Event()
    release_first = threading.Event()
    load_count = 0

    def load_frame(*_args):
        nonlocal load_count
        load_count += 1
        if load_count == 1:
            first_started.set()
            assert release_first.wait(timeout=3)
        return pd.DataFrame([{"billboard_week": "2026-02-06", "artist_id": 53, "ms_played": 1000}])

    queue = JobQueue(max_workers=1, retry_base_seconds=0.01, retry_max_seconds=0.02)
    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(rebuild, "SettingsRepository", _Settings)
    monkeypatch.setattr(rebuild, "get_job_queue", lambda: queue)
    monkeypatch.setattr(rebuild, "load_billboard_raw_for_artists", load_frame)
    queue.register("track_credit_rebuild", rebuild.handle_track_credit_rebuild)
    queue.start(str(path))
    try:
        first = Job.create(
            "track_credit_rebuild",
            "track_credit",
            "global:revision:4",
            revision=4,
        )
        assert queue.enqueue_if_not_pending(first) == first.job_id
        assert first_started.wait(timeout=3)

        with _connection_factory(path)() as conn:
            conn.execute(
                """UPDATE track_credit_state
                   SET current_revision=5, rebuild_status='pending', last_error=NULL
                   WHERE state_id=1"""
            )
            conn.commit()
        latest = Job.create(
            "track_credit_rebuild",
            "track_credit",
            "global:revision:5",
            revision=5,
        )
        assert queue.enqueue_if_not_pending(latest) == latest.job_id
        release_first.set()
        queue.wait_until_idle()
    finally:
        release_first.set()
        queue.stop()

    with _connection_factory(path)() as conn:
        state = conn.execute("SELECT * FROM track_credit_state").fetchone()
        jobs = conn.execute(
            """SELECT entity_id, status FROM background_jobs
               WHERE job_type='track_credit_rebuild' ORDER BY entity_id"""
        ).fetchall()
    assert load_count == 2
    assert state["current_revision"] == 5
    assert state["active_aggregate_revision"] == 5
    assert state["rebuild_status"] == "ready"
    assert [tuple(row) for row in jobs] == [
        ("global:revision:4", "done"),
        ("global:revision:5", "done"),
    ]


def test_role_only_revision_advances_without_rebuilding_statistics(tmp_path, monkeypatch):
    path = tmp_path / "track-credit-role-only.db"
    _database(path)
    with _connection_factory(path)() as conn:
        conn.execute(
            """CREATE TABLE track_credit_change_sets (
                   change_set_id INTEGER PRIMARY KEY,
                   to_revision INTEGER NOT NULL,
                   statistics_membership_changed INTEGER NOT NULL
               )"""
        )
        conn.execute(
            """INSERT INTO track_credit_change_sets(
                   change_set_id, to_revision, statistics_membership_changed
               ) VALUES (1, 4, 0)"""
        )
        conn.commit()
    calls: list[tuple[str, object]] = []
    from backend.domains.music_search import index as search_index
    from backend.services import music_search_maintenance_service as maintenance

    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(
        rebuild,
        "load_billboard_raw_for_artists",
        lambda *_args: pytest.fail("role-only revision must not rebuild artist aggregates"),
    )
    monkeypatch.setattr(
        maintenance,
        "mark_music_search_for_rebuild",
        lambda **kwargs: (calls.append(("mark", kwargs)), kwargs["conn"].commit()),
    )
    monkeypatch.setattr(
        search_index,
        "rebuild_music_search_index",
        lambda conn: calls.append(("candidate", conn)),
    )

    rebuild.handle_track_credit_rebuild(
        Job.create(
            "track_credit_rebuild",
            "track_credit",
            "global:revision:4",
            revision=4,
        )
    )

    with _connection_factory(path)() as conn:
        state = conn.execute("SELECT * FROM track_credit_state").fetchone()
        aggregate = conn.execute("SELECT * FROM agg_weekly_artists").fetchall()
        config = dict(conn.execute("SELECT key, value FROM agg_config"))
    assert state["active_aggregate_revision"] == 4
    assert state["rebuild_status"] == "ready"
    assert [tuple(row) for row in aggregate] == [("2026-01-02", 99, 7, 7000)]
    assert config["identity_revision"] == "9"
    assert config["track_credit_revision"] == "4"
    assert config["track_identity_revision"] == "0"
    assert calls[0][0] == "mark"
    assert calls[0][1]["revision_kinds"] == ("candidate",)
    assert calls[0][1]["statistics"] is False
    assert calls[1] == ("candidate", ANY)


def test_membership_revision_prefers_bounded_delta_without_full_artist_scan(tmp_path, monkeypatch):
    path = tmp_path / "track-credit-membership-delta.db"
    _database(path)
    with _connection_factory(path)() as conn:
        conn.execute(
            """CREATE TABLE track_credit_change_sets (
                   change_set_id INTEGER PRIMARY KEY,
                   from_revision INTEGER NOT NULL,
                   to_revision INTEGER NOT NULL,
                   track_id INTEGER NOT NULL,
                   canonical_track_ids_json TEXT NOT NULL,
                   before_credits_json TEXT NOT NULL,
                   after_credits_json TEXT NOT NULL,
                   before_roles_json TEXT NOT NULL,
                   after_roles_json TEXT NOT NULL,
                   affected_artist_ids_json TEXT NOT NULL,
                   candidate_changed INTEGER NOT NULL,
                   statistics_membership_changed INTEGER NOT NULL
               )"""
        )
        conn.execute(
            """INSERT INTO track_credit_change_sets VALUES(
                   1, 3, 4, 1, '[1]',
                   '[{"artist_id":10,"role":"primary"}]',
                   '[{"artist_id":10,"role":"primary"},{"artist_id":20,"role":"featured"}]',
                   '{"10":"primary"}',
                   '{"10":"primary","20":"featured"}',
                   '[10,20]', 1, 1
               )"""
        )
        conn.commit()

    calls: list[str] = []
    from backend.domains.music_search import (
        index as search_index,
    )
    from backend.domains.music_search import (
        track_credit_delta,
        variants,
    )
    from backend.services import music_search_maintenance_service as maintenance

    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(
        rebuild,
        "load_billboard_raw_for_artists",
        lambda *_args: pytest.fail("bounded credit delta must not scan all artist lifetime rows"),
    )
    monkeypatch.setattr(
        search_index,
        "rebuild_music_search_index",
        lambda _conn: calls.append("candidate"),
    )
    monkeypatch.setattr(maintenance, "_current_filter_values", lambda _conn: {})
    monkeypatch.setattr(
        variants,
        "build_music_search_variant_contexts",
        lambda _conn, _filters: (ANY,),
    )

    def apply_delta(conn, _contexts, changes, *, target_revision):
        assert changes[0]["before_credits"][0]["artist_id"] == 10
        assert changes[0]["after_credits"][1]["artist_id"] == 20
        conn.execute(
            """UPDATE track_credit_state
                  SET active_aggregate_revision=?, rebuild_status='ready'
                WHERE state_id=1""",
            (target_revision,),
        )
        conn.commit()
        calls.append("delta")
        return {"status": "ready", "strategy": "track_credit_delta"}

    monkeypatch.setattr(track_credit_delta, "apply_track_credit_statistics_delta", apply_delta)
    monkeypatch.setattr(
        maintenance,
        "enqueue_music_search_snapshot_rebuild",
        lambda **_kwargs: calls.append("projection"),
    )

    rebuild.handle_track_credit_rebuild(
        Job.create(
            "track_credit_rebuild",
            "track_credit",
            "global:revision:4",
            revision=4,
        )
    )

    assert calls == ["candidate", "delta", "projection"]
    with _connection_factory(path)() as conn:
        state = conn.execute("SELECT * FROM track_credit_state").fetchone()
        aggregate = conn.execute("SELECT * FROM agg_weekly_artists").fetchall()
    assert state["active_aggregate_revision"] == 4
    assert state["rebuild_status"] == "ready"
    assert [tuple(row) for row in aggregate] == [("2026-01-02", 99, 7, 7000)]
