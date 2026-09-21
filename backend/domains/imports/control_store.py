"""Durable import control plane kept outside the restorable application DB.

This database stores orchestration evidence only.  Playback facts remain in the
main SQLite database and every recovery decision must fence against that state.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core import db as db_module

CONTROL_SCHEMA_VERSION = 2
logger = logging.getLogger(__name__)
_UNSET = object()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def control_root(db_path: str | None = None) -> Path:
    database = Path(db_path or db_module.DB_PATH).resolve()
    if database.name == "spotify_stats.db":
        return database.parent / "import_control"
    return database.parent / f".{database.name}.import_control"


def control_db_path(db_path: str | None = None) -> Path:
    return control_root(db_path) / "control.sqlite3"


def source_root(db_path: str | None = None) -> Path:
    database = Path(db_path or db_module.DB_PATH).resolve()
    if database.name == "spotify_stats.db":
        return database.parent / "import_sources"
    return database.parent / f".{database.name}.import_sources"


def connect_control(db_path: str | None = None) -> sqlite3.Connection:
    root = control_root(db_path)
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    conn = sqlite3.connect(control_db_path(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS control_schema (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS import_batches (
            batch_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK(kind IN ('snapshot','delta','legacy')),
            status TEXT NOT NULL CHECK(status IN ('receiving','frozen','invalid','published')),
            parent_source_version_id TEXT,
            packet_path TEXT NOT NULL,
            resolved_path TEXT NOT NULL,
            manifest_json TEXT NOT NULL,
            manifest_digest TEXT NOT NULL,
            fingerprint_contract_version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            frozen_at TEXT,
            error_code TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_import_batch_content
            ON import_batches(kind, manifest_digest, COALESCE(parent_source_version_id,''))
            WHERE status IN ('frozen','published');
        CREATE TABLE IF NOT EXISTS import_source_state (
            state_id INTEGER PRIMARY KEY CHECK(state_id=1),
            active_source_version_id TEXT,
            active_generation_id TEXT,
            active_dataset_digest TEXT,
            updated_at TEXT NOT NULL
        );
        INSERT OR IGNORE INTO import_source_state(state_id, updated_at)
            VALUES (1, datetime('now'));
        CREATE TABLE IF NOT EXISTS import_runs (
            run_id TEXT PRIMARY KEY,
            execution_key TEXT NOT NULL UNIQUE,
            batch_id TEXT NOT NULL REFERENCES import_batches(batch_id),
            source_version_id TEXT NOT NULL REFERENCES import_batches(batch_id),
            confirmation_digest TEXT NOT NULL,
            requested_mode TEXT NOT NULL,
            detected_relation TEXT,
            strategy TEXT,
            baseline_reason_code TEXT,
            status TEXT NOT NULL,
            publication_state TEXT NOT NULL,
            progress_pct REAL NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            result_json TEXT,
            plan_json TEXT,
            change_set_json TEXT,
            old_generation_id TEXT,
            old_dataset_digest TEXT,
            old_source_version_id TEXT,
            new_generation_id TEXT,
            new_dataset_digest TEXT,
            database_snapshot_path TEXT,
            recovery_status TEXT,
            error_code TEXT,
            error_detail TEXT,
            retryable INTEGER NOT NULL DEFAULT 0,
            report_status TEXT NOT NULL DEFAULT 'pending',
            report_error_code TEXT,
            report_updated_at TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_import_runs_started
            ON import_runs(started_at DESC, run_id DESC);
        CREATE INDEX IF NOT EXISTS idx_import_runs_publication
            ON import_runs(publication_state, updated_at);
        CREATE TABLE IF NOT EXISTS import_stage_runs (
            run_id TEXT NOT NULL REFERENCES import_runs(run_id) ON DELETE CASCADE,
            stage TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            target_generation_id TEXT NOT NULL,
            target_dataset_digest TEXT NOT NULL,
            dependency_revision_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL,
            strategy TEXT,
            fallback_reason TEXT,
            output_evidence_json TEXT,
            job_id TEXT,
            error_code TEXT,
            error_detail TEXT,
            retryable INTEGER NOT NULL DEFAULT 0,
            queued_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            PRIMARY KEY(run_id, stage, attempt)
        );
        CREATE INDEX IF NOT EXISTS idx_import_stage_latest
            ON import_stage_runs(run_id, stage, attempt DESC);
        CREATE TABLE IF NOT EXISTS import_write_gate (
            state_id INTEGER PRIMARY KEY CHECK(state_id=1),
            blocked INTEGER NOT NULL DEFAULT 0,
            run_id TEXT,
            reason_code TEXT,
            updated_at TEXT NOT NULL
        );
        INSERT OR IGNORE INTO import_write_gate(state_id, blocked, updated_at)
            VALUES (1, 0, datetime('now'));
        """
    )
    run_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(import_runs)")}
    for column, declaration in {
        "report_status": "TEXT NOT NULL DEFAULT 'pending'",
        "report_error_code": "TEXT",
        "report_updated_at": "TEXT",
    }.items():
        if column not in run_columns:
            conn.execute(f"ALTER TABLE import_runs ADD COLUMN {column} {declaration}")
    conn.execute(
        "INSERT OR IGNORE INTO control_schema(version, applied_at) VALUES (?, ?)",
        (CONTROL_SCHEMA_VERSION, utc_now()),
    )
    conn.commit()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def create_run(
    *,
    run_id: str,
    execution_key: str,
    batch_id: str,
    confirmation_digest: str,
    requested_mode: str,
    detected_relation: str | None,
    strategy: str | None,
    baseline_reason_code: str | None,
    plan: dict[str, Any],
    db_path: str | None = None,
) -> tuple[str, bool]:
    """Create one idempotent execution record, returning (run_id, created)."""

    conn = connect_control(db_path)
    now = utc_now()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT run_id FROM import_runs WHERE execution_key=?", (execution_key,)
        ).fetchone()
        if existing is not None:
            conn.rollback()
            return str(existing[0]), False
        conn.execute(
            """INSERT INTO import_runs(
                   run_id, execution_key, batch_id, source_version_id,
                   confirmation_digest, requested_mode, detected_relation,
                   strategy, baseline_reason_code, status, publication_state,
                   plan_json, started_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'planned', ?, ?, ?)""",
            (
                run_id,
                execution_key,
                batch_id,
                batch_id,
                confirmation_digest,
                requested_mode,
                detected_relation,
                strategy,
                baseline_reason_code,
                json_text(plan),
                now,
                now,
            ),
        )
        conn.commit()
        return run_id, True
    finally:
        conn.close()


def update_run(run_id: str, *, db_path: str | None = None, **fields: Any) -> None:
    allowed = {
        "status",
        "publication_state",
        "progress_pct",
        "message",
        "result_json",
        "change_set_json",
        "source_version_id",
        "old_generation_id",
        "old_dataset_digest",
        "old_source_version_id",
        "new_generation_id",
        "new_dataset_digest",
        "database_snapshot_path",
        "recovery_status",
        "error_code",
        "error_detail",
        "retryable",
        "completed_at",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unsupported import run fields: {sorted(unknown)}")
    if not fields:
        return
    values = dict(fields)
    if "progress_pct" in values:
        values["progress_pct"] = max(0.0, min(1.0, float(values["progress_pct"])))
    if (
        "result_json" in values
        and values["result_json"] is not None
        and not isinstance(values["result_json"], str)
    ):
        values["result_json"] = json_text(values["result_json"])
    if (
        "change_set_json" in values
        and values["change_set_json"] is not None
        and not isinstance(values["change_set_json"], str)
    ):
        values["change_set_json"] = json_text(values["change_set_json"])
    values["updated_at"] = utc_now()
    assignments = ", ".join(f"{name}=?" for name in values)
    conn = connect_control(db_path)
    try:
        cursor = conn.execute(
            f"UPDATE import_runs SET {assignments} WHERE run_id=?",
            (*values.values(), run_id),
        )
        if cursor.rowcount != 1:
            raise KeyError(run_id)
        conn.commit()
    finally:
        conn.close()
    if values.get("status") in {
        "failed",
        "retryable_failed",
        "blocked",
        "succeeded",
        "superseded",
    } or values.get("publication_state") in {"core_ready", "ready", "recovery_blocked"}:
        try:
            from backend.services.import_run_report_service import write_import_run_reports

            write_import_run_reports(run_id, db_path=db_path)
        except Exception as exc:
            # Reporting is evidence about the import, not part of the playback
            # publication transaction. Keep the run state durable if local
            # report storage is unavailable and retain a diagnostic traceback.
            logger.exception("Failed to write import run report: run_id=%s", run_id)
            record_report_result(
                run_id,
                status="failed",
                error_code=getattr(exc, "error_code", "report_write_failed"),
                db_path=db_path,
            )
        else:
            record_report_result(run_id, status="ready", error_code=None, db_path=db_path)


def record_report_result(
    run_id: str,
    *,
    status: str,
    error_code: str | None,
    db_path: str | None = None,
) -> None:
    conn = connect_control(db_path)
    try:
        conn.execute(
            """UPDATE import_runs
               SET report_status=?, report_error_code=?, report_updated_at=?, updated_at=?
               WHERE run_id=?""",
            (status, error_code, utc_now(), utc_now(), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def import_write_gate_state(*, db_path: str | None = None) -> dict[str, Any]:
    conn = connect_control(db_path)
    try:
        row = conn.execute("SELECT * FROM import_write_gate WHERE state_id=1").fetchone()
        result = dict(row) if row is not None else {"blocked": 0}
        if not result.get("blocked"):
            pending = conn.execute(
                """SELECT run_id,publication_state FROM import_runs
                   WHERE publication_state IN ('prepared','facts_committed')
                   ORDER BY started_at LIMIT 1"""
            ).fetchone()
            if pending is not None:
                result.update(
                    blocked=1,
                    run_id=str(pending[0]),
                    reason_code=f"publication_{pending[1]}",
                )
        return result
    finally:
        conn.close()


def quarantine_import_writes(
    run_id: str,
    reason_code: str,
    *,
    db_path: str | None = None,
) -> None:
    conn = connect_control(db_path)
    try:
        conn.execute(
            """UPDATE import_write_gate
               SET blocked=1, run_id=?, reason_code=?, updated_at=? WHERE state_id=1""",
            (run_id, reason_code, utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def clear_import_write_quarantine(
    run_id: str,
    *,
    db_path: str | None = None,
) -> None:
    conn = connect_control(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT blocked,run_id FROM import_write_gate WHERE state_id=1"
        ).fetchone()
        if row is not None and bool(row[0]) and str(row[1] or "") not in {"", run_id}:
            raise RuntimeError("import_write_gate_owned_by_another_run")
        conn.execute(
            """UPDATE import_write_gate
               SET blocked=0, run_id=NULL, reason_code=NULL, updated_at=? WHERE state_id=1""",
            (utc_now(),),
        )
        conn.commit()
    finally:
        conn.close()


def mark_sources_published_and_clear_quarantine(
    run_id: str,
    *,
    progress_pct: float,
    message: str,
    db_path: str | None = None,
) -> None:
    """Atomically finish source publication and release its durable write gate."""

    conn = connect_control(db_path)
    now = utc_now()
    try:
        conn.execute("BEGIN IMMEDIATE")
        gate = conn.execute(
            "SELECT blocked,run_id FROM import_write_gate WHERE state_id=1"
        ).fetchone()
        if gate is not None and bool(gate[0]) and str(gate[1] or "") != run_id:
            raise RuntimeError("import_write_gate_owned_by_another_run")
        cursor = conn.execute(
            """UPDATE import_runs
               SET status='running', publication_state='sources_published',
                   progress_pct=?, message=?, error_code=NULL, error_detail=NULL,
                   retryable=0, completed_at=NULL, updated_at=?
               WHERE run_id=? AND publication_state IN ('facts_committed','sources_published')""",
            (max(0.0, min(1.0, float(progress_pct))), message, now, run_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("source_publication_run_compare_and_swap_failed")
        conn.execute(
            """UPDATE import_write_gate
               SET blocked=0, run_id=NULL, reason_code=NULL, updated_at=?
               WHERE state_id=1""",
            (now,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def recover_prepared_facts(
    run_id: str,
    *,
    generation_id: str,
    dataset_digest: str,
    change_set: dict[str, Any],
    db_path: str | None = None,
) -> None:
    """CAS a prepared run forward using evidence committed in the main DB."""

    conn = connect_control(db_path)
    now = utc_now()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """UPDATE import_runs
               SET status='running', publication_state='facts_committed',
                   new_generation_id=?, new_dataset_digest=?, change_set_json=?,
                   progress_pct=0.6,
                   message='已从主库恢复事实提交证据，正在发布活动原始来源',
                   recovery_status='facts_evidence_recovered',
                   error_code=NULL, error_detail=NULL, retryable=0,
                   completed_at=NULL, updated_at=?
               WHERE run_id=? AND publication_state='prepared'""",
            (generation_id, dataset_digest, json_text(change_set), now, run_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("prepared_fact_recovery_compare_and_swap_failed")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_run(run_id: str, *, db_path: str | None = None) -> dict[str, Any] | None:
    conn = connect_control(db_path)
    try:
        row = conn.execute("SELECT * FROM import_runs WHERE run_id=?", (run_id,)).fetchone()
        return _run_dict(row) if row is not None else None
    finally:
        conn.close()


def list_runs(
    *, limit: int = 50, offset: int = 0, db_path: str | None = None
) -> list[dict[str, Any]]:
    conn = connect_control(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM import_runs ORDER BY started_at DESC, run_id DESC LIMIT ? OFFSET ?",
            (max(1, min(201, int(limit))), max(0, int(offset))),
        ).fetchall()
        return [_run_dict(row) for row in rows]
    finally:
        conn.close()


def _run_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in ("result_json", "plan_json", "change_set_json"):
        encoded = result.pop(key, None)
        result[key.removesuffix("_json")] = json.loads(encoded) if encoded else None
    result["retryable"] = bool(result.get("retryable"))
    return result


def pending_publications(*, db_path: str | None = None) -> list[dict[str, Any]]:
    conn = connect_control(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM import_runs
               WHERE publication_state IN ('prepared','facts_committed')
               ORDER BY started_at, run_id"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def set_active_source(
    source_version_id: str,
    generation_id: str,
    dataset_digest: str,
    *,
    expected_source_version_id: str | None | object = _UNSET,
    db_path: str | None = None,
) -> None:
    conn = connect_control(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute(
            "SELECT status FROM import_batches WHERE batch_id=?", (source_version_id,)
        ).fetchone()
        if batch is None or str(batch[0]) not in {"frozen", "published"}:
            raise KeyError(source_version_id)
        current = conn.execute(
            "SELECT active_source_version_id FROM import_source_state WHERE state_id=1"
        ).fetchone()
        if expected_source_version_id is not _UNSET and str(
            current[0] if current is not None and current[0] is not None else ""
        ) != str(expected_source_version_id or ""):
            raise RuntimeError("active_source_compare_and_swap_failed")
        conn.execute(
            """UPDATE import_source_state
               SET active_source_version_id=?, active_generation_id=?,
                   active_dataset_digest=?, updated_at=? WHERE state_id=1""",
            (source_version_id, generation_id, dataset_digest, utc_now()),
        )
        conn.execute(
            "UPDATE import_batches SET status='published' WHERE batch_id=?",
            (source_version_id,),
        )
        conn.commit()
    finally:
        conn.close()


def restore_active_source(
    source_version_id: str | None,
    generation_id: str | None,
    dataset_digest: str | None,
    *,
    expected_source_version_id: str,
    db_path: str | None = None,
) -> None:
    """Restore the external source pointer after a partially failed publication."""

    conn = connect_control(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT active_source_version_id FROM import_source_state WHERE state_id=1"
        ).fetchone()
        if str(current[0] if current is not None and current[0] is not None else "") != str(
            expected_source_version_id
        ):
            raise RuntimeError("active_source_restore_compare_and_swap_failed")
        if source_version_id is not None:
            batch = conn.execute(
                "SELECT status FROM import_batches WHERE batch_id=?", (source_version_id,)
            ).fetchone()
            if batch is None or str(batch[0]) not in {"frozen", "published"}:
                raise KeyError(source_version_id)
        conn.execute(
            """UPDATE import_source_state
               SET active_source_version_id=?, active_generation_id=?,
                   active_dataset_digest=?, updated_at=? WHERE state_id=1""",
            (source_version_id, generation_id, dataset_digest, utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def active_source_state(*, db_path: str | None = None) -> dict[str, Any]:
    conn = connect_control(db_path)
    try:
        row = conn.execute("SELECT * FROM import_source_state WHERE state_id=1").fetchone()
        return dict(row) if row is not None else {}
    finally:
        conn.close()


def start_stage_attempt(
    run_id: str,
    stage: str,
    generation_id: str,
    dataset_digest: str,
    *,
    dependency_revision: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> int:
    conn = connect_control(db_path)
    now = utc_now()
    try:
        conn.execute("BEGIN IMMEDIATE")
        attempt = int(
            conn.execute(
                "SELECT COALESCE(MAX(attempt),0)+1 FROM import_stage_runs WHERE run_id=? AND stage=?",
                (run_id, stage),
            ).fetchone()[0]
        )
        conn.execute(
            """INSERT INTO import_stage_runs(
                   run_id,stage,attempt,target_generation_id,target_dataset_digest,
                   dependency_revision_json,status,queued_at,started_at
               ) VALUES (?,?,?,?,?,?,'running',?,?)""",
            (
                run_id,
                stage,
                attempt,
                generation_id,
                dataset_digest,
                json_text(dependency_revision or {}),
                now,
                now,
            ),
        )
        conn.commit()
        return attempt
    finally:
        conn.close()


def finish_stage_attempt(
    run_id: str,
    stage: str,
    attempt: int,
    *,
    status: str,
    output: dict[str, Any] | None = None,
    strategy: str | None = None,
    fallback_reason: str | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    retryable: bool = False,
    db_path: str | None = None,
) -> None:
    conn = connect_control(db_path)
    try:
        conn.execute(
            """UPDATE import_stage_runs
               SET status=?, output_evidence_json=?, strategy=?, fallback_reason=?,
                   error_code=?, error_detail=?, retryable=?, completed_at=?
               WHERE run_id=? AND stage=? AND attempt=?""",
            (
                status,
                json_text(output) if output is not None else None,
                strategy,
                fallback_reason,
                error_code,
                error_detail,
                int(retryable),
                utc_now(),
                run_id,
                stage,
                attempt,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def latest_stage_attempts(run_id: str, *, db_path: str | None = None) -> list[dict[str, Any]]:
    conn = connect_control(db_path)
    try:
        rows = conn.execute(
            """SELECT s.* FROM import_stage_runs s
               JOIN (
                   SELECT stage, MAX(attempt) AS attempt
                   FROM import_stage_runs WHERE run_id=? GROUP BY stage
               ) latest ON latest.stage=s.stage AND latest.attempt=s.attempt
               WHERE s.run_id=? ORDER BY s.queued_at, s.stage""",
            (run_id, run_id),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            encoded = item.pop("output_evidence_json", None)
            item["output_evidence"] = json.loads(encoded) if encoded else None
            encoded_dependency = item.pop("dependency_revision_json", None)
            item["dependency_revision"] = (
                json.loads(encoded_dependency) if encoded_dependency else {}
            )
            item["retryable"] = bool(item.get("retryable"))
            result.append(item)
        return result
    finally:
        conn.close()


def latest_successful_stage_output(
    run_id: str, stage: str, *, db_path: str | None = None
) -> dict[str, Any] | None:
    conn = connect_control(db_path)
    try:
        row = conn.execute(
            """SELECT output_evidence_json FROM import_stage_runs
               WHERE run_id=? AND stage=? AND status='succeeded'
               ORDER BY attempt DESC LIMIT 1""",
            (run_id, stage),
        ).fetchone()
        return json.loads(row[0]) if row is not None and row[0] else None
    finally:
        conn.close()


def supersede_other_runs(
    active_run_id: str, generation_id: str, *, db_path: str | None = None
) -> None:
    conn = connect_control(db_path)
    try:
        conn.execute(
            """UPDATE import_runs
               SET status='superseded', publication_state='superseded',
                   completed_at=?, updated_at=?, error_code='generation_superseded'
               WHERE run_id<>? AND new_generation_id IS NOT NULL
                 AND new_generation_id<>?
                 AND status NOT IN ('succeeded','failed','blocked','superseded')""",
            (utc_now(), utc_now(), active_run_id, generation_id),
        )
        conn.commit()
    finally:
        conn.close()


def pending_stage_runs(*, db_path: str | None = None) -> list[dict[str, Any]]:
    conn = connect_control(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM import_runs
               WHERE publication_state IN ('sources_published','core_ready')
                 AND status NOT IN ('succeeded','failed','blocked','superseded')
               ORDER BY started_at,run_id"""
        ).fetchall()
        return [_run_dict(row) for row in rows]
    finally:
        conn.close()


def insert_batch(row: dict[str, Any], *, db_path: str | None = None) -> str:
    conn = connect_control(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """SELECT batch_id FROM import_batches
               WHERE kind=? AND manifest_digest=?
                 AND COALESCE(parent_source_version_id,'')=COALESCE(?,'')
                 AND status IN ('frozen','published')""",
            (row["kind"], row["manifest_digest"], row.get("parent_source_version_id")),
        ).fetchone()
        if existing is not None:
            conn.rollback()
            return str(existing[0])
        conn.execute(
            """INSERT INTO import_batches(
                   batch_id,kind,status,parent_source_version_id,packet_path,resolved_path,
                   manifest_json,manifest_digest,fingerprint_contract_version,
                   created_at,frozen_at,error_code
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["batch_id"],
                row["kind"],
                row["status"],
                row.get("parent_source_version_id"),
                row["packet_path"],
                row["resolved_path"],
                json_text(row["manifest"]),
                row["manifest_digest"],
                row["fingerprint_contract_version"],
                row["created_at"],
                row.get("frozen_at"),
                row.get("error_code"),
            ),
        )
        conn.commit()
        return str(row["batch_id"])
    finally:
        conn.close()


def update_batch(batch_id: str, *, db_path: str | None = None, **fields: Any) -> None:
    allowed = {
        "status",
        "resolved_path",
        "manifest_json",
        "manifest_digest",
        "frozen_at",
        "error_code",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unsupported import batch fields: {sorted(unknown)}")
    if not fields:
        return
    values = dict(fields)
    if "manifest_json" in values and not isinstance(values["manifest_json"], str):
        values["manifest_json"] = json_text(values["manifest_json"])
    assignments = ", ".join(f"{name}=?" for name in values)
    conn = connect_control(db_path)
    try:
        cursor = conn.execute(
            f"UPDATE import_batches SET {assignments} WHERE batch_id=?",
            (*values.values(), batch_id),
        )
        if cursor.rowcount != 1:
            raise KeyError(batch_id)
        conn.commit()
    finally:
        conn.close()


def get_batch(batch_id: str, *, db_path: str | None = None) -> dict[str, Any] | None:
    conn = connect_control(db_path)
    try:
        row = conn.execute("SELECT * FROM import_batches WHERE batch_id=?", (batch_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["manifest"] = json.loads(result.pop("manifest_json"))
        return result
    finally:
        conn.close()


def find_frozen_batch(
    kind: str,
    manifest_digest: str,
    parent_source_version_id: str | None,
    *,
    db_path: str | None = None,
) -> dict[str, Any] | None:
    conn = connect_control(db_path)
    try:
        row = conn.execute(
            """SELECT * FROM import_batches
               WHERE kind=? AND manifest_digest=?
                 AND COALESCE(parent_source_version_id,'')=COALESCE(?,'')
                 AND status IN ('frozen','published') LIMIT 1""",
            (kind, manifest_digest, parent_source_version_id),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["manifest"] = json.loads(result.pop("manifest_json"))
        return result
    finally:
        conn.close()


def iter_batches(batch_ids: Iterable[str], *, db_path: str | None = None) -> list[dict[str, Any]]:
    return [batch for batch_id in batch_ids if (batch := get_batch(batch_id, db_path=db_path))]
