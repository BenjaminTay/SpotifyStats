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

        def start(self, _db_path):
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
        lambda actual_queue: events.append("recovery:scan")
        if actual_queue is queue
        else pytest.fail("startup used a different queue"),
    )
    monkeypatch.setattr(
        music_search,
        "enqueue_music_search_snapshot_rebuild",
        lambda: events.append("search:enqueue"),
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

    assert events.index("register:playback_import_maintenance") < events.index("queue:start")
    assert events.index("queue:start") < events.index("recovery:scan")
    assert events.index("recovery:scan") < events.index("search:enqueue")
