"""Cooperative cancellation tokens for in-process AI task workers.

The database remains the durable source of truth.  Tokens only shorten the
time between an API cancellation request and a worker noticing it.
"""

from __future__ import annotations

import threading


class AgentCancellationToken:
    """Thread-safe, cooperative cancellation signal."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class AgentCancellationRegistry:
    """Small process-local registry; durable state is stored in SQLite."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens: dict[str, AgentCancellationToken] = {}

    def token_for(self, task_id: str) -> AgentCancellationToken:
        with self._lock:
            return self._tokens.setdefault(task_id, AgentCancellationToken())

    def request_cancel(self, task_id: str) -> None:
        self.token_for(task_id).cancel()

    def is_cancel_requested(self, task_id: str) -> bool:
        with self._lock:
            token = self._tokens.get(task_id)
            return bool(token and token.is_cancelled)

    def discard(self, task_id: str) -> None:
        with self._lock:
            self._tokens.pop(task_id, None)


cancellation_registry = AgentCancellationRegistry()
