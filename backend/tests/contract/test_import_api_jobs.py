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
def reset_import_jobs(monkeypatch):
    from backend.api import import_ as import_api

    import_api._jobs.clear()
    monkeypatch.setattr(
        import_api,
        "inspect_data_sources",
        lambda streaming_dir, account_dir: {"status": "healthy", "blockers": [], "warnings": []},
    )
    monkeypatch.setattr(
        import_api,
        "create_database_snapshot",
        lambda job_id: {"status": "skipped", "reason": "test"},
    )
    monkeypatch.setattr(
        import_api,
        "_post_streaming_health_summary",
        lambda: {
            "status": "healthy",
            "blockers": [],
            "warnings": [],
            "play_count": 3,
            "sqlite_integrity": "ok",
            "orphan_play_track_count": 0,
            "orphan_play_album_count": 0,
        },
    )
    yield
    import_api._jobs.clear()


def test_streaming_import_job_completes_and_exposes_progress(client, monkeypatch):
    from backend.api import import_ as import_api

    progress_events = []

    def fake_import_data(progress_callback, build_preaggregations=True):
        progress_callback("读取 Extended Streaming History", 0.4)
        progress_events.append(dict(import_api._jobs))
        return {"files": 2, "records": 3, "artists": 4, "albums": 5, "tracks": 6}

    def fake_maintenance(progress_callback):
        progress_callback("维护派生数据", 0.8)
        return {"maintenance_status": "ok"}

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    monkeypatch.setattr(
        import_api, "run_post_streaming_import_maintenance", fake_maintenance, raising=False
    )

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
        "result": {
            "files": 2,
            "records": 3,
            "artists": 4,
            "albums": 5,
            "tracks": 6,
            "duplicate_records_skipped": 0,
            "database_snapshot": {"status": "skipped", "reason": "test"},
            "post_import_health": {
                "status": "healthy",
                "blockers": [],
                "warnings": [],
                "play_count": 3,
                "sqlite_integrity": "ok",
                "orphan_play_track_count": 0,
                "orphan_play_album_count": 0,
            },
            "maintenance_status": "ok",
        },
    }


def test_import_preflight_is_read_only_and_has_response_contract(client, monkeypatch, tmp_path):
    from backend.api import import_ as import_api
    from backend.domains.imports.source_inspector import inspect_data_sources

    streaming_dir = tmp_path / "streaming"
    account_dir = tmp_path / "account"
    streaming_dir.mkdir()
    account_dir.mkdir()
    (streaming_dir / "Streaming_History_Audio_000.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(import_api, "DATA_DIR", str(streaming_dir))
    monkeypatch.setattr(import_api, "ACCOUNT_DATA_DIR", str(account_dir))
    monkeypatch.setattr(import_api, "inspect_data_sources", inspect_data_sources)

    response = client.get("/api/import/preflight")

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["streaming_files"][0]["file_name"] == "Streaming_History_Audio_000.json"
    assert "X-Request-ID" in response.headers


def test_import_health_has_nested_database_and_derived_sections(client):
    response = client.get("/api/import/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "partial", "blocked", "stale", "failed"}
    assert isinstance(payload["checked_at"], str)
    assert "play_count" in payload["database"]
    assert "billboard_aggregates_ready" in payload["derived"]
    assert isinstance(payload["issues"], list)
    if payload["issues"]:
        assert {"code", "severity", "affected_play_count", "recommended_action"}.issubset(
            payload["issues"][0]
        )


def test_streaming_import_job_runs_derived_maintenance_before_done(client, monkeypatch):
    from backend.api import import_ as import_api

    events = []

    def fake_import_data(progress_callback, build_preaggregations=True):
        events.append(("import", build_preaggregations))
        progress_callback("导入基础播放", 0.5)
        return {"total_records": 3, "unique_artists": 1, "unique_albums": 1, "unique_tracks": 1}

    def fake_maintenance(progress_callback):
        events.append(("maintenance", None))
        progress_callback("维护派生数据", 0.9)
        return {
            "maintenance_status": "ok",
            "tracks_metadata_updated": 2,
            "albums_metadata_updated": 1,
            "album_projects_rebuilt": True,
            "agg_track_wks": 3,
            "agg_album_wks": 2,
            "unresolved_recent_tracks": 0,
            "unresolved_recent_albums": 0,
        }

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    monkeypatch.setattr(
        import_api, "run_post_streaming_import_maintenance", fake_maintenance, raising=False
    )

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert events == [("import", False), ("maintenance", None)]
    assert status["status"] == "done"
    assert status["result"]["maintenance_status"] == "ok"
    assert status["result"]["album_projects_rebuilt"] is True
    assert status["result"]["database_snapshot"]["status"] == "skipped"


def test_streaming_import_blocks_before_snapshot_when_preflight_has_blockers(client, monkeypatch):
    from backend.api import import_ as import_api

    snapshot_calls = []
    import_calls = []

    monkeypatch.setattr(
        import_api,
        "inspect_data_sources",
        lambda streaming_dir, account_dir: {
            "status": "blocked",
            "blockers": ["存在完全重复文件"],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        import_api,
        "create_database_snapshot",
        lambda job_id: snapshot_calls.append(job_id),
    )
    monkeypatch.setattr(
        import_api,
        "import_data",
        lambda **kwargs: import_calls.append(kwargs),
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "blocked"
    assert status["progress_pct"] == 0.0
    assert status["result"]["import_started"] is False
    assert snapshot_calls == []
    assert import_calls == []


def test_streaming_import_requires_warning_confirmation_then_runs(client, monkeypatch):
    from backend.api import import_ as import_api

    import_calls = []
    monkeypatch.setattr(
        import_api,
        "inspect_data_sources",
        lambda streaming_dir, account_dir: {
            "status": "partial",
            "blockers": [],
            "warnings": ["日期范围重叠"],
        },
    )
    monkeypatch.setattr(
        import_api,
        "import_data",
        lambda progress_callback, build_preaggregations=True: (
            import_calls.append(True) or {"total_records": 1}
        ),
    )
    monkeypatch.setattr(
        import_api,
        "run_post_streaming_import_maintenance",
        lambda progress_callback: {"maintenance_status": "ok"},
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    first_response = client.post("/api/import/streaming")
    first_job_id = first_response.json()["job_id"]
    first_status = client.get(f"/api/import/status/{first_job_id}").json()
    assert first_status["status"] == "needs_confirmation"
    assert first_status["result"]["import_started"] is False
    assert import_calls == []

    confirmed_response = client.post("/api/import/streaming?confirm_warnings=true")
    confirmed_job_id = confirmed_response.json()["job_id"]
    confirmed_status = client.get(f"/api/import/status/{confirmed_job_id}").json()
    assert confirmed_status["status"] == "done"
    assert import_calls == [True]


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
        "database_snapshot": {"status": "skipped", "reason": "test"},
    }


def test_streaming_import_job_records_error_status(client, monkeypatch):
    from backend.api import import_ as import_api

    def failing_import_data(progress_callback, build_preaggregations=True):
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
    assert status["result"] == {
        "database_snapshot": {"status": "skipped", "reason": "test"},
        "rollback": {"status": "not_needed"},
    }


def test_streaming_import_restores_snapshot_when_import_fails(client, monkeypatch):
    from backend.api import import_ as import_api

    snapshot = {
        "status": "created",
        "path": "/tmp/spotify-stats-import-snapshot.db",
    }
    rollback_calls = []

    def failing_import_data(progress_callback, build_preaggregations=True):
        raise RuntimeError("fixture destructive import failure")

    def fake_restore(snapshot_path):
        rollback_calls.append(snapshot_path)
        return {"status": "restored", "path": snapshot_path}

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "create_database_snapshot", lambda job_id: snapshot)
    monkeypatch.setattr(import_api, "restore_database_snapshot", fake_restore)
    monkeypatch.setattr(import_api, "import_data", failing_import_data)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert rollback_calls == [snapshot["path"]]
    assert status["result"]["rollback"]["status"] == "restored"


def test_streaming_import_restores_snapshot_when_maintenance_fails(client, monkeypatch):
    from backend.api import import_ as import_api

    snapshot = {"status": "created", "path": "/tmp/maintenance-failure-snapshot.db"}
    rollback_calls = []

    def fake_import_data(progress_callback, build_preaggregations=True):
        return {"total_records": 2}

    def failing_maintenance(progress_callback):
        raise RuntimeError("fixture maintenance failure")

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "create_database_snapshot", lambda job_id: snapshot)
    monkeypatch.setattr(
        import_api,
        "restore_database_snapshot",
        lambda snapshot_path: rollback_calls.append(snapshot_path) or {"status": "restored"},
    )
    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    monkeypatch.setattr(import_api, "run_post_streaming_import_maintenance", failing_maintenance)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert status["message"] == "fixture maintenance failure"
    assert rollback_calls == [snapshot["path"]]


def test_streaming_import_restores_snapshot_when_post_import_health_fails(client, monkeypatch):
    from backend.api import import_ as import_api

    snapshot = {"status": "created", "path": "/tmp/post-health-failure-snapshot.db"}
    rollback_calls = []

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "create_database_snapshot", lambda job_id: snapshot)
    monkeypatch.setattr(
        import_api,
        "restore_database_snapshot",
        lambda snapshot_path: rollback_calls.append(snapshot_path) or {"status": "restored"},
    )
    monkeypatch.setattr(import_api, "import_data", lambda **kwargs: {"total_records": 2})
    monkeypatch.setattr(
        import_api,
        "run_post_streaming_import_maintenance",
        lambda progress_callback: {"maintenance_status": "ok"},
    )
    monkeypatch.setattr(
        import_api,
        "_post_streaming_health_summary",
        lambda: {
            "status": "blocked",
            "blockers": ["SQLite 完整性检查结果为 damaged"],
            "warnings": [],
            "play_count": 2,
            "sqlite_integrity": "damaged",
            "orphan_play_track_count": 0,
            "orphan_play_album_count": 0,
        },
    )

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert "导入后健康检查未通过" in status["message"]
    assert rollback_calls == [snapshot["path"]]


def test_import_job_does_not_start_while_another_import_holds_slot(client, monkeypatch):
    from backend.api import import_ as import_api

    assert import_api._import_lock.acquire(blocking=False)
    try:
        monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
        response = client.post("/api/import/streaming")

        assert response.status_code == 200
        job_id = response.json()["job_id"]
        status = client.get(f"/api/import/status/{job_id}").json()
        assert status["status"] == "error"
        assert status["message"] == "已有导入任务正在运行，本次导入未开始"
        assert status["result"] is None
    finally:
        import_api._import_lock.release()


def test_import_progress_callback_clamps_status_percent(client, monkeypatch):
    from backend.api import import_ as import_api

    observed = []

    def fake_import_data(progress_callback, build_preaggregations=True):
        progress_callback("negative progress", -0.5)
        observed.append(next(iter(import_api._jobs.values()))["progress_pct"])
        progress_callback("overflow progress", 1.5)
        observed.append(next(iter(import_api._jobs.values()))["progress_pct"])
        raise RuntimeError("stop after progress probes")

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", fake_import_data)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    assert observed == [0.0, 1.0]
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert status["progress_pct"] == 1.0
