from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path


def _record(day: int) -> dict:
    return {
        "ts": f"2026-01-{day:02d}T12:00:00Z",
        "ms_played": 60_000,
        "platform": "governance-test",
        "master_metadata_track_name": f"Track {day}",
        "master_metadata_album_artist_name": "Governance artist",
        "master_metadata_album_album_name": "Governance album",
        "spotify_track_uri": f"spotify:track:{day:022d}",
        "reason_start": "clickrow",
        "reason_end": "trackdone",
    }


def _source(root: Path, label: str, days: list[int]) -> Path:
    directory = root / label
    directory.mkdir()
    (directory / "Streaming_History_Audio_0.json").write_text(
        json.dumps([_record(day) for day in days]), encoding="utf-8"
    )
    return directory


def _setup(tmp_path, monkeypatch):
    from backend.api import import_ as api
    from backend.core import db as db_module
    from backend.core.migrations import run_migrations

    database = tmp_path / "state" / "app.db"
    database.parent.mkdir()
    monkeypatch.setattr(db_module, "DB_PATH", str(database))
    sqlite3.connect(database).close()
    run_migrations()
    account = tmp_path / "account"
    account.mkdir()
    (account / "UserAttributes.json").write_text(
        json.dumps({"username": "governance-orchestration"}), encoding="utf-8"
    )
    monkeypatch.setattr(api, "ACCOUNT_DATA_DIR", str(account))

    def finish_without_derived_work(run_id, change_set):
        del change_set
        api.update_control_run(run_id, status="succeeded", message="derived stages skipped")
        return {"status": "skipped_in_orchestration_test"}

    monkeypatch.setattr(api, "run_import_stages", finish_without_derived_work)
    return api, database, account


def _plan_run(api, source: Path, *, mode="auto"):
    from backend.domains.imports.source_registry import freeze_local_batch

    batch = freeze_local_batch(source, kind="snapshot")
    return _plan_batch_run(api, batch, mode=mode)


def _plan_batch_run(api, batch, *, mode="auto"):
    from backend.domains.imports.control_store import create_run

    assessment = api.assess_streaming_import(
        api.resolve_batch_directory(batch["batch_id"]),
        api.ACCOUNT_DATA_DIR,
        requested_mode=mode,
        retain_staging=False,
    )
    token = api._batch_confirmation_token(
        batch["batch_id"], assessment.report["confirmation_token"], mode=mode
    )
    run_id = uuid.uuid4().hex[:12]
    create_run(
        run_id=run_id,
        execution_key=run_id,
        batch_id=batch["batch_id"],
        confirmation_digest=token,
        requested_mode=mode,
        detected_relation=assessment.plan.relation.value,
        strategy=assessment.plan.estimated_strategy.value,
        baseline_reason_code=assessment.baseline_reason_code,
        plan=api._plan_payload(assessment),
    )
    return run_id, batch, token, assessment


def _execute(api, planned, *, mode="auto"):
    run_id, batch, token, _assessment = planned
    api._execute_control_run(
        run_id,
        batch["batch_id"],
        mode=mode,
        confirm_plan=True,
        confirmation_digest=token,
    )


def test_snapshot_tail_materializes_replayable_delta_and_noop_is_side_effect_free(
    tmp_path, monkeypatch
):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import active_source_state, get_batch, get_run
    from backend.domains.imports.source_registry import source_dataset_summary, source_root

    api, database, _account = _setup(tmp_path, monkeypatch)
    baseline = _plan_run(api, _source(tmp_path, "baseline", [1, 2]), mode="replace")
    _execute(api, baseline, mode="replace")
    old_source = active_source_state()["active_source_version_id"]

    tail = _plan_run(api, _source(tmp_path, "tail", [2, 3]))
    assert tail[3].plan.relation.value == "delta_tail"
    _execute(api, tail)
    run = get_run(tail[0])
    assert run["publication_state"] == "sources_published"
    assert run["source_version_id"] != run["batch_id"]
    publication = get_batch(run["source_version_id"])
    assert publication["kind"] == "delta"
    assert publication["parent_source_version_id"] == old_source

    conn = db_module.get_db(readonly=True)
    try:
        state = conn.execute(
            "SELECT record_count,dataset_digest,active_source_version_id FROM playback_import_state"
        ).fetchone()
        main_run_count = conn.execute("SELECT COUNT(*) FROM playback_import_runs").fetchone()[0]
    finally:
        conn.close()
    source_summary = source_dataset_summary(run["source_version_id"])
    assert source_summary == {"record_count": state[0], "dataset_digest": state[1]}
    assert state[0] == 3
    assert state[2] == run["source_version_id"]

    # A clean replay through the real importer must reconstruct the same facts.
    from backend.core.import_data import import_data
    from backend.core.migrations import run_migrations

    replay_db = tmp_path / "replay" / "app.db"
    replay_db.parent.mkdir()
    sqlite3.connect(replay_db).close()
    db_module.DB_PATH = str(replay_db)
    run_migrations()
    replay = import_data(
        data_dir=publication["resolved_path"],
        build_preaggregations=False,
        mode="replace",
    )
    assert replay["active_records"] == 3
    assert replay["dataset_digest"] == source_summary["dataset_digest"]
    db_module.DB_PATH = str(database)

    backup_dir = database.parent / "import_backups"
    backups_before = tuple(sorted(backup_dir.glob("*"))) if backup_dir.exists() else ()
    source_versions_before = tuple(sorted(source_root().iterdir()))
    state_before = tuple(state)
    noop = _plan_run(
        api,
        Path(str(publication["resolved_path"])),
    )
    assert noop[3].plan.relation.value == "identical"
    _execute(api, noop)
    noop_run = get_run(noop[0])
    assert noop_run["status"] == "succeeded"
    assert noop_run["result"]["noop"] is True
    conn = db_module.get_db(readonly=True)
    try:
        state_after = tuple(
            conn.execute(
                "SELECT record_count,dataset_digest,active_source_version_id FROM playback_import_state"
            ).fetchone()
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM playback_import_runs").fetchone()[0]
            == main_run_count
        )
    finally:
        conn.close()
    assert state_after == state_before
    assert set(source_root().iterdir()) - set(source_versions_before) == {
        source_root() / noop[1]["batch_id"]
    }
    assert (tuple(sorted(backup_dir.glob("*"))) if backup_dir.exists() else ()) == backups_before


def test_publication_source_matrix_for_snapshot_delta_reconcile_and_replace(tmp_path, monkeypatch):
    from backend.domains.imports.control_store import active_source_state, get_batch, get_run
    from backend.domains.imports.source_registry import freeze_local_batch, source_dataset_summary

    api, _database, _account = _setup(tmp_path, monkeypatch)
    baseline = _plan_run(api, _source(tmp_path, "matrix-baseline", [1, 2]), mode="replace")
    _execute(api, baseline, mode="replace")

    superset = _plan_run(api, _source(tmp_path, "matrix-superset", [1, 2, 3]))
    assert superset[3].plan.relation.value == "snapshot_superset"
    _execute(api, superset)
    superset_run = get_run(superset[0])
    assert superset_run["source_version_id"] == superset_run["batch_id"]
    assert source_dataset_summary(superset_run["source_version_id"])["record_count"] == 3

    parent_id = active_source_state()["active_source_version_id"]
    explicit_delta = freeze_local_batch(
        _source(tmp_path, "matrix-explicit-delta", [4]),
        kind="delta",
        parent_source_version_id=parent_id,
    )
    delta = _plan_batch_run(api, explicit_delta, mode="append")
    assert delta[3].plan.relation.value == "delta_tail"
    _execute(api, delta, mode="append")
    delta_run = get_run(delta[0])
    assert delta_run["source_version_id"] == delta_run["batch_id"]
    assert source_dataset_summary(delta_run["source_version_id"])["record_count"] == 4

    reconcile = _plan_run(api, _source(tmp_path, "matrix-reconcile", [1, 3, 4, 5]))
    assert reconcile[3].plan.relation.value == "reconciled_snapshot"
    _execute(api, reconcile)
    reconcile_run = get_run(reconcile[0])
    reconcile_source = get_batch(reconcile_run["source_version_id"])
    assert reconcile_source["kind"] == "snapshot"
    assert reconcile_source["parent_source_version_id"] is None
    assert source_dataset_summary(reconcile_run["source_version_id"])["record_count"] == 4

    replacement = _plan_run(api, _source(tmp_path, "matrix-replace", [6, 7]), mode="replace")
    _execute(api, replacement, mode="replace")
    replacement_run = get_run(replacement[0])
    replacement_source = get_batch(replacement_run["source_version_id"])
    assert replacement_source["kind"] == "snapshot"
    assert replacement_source["parent_source_version_id"] is None
    assert source_dataset_summary(replacement_run["source_version_id"])["record_count"] == 2


def test_stale_replace_is_rejected_after_real_cross_process_publication(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.domains.imports.control_store import get_run

    api, database, account = _setup(tmp_path, monkeypatch)
    baseline = _plan_run(api, _source(tmp_path, "baseline", [1, 2]), mode="replace")
    _execute(api, baseline, mode="replace")
    stale = _plan_run(api, _source(tmp_path, "stale", [1, 2, 3]), mode="replace")
    winner_source = _source(tmp_path, "winner", [1, 2, 3, 4, 5])
    worker = tmp_path / "cross_process_worker.py"
    worker.write_text(
        """
import json, sys, uuid
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from backend.core import db
db.DB_PATH=sys.argv[2]
from backend.api import import_ as api
api.ACCOUNT_DATA_DIR=sys.argv[3]
def finish(run_id, change_set):
    api.update_control_run(run_id,status='succeeded',message='derived stages skipped')
    return {'status':'skipped'}
api.run_import_stages=finish
from backend.domains.imports.source_registry import freeze_local_batch, resolve_batch_directory
from backend.domains.imports.control_store import create_run, get_run
batch=freeze_local_batch(sys.argv[4],kind='snapshot')
assessment=api.assess_streaming_import(resolve_batch_directory(batch['batch_id']),api.ACCOUNT_DATA_DIR,requested_mode='replace',retain_staging=False)
token=api._batch_confirmation_token(batch['batch_id'],assessment.report['confirmation_token'],mode='replace')
run_id=uuid.uuid4().hex[:12]
create_run(run_id=run_id,execution_key=run_id,batch_id=batch['batch_id'],confirmation_digest=token,requested_mode='replace',detected_relation=assessment.plan.relation.value,strategy='replace',baseline_reason_code=assessment.baseline_reason_code,plan=api._plan_payload(assessment))
api._execute_control_run(run_id,batch['batch_id'],mode='replace',confirm_plan=True,confirmation_digest=token)
print(json.dumps({'run_id':run_id,'status':get_run(run_id)['status']}))
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(worker),
            str(Path(__file__).resolve().parents[3]),
            str(database),
            str(account),
            str(winner_source),
        ],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[3])},
    )
    assert json.loads(completed.stdout)["status"] == "succeeded"

    _execute(api, stale, mode="replace")
    stale_run = get_run(stale[0])
    assert stale_run["status"] == "blocked"
    assert stale_run["publication_state"] == "failed_before_facts"
    assert stale_run["error_code"] == "confirmed_plan_drift"
    conn = db_module.get_db(readonly=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 5
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_replace_transaction_fence_rejects_stale_baseline_before_delete(tmp_path, monkeypatch):
    import pytest

    from backend.core import db as db_module
    from backend.core.import_data import (
        ImportBaselineDriftError,
        ImportBaselineFence,
        import_data,
    )

    api, _database, _account = _setup(tmp_path, monkeypatch)
    baseline = _plan_run(api, _source(tmp_path, "fence-baseline", [1, 2]), mode="replace")
    _execute(api, baseline, mode="replace")
    conn = db_module.get_db(readonly=True)
    try:
        state_before = tuple(
            conn.execute(
                """SELECT active_generation_id,dataset_digest,active_source_version_id,
                          record_count,fingerprint_version
                   FROM playback_import_state"""
            ).fetchone()
        )
        plays_before = conn.execute(
            "SELECT ts,source_fingerprint FROM plays ORDER BY play_id"
        ).fetchall()
    finally:
        conn.close()
    stale_fence = ImportBaselineFence(
        generation_id="stale-generation",
        dataset_digest=state_before[1],
        source_version_id=state_before[2],
        state_record_count=state_before[3],
        play_count=state_before[3],
        fingerprint_version=state_before[4],
    )
    with pytest.raises(ImportBaselineDriftError, match="baseline changed"):
        import_data(
            data_dir=str(_source(tmp_path, "fence-replace", [3])),
            build_preaggregations=False,
            mode="replace",
            expected_baseline=stale_fence,
        )
    conn = db_module.get_db(readonly=True)
    try:
        assert (
            tuple(
                conn.execute(
                    """SELECT active_generation_id,dataset_digest,active_source_version_id,
                          record_count,fingerprint_version
                   FROM playback_import_state"""
                ).fetchone()
            )
            == state_before
        )
        assert (
            conn.execute("SELECT ts,source_fingerprint FROM plays ORDER BY play_id").fetchall()
            == plays_before
        )
    finally:
        conn.close()


def test_prepared_after_fact_commit_recovers_control_evidence_and_source(tmp_path, monkeypatch):
    import pytest

    from backend.domains.imports.control_store import get_run, import_write_gate_state
    from backend.services.import_publication_service import recover_interrupted_publications

    api, _database, _account = _setup(tmp_path, monkeypatch)
    baseline = _plan_run(api, _source(tmp_path, "baseline", [1, 2]), mode="replace")
    _execute(api, baseline, mode="replace")
    crashed = _plan_run(api, _source(tmp_path, "crashed", [1, 2, 3]), mode="replace")

    def hard_stop(*_args, **_kwargs):
        raise KeyboardInterrupt("simulated hard stop after fact commit")

    monkeypatch.setattr(api, "mark_facts_committed", hard_stop)
    with pytest.raises(KeyboardInterrupt):
        _execute(api, crashed, mode="replace")
    run = get_run(crashed[0])
    assert run["publication_state"] == "prepared"
    assert run["change_set"] is None
    assert import_write_gate_state()["blocked"] == 1
    monkeypatch.undo()
    # Restore only the paths needed after undoing the injected hard stop.
    from backend.api import import_ as restored_api
    from backend.core import db as restored_db

    restored_db.DB_PATH = str(_database)
    restored_api.ACCOUNT_DATA_DIR = str(_account)
    assert recover_interrupted_publications() == {
        "completed": 1,
        "not_committed": 0,
        "blocked": 0,
    }
    recovered = get_run(crashed[0])
    assert recovered["publication_state"] == "sources_published"
    assert recovered["change_set"] is not None
    assert recovered["new_generation_id"] == recovered["change_set"]["generation_id"]
    assert import_write_gate_state()["blocked"] == 0
