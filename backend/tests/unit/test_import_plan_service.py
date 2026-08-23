from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            content_type TEXT NOT NULL,
            source_fingerprint TEXT,
            source_fingerprint_version INTEGER,
            import_generation_id TEXT
        );
        CREATE TABLE playback_import_state (
            state_id INTEGER PRIMARY KEY,
            active_generation_id TEXT,
            account_identity_hash TEXT,
            fingerprint_version INTEGER,
            dataset_digest TEXT,
            record_count INTEGER NOT NULL DEFAULT 0,
            first_ts TEXT,
            latest_ts TEXT,
            last_relation TEXT,
            last_strategy TEXT,
            updated_at TEXT
        );
        INSERT INTO playback_import_state(state_id, record_count) VALUES (1, 0);
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    return conn


def _source_dirs(tmp_path, records):
    streaming_dir = tmp_path / "streaming"
    account_dir = tmp_path / "account"
    streaming_dir.mkdir()
    account_dir.mkdir()
    (streaming_dir / "Streaming_History_Audio_000.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
    return streaming_dir, account_dir


def test_preflight_reports_baseline_required_without_writing(tmp_path):
    from backend.services.import_plan_service import build_streaming_import_preflight

    conn = _connection()
    conn.execute(
        """INSERT INTO plays(play_id, ts, content_type)
           VALUES (1, '2025-01-01T00:00:00Z', 'audio')"""
    )
    conn.commit()
    streaming_dir, account_dir = _source_dirs(
        tmp_path,
        [{"ts": "2026-01-02T01:02:03Z", "ms_played": 30_000}],
    )
    before = conn.total_changes

    report = build_streaming_import_preflight(
        streaming_dir,
        account_dir,
        conn=conn,
    )
    replace_report = build_streaming_import_preflight(
        streaming_dir,
        account_dir,
        requested_mode="replace",
        conn=conn,
    )

    assert report["fingerprint_baseline_status"] == "missing"
    assert report["detected_relation"] == "baseline_required"
    assert report["estimated_strategy"] == "full"
    assert report["requires_confirmation"] is True
    assert len(report["confirmation_token"]) == 64
    assert replace_report["confirmation_token"] == report["confirmation_token"]
    assert report["existing_record_count"] == 1
    assert report["incoming_record_count"] == 1
    assert conn.total_changes == before


def test_preflight_identifies_an_exact_ready_dataset(tmp_path):
    from backend.domains.imports.incremental import FingerprintRecord, dataset_digest
    from backend.domains.imports.source_inspector import record_fingerprint
    from backend.services.import_plan_service import build_streaming_import_preflight

    record = {"ts": "2026-01-02T01:02:03Z", "ms_played": 30_000}
    fingerprint = record_fingerprint(record)
    digest = dataset_digest([FingerprintRecord("audio", fingerprint, timestamp=None)])
    conn = _connection()
    conn.execute(
        """INSERT INTO plays(
               play_id, ts, content_type, source_fingerprint,
               source_fingerprint_version, import_generation_id
           ) VALUES (1, ?, 'audio', ?, 1, 'generation-1')""",
        (record["ts"], fingerprint),
    )
    conn.execute(
        """UPDATE playback_import_state
           SET active_generation_id='generation-1', fingerprint_version=1,
               dataset_digest=?, record_count=1""",
        (digest,),
    )
    conn.commit()
    streaming_dir, account_dir = _source_dirs(tmp_path, [record])

    report = build_streaming_import_preflight(
        streaming_dir,
        account_dir,
        conn=conn,
    )

    assert report["fingerprint_baseline_status"] == "ready"
    assert report["detected_relation"] == "identical"
    assert report["estimated_strategy"] == "noop"
    assert report["unchanged_record_count"] == 1
    assert report["added_record_count"] == 0
    assert report["removed_record_count"] == 0
    assert report["affected_weeks_count"] == 0


def test_preflight_hashes_username_without_exposing_it(tmp_path):
    from backend.domains.imports.incremental import FingerprintRecord, dataset_digest
    from backend.domains.imports.source_inspector import record_fingerprint
    from backend.services.import_plan_service import build_streaming_import_preflight

    username = "private-user-name"
    record = {"ts": "2026-01-02T01:02:03Z", "ms_played": 30_000}
    fingerprint = record_fingerprint(record)
    digest = dataset_digest([FingerprintRecord("audio", fingerprint)])
    account_hash = hashlib.sha256(
        b"spotifystats-account-v1\0" + username.casefold().encode("utf-8")
    ).hexdigest()
    conn = _connection()
    conn.execute(
        """INSERT INTO plays VALUES (
               1, ?, 'audio', ?, 1, 'generation-1'
           )""",
        (record["ts"], fingerprint),
    )
    conn.execute(
        """UPDATE playback_import_state
           SET active_generation_id='generation-1', account_identity_hash=?,
               fingerprint_version=1, dataset_digest=?, record_count=1""",
        (account_hash, digest),
    )
    conn.commit()
    streaming_dir, account_dir = _source_dirs(tmp_path, [record])
    (account_dir / "UserAttributes.json").write_text(
        json.dumps({"username": username}), encoding="utf-8"
    )

    report = build_streaming_import_preflight(
        streaming_dir,
        account_dir,
        conn=conn,
    )

    assert report["account_identity_status"] == "matched"
    assert username not in json.dumps(report)
