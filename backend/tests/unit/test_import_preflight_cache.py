"""Exact GET reuse and the existing confirmation/ETL safety boundary."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.core import db
from backend.domains.imports import streaming_staging as cache
from backend.services import import_plan_service as service

pytestmark = pytest.mark.unit


@pytest.fixture
def packet(tmp_path, monkeypatch):
    from backend.tests.unit.test_import_plan_service import _connection, _source_dirs

    database = tmp_path / "main.db"
    source = _connection()
    with sqlite3.connect(database) as destination:
        source.backup(destination)
    source.close()
    monkeypatch.setattr(db, "DB_PATH", str(database))
    streaming, account = _source_dirs(
        tmp_path, [{"ts": "2026-01-02T01:02:03Z", "ms_played": 30000}]
    )
    cache._close_cached_stagings()
    builds = []
    original = cache.StreamingImportStaging.build

    def build(directory):
        staging = original(directory)
        builds.append(staging)
        return staging

    monkeypatch.setattr(cache.StreamingImportStaging, "build", build)
    yield streaming, account, database, builds
    cache._close_cached_stagings()


def read(packet, mode="auto"):
    return service.build_streaming_import_preflight(
        *packet[:2], requested_mode=mode, retain_staging_for_confirmation=True
    )


def test_four_concurrent_reads_build_once_and_preserve_all_fields(packet):
    before_db = packet[2].read_bytes()
    path = next(packet[0].glob("*.json"))
    before_source = path.read_bytes()
    expected = service.build_streaming_import_preflight(*packet[:2])
    packet[3].clear()
    barrier = threading.Barrier(4)

    def request(_):
        barrier.wait()
        return read(packet)

    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(request, range(4)))
    assert reports == [expected] * 4
    assert read(packet) == expected
    assert len(packet[3]) == 1
    reports[0]["warnings"].append("caller mutation")
    assert read(packet) == expected
    assert packet[2].read_bytes() == before_db
    assert path.read_bytes() == before_source


def test_modes_have_distinct_cached_reports_even_when_tokens_match(packet):
    reports = {mode: read(packet, mode) for mode in ("auto", "append", "replace")}
    for mode, report in reports.items():
        assert read(packet, mode) == report
        assert report["requested_mode"] == mode
    assert len(packet[3]) == 3
    assert len(cache._staging_cache) == 3


@pytest.mark.parametrize(
    "change",
    ["add", "delete", "size", "mtime", "same_size_same_mtime", "account", "account_report"],
)
def test_source_facts_invalidate(packet, change):
    read(packet)
    source, account = packet[:2]
    path = next(source.glob("*.json"))
    if change == "add":
        (source / "Streaming_History_Audio_001.json").write_text("[]")
    elif change == "delete":
        path.unlink()
    elif change == "size":
        path.write_text(path.read_text() + " ")
    elif change == "mtime":
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
    elif change == "same_size_same_mtime":
        st = path.stat()
        path.write_text(path.read_text().replace("30000", "40000"))
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    elif change == "account":
        (account / "UserAttributes.json").write_text(json.dumps({"username": "changed"}))
    else:
        (account / "Identity.json").write_text("{}")
    actual = read(packet)
    assert len(packet[3]) == 2
    assert actual == service.build_streaming_import_preflight(source, account)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE playback_import_state SET active_generation_id='new'",
        "UPDATE playback_import_state SET dataset_digest='new'",
        "UPDATE playback_import_state SET record_count=1",
        "UPDATE playback_import_state SET account_identity_hash='new'",
        "UPDATE playback_import_state SET fingerprint_version=999",
        "INSERT INTO plays(play_id,ts,content_type) VALUES(1,'2026-01-01','audio')",
        "INSERT INTO settings VALUES('bb_week_start_hour','13')",
    ],
)
def test_database_changes_invalidate_and_preserve_real_baseline_status(packet, sql):
    read(packet)
    with sqlite3.connect(packet[2]) as writer:
        writer.execute(sql)
    report = read(packet)
    assert len(packet[3]) == 2
    assert report == service.build_streaming_import_preflight(*packet[:2])


@pytest.mark.parametrize("damage", ["missing", "corrupt", "expired", "version"])
def test_staging_damage_expiry_and_builder_version_rebuild(packet, monkeypatch, damage):
    report = read(packet)
    staging = packet[3][0]
    if damage == "missing":
        staging.database_path.unlink()
    elif damage == "corrupt":
        with staging.database_path.open("r+b") as handle:
            handle.write(b"broken SQLite!")
    elif damage == "expired":
        monkeypatch.setattr(cache, "_CACHE_TTL_SECONDS", -1)
    else:
        monkeypatch.setattr(service, "PREFLIGHT_CONTRACT_VERSION", 2)
    rebuilt = read(packet)
    if damage == "version":
        assert rebuilt["confirmation_token"] != report["confirmation_token"]
        assert {key: value for key, value in rebuilt.items() if key != "confirmation_token"} == {
            key: value for key, value in report.items() if key != "confirmation_token"
        }
    else:
        assert rebuilt == report
    assert len(packet[3]) == 2
    if damage != "version":
        assert not staging.temp_dir.exists()
        assert staging.preflight_observer is None


def test_capacity_and_shutdown_close_staging_and_observers(packet, monkeypatch):
    for version in range(5):
        monkeypatch.setattr(service, "PREFLIGHT_CONTRACT_VERSION", version)
        read(packet)
    assert len(cache._staging_cache) == 3
    assert not packet[3][0].temp_dir.exists()
    cache._close_cached_stagings()
    assert all(
        not staging.temp_dir.exists() and staging.preflight_observer is None
        for staging in packet[3]
    )


def test_preflight_to_real_import_reuses_staging_and_rejects_later_source_drift(
    packet, monkeypatch
):
    from backend.core import import_data

    report = read(packet)
    staged = cache.take_cached_staging(report["confirmation_token"])
    assert staged is packet[3][0]
    # The actual importer owns a full schema, separately from the lightweight
    # legacy-baseline fixture used to obtain the report.
    monkeypatch.setattr(db, "DB_PATH", str(packet[2].with_name("import.db")))
    try:
        result = import_data.import_data(
            str(packet[0]), staging=staged, build_preaggregations=False
        )
        assert result["inserted_records"] == 1
        assert len(packet[3]) == 1
        path = next(packet[0].glob("*.json"))
        st = path.stat()
        path.write_text(path.read_text().replace("30000", "40000"))
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        with pytest.raises(RuntimeError, match="changed after staging"):
            import_data.import_data(str(packet[0]), staging=staged, build_preaggregations=False)
        with sqlite3.connect(db.DB_PATH) as conn:
            assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 1
    finally:
        staged.close()
        db._load_plays_cached.cache_clear()
        db._load_plays_for_artists_cached.cache_clear()


@pytest.mark.parametrize("semantic_change", [True, False])
def test_source_drift_rejects_displayed_confirmation_before_import(
    packet, monkeypatch, semantic_change
):
    from backend.api import import_ as api

    report = read(packet)
    monkeypatch.setattr(api, "DATA_DIR", str(packet[0]))
    monkeypatch.setattr(api, "ACCOUNT_DATA_DIR", str(packet[1]))
    monkeypatch.setattr(api, "_record_plan_outcome", lambda *a, **k: None)
    path = next(packet[0].glob("*.json"))
    original = path.read_text()
    path.write_text(
        original.replace("30000", "40000")
        if semantic_change
        else original.replace('"ts": ', '"ts" :')
    )
    job = api._make_job()
    try:
        result = api._streaming_execution_gate(
            job,
            confirm_warnings=True,
            requested_mode="auto",
            confirm_plan=True,
            confirmation_token=report["confirmation_token"],
        )
        assert result is None
        assert api._jobs[job]["result"]["confirmation_reason"] == "stale_plan"
        assert api._jobs[job]["result"]["import_started"] is False
    finally:
        api._jobs.pop(job)
