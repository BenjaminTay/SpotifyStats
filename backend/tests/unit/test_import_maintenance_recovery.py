from __future__ import annotations

import json
import sqlite3
from copy import deepcopy

import pytest

from backend.core.job_queue import Job
from backend.domains.imports.change_set import PlaybackChangeSet
from backend.domains.imports.incremental import FINGERPRINT_VERSION

pytestmark = pytest.mark.unit


def _change_set(*, generation_id: str = "generation-current", added_count: int = 1):
    return PlaybackChangeSet(
        generation_id=generation_id,
        strategy="incremental",
        previous_dataset_digest="previous-digest",
        added_count=added_count,
        removed_count=0,
        earliest_changed_ts="2026-08-23T00:00:00+00:00",
        latest_changed_ts="2026-08-23T00:00:00+00:00",
        track_ids=frozenset({1}),
        album_ids=frozenset({2}),
        source_album_ids=frozenset({2}),
        artist_ids=frozenset({3}),
        spotify_track_ids=frozenset({"spotify-track"}),
        spotify_album_ids=frozenset({"spotify-album"}),
        dates=frozenset({"2026-08-23"}),
        months=frozenset({"2026-08"}),
        years=frozenset({2026}),
        billboard_weeks=frozenset({"2026-08-21"}),
        billboard_scope_exact=True,
        previous_open_week="2026-08-14",
        current_open_week="2026-08-21",
        semantic_revisions={
            "playback_policy": "logical_playback_v2",
            "settings": "settings-digest",
            "artist_identity": 1,
            "track_credit": 2,
        },
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(extra="unexpected"),
        lambda payload: payload.pop("generation_id"),
        lambda payload: payload.update(schema_version="playback_change_set_v1"),
        lambda payload: payload.update(added_count=True),
        lambda payload: payload.update(track_ids=[1, 1]),
        lambda payload: payload.update(entity_count=999),
    ],
)
def test_change_set_from_dict_rejects_schema_and_type_drift(mutate) -> None:
    payload = deepcopy(_change_set().to_dict())
    mutate(payload)

    with pytest.raises(ValueError):
        PlaybackChangeSet.from_dict(payload)


def test_change_set_from_dict_round_trips_current_schema() -> None:
    expected = _change_set()

    assert PlaybackChangeSet.from_dict(expected.to_dict()) == expected


@pytest.fixture
def recovery_db(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.core.migrations import migrate_037, migrate_038
    from backend.domains.imports.state import publish_playback_import_state

    path = tmp_path / "recovery.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(path))
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE plays (
               play_id INTEGER PRIMARY KEY,
               ts TEXT NOT NULL,
               content_type TEXT NOT NULL DEFAULT 'audio'
           )"""
    )
    migrate_037(conn)
    migrate_038(conn)
    conn.execute(
        """INSERT INTO plays(
               play_id, ts, content_type, source_fingerprint,
               source_fingerprint_version, import_generation_id
           ) VALUES (1, '2026-08-23T00:00:00+00:00', 'audio', ?, ?, ?)""",
        ("a" * 64, FINGERPRINT_VERSION, "generation-current"),
    )
    publish_playback_import_state(
        conn,
        generation_id="generation-current",
        account_identity_hash="account-hash",
        relation="snapshot_superset",
        strategy="incremental",
    )
    conn.execute(
        """INSERT INTO playback_import_runs(
               run_id, requested_mode, status, incoming_count, unchanged_count,
               added_count, removed_count, started_at, change_set_json
           ) VALUES ('run-pending', 'auto', 'maintenance_pending', 1, 0, 1, 0,
                     '2026-08-23T00:00:00+00:00', ?)""",
        (json.dumps(_change_set().to_dict()),),
    )
    conn.commit()
    conn.close()
    return path


class _FakeQueue:
    def __init__(self) -> None:
        self.jobs: dict[tuple[str, str, str], Job] = {}

    def enqueue_if_not_pending(self, job: Job) -> str | None:
        key = (job.job_type, job.entity_type, job.entity_id)
        if key in self.jobs:
            return None
        self.jobs[key] = job
        return job.job_id


def _run_row(path) -> tuple[str, str | None, str | None]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            """SELECT status, completed_at, error_code
               FROM playback_import_runs WHERE run_id='run-pending'"""
        ).fetchone()
    finally:
        conn.close()


def test_startup_scan_validates_and_idempotently_enqueues_pending_run(recovery_db) -> None:
    from backend.services.import_maintenance_recovery_service import (
        PLAYBACK_IMPORT_MAINTENANCE_JOB_TYPE,
        enqueue_pending_import_maintenance,
    )

    queue = _FakeQueue()
    first = enqueue_pending_import_maintenance(queue)  # type: ignore[arg-type]
    second = enqueue_pending_import_maintenance(queue)  # type: ignore[arg-type]

    assert first == {"pending_runs": 1, "enqueued": 1, "already_pending": 0, "blocked": 0}
    assert second == {"pending_runs": 1, "enqueued": 0, "already_pending": 1, "blocked": 0}
    job = next(iter(queue.jobs.values()))
    assert job.job_type == PLAYBACK_IMPORT_MAINTENANCE_JOB_TYPE
    assert job.entity_id == "run-pending"
    assert job.payload == {"generation_id": "generation-current"}
    assert _run_row(recovery_db) == ("maintenance_pending", None, None)


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("invalid_json", "recovery_change_set_invalid"),
        ("generation", "recovery_active_generation_drift"),
        ("count", "recovery_active_count_drift"),
        ("digest", "recovery_active_digest_drift"),
        ("generation_count", "recovery_generation_count_drift"),
    ],
)
def test_startup_scan_blocks_invalid_or_drifted_recovery_evidence(
    recovery_db, mutation: str, error_code: str
) -> None:
    from backend.services.import_maintenance_recovery_service import (
        enqueue_pending_import_maintenance,
    )

    conn = sqlite3.connect(recovery_db)
    if mutation == "invalid_json":
        conn.execute(
            "UPDATE playback_import_runs SET change_set_json='[' WHERE run_id='run-pending'"
        )
    elif mutation == "generation":
        conn.execute("UPDATE playback_import_state SET active_generation_id='generation-other'")
    elif mutation == "count":
        conn.execute("UPDATE playback_import_state SET record_count=2")
    elif mutation == "digest":
        conn.execute("UPDATE playback_import_state SET dataset_digest='wrong-digest'")
    else:
        payload = _change_set(added_count=2).to_dict()
        conn.execute(
            "UPDATE playback_import_runs SET change_set_json=? WHERE run_id='run-pending'",
            (json.dumps(payload),),
        )
    conn.commit()
    conn.close()
    queue = _FakeQueue()

    report = enqueue_pending_import_maintenance(queue)  # type: ignore[arg-type]

    assert report == {"pending_runs": 1, "enqueued": 0, "already_pending": 0, "blocked": 1}
    status, completed_at, actual_error = _run_row(recovery_db)
    assert status == "recovery_blocked"
    assert completed_at is not None
    assert actual_error == error_code
    assert queue.jobs == {}


def _recovery_job() -> Job:
    return Job.create(
        "playback_import_maintenance",
        "playback_import_run",
        "run-pending",
        generation_id="generation-current",
    )


def test_recovery_handler_replays_maintenance_and_cas_promotes_success(
    recovery_db, monkeypatch
) -> None:
    from backend.services import import_maintenance_recovery_service as recovery

    calls: list[PlaybackChangeSet] = []

    def run_maintenance(*, defer_music_search_snapshots, change_set):
        assert defer_music_search_snapshots is True
        calls.append(change_set)
        return {}

    monkeypatch.setattr(
        recovery,
        "run_post_streaming_import_maintenance",
        run_maintenance,
    )
    monkeypatch.setattr(recovery, "build_import_health_report", lambda _conn: {"blockers": []})

    job = _recovery_job()
    recovery.handle_import_maintenance_recovery(job)
    recovery.handle_import_maintenance_recovery(job)

    assert calls == [_change_set()]
    status, completed_at, error_code = _run_row(recovery_db)
    assert status == "success"
    assert completed_at is not None
    assert error_code is None


def test_recovery_handler_blocks_generation_drift_after_maintenance(
    recovery_db, monkeypatch
) -> None:
    from backend.services import import_maintenance_recovery_service as recovery

    def drift_after_maintenance(**_kwargs) -> dict:
        conn = sqlite3.connect(recovery_db)
        conn.execute("UPDATE playback_import_state SET active_generation_id='generation-other'")
        conn.commit()
        conn.close()
        return {}

    monkeypatch.setattr(recovery, "run_post_streaming_import_maintenance", drift_after_maintenance)
    monkeypatch.setattr(recovery, "build_import_health_report", lambda _conn: {"blockers": []})

    recovery.handle_import_maintenance_recovery(_recovery_job())

    assert _run_row(recovery_db)[::2] == (
        "recovery_blocked",
        "recovery_active_generation_drift",
    )


def test_recovery_handler_leaves_pending_for_transient_maintenance_retry(
    recovery_db, monkeypatch
) -> None:
    from backend.services import import_maintenance_recovery_service as recovery

    def fail_maintenance(**_kwargs):
        raise RuntimeError("temporary provider failure")

    monkeypatch.setattr(recovery, "run_post_streaming_import_maintenance", fail_maintenance)

    with pytest.raises(RuntimeError, match="temporary provider failure"):
        recovery.handle_import_maintenance_recovery(_recovery_job())

    assert _run_row(recovery_db) == ("maintenance_pending", None, None)
