from __future__ import annotations

import asyncio

import pytest

from backend.main import _music_search_startup_rebuild_enabled, lifespan

pytestmark = pytest.mark.unit


def test_music_search_startup_rebuild_flag_defaults_enabled(monkeypatch) -> None:
    monkeypatch.delenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", raising=False)

    assert _music_search_startup_rebuild_enabled() is True


def test_music_search_startup_rebuild_flag_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "0")

    assert _music_search_startup_rebuild_enabled() is False


def test_music_search_startup_rebuild_flag_is_independent_from_cache_warmup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SPOTIFY_STATS_WARMUP", "0")
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "1")

    assert _music_search_startup_rebuild_enabled() is True


def test_import_maintenance_recovery_is_registered_and_scanned_before_search_startup(
    monkeypatch,
) -> None:
    from backend.core import job_queue as job_queue_module
    from backend.domains.metadata import artist_identity, track_credits
    from backend.services import cover_cache_service
    from backend.services import (
        import_maintenance_recovery_service as recovery,
    )
    from backend.services import (
        music_search_maintenance_service as music_search,
    )

    events: list[str] = []

    class FakeQueue:
        def register(self, job_type, _handler):
            events.append(f"register:{job_type}")

        def prepare(self, _db_path):
            events.append("queue:prepare")

        def start(self, _db_path, *, priority_job_types=()):
            assert priority_job_types == (recovery.PLAYBACK_IMPORT_MAINTENANCE_JOB_TYPE,)
            events.append("queue:start")

        def enqueue_if_not_pending(self, job):
            events.append(f"queue:enqueue:{job.job_type}")
            return job.job_id

        def stop(self):
            events.append("queue:stop")

    queue = FakeQueue()
    monkeypatch.setattr(job_queue_module, "get_job_queue", lambda: queue)
    monkeypatch.setattr(
        recovery,
        "enqueue_pending_import_maintenance",
        lambda actual_queue: (
            events.append("recovery:scan")
            if actual_queue is queue
            else pytest.fail("startup used a different queue")
        ),
    )
    monkeypatch.setattr(
        music_search,
        "enqueue_music_search_snapshot_rebuild",
        lambda **_kwargs: events.append("search:enqueue"),
    )
    monkeypatch.setattr(
        cover_cache_service,
        "enqueue_failed_cover_download_recovery",
        lambda actual_queue: (
            events.append("cover:recover")
            if actual_queue is queue
            else pytest.fail("startup used a different queue")
        ),
    )
    ready_state = {
        "rebuild_status": "ready",
        "current_revision": 0,
        "active_aggregate_revision": 0,
    }
    monkeypatch.setattr(artist_identity, "get_identity_state", lambda _conn: ready_state)
    monkeypatch.setattr(track_credits, "get_track_credit_state", lambda _conn: ready_state)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "1")
    monkeypatch.setenv("SPOTIFY_STATS_WARMUP", "0")

    async def exercise_lifespan() -> None:
        async with lifespan(None):  # type: ignore[arg-type]
            events.append("lifespan:yield")

    asyncio.run(exercise_lifespan())

    assert events.index("register:playback_import_maintenance") < events.index("queue:prepare")
    assert events.index("queue:prepare") < events.index("recovery:scan")
    assert events.index("recovery:scan") < events.index("queue:start")
    assert events.index("queue:start") < events.index("cover:recover")
    assert events.index("cover:recover") < events.index("search:enqueue")
    assert events.index("queue:start") < events.index("search:enqueue")


@pytest.mark.parametrize(
    ("credit_state", "should_recover"),
    [
        (
            {
                "rebuild_status": "pending",
                "current_revision": 35,
                "active_aggregate_revision": 33,
            },
            True,
        ),
        (
            {
                "rebuild_status": "failed",
                "current_revision": 35,
                "active_aggregate_revision": 33,
            },
            True,
        ),
        (
            {
                "rebuild_status": "running",
                "current_revision": 35,
                "active_aggregate_revision": 33,
            },
            True,
        ),
        (
            {
                "rebuild_status": "ready",
                "current_revision": 35,
                "active_aggregate_revision": 35,
            },
            False,
        ),
    ],
)
def test_track_credit_startup_recovery_targets_latest_revision(
    monkeypatch, credit_state, should_recover
) -> None:
    from backend.core import job_queue as job_queue_module
    from backend.domains.metadata import artist_identity, track_credits
    from backend.services import cover_cache_service
    from backend.services import import_maintenance_recovery_service as recovery
    from backend.services import music_search_maintenance_service as music_search

    queued = []

    class FakeQueue:
        def register(self, _job_type, _handler):
            pass

        def prepare(self, _db_path):
            pass

        def start(self, _db_path, *, priority_job_types=()):
            assert priority_job_types == (recovery.PLAYBACK_IMPORT_MAINTENANCE_JOB_TYPE,)

        def enqueue_if_not_pending(self, job):
            queued.append(job)
            return job.job_id

        def stop(self):
            pass

    queue = FakeQueue()
    ready_identity = {
        "rebuild_status": "ready",
        "current_revision": 0,
        "active_aggregate_revision": 0,
    }
    monkeypatch.setattr(job_queue_module, "get_job_queue", lambda: queue)
    monkeypatch.setattr(recovery, "enqueue_pending_import_maintenance", lambda _queue: None)
    monkeypatch.setattr(
        cover_cache_service, "enqueue_failed_cover_download_recovery", lambda _queue: None
    )
    monkeypatch.setattr(
        music_search,
        "enqueue_music_search_snapshot_rebuild",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(artist_identity, "get_identity_state", lambda _conn: ready_identity)
    monkeypatch.setattr(track_credits, "get_track_credit_state", lambda _conn: credit_state)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "0")
    monkeypatch.setenv("SPOTIFY_STATS_WARMUP", "0")

    async def exercise_lifespan() -> None:
        async with lifespan(None):  # type: ignore[arg-type]
            pass

    asyncio.run(exercise_lifespan())

    credit_jobs = [job for job in queued if job.job_type == "track_credit_rebuild"]
    if should_recover:
        assert len(credit_jobs) == 1
        assert credit_jobs[0].entity_id == "global:revision:35"
        assert credit_jobs[0].payload["revision"] == 35
    else:
        assert credit_jobs == []
