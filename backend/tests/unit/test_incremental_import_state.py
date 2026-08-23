from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from backend.core.migrations import migrate_037
from backend.domains.imports.incremental import (
    FINGERPRINT_VERSION,
    FingerprintRecord,
    ImportCoverage,
    build_import_plan,
    dataset_digest,
)
from backend.domains.imports.state import (
    FingerprintBaselineError,
    PlaybackImportRunStatus,
    publish_playback_import_state,
    record_playback_import_run,
    summarise_current_playback_dataset,
)

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'audio'
        )"""
    )
    migrate_037(conn)
    conn.commit()
    return conn


def _insert_play(
    conn: sqlite3.Connection,
    *,
    play_id: int,
    source_type: str,
    fingerprint: str | None,
    version: int | None = FINGERPRINT_VERSION,
    timestamp: str = "2026-08-01T00:00:00Z",
) -> None:
    conn.execute(
        """INSERT INTO plays(
               play_id, ts, content_type,
               source_fingerprint, source_fingerprint_version
           ) VALUES (?, ?, ?, ?, ?)""",
        (play_id, timestamp, source_type, fingerprint, version),
    )


def test_summarise_current_playback_dataset_uses_shared_digest_and_range() -> None:
    conn = _connection()
    try:
        _insert_play(
            conn,
            play_id=1,
            source_type="video",
            fingerprint="b" * 64,
            timestamp="2026-08-03T00:00:00Z",
        )
        _insert_play(
            conn,
            play_id=2,
            source_type="audio",
            fingerprint="a" * 64,
            timestamp="2026-08-01T00:00:00Z",
        )

        summary = summarise_current_playback_dataset(conn)

        assert summary.fingerprint_version == FINGERPRINT_VERSION
        assert summary.dataset_digest == dataset_digest(
            [
                FingerprintRecord("audio", "a" * 64),
                FingerprintRecord("video", "b" * 64),
            ]
        )
        assert summary.record_count == 2
        assert summary.first_ts == "2026-08-01T00:00:00Z"
        assert summary.latest_ts == "2026-08-03T00:00:00Z"
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("fingerprint", "version"),
    [(None, None), ("a" * 64, FINGERPRINT_VERSION + 1)],
)
def test_summarise_current_playback_dataset_rejects_incomplete_baseline(
    fingerprint: str | None,
    version: int | None,
) -> None:
    conn = _connection()
    try:
        _insert_play(
            conn,
            play_id=1,
            source_type="audio",
            fingerprint=fingerprint,
            version=version,
        )

        with pytest.raises(FingerprintBaselineError):
            summarise_current_playback_dataset(conn)
    finally:
        conn.close()


def test_publish_playback_import_state_stays_in_caller_transaction() -> None:
    conn = _connection()
    try:
        _insert_play(
            conn,
            play_id=1,
            source_type="audio",
            fingerprint="a" * 64,
        )
        conn.commit()
        summary = publish_playback_import_state(
            conn,
            generation_id="generation-1",
            account_identity_hash="account-hash",
            relation="baseline_required",
            strategy="full",
            updated_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        assert conn.in_transaction
        state = conn.execute("SELECT * FROM playback_import_state WHERE state_id=1").fetchone()
        assert state["active_generation_id"] == "generation-1"
        assert state["dataset_digest"] == summary.dataset_digest
        assert state["record_count"] == 1

        conn.rollback()
        rolled_back = conn.execute(
            "SELECT active_generation_id FROM playback_import_state WHERE state_id=1"
        ).fetchone()
        assert rolled_back[0] is None
    finally:
        conn.close()


@pytest.mark.parametrize(
    "status",
    ["maintenance_pending", "recovery_blocked", "success", "noop", "needs_confirmation"],
)
def test_record_playback_import_run_is_compact_private_and_transactional(
    status: PlaybackImportRunStatus,
) -> None:
    incoming = [
        FingerprintRecord(
            "audio",
            "a" * 64,
            datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
    ]
    plan = build_import_plan(
        incoming,
        existing_records=[],
        coverage=ImportCoverage.SNAPSHOT,
    )
    conn = _connection()
    try:
        record_playback_import_run(
            conn,
            run_id=f"run-{status}",
            requested_mode="auto",
            status=status,
            plan=plan,
            earliest_changed_ts=datetime(2026, 8, 23, tzinfo=timezone.utc),
            latest_changed_ts=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        assert conn.in_transaction
        row = conn.execute(
            "SELECT * FROM playback_import_runs WHERE run_id=?",
            (f"run-{status}",),
        ).fetchone()
        payload = json.loads(row["plan_json"])
        assert row["status"] == status
        assert (row["completed_at"] is None) is (status == "maintenance_pending")
        assert row["incoming_count"] == 1
        assert row["added_count"] == 1
        assert set(payload) == {
            "schema_version",
            "detected_relation",
            "estimated_strategy",
            "requires_confirmation",
            "existing_count",
            "incoming_count",
            "unchanged_count",
            "added_count",
            "removed_count",
        }
        assert "fingerprint" not in row["plan_json"]
        assert "username" not in row["plan_json"]

        conn.rollback()
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM playback_import_runs WHERE run_id=?",
                (f"run-{status}",),
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_record_playback_import_run_promotes_pending_row_without_duplicate() -> None:
    plan = build_import_plan([], existing_records=[])
    conn = _connection()
    try:
        record_playback_import_run(
            conn,
            run_id="run-promote",
            requested_mode="auto",
            status="maintenance_pending",
            plan=plan,
        )
        started_at = conn.execute(
            "SELECT started_at FROM playback_import_runs WHERE run_id='run-promote'"
        ).fetchone()[0]
        record_playback_import_run(
            conn,
            run_id="run-promote",
            requested_mode="auto",
            status="success",
            plan=plan,
        )
        row = conn.execute(
            "SELECT status, started_at, completed_at FROM playback_import_runs "
            "WHERE run_id='run-promote'"
        ).fetchone()
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM playback_import_runs WHERE run_id='run-promote'"
            ).fetchone()[0]
            == 1
        )
        assert row["status"] == "success"
        assert row["started_at"] == started_at
        assert row["completed_at"] is not None
    finally:
        conn.close()


def test_record_playback_import_run_rejects_non_terminal_status() -> None:
    plan = build_import_plan([], existing_records=[])
    conn = _connection()
    try:
        with pytest.raises(ValueError, match="unsupported"):
            record_playback_import_run(
                conn,
                run_id="run-running",
                requested_mode="auto",
                status="running",  # type: ignore[arg-type]
                plan=plan,
            )
    finally:
        conn.close()
