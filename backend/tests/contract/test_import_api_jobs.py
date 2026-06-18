from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


class _ImmediateThread:
    def __init__(self, target, daemon=True):
        self._target = target
        self.daemon = daemon

    def start(self):
        self._target()


@pytest.fixture(autouse=True)
def reset_import_jobs():
    from backend.api import import_ as import_api

    import_api._jobs.clear()
    yield
    import_api._jobs.clear()


def test_streaming_import_job_completes_and_exposes_progress(client, monkeypatch):
    from backend.api import import_ as import_api

    progress_events = []

    def fake_import_data(progress_callback):
        progress_callback("读取 Extended Streaming History", 0.4)
        progress_events.append(dict(import_api._jobs))
        return {"files": 2, "records": 3, "artists": 4, "albums": 5, "tracks": 6}

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", fake_import_data)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    job_id = response.json()["job_id"]
    assert len(job_id) == 12
    assert progress_events

    status = client.get(f"/api/import/status/{job_id}").json()
    assert status == {
        "job_id": job_id,
        "status": "done",
        "progress_pct": 1.0,
        "message": "导入完成",
        "result": {"files": 2, "records": 3, "artists": 4, "albums": 5, "tracks": 6},
    }


def test_account_import_job_summarizes_nested_results(client, monkeypatch):
    from backend.api import import_ as import_api

    def fake_import_all(progress_callback):
        progress_callback("导入账号数据", 0.5)
        return {
            "saved_tracks": {"inserted": 10, "skipped": 2, "items": []},
            "profile": {"display_name": "Fixture User", "raw": {"ignored": True}},
            "status": "ok",
        }

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_all", fake_import_all)

    response = client.post("/api/import/account")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "done"
    assert status["progress_pct"] == 1.0
    assert status["message"] == "导入完成"
    assert status["result"] == {
        "saved_tracks.inserted": 10,
        "saved_tracks.skipped": 2,
        "profile.display_name": "Fixture User",
        "status": "ok",
    }


def test_streaming_import_job_records_error_status(client, monkeypatch):
    from backend.api import import_ as import_api

    def failing_import_data(progress_callback):
        progress_callback("读取失败前进度", 0.2)
        raise RuntimeError("fixture import failure")

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", failing_import_data)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert status["progress_pct"] == 0.2
    assert status["message"] == "fixture import failure"
    assert status["result"] is None
