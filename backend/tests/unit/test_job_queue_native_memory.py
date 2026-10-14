"""Native page release belongs to successful, serialized maintenance completion."""

import threading
from functools import lru_cache

import pytest

import backend.core.job_queue as queue_module
from backend.core.job_queue import Job, JobQueue

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("released", [True, False])
def test_maintenance_releases_after_handler_before_done_preserving_cache(monkeypatch, released):
    queue = JobQueue(max_workers=0)
    events = []
    cache_value = object()

    @lru_cache(maxsize=1)
    def ready_snapshot():
        return cache_value

    assert ready_snapshot() is cache_value
    before_cache = ready_snapshot.cache_info()

    def handler(job):
        events.append("handler")

    def trim():
        events.append("trim")
        assert not queue._cpu_heavy_gate.acquire(blocking=False)
        assert ready_snapshot.cache_info() == before_cache
        assert ready_snapshot() is cache_value
        return released

    monkeypatch.setattr(queue_module, "trim_unused_native_memory", trim)
    monkeypatch.setattr(
        queue, "_update_db_status", lambda job_id, status, *a, **kw: events.append(status)
    )
    queue.register("analysis_snapshot_rebuild", handler)
    assert queue._process_job(Job.create("analysis_snapshot_rebuild", "snapshot", "global"))
    assert events == ["running", "handler", "trim", "done"]
    assert queue._cpu_heavy_gate.acquire(blocking=False)
    queue._cpu_heavy_gate.release()


@pytest.mark.parametrize("job_type", ["cover_download", "custom_job", "startup_cache_warmup"])
def test_nonmaintenance_and_warmup_do_not_add_trim(monkeypatch, job_type):
    queue = JobQueue(max_workers=0)
    calls = []
    monkeypatch.setattr(queue_module, "trim_unused_native_memory", lambda: calls.append("trim"))
    queue.register(job_type, lambda job: calls.append("handler"))
    assert queue._process_job(Job.create(job_type, "entity", "one", resource_class="critical"))
    assert calls == ["handler"]


def test_missing_and_failed_handlers_skip_trim_and_keep_retry(monkeypatch):
    queue = JobQueue(max_workers=0)
    calls = []
    statuses = []
    retries = []
    monkeypatch.setattr(queue_module, "trim_unused_native_memory", lambda: calls.append("trim"))
    monkeypatch.setattr(
        queue, "_update_db_status", lambda job_id, status, *a, **kw: statuses.append(status)
    )
    monkeypatch.setattr(queue, "_persist_pending_retry", lambda job, error: calls.append(error))
    job = Job.create("artist_rank_context_rebuild", "snapshot", "global")
    assert not queue._process_job(job)
    assert job.attempts == 0

    def failed_handler(job):
        raise ValueError("builder failed")

    queue.register(job.job_type, failed_handler)
    queue._running = True
    assert queue._process_job(job, retry=retries.append)
    assert retries == [job]
    assert job.attempts == 1
    assert job.next_attempt_at == ""
    assert calls == ["builder failed"]
    queue._running = False
    assert not queue._process_job(job)
    assert calls == ["builder failed"]
    assert statuses == ["failed", "running", "running", "failed"]


def test_next_heavy_handler_waits_for_previous_trim(monkeypatch):
    queue = JobQueue(max_workers=0)
    first_trimming = threading.Event()
    release_trim = threading.Event()
    second_waiting = threading.Event()
    second_started = threading.Event()
    original_gate = queue._cpu_heavy_gate
    calls = []
    results = []

    class ObservedGate:
        def __enter__(self):
            if threading.current_thread().name == "second-maintenance":
                second_waiting.set()
            original_gate.acquire()

        def __exit__(self, *args):
            original_gate.release()

    queue._cpu_heavy_gate = ObservedGate()

    def trim():
        calls.append(threading.current_thread().name)
        if len(calls) == 1:
            first_trimming.set()
            assert release_trim.wait(3)
        return True

    monkeypatch.setattr(queue_module, "trim_unused_native_memory", trim)
    queue.register("analysis_snapshot_rebuild", lambda job: None)
    queue.register("versus_rank_context_rebuild", lambda job: second_started.set())
    first = threading.Thread(
        target=lambda: results.append(
            queue._process_job(Job.create("analysis_snapshot_rebuild", "snapshot", "first"))
        ),
        name="first-maintenance",
    )
    second = threading.Thread(
        target=lambda: results.append(
            queue._process_job(Job.create("versus_rank_context_rebuild", "snapshot", "second"))
        ),
        name="second-maintenance",
    )
    try:
        first.start()
        assert first_trimming.wait(3)
        second.start()
        assert second_waiting.wait(3)
        assert not second_started.is_set()
    finally:
        release_trim.set()
        first.join(timeout=3)
        if second.ident is not None:
            second.join(timeout=3)
    assert not first.is_alive() and not second.is_alive()
    assert results == [True, True]
    assert second_started.is_set()
    assert calls == ["first-maintenance", "second-maintenance"]
