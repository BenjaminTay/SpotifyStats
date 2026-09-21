from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest


def _packet(root: Path, name: str, records: list[dict]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"Streaming_History_Audio_{name}.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
    return root


def test_frozen_snapshot_and_delta_resolve_complete_immutable_chain(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import set_active_source
    from backend.domains.imports.source_registry import (
        freeze_local_batch,
        resolve_batch_directory,
    )

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    first_source = _packet(
        tmp_path / "first",
        "0",
        [{"ts": "2025-01-01T00:00:00Z", "ms_played": 1000}],
    )
    first = freeze_local_batch(first_source, kind="snapshot")
    same = freeze_local_batch(first_source, kind="snapshot")
    assert same["batch_id"] == first["batch_id"]
    set_active_source(first["batch_id"], "generation-1", "digest-1")

    delta_source = _packet(
        tmp_path / "delta",
        "0",
        [{"ts": "2025-01-02T00:00:00Z", "ms_played": 2000}],
    )
    delta = freeze_local_batch(
        delta_source,
        kind="delta",
        parent_source_version_id=first["batch_id"],
    )
    packet_files = list(resolve_batch_directory(delta["batch_id"]).glob("*.json"))
    active_files = list(resolve_batch_directory(delta["batch_id"], active=True).glob("*.json"))
    assert len(packet_files) == 1
    assert len(active_files) == 2

    # Managed bytes do not change when the intake directory is edited later.
    next(first_source.glob("*.json")).write_text("[]", encoding="utf-8")
    assert json.loads(packet_files[0].read_text(encoding="utf-8"))[0]["ms_played"] == 2000


def test_control_run_is_idempotent_and_survives_main_database_replacement(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import create_run, get_run, update_run
    from backend.domains.imports.source_registry import freeze_local_batch

    database = tmp_path / "state" / "app.db"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"old-main")
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    batch = freeze_local_batch(
        _packet(
            tmp_path / "packet",
            "0",
            [{"ts": "2025-01-01T00:00:00Z", "ms_played": 1000}],
        )
    )
    args = dict(
        execution_key="same-execution",
        batch_id=batch["batch_id"],
        confirmation_digest="confirm",
        requested_mode="auto",
        detected_relation="baseline_required",
        strategy="replace",
        baseline_reason_code="not_initialized",
        plan={"incoming_count": 1},
    )
    first = create_run(run_id="run-one", **args)
    second = create_run(run_id="run-two", **args)
    assert first == ("run-one", True)
    assert second == ("run-one", False)
    update_run(
        "run-one",
        status="failed",
        publication_state="failed_before_facts",
        error_code="fixture_failure",
    )

    database.write_bytes(b"replacement-main")
    persisted = get_run("run-one")
    assert persisted is not None
    assert persisted["error_code"] == "fixture_failure"


def test_publication_recovery_completes_source_pointer_from_main_fact_provenance(
    tmp_path, monkeypatch
):
    import sqlite3

    from backend.core import db as db_module
    from backend.core.migrations import migrate_037, migrate_079
    from backend.domains.imports.control_store import (
        active_source_state,
        create_run,
        get_run,
        update_run,
    )
    from backend.domains.imports.source_registry import freeze_local_batch
    from backend.services.import_publication_service import recover_interrupted_publications

    database = tmp_path / "state" / "app.db"
    database.parent.mkdir(parents=True)
    conn = sqlite3.connect(database)
    conn.execute(
        "CREATE TABLE plays(play_id INTEGER PRIMARY KEY, content_type TEXT NOT NULL DEFAULT 'audio')"
    )
    migrate_037(conn)
    migrate_079(conn)
    conn.commit()
    conn.close()
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    batch = freeze_local_batch(
        _packet(
            tmp_path / "packet-recovery",
            "0",
            [{"ts": "2025-01-01T00:00:00Z", "ms_played": 1000}],
        )
    )
    create_run(
        run_id="run-recover",
        execution_key="recover-key",
        batch_id=batch["batch_id"],
        confirmation_digest="confirm",
        requested_mode="replace",
        detected_relation="baseline_required",
        strategy="replace",
        baseline_reason_code="not_initialized",
        plan={},
    )
    update_run(
        "run-recover",
        status="running",
        publication_state="facts_committed",
        new_generation_id="generation-1",
        new_dataset_digest="digest-1",
    )
    conn = sqlite3.connect(database)
    conn.execute(
        """UPDATE playback_import_state
           SET active_generation_id='generation-1', dataset_digest='digest-1',
               active_publication_id='run-recover', publication_state='facts_committed'
           WHERE state_id=1"""
    )
    conn.commit()
    conn.close()

    assert recover_interrupted_publications() == {
        "completed": 1,
        "not_committed": 0,
        "blocked": 0,
    }
    assert get_run("run-recover")["publication_state"] == "sources_published"
    assert active_source_state()["active_source_version_id"] == batch["batch_id"]


@pytest.mark.parametrize(
    ("publication_state", "main_publication_id", "expected"),
    [
        ("prepared", None, {"completed": 0, "not_committed": 1, "blocked": 0}),
        ("facts_committed", "other-run", {"completed": 0, "not_committed": 0, "blocked": 1}),
    ],
)
def test_publication_recovery_distinguishes_uncommitted_and_drifted_windows(
    tmp_path,
    monkeypatch,
    publication_state,
    main_publication_id,
    expected,
):
    import sqlite3

    from backend.core import db as db_module
    from backend.core.migrations import migrate_037, migrate_079
    from backend.domains.imports.control_store import create_run, get_run, update_run
    from backend.domains.imports.source_registry import freeze_local_batch
    from backend.services.import_publication_service import recover_interrupted_publications

    database = tmp_path / "state" / "app.db"
    database.parent.mkdir(parents=True)
    conn = sqlite3.connect(database)
    conn.execute(
        "CREATE TABLE plays(play_id INTEGER PRIMARY KEY, content_type TEXT NOT NULL DEFAULT 'audio')"
    )
    migrate_037(conn)
    migrate_079(conn)
    if main_publication_id:
        conn.execute(
            "UPDATE playback_import_state SET active_publication_id=? WHERE state_id=1",
            (main_publication_id,),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    batch = freeze_local_batch(
        _packet(tmp_path / publication_state, "0", [{"ts": "2025-01-01T00:00:00Z"}])
    )
    create_run(
        run_id="run-window",
        execution_key=f"key-{publication_state}",
        batch_id=batch["batch_id"],
        confirmation_digest="confirmed",
        requested_mode="replace",
        detected_relation="baseline_required",
        strategy="replace",
        baseline_reason_code="not_initialized",
        plan={},
    )
    update_run(
        "run-window",
        status="running",
        publication_state=publication_state,
        new_generation_id="generation-new",
        new_dataset_digest="digest-new",
    )

    assert recover_interrupted_publications() == expected
    recovered = get_run("run-window")
    if publication_state == "prepared":
        assert recovered["publication_state"] == "failed_before_facts"
        assert recovered["recovery_status"] == "not_committed"
    else:
        assert recovered["publication_state"] == "recovery_blocked"
        assert recovered["recovery_status"] == "blocked"


def test_browser_receiving_batch_uploads_and_freezes_server_owned_files(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.source_registry import (
        create_receiving_batch,
        finalize_receiving_batch,
        receive_batch_file,
        resolve_batch_directory,
    )

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    batch = create_receiving_batch(kind="snapshot")
    payload = json.dumps([{"ts": "2025-01-01T00:00:00Z", "ms_played": 1000}]).encode()

    async def chunks():
        yield payload[:5]
        yield payload[5:]

    uploaded = asyncio.run(
        receive_batch_file(
            batch["batch_id"],
            "Streaming_History_Audio_0.json",
            "audio",
            chunks(),
        )
    )
    assert uploaded["status"] == "received"
    frozen = finalize_receiving_batch(batch["batch_id"])
    assert frozen["status"] == "frozen"
    assert [path.name for path in resolve_batch_directory(batch["batch_id"]).iterdir()] == [
        "Streaming_History_Audio_0.json"
    ]


def test_delta_active_resolution_fails_closed_when_parent_or_resolved_bytes_drift(
    tmp_path, monkeypatch
):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import set_active_source
    from backend.domains.imports.source_registry import (
        ImportSourceError,
        freeze_local_batch,
        resolve_batch_directory,
    )

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    parent = freeze_local_batch(_packet(tmp_path / "parent", "0", [{"ts": "2025-01-01T00:00:00Z"}]))
    set_active_source(parent["batch_id"], "generation-1", "digest-1")
    child = freeze_local_batch(
        _packet(tmp_path / "child", "1", [{"ts": "2025-01-02T00:00:00Z"}]),
        kind="delta",
        parent_source_version_id=parent["batch_id"],
    )
    resolved = resolve_batch_directory(child["batch_id"], active=True)
    next(resolved.glob("*.json")).write_text("[]", encoding="utf-8")
    try:
        resolve_batch_directory(child["batch_id"], active=True)
    except ImportSourceError as exc:
        assert exc.error_code == "batch_resolved_manifest_drift"
    else:
        raise AssertionError("resolved source drift must fail closed")


def test_delta_batch_rejects_a_frozen_but_inactive_parent(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import set_active_source
    from backend.domains.imports.source_registry import ImportSourceError, freeze_local_batch

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    active = freeze_local_batch(_packet(tmp_path / "active", "0", [{"ts": "2025-01-01T00:00:00Z"}]))
    stale = freeze_local_batch(_packet(tmp_path / "stale", "1", [{"ts": "2024-01-01T00:00:00Z"}]))
    set_active_source(active["batch_id"], "generation-1", "digest-1")

    with pytest.raises(ImportSourceError, match="delta_parent_not_active"):
        freeze_local_batch(
            _packet(tmp_path / "delta-stale", "2", [{"ts": "2025-01-02T00:00:00Z"}]),
            kind="delta",
            parent_source_version_id=stale["batch_id"],
        )


def test_publication_gate_blocks_ordinary_writer_but_not_nested_writer(tmp_path, monkeypatch):
    import fcntl
    import os

    from backend.core import db as db_module
    from backend.domains.imports.write_coordinator import (
        ImportWriteBusyError,
        acquire_writer_lease,
        exclusive_publication,
    )

    database = tmp_path / "state" / "app.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    lease = acquire_writer_lease(db_path=str(database))
    try:
        try:
            with exclusive_publication(db_path=str(database), blocking=False):
                pass
        except ImportWriteBusyError:
            pass
        else:
            raise AssertionError("exclusive publication must reject an active ordinary writer")
    finally:
        assert lease is not None
        fcntl.flock(lease, fcntl.LOCK_UN)
        os.close(lease)

    with exclusive_publication(db_path=str(database), blocking=False):
        assert acquire_writer_lease(db_path=str(database)) is None


def test_coordinated_sqlite_connect_only_leases_active_database(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.write_coordinator import (
        ImportWriteBusyError,
        coordinated_sqlite_connect,
        exclusive_publication,
    )

    active = tmp_path / "state" / "active.db"
    offline = tmp_path / "offline.db"
    active.parent.mkdir()
    monkeypatch.setattr(db_module, "DB_PATH", str(active))

    offline_conn = coordinated_sqlite_connect(offline)
    try:
        with exclusive_publication(db_path=str(active), blocking=False):
            nested = coordinated_sqlite_connect(active)
            nested.close()
    finally:
        offline_conn.close()

    active_conn = coordinated_sqlite_connect(active)
    try:
        with pytest.raises(ImportWriteBusyError):
            with exclusive_publication(db_path=str(active), blocking=False):
                pass
    finally:
        active_conn.close()


def test_readiness_recheck_promotes_only_after_all_exact_families_are_ready(monkeypatch):
    from backend.services import import_stage_service as service

    updates = []
    attempts = []
    monkeypatch.setattr(
        service,
        "get_run",
        lambda run_id: {
            "run_id": run_id,
            "new_generation_id": "generation-1",
            "new_dataset_digest": "digest-1",
        },
    )
    monkeypatch.setattr(service, "_fact_fence", lambda *args: None)
    monkeypatch.setattr(service, "_publish_main_state", lambda *args: updates.append(args))
    monkeypatch.setattr(
        service,
        "inspect_import_readiness",
        lambda *args: {
            "status": "ready",
            "search_ready_count": 4,
            "year_end_ready_count": 4,
            "billboard_ready": True,
        },
    )
    monkeypatch.setattr(service, "start_stage_attempt", lambda *args, **kwargs: 2)
    monkeypatch.setattr(
        service, "finish_stage_attempt", lambda *args, **kwargs: attempts.append((args, kwargs))
    )
    monkeypatch.setattr(
        service, "update_run", lambda run_id, **kwargs: updates.append((run_id, kwargs))
    )

    result = service.reconcile_import_readiness("run-1")
    assert result["status"] == "ready"
    assert attempts[0][1]["status"] == "succeeded"
    assert ("generation-1", "digest-1", "ready") in updates
    assert any(item[1].get("publication_state") == "ready" for item in updates if len(item) == 2)
    assert any(item[1].get("status") == "succeeded" for item in updates if len(item) == 2)


def test_year_end_projection_warming_is_a_valid_readiness_state(monkeypatch):
    from backend.domains.music_search import variants, year_end_projection
    from backend.services import (
        billboard_snapshot_service,
        import_stage_service,
        music_search_maintenance_service,
    )

    service = import_stage_service

    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(service, "get_db", lambda readonly=True: conn)
    monkeypatch.setattr(
        variants, "build_music_search_variant_contexts", lambda *_args: (1, 2, 3, 4)
    )
    monkeypatch.setattr(
        year_end_projection,
        "year_end_projection_set_status",
        lambda *_args: {
            "status": "warming",
            "ready_count": 0,
            "variants": [{"status": "pending"} for _ in range(4)],
        },
    )
    monkeypatch.setattr(
        music_search_maintenance_service,
        "_current_filter_values",
        lambda _conn: {},
    )
    monkeypatch.setattr(
        music_search_maintenance_service,
        "_revalidated_snapshot_set_report",
        lambda *_args: {"ready_count": 4},
    )
    monkeypatch.setattr(
        billboard_snapshot_service,
        "billboard_default_snapshots_ready",
        lambda: True,
    )
    monkeypatch.setattr(
        billboard_snapshot_service,
        "billboard_default_snapshots_have_lkg",
        lambda: True,
    )

    result = service.inspect_import_readiness()

    assert result["status"] == "warming"
    assert result["build_in_progress"] is True


def test_unavailable_without_lkg_remains_watchable_while_job_is_active(monkeypatch):
    from backend.domains.music_search import variants, year_end_projection
    from backend.services import (
        billboard_snapshot_service,
        import_stage_service,
        music_search_maintenance_service,
    )

    service = import_stage_service

    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE music_search_snapshot_variant_state(
            maintenance_status TEXT,
            active_snapshot_key TEXT
        );
        INSERT INTO music_search_snapshot_variant_state VALUES
            ('pending', NULL), ('pending', NULL), ('pending', NULL), ('pending', NULL);
        CREATE TABLE background_jobs(job_id TEXT PRIMARY KEY, status TEXT NOT NULL);
        INSERT INTO background_jobs VALUES ('search-job', 'pending');
        """
    )
    monkeypatch.setattr(service, "get_db", lambda readonly=True: conn)
    monkeypatch.setattr(
        service,
        "latest_stage_attempts",
        lambda _run_id: [
            {
                "stage": "candidate_index",
                "output_evidence": {"search_job_id": "search-job"},
            }
        ],
    )
    monkeypatch.setattr(
        variants, "build_music_search_variant_contexts", lambda *_args: (1, 2, 3, 4)
    )
    monkeypatch.setattr(
        year_end_projection,
        "year_end_projection_set_status",
        lambda *_args: {
            "status": "ready",
            "ready_count": 4,
            "variants": [{"status": "ready"} for _ in range(4)],
        },
    )
    monkeypatch.setattr(
        music_search_maintenance_service,
        "_current_filter_values",
        lambda _conn: {},
    )
    monkeypatch.setattr(
        music_search_maintenance_service,
        "_revalidated_snapshot_set_report",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        billboard_snapshot_service,
        "billboard_default_snapshots_ready",
        lambda: True,
    )
    monkeypatch.setattr(
        billboard_snapshot_service,
        "billboard_default_snapshots_have_lkg",
        lambda: True,
    )

    result = service.inspect_import_readiness("run-1")

    assert result["status"] == "unavailable"
    assert result["search_job_status"] == "pending"
    assert result["build_in_progress"] is True


def test_reconcile_keeps_unavailable_active_build_running(monkeypatch):
    from backend.services import import_stage_service as service

    updates = []
    monkeypatch.setattr(
        service,
        "get_run",
        lambda _run_id: {
            "new_generation_id": "generation-1",
            "new_dataset_digest": "digest-1",
        },
    )
    monkeypatch.setattr(service, "_fact_fence", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "inspect_import_readiness",
        lambda _run_id: {"status": "unavailable", "build_in_progress": True},
    )
    monkeypatch.setattr(service, "update_run", lambda _run_id, **fields: updates.append(fields))
    monkeypatch.setattr(
        service,
        "start_stage_attempt",
        lambda *_args, **_kwargs: pytest.fail("active build must not be finalized as failed"),
    )

    result = service.reconcile_import_readiness("run-1")

    assert result["status"] == "unavailable"
    assert updates == [
        {
            "status": "running",
            "publication_state": "core_ready",
            "progress_pct": 0.95,
            "completed_at": None,
            "message": "核心数据可用，精确快照正在后台构建",
        }
    ]


def test_readiness_watcher_waits_through_unavailable_active_build(monkeypatch):
    from backend.services import import_stage_service as service

    results = iter(
        (
            {"status": "unavailable", "build_in_progress": True},
            {"status": "ready", "build_in_progress": False},
        )
    )
    observed = []
    monkeypatch.setattr(service, "get_run", lambda _run_id: {"status": "running"})
    monkeypatch.setattr(
        service,
        "reconcile_import_readiness",
        lambda _run_id: observed.append("poll") or next(results),
    )
    monkeypatch.setattr(service.time, "sleep", lambda _seconds: None)

    service._watch_readiness("run-1")

    assert observed == ["poll", "poll"]


def test_terminal_control_run_writes_private_json_and_markdown_reports(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import control_root, create_run, update_run
    from backend.domains.imports.source_registry import freeze_local_batch
    from backend.services.import_run_report_service import build_import_run_report

    database = tmp_path / "state" / "app.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    batch = freeze_local_batch(
        _packet(tmp_path / "report-packet", "0", [{"ts": "2025-01-01T00:00:00Z"}])
    )
    create_run(
        run_id="report-run",
        execution_key="report-key",
        batch_id=batch["batch_id"],
        confirmation_digest="confirmed",
        requested_mode="auto",
        detected_relation="snapshot_superset",
        strategy="append",
        baseline_reason_code=None,
        plan={
            "existing_count": 1,
            "incoming_count": 2,
            "unchanged_count": 1,
            "added_count": 1,
            "removed_count": 0,
        },
    )
    update_run(
        "report-run",
        status="failed",
        publication_state="failed_before_facts",
        progress_pct=4,
        error_code="fixture_failure",
        retryable=0,
        completed_at="2026-09-21T00:00:01+00:00",
    )

    report_root = control_root() / "reports"
    assert (report_root / "report-run.json").is_file()
    assert (report_root / "report-run.md").is_file()
    assert "fixture_failure" in (report_root / "report-run.md").read_text(encoding="utf-8")
    report = build_import_run_report("report-run")
    assert report["conservation"]["added_count"] == 1
    assert report["errors"][0]["error_code"] == "fixture_failure"


def test_finalize_failure_removes_unpublished_resolved_directory(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports import source_registry
    from backend.domains.imports.source_registry import (
        create_receiving_batch,
        finalize_receiving_batch,
        receive_batch_file,
    )

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    batch = create_receiving_batch(kind="snapshot")

    async def chunks():
        yield b"[]"

    asyncio.run(
        receive_batch_file(
            batch["batch_id"],
            "Streaming_History_Audio_0.json",
            "audio",
            chunks(),
        )
    )
    original_manifest = source_registry._directory_manifest
    monkeypatch.setattr(
        source_registry,
        "_directory_manifest",
        lambda directory: (_ for _ in ()).throw(OSError("fixture disk failure")),
    )
    try:
        try:
            finalize_receiving_batch(batch["batch_id"])
        except OSError as exc:
            assert "fixture disk failure" in str(exc)
        else:
            raise AssertionError("finalize must fail when the resolved manifest cannot be read")
        assert not Path(str(batch["resolved_path"])).exists()
    finally:
        monkeypatch.setattr(source_registry, "_directory_manifest", original_manifest)


def test_retryable_exact_failure_keeps_core_ready_and_task_state_separate(monkeypatch):
    from backend.services import import_stage_service as service

    updates = []
    finished = []
    monkeypatch.setattr(
        service,
        "get_run",
        lambda run_id: {
            "run_id": run_id,
            "status": "running",
            "publication_state": "core_ready",
            "new_generation_id": "generation-1",
            "new_dataset_digest": "digest-1",
            "result": {},
        },
    )
    monkeypatch.setattr(service, "latest_stage_attempts", lambda run_id: [])
    monkeypatch.setattr(service, "_fact_fence", lambda *args: None)
    monkeypatch.setattr(service, "start_stage_attempt", lambda *args, **kwargs: 1)
    monkeypatch.setattr(
        service,
        "finish_stage_attempt",
        lambda *args, **kwargs: finished.append(kwargs),
    )
    monkeypatch.setattr(
        service,
        "_run_stage",
        lambda *args, **kwargs: {
            "status": "failed",
            "error_code": "exact_snapshot_failed",
        },
    )
    monkeypatch.setattr(service, "update_run", lambda run_id, **kwargs: updates.append(kwargs))

    result = service.run_import_stages("run-1", _change_set_fixture(), stages=("exact_snapshots",))
    assert result["status"] == "retryable_failed"
    assert finished[-1]["status"] == "retryable_failed"
    assert updates[-1]["status"] == "retryable_failed"
    assert updates[-1]["publication_state"] == "core_ready"


def test_active_exact_build_without_lkg_starts_watcher(monkeypatch):
    from backend.services import import_stage_service as service

    finished = []
    watchers = []
    stable_revision = {"schema_version": 1, "sha256": "stable"}
    monkeypatch.setattr(
        service,
        "get_run",
        lambda _run_id: {
            "run_id": "run-1",
            "status": "running",
            "publication_state": "core_ready",
            "new_generation_id": "generation-1",
            "new_dataset_digest": "digest-1",
            "result": {},
        },
    )
    monkeypatch.setattr(
        service,
        "latest_stage_attempts",
        lambda _run_id: [
            {
                "stage": "critical_prewarm",
                "status": "succeeded",
                "output_evidence": {
                    "status": "ready",
                    "validation_dependency_revision": stable_revision,
                },
            }
        ],
    )
    monkeypatch.setattr(service, "_stage_dependency_revision", lambda _stage: stable_revision)
    monkeypatch.setattr(service, "_fact_fence", lambda *_args: None)
    monkeypatch.setattr(service, "supersede_other_runs", lambda *_args: None)
    monkeypatch.setattr(service, "start_stage_attempt", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(
        service,
        "finish_stage_attempt",
        lambda *_args, **kwargs: finished.append(kwargs),
    )
    monkeypatch.setattr(
        service,
        "_run_stage",
        lambda *_args, **_kwargs: {
            "status": "unavailable",
            "build_in_progress": True,
        },
    )
    monkeypatch.setattr(service, "update_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "start_import_readiness_watcher",
        lambda run_id: watchers.append(run_id),
    )

    result = service.run_import_stages(
        "run-1",
        _change_set_fixture(),
        stages=("exact_snapshots",),
    )

    assert result["status"] == "running"
    assert finished[-1]["status"] == "warming"
    assert finished[-1]["output"]["status"] == "unavailable"
    assert watchers == ["run-1"]


def _change_set_fixture():
    from backend.domains.imports.change_set import PlaybackChangeSet

    return PlaybackChangeSet(
        generation_id="generation-1",
        strategy="full",
        previous_dataset_digest=None,
        added_count=0,
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


def test_exclusive_error_recovery_callback_runs_before_lock_release(tmp_path, monkeypatch):
    import fcntl
    import os

    from backend.core import db as db_module
    from backend.domains.imports.write_coordinator import (
        exclusive_publication,
        publication_lock_path,
    )

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    callback_observed_exclusive = []

    def on_error(_exc):
        descriptor = os.open(publication_lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
            callback_observed_exclusive.append(True)
        finally:
            os.close(descriptor)

    with pytest.raises(RuntimeError, match="fixture"):
        with exclusive_publication(on_error=on_error):
            raise RuntimeError("fixture")
    assert callback_observed_exclusive == [True]


def test_batch_lock_rejects_upload_and_finalize_races(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.source_registry import (
        ImportSourceError,
        _batch_mutation_lock,
        create_receiving_batch,
        finalize_receiving_batch,
        receive_batch_file,
    )

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    batch = create_receiving_batch(kind="snapshot")

    async def chunks():
        yield b"[]"

    with _batch_mutation_lock(batch["batch_id"]):
        with pytest.raises(ImportSourceError, match="batch_busy"):
            asyncio.run(
                receive_batch_file(
                    batch["batch_id"],
                    "Streaming_History_Audio_0.json",
                    "audio",
                    chunks(),
                )
            )
        with pytest.raises(ImportSourceError, match="batch_busy"):
            finalize_receiving_batch(batch["batch_id"])


def test_persistent_quarantine_blocks_and_then_releases_normal_writers(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import (
        clear_import_write_quarantine,
        quarantine_import_writes,
    )
    from backend.domains.imports.write_coordinator import (
        ImportWriteQuarantinedError,
        acquire_writer_lease,
    )

    database = tmp_path / "state" / "app.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    quarantine_import_writes("run-quarantine", "source_pending")
    with pytest.raises(ImportWriteQuarantinedError):
        acquire_writer_lease()
    clear_import_write_quarantine("run-quarantine")
    descriptor = acquire_writer_lease()
    assert descriptor is not None
    import os

    os.close(descriptor)


def test_persistent_quarantine_blocks_unowned_exclusive_writer(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import (
        clear_import_write_quarantine,
        quarantine_import_writes,
    )
    from backend.domains.imports.write_coordinator import (
        ImportWriteQuarantinedError,
        acquire_writer_lease,
        exclusive_publication,
    )

    database = tmp_path / "state" / "app.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    quarantine_import_writes("run-owner", "source_pending")

    with pytest.raises(ImportWriteQuarantinedError):
        with exclusive_publication():
            pass
    with pytest.raises(ImportWriteQuarantinedError):
        with exclusive_publication(owner_run_id="run-other"):
            pass

    with exclusive_publication(owner_run_id="run-owner"):
        assert acquire_writer_lease() is None

    clear_import_write_quarantine("run-owner")


def test_source_publication_state_and_gate_clear_are_atomic(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import (
        create_run,
        get_run,
        import_write_gate_state,
        mark_sources_published_and_clear_quarantine,
        quarantine_import_writes,
        update_run,
    )
    from backend.domains.imports.source_registry import freeze_local_batch

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    batch = freeze_local_batch(_packet(tmp_path / "atomic-source", "0", [{"ts": "x"}]))

    def make_run(run_id: str) -> None:
        create_run(
            run_id=run_id,
            execution_key=f"{run_id}-key",
            batch_id=batch["batch_id"],
            confirmation_digest="confirmed",
            requested_mode="auto",
            detected_relation="snapshot_superset",
            strategy="append",
            baseline_reason_code=None,
            plan={},
        )
        update_run(run_id, status="running", publication_state="facts_committed")

    make_run("run-published")
    update_run(
        "run-published",
        status="blocked",
        error_code="source_publish_failed",
        completed_at="2026-09-21T00:00:00+00:00",
    )
    quarantine_import_writes("run-published", "source_pending")
    mark_sources_published_and_clear_quarantine(
        "run-published",
        progress_pct=0.65,
        message="published",
    )
    published = get_run("run-published")
    assert published["publication_state"] == "sources_published"
    assert published["status"] == "running"
    assert published["completed_at"] is None
    assert published["error_code"] is None
    assert not import_write_gate_state()["blocked"]

    make_run("run-cas-rejected")
    quarantine_import_writes("different-owner", "source_pending")
    with pytest.raises(RuntimeError, match="import_write_gate_owned_by_another_run"):
        mark_sources_published_and_clear_quarantine(
            "run-cas-rejected",
            progress_pct=0.65,
            message="must roll back",
        )
    assert get_run("run-cas-rejected")["publication_state"] == "facts_committed"
    assert import_write_gate_state()["run_id"] == "different-owner"


def test_report_write_failure_is_persisted_and_can_be_retried(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import create_run, get_run, update_run
    from backend.domains.imports.source_registry import freeze_local_batch
    from backend.services import import_run_report_service

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    batch = freeze_local_batch(_packet(tmp_path / "report-failure", "0", [{"ts": "x"}]))
    create_run(
        run_id="report-failure",
        execution_key="report-failure-key",
        batch_id=batch["batch_id"],
        confirmation_digest="confirmed",
        requested_mode="auto",
        detected_relation="unknown",
        strategy="blocked",
        baseline_reason_code=None,
        plan={},
    )
    original = import_run_report_service.write_import_run_reports
    monkeypatch.setattr(
        import_run_report_service,
        "write_import_run_reports",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    update_run("report-failure", status="failed", publication_state="failed_before_facts")
    assert get_run("report-failure")["report_status"] == "failed"
    assert get_run("report-failure")["report_error_code"] == "report_write_failed"
    monkeypatch.setattr(import_run_report_service, "write_import_run_reports", original)
    update_run("report-failure", status="failed")
    assert get_run("report-failure")["report_status"] == "ready"


def test_pending_stage_recovery_is_not_truncated_at_two_hundred(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import create_run, pending_stage_runs, update_run
    from backend.domains.imports.source_registry import freeze_local_batch

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "state" / "app.db"))
    batch = freeze_local_batch(_packet(tmp_path / "many-runs", "0", [{"ts": "x"}]))
    for index in range(205):
        run_id = f"pending-{index:03d}"
        create_run(
            run_id=run_id,
            execution_key=f"key-{index:03d}",
            batch_id=batch["batch_id"],
            confirmation_digest="confirmed",
            requested_mode="auto",
            detected_relation="snapshot_superset",
            strategy="append",
            baseline_reason_code=None,
            plan={},
        )
        update_run(run_id, status="running", publication_state="sources_published")
    assert len(pending_stage_runs()) == 205


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            dict(
                search_ready=False,
                search_failed=True,
                search_warming=False,
                year_end_ready=True,
                year_end_failed=False,
                year_end_warming=False,
                billboard_ready=True,
                billboard_failed=False,
                billboard_warming=False,
            ),
            "failed",
        ),
        (
            dict(
                search_ready=False,
                search_failed=False,
                search_warming=False,
                year_end_ready=True,
                year_end_failed=False,
                year_end_warming=False,
                billboard_ready=True,
                billboard_failed=False,
                billboard_warming=False,
            ),
            "unavailable",
        ),
        (
            dict(
                search_ready=False,
                search_failed=False,
                search_warming=True,
                year_end_ready=True,
                year_end_failed=False,
                year_end_warming=False,
                billboard_ready=True,
                billboard_failed=False,
                billboard_warming=False,
            ),
            "warming",
        ),
    ],
)
def test_readiness_status_never_disguises_failed_or_missing_as_warming(kwargs, expected):
    from backend.services.import_stage_service import _classify_readiness

    assert _classify_readiness(**kwargs) == expected


def test_stage_dependency_revision_ignores_publication_bookkeeping(tmp_path, monkeypatch):
    from backend.services import import_stage_service as service

    database = tmp_path / "dependency.db"
    conn = sqlite3.connect(database)
    conn.execute(
        """CREATE TABLE playback_import_state(
               state_id INTEGER PRIMARY KEY,
               active_generation_id TEXT,
               dataset_digest TEXT,
               record_count INTEGER,
               active_source_version_id TEXT,
               active_publication_id TEXT,
               publication_state TEXT,
               last_relation TEXT,
               last_strategy TEXT,
               updated_at TEXT
           )"""
    )
    conn.execute(
        """INSERT INTO playback_import_state VALUES(
               1, 'generation-1', 'digest-1', 10, 'source-1', 'publication-1',
               'sources_published', 'snapshot_superset', 'append', '2026-09-21T00:00:00Z'
           )"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(
        service,
        "get_db",
        lambda readonly=True: sqlite3.connect(database),
    )

    before = service._stage_dependency_revision("metadata")
    conn = sqlite3.connect(database)
    conn.execute(
        """UPDATE playback_import_state
           SET active_source_version_id='source-2',
               active_publication_id='publication-2',
               publication_state='core_ready',
               last_relation='identical',
               last_strategy='reuse',
               updated_at='2026-09-21T00:01:00Z'
           WHERE state_id=1"""
    )
    conn.commit()
    conn.close()

    assert service._stage_dependency_revision("metadata") == before

    conn = sqlite3.connect(database)
    conn.execute("UPDATE playback_import_state SET dataset_digest='digest-2' WHERE state_id=1")
    conn.commit()
    conn.close()
    assert service._stage_dependency_revision("metadata") != before


def test_core_ready_restart_reuses_verified_early_stages(monkeypatch):
    from backend.services import import_stage_service as service

    calls = []
    stable_revision = {"schema_version": 1, "sha256": "stable"}
    monkeypatch.setattr(
        service,
        "IMPORT_STAGES",
        ("metadata", "critical_prewarm", "exact_snapshots"),
    )
    monkeypatch.setattr(
        service,
        "get_run",
        lambda _run_id: {
            "run_id": "run-1",
            "publication_state": "core_ready",
            "new_generation_id": "generation-1",
            "new_dataset_digest": "digest-1",
            "result": {"active_records": 10},
        },
    )
    monkeypatch.setattr(
        service,
        "latest_stage_attempts",
        lambda _run_id: [
            {
                "stage": stage,
                "status": "succeeded",
                "output_evidence": {
                    "status": "ready",
                    "validation_dependency_revision": stable_revision,
                },
            }
            for stage in ("metadata", "critical_prewarm")
        ],
    )
    monkeypatch.setattr(service, "_stage_dependency_revision", lambda _stage: stable_revision)
    monkeypatch.setattr(service, "_fact_fence", lambda *_args: None)
    monkeypatch.setattr(service, "supersede_other_runs", lambda *_args: None)
    monkeypatch.setattr(service, "start_stage_attempt", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(service, "finish_stage_attempt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "_run_stage",
        lambda stage, **_kwargs: calls.append(stage) or {"status": "ready"},
    )
    monkeypatch.setattr(service, "_publish_main_state", lambda *_args: None)
    monkeypatch.setattr(service, "update_run", lambda *_args, **_kwargs: None)

    result = service.run_import_stages("run-1", _change_set_fixture())

    assert result["status"] == "succeeded"
    assert calls == ["exact_snapshots"]


def test_stage_success_is_replayed_when_declared_dependency_revision_changes(monkeypatch):
    from backend.services import import_stage_service as service

    calls = []
    monkeypatch.setattr(service, "IMPORT_STAGES", ("identity_merge",))
    monkeypatch.setattr(
        service,
        "get_run",
        lambda run_id: {
            "run_id": run_id,
            "publication_state": "sources_published",
            "new_generation_id": "generation-1",
            "new_dataset_digest": "digest-1",
            "result": {"active_records": 10},
        },
    )
    monkeypatch.setattr(
        service,
        "latest_stage_attempts",
        lambda run_id: [
            {
                "stage": "identity_merge",
                "status": "succeeded",
                "output_evidence": {
                    "status": "ready",
                    "validation_dependency_revision": {"sha256": "old"},
                },
            }
        ],
    )
    monkeypatch.setattr(service, "_stage_dependency_revision", lambda stage: {"sha256": "new"})
    monkeypatch.setattr(service, "_fact_fence", lambda *args: None)
    monkeypatch.setattr(service, "supersede_other_runs", lambda *args: None)
    monkeypatch.setattr(service, "start_stage_attempt", lambda *args, **kwargs: 2)
    monkeypatch.setattr(service, "finish_stage_attempt", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        service,
        "_run_stage",
        lambda *args, **kwargs: calls.append("identity_merge") or {"status": "ready"},
    )
    monkeypatch.setattr(service, "update_run", lambda *args, **kwargs: None)

    service.run_import_stages("run-1", _change_set_fixture())
    assert calls == ["identity_merge"]


def test_partial_metadata_stage_remains_retryable_without_reimport(monkeypatch):
    from backend.services import import_stage_service as service

    updates = []
    finished = []
    monkeypatch.setattr(
        service,
        "get_run",
        lambda run_id: {
            "run_id": run_id,
            "publication_state": "sources_published",
            "new_generation_id": "generation-1",
            "new_dataset_digest": "digest-1",
            "result": {"active_records": 10},
        },
    )
    monkeypatch.setattr(service, "latest_stage_attempts", lambda run_id: [])
    monkeypatch.setattr(service, "_stage_dependency_revision", lambda stage: {"sha256": "stable"})
    monkeypatch.setattr(service, "_fact_fence", lambda *args: None)
    monkeypatch.setattr(service, "supersede_other_runs", lambda *args: None)
    monkeypatch.setattr(service, "start_stage_attempt", lambda *args, **kwargs: 1)
    monkeypatch.setattr(
        service, "finish_stage_attempt", lambda *args, **kwargs: finished.append(kwargs)
    )
    monkeypatch.setattr(
        service,
        "_run_stage",
        lambda *args, **kwargs: {
            "status": "partial",
            "provider_available": False,
            "errors": ["missing credential"],
        },
    )
    monkeypatch.setattr(service, "update_run", lambda run_id, **kwargs: updates.append(kwargs))

    result = service.run_import_stages("run-1", _change_set_fixture(), stages=("metadata",))
    assert result["status"] == "retryable_failed"
    assert finished[-1]["status"] == "retryable_failed"
    assert updates[-1]["retryable"] == 1
    assert updates[-1]["publication_state"] == "sources_published"


def test_source_pointer_is_restored_if_main_provenance_update_fails(tmp_path, monkeypatch):
    import sqlite3

    from backend.core import db as db_module
    from backend.core.migrations import migrate_037, migrate_079
    from backend.domains.imports.control_store import (
        active_source_state,
        create_run,
        set_active_source,
        update_run,
    )
    from backend.domains.imports.source_registry import freeze_local_batch
    from backend.services import import_publication_service as service

    database = tmp_path / "state" / "app.db"
    database.parent.mkdir(parents=True)
    setup = sqlite3.connect(database)
    setup.execute(
        "CREATE TABLE plays(play_id INTEGER PRIMARY KEY, content_type TEXT NOT NULL DEFAULT 'audio')"
    )
    migrate_037(setup)
    migrate_079(setup)
    setup.commit()
    setup.close()
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    old = freeze_local_batch(_packet(tmp_path / "old-source", "0", [{"ts": "old"}]))
    new = freeze_local_batch(_packet(tmp_path / "new-source", "0", [{"ts": "new"}]))
    set_active_source(old["batch_id"], "generation-old", "digest-old")
    create_run(
        run_id="run-source-rollback",
        execution_key="source-rollback-key",
        batch_id=new["batch_id"],
        confirmation_digest="confirmed",
        requested_mode="auto",
        detected_relation="snapshot_superset",
        strategy="append",
        baseline_reason_code=None,
        plan={},
    )
    update_run(
        "run-source-rollback",
        status="running",
        publication_state="facts_committed",
        old_generation_id="generation-old",
        old_dataset_digest="digest-old",
        old_source_version_id=old["batch_id"],
        new_generation_id="generation-new",
        new_dataset_digest="digest-new",
    )
    setup = sqlite3.connect(database)
    setup.execute(
        """UPDATE playback_import_state
           SET active_generation_id='generation-new',dataset_digest='digest-new',
               active_publication_id='run-source-rollback',publication_state='facts_committed'
           WHERE state_id=1"""
    )
    setup.commit()
    setup.close()

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if "SET active_source_version_id" in sql:
                raise sqlite3.OperationalError("fixture main publish failure")
            return super().execute(sql, parameters)

    opens = 0

    def get_connection(*, readonly=False):
        nonlocal opens
        opens += 1
        factory = sqlite3.Connection if opens == 1 else FailingConnection
        connection = sqlite3.connect(database, factory=factory)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(service, "get_db", get_connection)
    with pytest.raises(sqlite3.OperationalError, match="fixture main publish failure"):
        service.publish_sources(
            "run-source-rollback",
            new["batch_id"],
            generation_id="generation-new",
            dataset_digest="digest-new",
        )
    assert active_source_state()["active_source_version_id"] == old["batch_id"]
