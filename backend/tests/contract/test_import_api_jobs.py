from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import Literal

import pytest

from backend.domains.imports.change_set import PlaybackChangeSet
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


def _change_set(
    generation_id: str,
    strategy: Literal["incremental", "reconcile", "full"] = "full",
) -> PlaybackChangeSet:
    return PlaybackChangeSet(
        generation_id=generation_id,
        strategy=strategy,
        previous_dataset_digest=None,
        added_count=1,
        removed_count=0,
        earliest_changed_ts=None,
        latest_changed_ts=None,
        track_ids=frozenset(),
        album_ids=frozenset(),
        source_album_ids=frozenset(),
        artist_ids=frozenset(),
        spotify_track_ids=frozenset(),
        spotify_album_ids=frozenset(),
        dates=frozenset(),
        months=frozenset(),
        years=frozenset(),
        billboard_weeks=frozenset(),
        billboard_scope_exact=True,
        previous_open_week=None,
        current_open_week=None,
        semantic_revisions={},
    )


def _install_successful_durable_pipeline(monkeypatch, import_api, *, import_impl=None):
    from backend.domains.imports.control_store import clear_import_write_quarantine, update_run

    def default_import_data(progress_callback=None, **kwargs):
        if progress_callback:
            progress_callback("提交播放事实", 0.5)
        strategy = "incremental" if kwargs["mode"] == "append" else kwargs["mode"]
        if strategy == "replace":
            strategy = "full"
        return {
            "generation_id": kwargs["generation_id"],
            "dataset_digest": "digest-new",
            "inserted_records": 1,
            "unchanged_records": 0,
            "active_records": 1,
            "change_set": _change_set(kwargs["generation_id"], strategy),
        }

    monkeypatch.setattr(import_api, "import_data", import_impl or default_import_data)

    def publish_sources(run_id, batch_id, *, generation_id, dataset_digest):
        del batch_id, generation_id, dataset_digest
        update_run(run_id, publication_state="sources_published")
        clear_import_write_quarantine(run_id)

    def run_stages(run_id, change_set, **kwargs):
        del change_set, kwargs
        update_run(
            run_id,
            status="succeeded",
            publication_state="ready",
            progress_pct=1.0,
            message="导入完成",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        return {"status": "succeeded", "stages": {}}

    monkeypatch.setattr(import_api, "publish_sources", publish_sources)
    monkeypatch.setattr(import_api, "run_import_stages", run_stages)


@pytest.fixture(autouse=True)
def reset_import_jobs(monkeypatch, client):
    from backend.api import import_ as import_api
    from backend.domains.imports.control_store import connect_control

    control = connect_control()
    try:
        control.execute("DELETE FROM import_stage_runs")
        control.execute("DELETE FROM import_runs")
        control.execute("UPDATE import_source_state SET active_source_version_id=NULL")
        control.execute("DELETE FROM import_batches")
        control.commit()
    finally:
        control.close()

    import_api._jobs.clear()
    monkeypatch.setattr(import_api, "_import_lock", Lock())
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
    from backend.domains.imports.control_store import get_run

    progress_events = []

    def fake_import_data(progress_callback, **kwargs):
        progress_callback("读取 Extended Streaming History", 0.4)
        progress_events.append(get_run(active_run_id[0])["progress_pct"])
        return {
            "generation_id": kwargs["generation_id"],
            "dataset_digest": "digest-new",
            "inserted_records": 1,
            "unchanged_records": 0,
            "active_records": 1,
            "change_set": _change_set(kwargs["generation_id"]),
        }

    active_run_id = []
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    original_create = import_api.create_control_run

    def capture_create(**kwargs):
        result = original_create(**kwargs)
        active_run_id[:] = [result[0]]
        return result

    monkeypatch.setattr(import_api, "create_control_run", capture_create)
    _install_successful_durable_pipeline(monkeypatch, import_api, import_impl=fake_import_data)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    job_id = response.json()["job_id"]
    assert len(job_id) == 12
    assert progress_events == [pytest.approx(0.352)]

    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "done"
    assert status["progress_pct"] == 1.0
    assert status["message"] == "导入完成"
    assert status["result"] == {
        "active_records": 1,
        "detected_relation": "baseline_required",
        "duplicate_records_skipped": 0,
        "executed_strategy": "full",
        "inserted_records": 1,
        "noop": False,
        "unchanged_records": 0,
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


def test_import_health_has_nested_database_and_derived_sections(
    client, published_governance_snapshot
):
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


def test_immutable_batch_run_history_report_and_recheck_api_contract(client, monkeypatch):
    from backend.api import import_ as import_api

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    _install_successful_durable_pipeline(monkeypatch, import_api)
    monkeypatch.setattr(
        import_api,
        "build_streaming_import_preflight",
        lambda *args, **kwargs: dict(_assessment().report),
    )

    created = client.post("/api/import/batches", json={"kind": "snapshot"})
    assert created.status_code == 200
    batch_id = created.json()["batch_id"]

    uploaded = client.put(
        f"/api/import/batches/{batch_id}/files/Streaming_History_Audio_0.json",
        params={"source_type": "audio"},
        content=b"[]",
        headers={"Content-Type": "application/json"},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["status"] == "received"

    finalized = client.post(f"/api/import/batches/{batch_id}/finalize")
    assert finalized.status_code == 200
    frozen_id = finalized.json()["batch_id"]
    assert finalized.json()["status"] == "frozen"

    preflight = client.get(f"/api/import/batches/{frozen_id}/preflight")
    assert preflight.status_code == 200
    assert preflight.json()["record_delta_comparable"] is False

    executed = client.post(
        f"/api/import/batches/{frozen_id}/runs",
        json={
            "mode": "auto",
            "confirmation_token": preflight.json()["confirmation_token"],
            "confirm_warnings": False,
            "confirm_plan": True,
        },
    )
    assert executed.status_code == 200, executed.json()
    run_id = executed.json()["run_id"]

    history = client.get("/api/import/runs", params={"limit": 1, "offset": 0})
    latest = client.get("/api/import/runs/latest")
    detail = client.get(f"/api/import/runs/{run_id}")
    report = client.get(f"/api/import/runs/{run_id}/report")
    markdown = client.get(f"/api/import/runs/{run_id}/report", params={"format": "markdown"})
    for response in (history, latest, detail, report, markdown):
        assert response.status_code == 200
    assert history.json()["runs"][0]["run_id"] == run_id
    assert latest.json()["status"] == "succeeded", latest.json()

    assert client.get(f"/api/import/runs/{run_id}/report?format=xml").status_code == 422
    assert detail.json()["publication_state"] == "ready"
    assert report.json()["run_id"] == run_id
    assert markdown.text.startswith(f"# 导入运行报告 {run_id}")

    monkeypatch.setattr(
        import_api,
        "reconcile_import_readiness",
        lambda selected_run_id: {"status": "ready", "run_id": selected_run_id},
    )
    rechecked = client.post(f"/api/import/runs/{run_id}/recheck")
    assert rechecked.status_code == 200
    assert rechecked.json()["run_id"] == run_id


def test_immutable_import_route_boundaries_are_explicit(client):
    created = client.post("/api/import/batches", json={"kind": "snapshot"})
    batch_id = created.json()["batch_id"]
    invalid_source = client.put(
        f"/api/import/batches/{batch_id}/files/Streaming_History_Audio_0.json",
        params={"source_type": "podcast"},
        content=b"[]",
    )
    invalid_name = client.put(
        f"/api/import/batches/{batch_id}/files/not-a-streaming-export.json",
        params={"source_type": "audio"},
        content=b"[]",
    )

    assert invalid_source.status_code == 422
    assert invalid_name.status_code == 409
    assert client.get("/api/import/batches/missing/preflight").status_code == 409
    assert client.get("/api/import/runs/missing").status_code == 404
    assert client.get("/api/import/runs/missing/report").status_code == 404


def test_streaming_import_job_runs_derived_maintenance_before_done(client, monkeypatch):
    from backend.api import import_ as import_api
    from backend.domains.imports.control_store import update_run

    events = []

    def fake_import_data(progress_callback, **kwargs):
        events.append(("import", kwargs["build_preaggregations"], kwargs["mode"]))
        progress_callback("导入基础播放", 0.5)
        return {
            "generation_id": kwargs["generation_id"],
            "dataset_digest": "digest-new",
            "inserted_records": 1,
            "active_records": 1,
            "change_set": _change_set(kwargs["generation_id"]),
        }

    def fake_publish(run_id, batch_id, **kwargs):
        del batch_id, kwargs
        events.append(("publish_sources",))
        update_run(run_id, publication_state="sources_published")

    def fake_stages(run_id, change_set):
        del change_set
        events.append(("stages",))
        update_run(
            run_id,
            status="succeeded",
            publication_state="ready",
            progress_pct=1,
            message="导入完成",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        return {"status": "succeeded"}

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    monkeypatch.setattr(import_api, "publish_sources", fake_publish)
    monkeypatch.setattr(import_api, "run_import_stages", fake_stages)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert events == [
        ("import", False, "replace"),
        ("publish_sources",),
        ("stages",),
    ]
    assert status["status"] == "done"
    assert status["result"]["executed_strategy"] == "full"


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

    def fake_import(progress_callback=None, **kwargs):
        import_calls.append(True)
        return {
            "generation_id": kwargs["generation_id"],
            "dataset_digest": "digest-new",
            "inserted_records": 1,
            "active_records": 1,
            "change_set": _change_set(kwargs["generation_id"]),
        }

    _install_successful_durable_pipeline(monkeypatch, import_api, import_impl=fake_import)
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
    assert confirmed_status["status"] == "done", confirmed_status
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


def test_streaming_execution_rechecks_confirmation_against_active_baseline(client, monkeypatch):
    from backend.api import import_ as import_api

    assessments = iter(
        [
            _assessment(),
            replace(
                _assessment(),
                report={**_assessment().report, "confirmation_token": "token-v2"},
            ),
        ]
    )
    snapshot_calls = []
    import_calls = []
    monkeypatch.setattr(
        import_api, "assess_streaming_import", lambda *args, **kwargs: next(assessments)
    )
    monkeypatch.setattr(
        import_api,
        "create_database_snapshot",
        lambda **kwargs: snapshot_calls.append(kwargs),
    )
    monkeypatch.setattr(import_api, "import_data", lambda **kwargs: import_calls.append(kwargs))
    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)

    response = client.post("/api/import/streaming")
    status = client.get(f"/api/import/status/{response.json()['job_id']}").json()

    assert status["status"] == "blocked"
    assert "重新预检" in status["message"]
    assert snapshot_calls == []
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
        import_api, "run_import_stages", lambda **kwargs: maintenance_calls.append(kwargs)
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
            "dataset_digest": "digest-new",
            "change_set": _change_set(kwargs["generation_id"], "incremental"),
        }

    _install_successful_durable_pipeline(monkeypatch, import_api, import_impl=fake_import_data)
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
            "dataset_digest": "digest-new",
            "change_set": _change_set(kwargs["generation_id"], "reconcile"),
        }

    _install_successful_durable_pipeline(monkeypatch, import_api, import_impl=fake_import_data)
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

    def fake_import(**kwargs):
        import_modes.append(kwargs["mode"])
        return {
            "generation_id": kwargs["generation_id"],
            "dataset_digest": "digest-new",
            "inserted_records": 1,
            "active_records": 1,
            "change_set": _change_set(kwargs["generation_id"]),
        }

    _install_successful_durable_pipeline(monkeypatch, import_api, import_impl=fake_import)
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
    assert status["progress_pct"] == pytest.approx(0.276)
    assert status["message"] == "fixture import failure"
    assert status["result"] == {"rollback": None}


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


def test_streaming_import_keeps_committed_facts_when_maintenance_fails(client, monkeypatch):
    from backend.api import import_ as import_api
    from backend.domains.imports.control_store import update_run

    snapshot = {"status": "created", "path": "/tmp/maintenance-failure-snapshot.db"}
    rollback_calls = []

    def fake_import_data(**kwargs):
        return {
            "generation_id": kwargs["generation_id"],
            "dataset_digest": "digest-new",
            "inserted_records": 1,
            "active_records": 1,
            "change_set": _change_set(kwargs["generation_id"]),
        }

    def failing_maintenance(run_id, change_set):
        del run_id, change_set
        raise RuntimeError("fixture maintenance failure")

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "create_database_snapshot", lambda job_id: snapshot)
    monkeypatch.setattr(
        import_api,
        "restore_database_snapshot",
        lambda snapshot_path: rollback_calls.append(snapshot_path) or {"status": "restored"},
    )
    _install_successful_durable_pipeline(monkeypatch, import_api, import_impl=fake_import_data)

    def published_sources(run_id, batch_id, **kwargs):
        del batch_id, kwargs
        update_run(run_id, publication_state="sources_published")

    monkeypatch.setattr(import_api, "publish_sources", published_sources)
    monkeypatch.setattr(import_api, "run_import_stages", failing_maintenance)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert status["message"] == "播放事实与来源已发布，后处理失败"
    assert rollback_calls == []


def test_streaming_import_keeps_committed_facts_when_post_import_health_fails(client, monkeypatch):
    from backend.api import import_ as import_api
    from backend.domains.imports.control_store import update_run

    snapshot = {"status": "created", "path": "/tmp/post-health-failure-snapshot.db"}
    rollback_calls = []

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "create_database_snapshot", lambda job_id: snapshot)
    monkeypatch.setattr(
        import_api,
        "restore_database_snapshot",
        lambda snapshot_path: rollback_calls.append(snapshot_path) or {"status": "restored"},
    )
    _install_successful_durable_pipeline(monkeypatch, import_api)

    def fail_core_stage(run_id, change_set):
        del change_set
        update_run(
            run_id,
            status="failed",
            publication_state="sources_published",
            error_code="critical_prewarm_failed",
            message="核心统计健康检查失败",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        return {"status": "failed", "stage": "critical_prewarm"}

    monkeypatch.setattr(import_api, "run_import_stages", fail_core_stage)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert status["message"] == "核心统计健康检查失败"
    assert rollback_calls == []


def test_import_job_does_not_start_while_another_import_holds_slot(client, monkeypatch):
    from backend.api import import_ as import_api

    _install_successful_durable_pipeline(monkeypatch, import_api)

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

    retried = client.post(
        f"/api/import/runs/{job_id}/retry",
        json={"stage": "facts"},
    )
    assert retried.status_code == 200
    retried_status = client.get(f"/api/import/status/{job_id}").json()
    assert retried_status["status"] == "done", retried_status


def test_import_progress_callback_clamps_status_percent(client, monkeypatch):
    from backend.api import import_ as import_api
    from backend.domains.imports.control_store import get_run

    observed = []
    active_run_id = []

    def fake_import_data(progress_callback, build_preaggregations=True, **kwargs):
        progress_callback("negative progress", -0.5)
        observed.append(get_run(active_run_id[0])["progress_pct"])
        progress_callback("overflow progress", 1.5)
        observed.append(get_run(active_run_id[0])["progress_pct"])
        raise RuntimeError("stop after progress probes")

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    original_create = import_api.create_control_run

    def capture_create(**kwargs):
        result = original_create(**kwargs)
        active_run_id[:] = [result[0]]
        return result

    monkeypatch.setattr(import_api, "create_control_run", capture_create)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    assert observed == pytest.approx([0.2, 0.58])
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert status["status"] == "error"
    assert status["progress_pct"] == pytest.approx(0.58)
