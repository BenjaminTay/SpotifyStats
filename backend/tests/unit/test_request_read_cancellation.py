"""Disconnects stop owned stages without poisoning shared response caches."""

import asyncio
import time
from threading import Event

import anyio
import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request

from backend.core.request_cancellation import (
    check_read_cancelled,
    run_disconnect_aware_read,
)
from backend.services import entity_stats_service as stats

pytestmark = [pytest.mark.unit, pytest.mark.anyio]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def request_channel():
    messages = asyncio.Queue()

    async def receive():
        return messages.get_nowait() if not messages.empty() else await messages.get()

    return Request({"type": "http", "method": "GET", "headers": []}, receive), messages


async def wait_for(predicate):
    with anyio.fail_after(3):
        while not predicate():
            await anyio.sleep(0.001)


async def test_disconnect_does_not_enter_next_stage_or_leak_context():
    request, messages = request_channel()
    started = Event()
    stages = []

    def read():
        stages.append("first")
        started.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            check_read_cancelled()
            time.sleep(0.001)
        stages.append("second")

    async def disconnect():
        await wait_for(started.is_set)
        messages.put_nowait({"type": "http.disconnect"})

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(disconnect)
        with pytest.raises(HTTPException) as caught:
            await run_disconnect_aware_read(request, read)
        assert caught.value.status_code == 499
    assert stages == ["first"]
    check_read_cancelled()
    fresh, _ = request_channel()
    assert await run_disconnect_aware_read(fresh, lambda: {"complete": True}) == {"complete": True}


async def test_exception_cleanup_preserves_error_and_next_read():
    request, _ = request_channel()

    def fail():
        raise ValueError("read failed")

    # The helper handles only its cancellation exception. Other failures retain
    # their original exception, rather than an AnyIO task-group wrapper.
    with pytest.raises(ValueError, match="read failed"):
        await run_disconnect_aware_read(request, fail)
    check_read_cancelled()


@pytest.mark.parametrize("same_key", [True, False])
async def test_cancelled_owner_releases_cache_and_live_client_completes(monkeypatch, same_key):
    owner_request, owner_messages = request_channel()
    live_request, _ = request_channel()
    started = Event()
    live_entered = Event()
    builds = []
    closed = []
    responses = {}

    class Connection:
        def close(self):
            closed.append(self)

    def build(conn, name):
        builds.append(name)
        if len(builds) == 1:
            started.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                check_read_cancelled()
                time.sleep(0.001)
            raise AssertionError("disconnect not observed")
        return {"found": True, "ranks": {"lifetime": 7}}

    monkeypatch.setattr(stats, "get_db", lambda **_: Connection())
    monkeypatch.setattr(stats, "_build_album_stats", build)
    stats._album_stats_cached.cache_clear()

    async def owner():
        with pytest.raises(HTTPException) as caught:
            await run_disconnect_aware_read(
                owner_request, lambda: stats._album_stats_cached(("A",), (1,))
            )
        assert caught.value.status_code == 499

    async def live():
        def read():
            live_entered.set()
            return stats._album_stats_cached(("A" if same_key else "B",), (1,))

        responses["live"] = await run_disconnect_aware_read(live_request, read)

    try:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(owner)
            await wait_for(started.is_set)
            tasks.start_soon(live)
            await wait_for(live_entered.is_set)
            if not same_key:
                await wait_for(lambda: "live" in responses)
            owner_messages.put_nowait({"type": "http.disconnect"})
        assert responses["live"] == {"found": True, "ranks": {"lifetime": 7}}
        assert builds == ["A", "A" if same_key else "B"]
        assert len(closed) == 2
        assert stats._album_stats_cached.singleflight_stats() == {"active_keys": 0}
        assert stats._album_stats_cached.cache_info().currsize == 1
        key = "A" if same_key else "B"
        assert stats._album_stats_cached((key,), (1,)) == responses["live"]
        assert len(builds) == 2
    finally:
        stats._album_stats_cached.cache_clear()


async def test_disconnected_waiter_does_not_cancel_live_owner(monkeypatch):
    owner_request, _ = request_channel()
    waiter_request, waiter_messages = request_channel()
    started = Event()
    waiter_entered = Event()
    release = Event()
    builds = []
    result = {}

    class Connection:
        def close(self):
            pass

    def build(conn, name):
        builds.append(name)
        started.set()
        assert release.wait(3)
        check_read_cancelled()
        return {"found": True, "ranks": {"lifetime": 4}}

    monkeypatch.setattr(stats, "get_db", lambda **_: Connection())
    monkeypatch.setattr(stats, "_build_album_stats", build)
    stats._album_stats_cached.cache_clear()

    async def owner():
        result["owner"] = await run_disconnect_aware_read(
            owner_request, lambda: stats._album_stats_cached(("A",), (1,))
        )

    async def waiter():
        def read():
            waiter_entered.set()
            return stats._album_stats_cached(("A",), (1,))

        with pytest.raises(HTTPException) as caught:
            await run_disconnect_aware_read(waiter_request, read)
        assert caught.value.status_code == 499

    try:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(owner)
            await wait_for(started.is_set)
            tasks.start_soon(waiter)
            await wait_for(waiter_entered.is_set)
            waiter_messages.put_nowait({"type": "http.disconnect"})
            await anyio.sleep(0.1)
            release.set()
        assert result["owner"] == {"found": True, "ranks": {"lifetime": 4}}
        assert builds == ["A"]
        assert stats._album_stats_cached.singleflight_stats() == {"active_keys": 0}
    finally:
        release.set()
        stats._album_stats_cached.cache_clear()
