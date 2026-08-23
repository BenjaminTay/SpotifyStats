from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pytest

from backend.domains.imports.incremental import (
    FingerprintRecord,
    build_import_plan,
)
from backend.domains.imports.source_inspector import record_fingerprint
from backend.services.import_plan_service import StreamingImportAssessment

pytestmark = pytest.mark.unit


def _raw_record(track_id: str, timestamp: str) -> dict[str, object]:
    return {
        "ts": timestamp,
        "conn_country": "CN",
        "platform": "ios",
        "ms_played": 180_000,
        "master_metadata_track_name": f"Track {track_id}",
        "master_metadata_album_artist_name": "Phase B Artist",
        "master_metadata_album_album_name": "Phase B Album",
        "spotify_track_uri": f"spotify:track:{track_id}",
    }


def _assessment(records, *, existing_records=None) -> StreamingImportAssessment:
    fingerprint_records = [
        FingerprintRecord(
            source_type="audio",
            fingerprint=record_fingerprint(record),
            timestamp=datetime.fromisoformat(str(record["ts"]).replace("Z", "+00:00")),
        )
        for record in records
    ]
    plan = build_import_plan(fingerprint_records, existing_records=existing_records)
    return StreamingImportAssessment(
        report={},
        plan=plan,
        baseline_status="missing" if existing_records is None else "ready",
        existing_account_identity_hash="existing-account" if existing_records else None,
        incoming_account_identity_hash="incoming-account",
    )


def test_success_publish_then_identical_noop_preserves_active_generation(
    tmp_path, monkeypatch
) -> None:
    from backend.api import import_ as import_api
    from backend.core import db as db_mod
    from backend.core.import_data import import_data

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    records = [_raw_record("one", "2026-08-01T00:00:00Z")]
    (data_dir / "Streaming_History_Audio_000.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    result = import_data(
        str(data_dir),
        build_preaggregations=False,
        generation_id="generation-one",
    )
    baseline = _assessment(records)
    import_api._publish_import_state(
        baseline,
        result,
        executed_strategy="full",
    )
    import_api._record_plan_outcome(
        "baseline-run",
        baseline,
        requested_mode="auto",
        status="success",
    )

    identity = FingerprintRecord(
        source_type="audio",
        fingerprint=record_fingerprint(records[0]),
        timestamp=datetime.fromisoformat("2026-08-01T00:00:00+00:00"),
    )
    identical = _assessment(records, existing_records=[identity])
    noop_result = import_api._complete_noop_import(
        "noop-run",
        identical,
        requested_mode="auto",
    )

    conn = sqlite3.connect(db_path)
    try:
        state = conn.execute(
            """SELECT active_generation_id, account_identity_hash,
                      record_count, last_relation, last_strategy
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        runs = conn.execute(
            "SELECT run_id, status FROM playback_import_runs ORDER BY started_at, run_id"
        ).fetchall()
        plays = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    finally:
        conn.close()

    assert noop_result["noop"] is True
    assert plays == 1
    assert state == ("generation-one", "incoming-account", 1, "identical", "noop")
    assert runs == [("baseline-run", "success"), ("noop-run", "noop")]


def test_changeset_mismatch_does_not_publish_state_or_run(tmp_path, monkeypatch) -> None:
    from backend.api import import_ as import_api
    from backend.core import db as db_mod
    from backend.core.import_data import import_data

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    records = [_raw_record("one", "2026-08-01T00:00:00Z")]
    (data_dir / "Streaming_History_Audio_000.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    result = import_data(str(data_dir), build_preaggregations=False)
    result["inserted_records"] = 0

    with pytest.raises(RuntimeError, match="ChangeSet mismatch"):
        import_api._publish_import_state(
            _assessment(records),
            result,
            executed_strategy="full",
        )

    conn = sqlite3.connect(db_path)
    try:
        state = conn.execute(
            "SELECT active_generation_id FROM playback_import_state WHERE state_id=1"
        ).fetchone()[0]
        run_count = conn.execute("SELECT COUNT(*) FROM playback_import_runs").fetchone()[0]
    finally:
        conn.close()
    assert state is None
    assert run_count == 0


def test_append_source_change_fails_before_facts_and_state_commit(tmp_path, monkeypatch) -> None:
    from backend.api import import_ as import_api
    from backend.core import db as db_mod
    from backend.core.import_data import import_data

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    baseline_record = _raw_record("base", "2026-08-01T00:00:00Z")
    planned_record = _raw_record("planned", "2026-08-02T00:00:00Z")
    changed_record = _raw_record("changed", "2026-08-02T00:00:00Z")
    source_path = data_dir / "Streaming_History_Audio_000.json"
    source_path.write_text(json.dumps([baseline_record]), encoding="utf-8")
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    baseline_result = import_data(
        str(data_dir),
        build_preaggregations=False,
        generation_id="baseline-generation",
    )
    baseline = _assessment([baseline_record])
    import_api._publish_import_state(
        baseline,
        baseline_result,
        executed_strategy="full",
    )
    existing = FingerprintRecord(
        source_type="audio",
        fingerprint=record_fingerprint(baseline_record),
        timestamp=datetime.fromisoformat("2026-08-01T00:00:00+00:00"),
    )
    planned = _assessment(
        [baseline_record, planned_record],
        existing_records=[existing],
    )
    source_path.write_text(
        json.dumps([baseline_record, changed_record]),
        encoding="utf-8",
    )

    def publish(conn, result):
        assert conn.in_transaction is True
        import_api._publish_import_state(
            planned,
            result,
            executed_strategy="incremental",
            conn=conn,
        )

    with pytest.raises(RuntimeError, match="source files changed"):
        import_data(
            str(data_dir),
            build_preaggregations=False,
            mode="append",
            generation_id="changed-generation",
            expected_previous_digest=planned.plan.previous_digest,
            before_final_commit=publish,
        )

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT active_generation_id FROM playback_import_state WHERE state_id=1"
            ).fetchone()[0]
            == "baseline-generation"
        )
    finally:
        conn.close()
