"""Actual ASGI middleware must forward disconnects to album rank reads."""

import asyncio
import json
import time
from threading import Event
from types import SimpleNamespace

import anyio
import pytest
from fastapi import HTTPException

from backend.api import music
from backend.core.request_cancellation import check_read_cancelled
from backend.dependencies import PlayFilters, get_conn
from backend.main import app

pytestmark = [pytest.mark.contract, pytest.mark.anyio]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize(
    "path", ["/api/music/albums/Album/stats", "/api/music/album-projects/1/stats"]
)
@pytest.mark.parametrize("outcome", ["disconnect", "normal", "unavailable", "base_stats"])
async def test_album_stats_disconnect_and_cleanup_through_full_middleware(
    monkeypatch, path, outcome
):
    messages = asyncio.Queue()
    messages.put_nowait({"type": "http.request", "body": b"", "more_body": False})
    received = []
    stages = []
    started = Event()
    closed = Event()
    worker_finished = Event()

    class Connection:
        def close(self):
            assert worker_finished.is_set(), "dependency closed while worker still owns connection"
            closed.set()

    def connection():
        conn = Connection()
        try:
            yield conn
        finally:
            conn.close()

    def read(conn, *args, **kwargs):
        try:
            stages.append("first")
            started.set()
            if outcome == "disconnect":
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    check_read_cancelled()
                    time.sleep(0.001)
                raise AssertionError("full middleware did not propagate disconnect")
            if outcome == "unavailable":
                raise HTTPException(status_code=503, detail={"error": "snapshot_unavailable"})
            assert kwargs["include_rank_context"] == (outcome != "base_stats")
            stages.append("second")
            return {"found": False}
        finally:
            worker_finished.set()

    monkeypatch.setattr(music, "get_album_stats", read)
    monkeypatch.setattr(
        music,
        "_album_project_or_404",
        lambda *args: SimpleNamespace(canonical_name="Album", artist_name="Artist"),
    )
    monkeypatch.setattr(music, "_attach_requested_album_identity", lambda result, _: result)
    filters = SimpleNamespace(
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
    )
    monkeypatch.setitem(app.dependency_overrides, get_conn, connection)
    monkeypatch.setitem(app.dependency_overrides, PlayFilters, lambda: filters)

    async def receive():
        return messages.get_nowait() if not messages.empty() else await messages.get()

    async def send(message):
        received.append(message)

    async def disconnect():
        with anyio.fail_after(3):
            while not started.is_set():
                await anyio.sleep(0.001)
        messages.put_nowait({"type": "http.disconnect"})

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "scheme": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"include_rank_context=false" if outcome == "base_stats" else b"",
        "headers": [(b"host", b"localhost")],
        "client": ("127.0.0.1", 10000),
        "server": ("127.0.0.1", 8000),
    }
    with anyio.fail_after(5):
        async with anyio.create_task_group() as tasks:
            if outcome == "disconnect":
                tasks.start_soon(disconnect)
            await app(scope, receive, send)
    assert closed.is_set()
    check_read_cancelled()
    response = next(message for message in received if message["type"] == "http.response.start")
    assert (
        response["status"]
        == {
            "disconnect": 499,
            "normal": 200,
            "unavailable": 503,
            "base_stats": 200,
        }[outcome]
    )
    assert any(key == b"x-request-id" for key, _ in response["headers"])
    assert stages == (
        ["first"] if outcome in {"disconnect", "unavailable"} else ["first", "second"]
    )
    if outcome != "disconnect":
        body = b"".join(x.get("body", b"") for x in received if x["type"] == "http.response.body")
        assert json.loads(body) == (
            {"detail": {"error": "snapshot_unavailable"}}
            if outcome == "unavailable"
            else music.EntityStatsResponse(found=False).model_dump(mode="json")
        )
