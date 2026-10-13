"""Cooperative cancellation for request-owned synchronous read stages."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from threading import Event
from typing import TypeVar

import anyio
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request

_T = TypeVar("_T")
_read_cancelled: ContextVar[Event | None] = ContextVar("read_cancelled", default=None)


class RequestReadCancelledError(Exception):
    """The owner disconnected before its next synchronous read stage."""


def check_read_cancelled() -> None:
    signal = _read_cancelled.get()
    if signal is not None and signal.is_set():
        raise RequestReadCancelledError()


async def run_disconnect_aware_read(request: Request, read: Callable[[], _T]) -> _T:
    """Observe disconnects without abandoning a thread or its DB connection.

    Cancellation is request-local, never part of a semantic cache key. A
    cancelled cache owner raises before completing its response; lru_cache
    does not cache the exception and singleflight releases its lock so another
    live waiter can build the complete result with its own request context.
    Shared lower-level cache builders must not check this signal.

    These GET handlers do not consume request bodies. Their observer owns
    receive until the read ends; blocking receive also works through the
    application's BaseHTTPMiddleware, whose cancellation checkpoints prevent
    Request.is_disconnected()'s immediate poll from seeing a disconnect.
    """
    signal = Event()
    token = _read_cancelled.set(signal)

    async def observe_disconnect() -> None:
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                signal.set()
                return

    def run() -> _T:
        check_read_cancelled()
        result = read()
        check_read_cancelled()
        return result

    error: BaseException | None = None
    try:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(observe_disconnect)
            try:
                # Keep AnyIO's default shield: dependency cleanup must wait
                # for the worker to exit, rather than close its DB underneath it.
                result = await run_in_threadpool(run)
            except BaseException as exc:
                # Re-raise outside the task group so existing API exception
                # handlers keep receiving the original HTTP/service exception.
                error = exc
            finally:
                tasks.cancel_scope.cancel()
    finally:
        _read_cancelled.reset(token)
    if isinstance(error, RequestReadCancelledError):
        raise HTTPException(status_code=499, detail="Client disconnected")
    if error is not None:
        raise error
    return result
