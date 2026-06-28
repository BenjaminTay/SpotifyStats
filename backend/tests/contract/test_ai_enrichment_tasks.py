from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

import backend.api.ai_tasks as ai_tasks_api
from backend.core.db import get_db
from backend.services import ai_task_service, wikipedia_service

pytestmark = pytest.mark.contract


class SyncThread:
    def __init__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[Any, ...] = (),
        daemon: bool | None = None,
    ):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        self.target(*self.args)


def _latest_running_task_id(task_type: str) -> str:
    conn = get_db(readonly=True)
    try:
        row = conn.execute(
            """SELECT task_id FROM ai_task_runs
               WHERE task_type = ? AND status = 'running'
               ORDER BY created_at DESC, task_id DESC
               LIMIT 1""",
            (task_type,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row["task_id"]


def test_artist_enrichment_task_endpoint_runs_sync_and_persists_result(
    client,
    monkeypatch,
):
    wiki_payload = {
        "title": "Example Artist",
        "lang": "en",
        "url": "https://en.wikipedia.org/wiki/Example_Artist",
        "summary": "Example Artist biography.",
        "description": "singer",
        "thumbnail": "",
        "sections": {"early_life": "Started early.", "discography": "Two albums."},
    }

    def fake_get_artist_wiki(
        artist_name: str,
        progress_callback: Callable[[str, str], None] | None = None,
        should_continue: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        del should_continue
        assert artist_name == "Example Artist"
        assert progress_callback is not None
        progress_callback("checking_cache", "正在检查艺人 Wikipedia 缓存")
        progress_callback("fetching_external_data", "正在获取艺人 Wikipedia 外部资料")
        progress_callback("calling_llm", "正在调用 LLM 整理艺人百科")
        progress_callback("saving_cache", "正在保存艺人 Wikipedia 缓存")
        return wiki_payload

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(wikipedia_service, "get_artist_wiki", fake_get_artist_wiki)

    create_response = client.post(
        "/api/ai/tasks/enrichment/artist",
        json={"artist_name": "Example Artist"},
    )

    assert create_response.status_code == 200
    assert create_response.headers["x-request-id"]
    task_id = create_response.json()["task_id"]

    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "done"
    assert status_payload["stage"] == "done"
    assert status_payload["result"] == {"wiki": wiki_payload, "genius": None}
    assert events_payload["found"] is True
    stages = [event["stage"] for event in events_payload["events"]]
    assert "checking_cache" in stages
    assert "fetching_external_data" in stages
    assert "calling_llm" in stages
    assert "saving_cache" in stages
    assert stages[-1] == "done"


def test_album_enrichment_task_done_when_wikipedia_returns_none(client, monkeypatch):
    def fake_get_album_wiki(
        album_name: str,
        artist_name: str,
        progress_callback: Callable[[str, str], None] | None = None,
        should_continue: Callable[[], bool] | None = None,
    ) -> None:
        del should_continue
        assert album_name == "Missing Album"
        assert artist_name == "Missing Artist"
        assert progress_callback is not None
        progress_callback("checking_cache", "正在检查专辑 Wikipedia 缓存")
        progress_callback("fetching_external_data", "未找到专辑 Wikipedia 页面")
        progress_callback("saving_cache", "正在保存空专辑 Wikipedia 缓存")
        return None

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(wikipedia_service, "get_album_wiki", fake_get_album_wiki)

    create_response = client.post(
        "/api/ai/tasks/enrichment/album",
        json={"album_name": "Missing Album", "artist_name": "Missing Artist"},
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()

    assert status_payload["status"] == "done"
    assert status_payload["stage"] == "done"
    assert status_payload["result"] == {"wiki": None, "genius": None}


def test_enrichment_task_does_not_overwrite_cancelled_task_or_append_late_events(
    client,
    monkeypatch,
):
    def fake_get_artist_wiki(
        artist_name: str,
        progress_callback: Callable[[str, str], None] | None = None,
        should_continue: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        del should_continue
        assert artist_name == "Cancel Artist"
        assert progress_callback is not None
        progress_callback("checking_cache", "正在检查艺人 Wikipedia 缓存")
        ai_task_service.cancel_task(_latest_running_task_id("ai_enrichment_artist"))
        progress_callback("fetching_external_data", "取消后的晚到外部资料事件")
        return {"title": "Cancel Artist"}

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(wikipedia_service, "get_artist_wiki", fake_get_artist_wiki)

    create_response = client.post(
        "/api/ai/tasks/enrichment/artist",
        json={"artist_name": "Cancel Artist"},
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "cancelled"
    assert status_payload["stage"] == "cancelled"
    assert status_payload.get("result") is None
    assert "取消后的晚到外部资料事件" not in [
        event["message"] for event in events_payload["events"]
    ]
    assert events_payload["events"][-1]["stage"] == "cancelled"
    assert events_payload["events"][-1]["event_type"] == "stage_completed"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/ai/tasks/enrichment/artist", {}),
        ("/api/ai/tasks/enrichment/artist", {"artist_name": ""}),
        ("/api/ai/tasks/enrichment/album", {"album_name": "Only Album"}),
        ("/api/ai/tasks/enrichment/album", {"album_name": "", "artist_name": "Artist"}),
        ("/api/ai/tasks/enrichment/album", {"album_name": "Album", "artist_name": ""}),
    ],
)
def test_enrichment_task_endpoints_reject_missing_or_empty_fields(
    client,
    monkeypatch,
    path: str,
    payload: dict[str, Any],
):
    monkeypatch.setattr(
        ai_tasks_api,
        "start_artist_enrichment_task",
        lambda request: pytest.fail("invalid artist enrichment request must not start a task"),
        raising=False,
    )
    monkeypatch.setattr(
        ai_tasks_api,
        "start_album_enrichment_task",
        lambda request: pytest.fail("invalid album enrichment request must not start a task"),
        raising=False,
    )

    response = client.post(path, json=payload)

    assert response.status_code == 422
    assert response.headers["x-request-id"]
