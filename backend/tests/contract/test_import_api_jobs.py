from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.domains.imports.incremental import FingerprintRecord, build_import_plan
from backend.services.import_plan_service import StreamingImportAssessment

pytestmark = pytest.mark.contract


class _ImmediateThread:
    def __init__(self, target, daemon=True):
        self._target = target
        self.daemon = daemon

    def start(self):
        self._target()


def _assessment(*, blockers=None, warnings=None, plan=None) -> StreamingImportAssessment:
    plan = plan or build_import_plan([FingerprintRecord(source_type="audio", fingerprint="a" * 64)])
    return StreamingImportAssessment(
        report={
            "status": "blocked" if blockers else ("partial" if warnings else "healthy"),
            "blockers": list(blockers or []),
            "warnings": list(warnings or []),
            "requires_confirmation": False,
            "confirmation_token": "token-v1",
            "requested_mode": "auto",
            "planned_actions": [],
        },
        plan=plan,
        baseline_status="missing",
        existing_account_identity_hash=None,
        incoming_account_identity_hash=None,
    )


@pytest.fixture(autouse=True)
def reset_import_jobs(monkeypatch):
    from backend.api import import_ as import_api

    import_api._jobs.clear()
    monkeypatch.setattr(
        import_api, "assess_streaming_import", lambda *args, **kwargs: _assessment()
    )
    monkeypatch.setattr(import_api, "_publish_import_state", lambda *args, **kwargs: None)
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

    def fake_import_data(progress_callback, build_preaggregations=True, **kwargs):
        progress_callback("读取 Extended Streaming History", 0.4)
        progress_events.append(dict(import_api._jobs))
        return {"files": 2, "records": 3, "artists": 4, "albums": 5, "tracks": 6}

    def fake_maintenance(progress_callback, defer_music_search_snapshots=False):
        assert defer_music_search_snapshots is True
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
            "unchanged_records": 0,
            "inserted_records": 0,
            "active_records": 0,
            "detected_relation": "baseline_required",
            "executed_strategy": "full",
            "noop": False,
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
    from backend.core.db import get_db

    streaming_dir = tmp_path / "streaming"
    account_dir = tmp_path / "account"
    streaming_dir.mkdir()
    account_dir.mkdir()
    (streaming_dir / "Streaming_History_Audio_000.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(import_api, "DATA_DIR", str(streaming_dir))
    monkeypatch.setattr(import_api, "ACCOUNT_DATA_DIR", str(account_dir))

    conn = get_db(readonly=True)
    try:
        run_count_before = conn.execute("SELECT COUNT(*) FROM playback_import_runs").fetchone()[0]
    finally:
        conn.close()

    response = client.get("/api/import/preflight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["streaming_files"][0]["file_name"] == "Streaming_History_Audio_000.json"
    assert payload["fingerprint_baseline_status"] == "missing"
    assert payload["detected_relation"] == "baseline_required"
    assert payload["requested_mode"] == "auto"
    assert payload["estimated_strategy"] == "full"
    assert payload["planned_actions"]
    assert payload["comparison_status"] == "baseline_missing"
    assert payload["record_delta_comparable"] is False
    assert "X-Request-ID" in response.headers

    conn = get_db(readonly=True)
    try:
        run_count_after = conn.execute("SELECT COUNT(*) FROM playback_import_runs").fetchone()[0]
    finally:
        conn.close()
    assert run_count_after == run_count_before


def test_cleanup_preview_is_bounded_and_read_only(client):
    from backend.core.db import get_db

    conn = get_db(readonly=True)
    try:
        play_count_before = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    finally:
        conn.close()

    response = client.post("/api/import/governance/cleanup-preview?sample_limit=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["writes_performed"] is False
    assert len(payload["preview_token"]) == 64
    assert all(len(group["samples"]) <= 3 for group in payload["groups"])
    assert "audio_without_track" in payload["excluded_issue_codes"]

    conn = get_db(readonly=True)
    try:
        play_count_after = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    finally:
        conn.close()
    assert play_count_after == play_count_before


@pytest.mark.parametrize("sample_limit", [0, 101])
def test_cleanup_preview_rejects_out_of_range_sample_limit(client, sample_limit):
    response = client.post(
        "/api/import/governance/cleanup-preview",
        params={"sample_limit": sample_limit},
    )

    assert response.status_code == 422


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

    def fake_import_data(progress_callback, build_preaggregations=True, **kwargs):
        events.append(("import", build_preaggregations, kwargs["mode"]))
        progress_callback("导入基础播放", 0.5)
        return {"total_records": 3, "unique_artists": 1, "unique_albums": 1, "unique_tracks": 1}

    def fake_maintenance(progress_callback, defer_music_search_snapshots=False):
        events.append(("maintenance", defer_music_search_snapshots))
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
        import_api,
        "_publish_import_state",
        lambda assessment, result, executed_strategy: events.append(("publish", executed_strategy)),
    )
    monkeypatch.setattr(
        import_api, "run_post_streaming_import_maintenance", fake_maintenance, raising=False
    )

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert events == [
        ("import", False, "replace"),
        ("publish", "full"),
        ("maintenance", True),
    ]
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
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(blockers=["存在完全重复文件"]),
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
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(warnings=["日期范围重叠"]),
    )
    monkeypatch.setattr(
        import_api,
        "import_data",
        lambda progress_callback, build_preaggregations=True, **kwargs: (
            import_calls.append(True) or {"total_records": 1}
        ),
    )
    monkeypatch.setattr(
        import_api,
        "run_post_streaming_import_maintenance",
        lambda progress_callback, defer_music_search_snapshots=False: {"maintenance_status": "ok"},
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    first_response = client.post("/api/import/streaming")
    first_job_id = first_response.json()["job_id"]
    first_status = client.get(f"/api/import/status/{first_job_id}").json()
    assert first_status["status"] == "needs_confirmation"
    assert first_status["result"]["import_started"] is False
    assert import_calls == []

    confirmed_response = client.post(
        "/api/import/streaming?confirm_warnings=true&confirmation_token=token-v1"
    )
    confirmed_job_id = confirmed_response.json()["job_id"]
    confirmed_status = client.get(f"/api/import/status/{confirmed_job_id}").json()
    assert confirmed_status["status"] == "done"
    assert import_calls == [True]


def test_streaming_import_rejects_confirmation_for_a_changed_plan(client, monkeypatch):
    from backend.api import import_ as import_api

    import_calls = []
    monkeypatch.setattr(
        import_api,
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(warnings=["日期范围重叠"]),
    )
    monkeypatch.setattr(
        import_api,
        "import_data",
        lambda **kwargs: import_calls.append(kwargs),
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post(
        "/api/import/streaming?confirm_warnings=true&confirmation_token=stale-token"
    )
    status = client.get(f"/api/import/status/{response.json()['job_id']}").json()

    assert status["status"] == "needs_confirmation"
    assert "已变化" in status["message"]
    assert status["result"]["confirmation_reason"] == "stale_plan"
    assert status["result"]["preflight"]["confirmation_token"] == "token-v1"
    assert import_calls == []


def test_streaming_import_rejects_a_stale_displayed_plan_without_confirmation_flags(
    client, monkeypatch
):
    from backend.api import import_ as import_api

    import_calls = []
    monkeypatch.setattr(
        import_api,
        "import_data",
        lambda **kwargs: import_calls.append(kwargs),
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post("/api/import/streaming?confirmation_token=stale-token")
    status = client.get(f"/api/import/status/{response.json()['job_id']}").json()

    assert status["status"] == "needs_confirmation"
    assert status["result"]["confirmation_reason"] == "stale_plan"
    assert import_calls == []


def test_legacy_baseline_explicit_replace_still_requires_confirmation(client, monkeypatch):
    from backend.api import import_ as import_api

    plan = replace(
        build_import_plan([FingerprintRecord(source_type="audio", fingerprint="a" * 64)]),
        existing_count=10,
        requires_confirmation=True,
    )
    import_calls = []
    monkeypatch.setattr(
        import_api,
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(plan=plan),
    )
    monkeypatch.setattr(
        import_api,
        "import_data",
        lambda **kwargs: import_calls.append(kwargs),
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post("/api/import/streaming?mode=replace")
    status = client.get(f"/api/import/status/{response.json()['job_id']}").json()

    assert status["status"] == "needs_confirmation"
    assert import_calls == []


def test_identical_auto_import_is_noop_before_snapshot(client, monkeypatch):
    from backend.api import import_ as import_api

    record = FingerprintRecord(source_type="audio", fingerprint="a" * 64)
    plan = build_import_plan([record], existing_records=[record])
    snapshot_calls = []
    import_calls = []
    maintenance_calls = []
    monkeypatch.setattr(
        import_api,
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(plan=plan),
    )
    monkeypatch.setattr(
        import_api,
        "_complete_noop_import",
        lambda *args, **kwargs: {
            "detected_relation": "identical",
            "executed_strategy": "noop",
            "noop": True,
            "records": 1,
        },
    )
    monkeypatch.setattr(
        import_api,
        "create_database_snapshot",
        lambda job_id: snapshot_calls.append(job_id),
    )
    monkeypatch.setattr(import_api, "import_data", lambda **kwargs: import_calls.append(kwargs))
    monkeypatch.setattr(
        import_api,
        "run_post_streaming_import_maintenance",
        lambda **kwargs: maintenance_calls.append(kwargs),
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post("/api/import/streaming?mode=auto")
    status = client.get(f"/api/import/status/{response.json()['job_id']}").json()

    assert status["status"] == "done"
    assert status["message"] == "输入数据未变化，跳过导入"
    assert status["result"]["executed_strategy"] == "noop"
    assert snapshot_calls == []
    assert import_calls == []
    assert maintenance_calls == []


def test_snapshot_superset_auto_import_uses_append(client, monkeypatch):
    from backend.api import import_ as import_api

    old = FingerprintRecord(source_type="audio", fingerprint="a" * 64)
    new = FingerprintRecord(source_type="audio", fingerprint="b" * 64)
    plan = build_import_plan([old, new], existing_records=[old])
    import_modes = []
    monkeypatch.setattr(
        import_api,
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(plan=plan),
    )

    def fake_import_data(**kwargs):
        import_modes.append(kwargs["mode"])
        return {
            "inserted_records": 1,
            "unchanged_records": 1,
            "active_records": 2,
            "generation_id": kwargs["generation_id"],
        }

    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    monkeypatch.setattr(
        import_api,
        "run_post_streaming_import_maintenance",
        lambda **kwargs: {"maintenance_status": "ok"},
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post("/api/import/streaming?mode=auto")
    status = client.get(f"/api/import/status/{response.json()['job_id']}").json()

    assert status["status"] == "done"
    assert import_modes == ["append"]
    assert status["result"]["detected_relation"] == "snapshot_superset"
    assert status["result"]["executed_strategy"] == "incremental"
    assert status["result"]["inserted_records"] == 1


def test_reconcile_auto_requires_bound_confirmation_and_passes_exact_scope(client, monkeypatch):
    from backend.api import import_ as import_api

    def record(char: str, day: int) -> FingerprintRecord:
        return FingerprintRecord(
            source_type="audio",
            fingerprint=char * 64,
            timestamp=datetime(2026, 8, day, tzinfo=timezone.utc),
        )

    first = record("a", 1)
    removed = record("b", 2)
    added = record("c", 2)
    latest = record("d", 3)
    plan = build_import_plan(
        [first, added, latest],
        existing_records=[first, removed, latest],
        existing_account_identity_hash="same-account",
        incoming_account_identity_hash="same-account",
    )
    import_calls = []
    monkeypatch.setattr(
        import_api,
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(plan=plan),
    )

    def fake_import_data(**kwargs):
        import_calls.append(kwargs)
        return {
            "inserted_records": 1,
            "unchanged_records": 2,
            "active_records": 3,
            "generation_id": kwargs["generation_id"],
        }

    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    monkeypatch.setattr(
        import_api,
        "run_post_streaming_import_maintenance",
        lambda **kwargs: {"maintenance_status": "ok"},
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    unconfirmed = client.post("/api/import/streaming?mode=auto")
    unconfirmed_status = client.get(f"/api/import/status/{unconfirmed.json()['job_id']}").json()
    stale = client.post(
        "/api/import/streaming?mode=auto&confirm_plan=true&confirmation_token=stale"
    )
    stale_status = client.get(f"/api/import/status/{stale.json()['job_id']}").json()
    confirmed = client.post(
        "/api/import/streaming?mode=auto&confirm_plan=true&confirmation_token=token-v1"
    )
    confirmed_status = client.get(f"/api/import/status/{confirmed.json()['job_id']}").json()

    assert unconfirmed_status["status"] == "needs_confirmation"
    assert stale_status["status"] == "needs_confirmation"
    assert stale_status["result"]["confirmation_reason"] == "stale_plan"
    assert confirmed_status["status"] == "done"
    assert confirmed_status["result"]["executed_strategy"] == "reconcile"
    assert len(import_calls) == 1
    assert import_calls[0]["mode"] == "reconcile"
    assert import_calls[0]["expected_previous_digest"] == plan.previous_digest
    assert import_calls[0]["removed_identities"] == plan.removed
    assert "removed_identities" not in confirmed_status["result"]


def test_ambiguous_auto_requires_explicit_confirmed_replace(client, monkeypatch):
    from backend.api import import_ as import_api

    old = FingerprintRecord(source_type="audio", fingerprint="a" * 64)
    new = FingerprintRecord(source_type="audio", fingerprint="b" * 64)
    plan = build_import_plan([new], existing_records=[old])
    import_modes = []
    monkeypatch.setattr(
        import_api,
        "assess_streaming_import",
        lambda *args, **kwargs: _assessment(plan=plan),
    )
    monkeypatch.setattr(
        import_api,
        "import_data",
        lambda **kwargs: (
            import_modes.append(kwargs["mode"]) or {"inserted_records": 1, "active_records": 1}
        ),
    )
    monkeypatch.setattr(
        import_api,
        "run_post_streaming_import_maintenance",
        lambda **kwargs: {"maintenance_status": "ok"},
    )
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    auto = client.post(
        "/api/import/streaming?mode=auto&confirm_plan=true&confirmation_token=token-v1"
    )
    auto_status = client.get(f"/api/import/status/{auto.json()['job_id']}").json()
    unconfirmed = client.post("/api/import/streaming?mode=replace")
    unconfirmed_status = client.get(f"/api/import/status/{unconfirmed.json()['job_id']}").json()
    confirmed = client.post(
        "/api/import/streaming?mode=replace&confirm_plan=true&confirmation_token=token-v1"
    )
    confirmed_status = client.get(f"/api/import/status/{confirmed.json()['job_id']}").json()

    assert auto_status["status"] == "needs_confirmation"
    assert unconfirmed_status["status"] == "needs_confirmation"
    assert confirmed_status["status"] == "done"
    assert confirmed_status["result"]["executed_strategy"] == "full"
    assert import_modes == ["replace"]


def test_append_mode_cannot_bypass_missing_baseline(client, monkeypatch):
    from backend.api import import_ as import_api

    import_calls = []
    monkeypatch.setattr(import_api, "import_data", lambda **kwargs: import_calls.append(kwargs))
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post(
        "/api/import/streaming?mode=append&confirm_plan=true&confirmation_token=token-v1"
    )
    status = client.get(f"/api/import/status/{response.json()['job_id']}").json()

    assert status["status"] == "blocked"
    assert "完整" in status["message"]
    assert import_calls == []


def test_streaming_import_mode_rejects_unsupported_value(client):
    response = client.post("/api/import/streaming?mode=merge")

    assert response.status_code == 422
    assert response.json()["detail"]


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

    def failing_import_data(progress_callback, build_preaggregations=True, **kwargs):
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

    def failing_import_data(progress_callback, build_preaggregations=True, **kwargs):
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

    def fake_import_data(progress_callback, build_preaggregations=True, **kwargs):
        return {"total_records": 2}

    def failing_maintenance(progress_callback, defer_music_search_snapshots=False):
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
        lambda progress_callback, defer_music_search_snapshots=False: {"maintenance_status": "ok"},
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

    def fake_import_data(progress_callback, build_preaggregations=True, **kwargs):
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
