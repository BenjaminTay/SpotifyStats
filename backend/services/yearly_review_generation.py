"""In-process coordinator for exact-key Yearly Review artifact generation."""

from __future__ import annotations

import heapq
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Literal

from backend.models.yearly_review import (
    YearlyReviewFilterContext,
    YearlyReviewGenerationTask,
)

logger = logging.getLogger(__name__)

GenerationState = Literal["queued", "running", "ready", "failed"]
Artifact = dict[str, object]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PreparedYearlyReview:
    year: int
    context: YearlyReviewFilterContext
    context_json: str
    cache_key: str
    db_revision: str


@dataclass
class _GenerationTask:
    prepared: PreparedYearlyReview
    state: GenerationState = "queued"
    requested_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    result: Artifact | None = None
    priority: int = 0
    queue_revision: int = 0
    done: threading.Event = field(default_factory=threading.Event)

    def public(self) -> YearlyReviewGenerationTask:
        return YearlyReviewGenerationTask(
            year=self.prepared.year,
            state=self.state,
            requested_at=self.requested_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error=self.error,
        )


class YearlyReviewGenerationTimeoutError(TimeoutError):
    """The foreground request stopped waiting while generation continues."""


class YearlyReviewGenerationCoordinator:
    """Run all cold builds on one worker while serving exact cache hits directly."""

    def __init__(
        self,
        *,
        prepare: Callable[[int, YearlyReviewFilterContext], PreparedYearlyReview],
        refresh: Callable[[PreparedYearlyReview], PreparedYearlyReview],
        build: Callable[[PreparedYearlyReview], Artifact],
        is_ready: Callable[[str], bool],
        max_terminal_tasks: int = 32,
    ) -> None:
        self._prepare = prepare
        self._refresh = refresh
        self._build = build
        self._is_ready = is_ready
        self._max_terminal_tasks = max(0, max_terminal_tasks)
        self._condition = threading.Condition(threading.RLock())
        self._tasks: dict[str, _GenerationTask] = {}
        self._queue: list[tuple[int, int, str, int]] = []
        self._sequence = 0
        self._worker: threading.Thread | None = None

    def prepare(self, year: int, context: YearlyReviewFilterContext) -> PreparedYearlyReview:
        return self._prepare(year, context)

    def enqueue(
        self,
        year: int,
        context: YearlyReviewFilterContext,
        *,
        foreground: bool,
    ) -> YearlyReviewGenerationTask:
        prepared = self._prepare(year, context)
        if self._is_ready(prepared.cache_key):
            return self._ready_snapshot(prepared)
        task = self._enqueue_prepared(prepared, foreground=foreground)
        return task.public()

    def enqueue_prepared(
        self,
        prepared: PreparedYearlyReview,
        *,
        foreground: bool,
    ) -> YearlyReviewGenerationTask:
        if self._is_ready(prepared.cache_key):
            return self._ready_snapshot(prepared)
        return self._enqueue_prepared(prepared, foreground=foreground).public()

    def get_or_build(
        self,
        year: int,
        context: YearlyReviewFilterContext,
        *,
        timeout: float = 120.0,
    ) -> Artifact:
        """Promote one exact task and wait without owning its execution lifetime."""
        prepared = self._prepare(year, context)
        for _attempt in range(3):
            if self._is_ready(prepared.cache_key):
                return self._build(prepared)
            task = self._enqueue_prepared(prepared, foreground=True)
            if not task.done.wait(timeout=timeout):
                raise YearlyReviewGenerationTimeoutError(
                    f"yearly review generation timed out for {year}"
                )
            if task.state == "ready":
                return task.result if task.result is not None else self._build(prepared)
            refreshed = self._refresh(prepared)
            if refreshed.cache_key != prepared.cache_key:
                prepared = refreshed
                continue
            raise RuntimeError(task.error or "年度总结生成失败")
        raise RuntimeError("年度总结数据连续变化，暂时无法完成生成")

    def status(
        self, year: int, context: YearlyReviewFilterContext
    ) -> YearlyReviewGenerationTask | None:
        prepared = self._prepare(year, context)
        with self._condition:
            task = self._tasks.get(prepared.cache_key)
            if task is not None:
                return task.public()
        if self._is_ready(prepared.cache_key):
            return self._ready_snapshot(prepared)
        return None

    def status_prepared(self, prepared: PreparedYearlyReview) -> YearlyReviewGenerationTask | None:
        with self._condition:
            task = self._tasks.get(prepared.cache_key)
            if task is not None:
                return task.public()
        if self._is_ready(prepared.cache_key):
            return self._ready_snapshot(prepared)
        return None

    def _ready_snapshot(self, prepared: PreparedYearlyReview) -> YearlyReviewGenerationTask:
        now = _now()
        return YearlyReviewGenerationTask(
            year=prepared.year,
            state="ready",
            requested_at=now,
            started_at=None,
            finished_at=now,
        )

    def _enqueue_prepared(
        self,
        prepared: PreparedYearlyReview,
        *,
        foreground: bool,
    ) -> _GenerationTask:
        priority = -100_000 if foreground else -prepared.year
        with self._condition:
            task = self._tasks.get(prepared.cache_key)
            if task is not None and task.state == "ready":
                return task
            if task is not None and task.state == "running":
                return task
            if task is not None and task.state == "queued":
                if priority < task.priority:
                    task.priority = priority
                    task.queue_revision += 1
                    self._push(task)
                return task
            if task is not None and task.state == "failed":
                task.state = "queued"
                task.requested_at = _now()
                task.started_at = None
                task.finished_at = None
                task.error = None
                task.result = None
                task.done = threading.Event()
                task.priority = priority
                task.queue_revision += 1
            else:
                task = _GenerationTask(prepared=prepared, priority=priority)
                self._tasks[prepared.cache_key] = task
            self._push(task)
            self._ensure_worker_locked()
            self._condition.notify()
            return task

    def _push(self, task: _GenerationTask) -> None:
        self._sequence += 1
        heapq.heappush(
            self._queue,
            (
                task.priority,
                self._sequence,
                task.prepared.cache_key,
                task.queue_revision,
            ),
        )

    def _ensure_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="yearly-review-generation-worker",
            daemon=True,
        )
        self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._queue:
                    self._condition.wait()
                _priority, _sequence, key, revision = heapq.heappop(self._queue)
                task = self._tasks.get(key)
                if task is None or task.state != "queued" or task.queue_revision != revision:
                    continue
                task.state = "running"
                task.started_at = _now()

            try:
                refreshed = self._refresh(task.prepared)
                if refreshed.cache_key != task.prepared.cache_key:
                    self._finish_failed(task, "source_revision_changed")
                    self._enqueue_prepared(refreshed, foreground=task.priority < -10_000)
                    continue
                result = self._build(task.prepared)
            except Exception:
                logger.exception("Yearly Review generation failed for %d", task.prepared.year)
                self._finish_failed(task, "generation_failed")
                continue

            with self._condition:
                task.state = "ready"
                task.result = result
                task.finished_at = _now()
                task.done.set()
                self._prune_terminal_locked()
                self._condition.notify_all()

    def _finish_failed(self, task: _GenerationTask, error: str) -> None:
        with self._condition:
            task.state = "failed"
            task.error = error
            task.finished_at = _now()
            task.done.set()
            self._prune_terminal_locked()
            self._condition.notify_all()

    def _prune_terminal_locked(self) -> None:
        terminal = [
            task
            for task in self._tasks.values()
            if task.state in {"ready", "failed"} and task.finished_at is not None
        ]
        overflow = len(terminal) - self._max_terminal_tasks
        if overflow <= 0:
            return
        terminal.sort(key=lambda task: task.finished_at or task.requested_at)
        for task in terminal[:overflow]:
            self._tasks.pop(task.prepared.cache_key, None)
