from __future__ import annotations

import threading
import time

from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.yearly_review_generation import (
    PreparedYearlyReview,
    YearlyReviewGenerationCoordinator,
)


def _context() -> YearlyReviewFilterContext:
    return YearlyReviewFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="artist-rev",
        artist_identity_revision=1,
        track_credit_revision=2,
        track_group_revision="track-rev",
        album_project_revision="album-rev",
        filter_fingerprint="fingerprint",
    )


def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not reached")


def _prepared(year: int, context: YearlyReviewFilterContext, revision: str):
    return PreparedYearlyReview(
        year=year,
        context=context,
        context_json=context.model_dump_json(),
        cache_key=f"{year}-{revision}",
        db_revision=revision,
    )


def test_exact_task_is_deduplicated_and_foreground_promotes_queue() -> None:
    context = _context()
    blocker_started = threading.Event()
    release_blocker = threading.Event()
    order: list[int] = []

    def prepare(year, task_context):
        return _prepared(year, task_context, "r1")

    def build(item):
        order.append(item.year)
        if item.year == 2099:
            blocker_started.set()
            release_blocker.wait(timeout=1)
        return {"year": item.year}

    coordinator = YearlyReviewGenerationCoordinator(
        prepare=prepare,
        refresh=lambda item: item,
        build=build,
        is_ready=lambda _key: False,
    )
    coordinator.enqueue(2099, context, foreground=False)
    assert blocker_started.wait(timeout=1)
    coordinator.enqueue(2022, context, foreground=False)
    coordinator.enqueue(2024, context, foreground=False)
    first = coordinator.enqueue(2022, context, foreground=True)
    second = coordinator.enqueue(2022, context, foreground=True)

    assert first.requested_at == second.requested_at
    release_blocker.set()
    _wait_until(lambda: coordinator.status(2024, context).state == "ready")
    assert order == [2099, 2022, 2024]


def test_ready_year_is_not_blocked_by_another_cold_build() -> None:
    context = _context()
    cold_started = threading.Event()
    release_cold = threading.Event()

    def prepare(year, task_context):
        return _prepared(year, task_context, "r1")

    def build(item):
        if item.year == 2023:
            cold_started.set()
            release_cold.wait(timeout=1)
        return {"year": item.year}

    coordinator = YearlyReviewGenerationCoordinator(
        prepare=prepare,
        refresh=lambda item: item,
        build=build,
        is_ready=lambda key: key == "2024-r1",
    )
    coordinator.enqueue(2023, context, foreground=False)
    assert cold_started.wait(timeout=1)

    started_at = time.monotonic()
    result = coordinator.get_or_build(2024, context)

    assert result == {"year": 2024}
    assert time.monotonic() - started_at < 0.1
    release_cold.set()


def test_revision_drift_never_builds_under_stale_cache_key() -> None:
    context = _context()
    blocker_started = threading.Event()
    release_blocker = threading.Event()
    revision = {2025: "r1", 2099: "r1"}
    built_keys: list[str] = []

    def prepare(year, task_context):
        return _prepared(year, task_context, revision[year])

    def build(item):
        built_keys.append(item.cache_key)
        if item.year == 2099:
            blocker_started.set()
            release_blocker.wait(timeout=1)
        return {"year": item.year}

    coordinator = YearlyReviewGenerationCoordinator(
        prepare=prepare,
        refresh=lambda item: prepare(item.year, item.context),
        build=build,
        is_ready=lambda _key: False,
    )
    coordinator.enqueue(2099, context, foreground=False)
    assert blocker_started.wait(timeout=1)
    coordinator.enqueue(2025, context, foreground=False)
    revision[2025] = "r2"
    release_blocker.set()

    _wait_until(lambda: "2025-r2" in built_keys)
    assert "2025-r1" not in built_keys


def test_failed_task_can_be_retried() -> None:
    context = _context()
    attempts = 0

    def prepare(year, task_context):
        return _prepared(year, task_context, "r1")

    def build(item):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("private upstream detail")
        return {"year": item.year}

    coordinator = YearlyReviewGenerationCoordinator(
        prepare=prepare,
        refresh=lambda item: item,
        build=build,
        is_ready=lambda _key: False,
    )
    coordinator.enqueue(2025, context, foreground=False)
    _wait_until(lambda: coordinator.status(2025, context).state == "failed")
    failed = coordinator.status(2025, context)
    assert failed.error == "generation_failed"

    coordinator.enqueue(2025, context, foreground=True)
    _wait_until(lambda: coordinator.status(2025, context).state == "ready")
    assert attempts == 2


def test_terminal_task_registry_is_bounded() -> None:
    context = _context()

    def prepare(year, task_context):
        return _prepared(year, task_context, "r1")

    coordinator = YearlyReviewGenerationCoordinator(
        prepare=prepare,
        refresh=lambda item: item,
        build=lambda item: {"year": item.year},
        is_ready=lambda _key: False,
        max_terminal_tasks=2,
    )
    for year in [2022, 2023, 2024]:
        coordinator.enqueue(year, context, foreground=False)
        _wait_until(lambda year=year: coordinator.status(year, context).state == "ready")

    terminal_tasks = [
        task for task in coordinator._tasks.values() if task.state in {"ready", "failed"}
    ]
    assert len(terminal_tasks) <= 2
