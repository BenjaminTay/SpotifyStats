"""Archive revision domains, one invocation, publication and public read boundaries."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from backend.domains.account_archive import snapshot_store as store
from backend.domains.account_archive.context import build_archive_filter_context
from backend.domains.account_archive.snapshot_revision import (
    FAMILIES,
    family_revision,
    install_revision_tracking,
)
from backend.services import account_archive_snapshot_service as service
from backend.tests.unit.test_account_archive_relationships import _relationship_conn

pytestmark = pytest.mark.unit


@pytest.fixture
def archive(monkeypatch, tmp_path):
    from backend.core import config, db

    path = tmp_path / "source.db"
    source = _relationship_conn()
    conn = sqlite3.connect(path, check_same_thread=False)
    source.backup(conn)
    source.close()
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE search_queries(id INTEGER PRIMARY KEY,query_text,search_time_utc,platform,interaction_uri)"
    )
    conn.execute(
        "INSERT INTO search_queries VALUES(1,'A','2024-01-10T00:00:00Z','mobile','spotify:track:a')"
    )
    install_revision_tracking(conn)
    conn.commit()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    monkeypatch.setattr(config, "SPOTIFY_STATS_ARCHIVE_CACHE_PATH", str(tmp_path / "archive.db"))
    yield conn
    conn.close()


def test_shared_build_and_exact_reuse(archive, monkeypatch):
    from backend.domains.account_archive import source_data

    calls = []
    original = source_data.load_effective_archive_plays
    monkeypatch.setattr(
        source_data, "load_effective_archive_plays", lambda *a: calls.append(1) or original(*a)
    )
    result = service.ensure(archive)
    assert result["event_builds"] == 1
    assert len(calls) == 1
    assert set(result["published"]) == set(FAMILIES)
    assert service.ensure(archive) == {"published": [], "event_builds": 0}
    assert len(calls) == 1


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"merge_enabled": False},
        {"merge_level": 3},
        {"min_ms": 0},
        {"min_ms": 150000, "dynamic_threshold": False},
        {"max_merge_gap_minutes": 1},
        {"max_merge_gap_minutes": 60},
    ],
)
def test_all_fields_equal_to_independent_builders(archive, filters):
    from backend.domains.account_archive.cohorts import build_collection_cohorts
    from backend.domains.account_archive.discovery import build_archive_discovery
    from backend.domains.account_archive.journey import build_collection_journey
    from backend.domains.account_archive.other_media import build_archive_other_media
    from backend.domains.account_archive.overview import build_archive_overview
    from backend.domains.account_archive.returns import build_archive_returns

    service.ensure(archive, filters)
    builders = dict(
        cohorts=build_collection_cohorts,
        returns=build_archive_returns,
        discovery=build_archive_discovery,
        journey=build_collection_journey,
        other_media=build_archive_other_media,
    )
    for family in FAMILIES:
        actual = service.read(archive, family, filters)
        actual.pop("snapshot")
        context = build_archive_filter_context(archive, filters, family=family)
        expected = (
            build_archive_overview(archive, data_revision=family_revision(archive, family))
            if family == "overview"
            else builders[family](archive, context)
        )
        assert actual == expected, family


@pytest.mark.parametrize("table", ["saved_tracks", "search_queries", "plays"])
def test_empty_sources_remain_real_results(archive, table):
    archive.execute(f"DELETE FROM {table}")
    archive.commit()
    result = service.ensure(archive)
    assert len(result["published"]) == 6
    for family in FAMILIES:
        assert service.read(archive, family)["snapshot"]["status"] == "ready"


def test_precise_search_collection_and_group_invalidation(archive):
    service.ensure(archive)
    archive.execute("UPDATE search_queries SET query_text='B' WHERE id=1")
    archive.commit()
    assert service.read(archive, "cohorts")["snapshot"]["status"] == "ready"
    assert service.read(archive, "discovery")["snapshot"]["status"] == "warming"
    assert service.ensure(archive)["published"] == ["discovery"]
    archive.execute(
        "UPDATE saved_tracks SET added_date='2024-01-11T00:00:00Z' WHERE spotify_track_id='a'"
    )
    archive.commit()
    assert service.read(archive, "other_media")["snapshot"]["status"] == "ready"
    assert set(service.ensure(archive)["published"]) == {
        "cohorts",
        "returns",
        "discovery",
        "overview",
        "journey",
    }
    archive.execute("INSERT INTO track_groups VALUES(1,'Group',1,'recording',NULL)")
    archive.execute("INSERT INTO track_group_members VALUES(1,1)")
    archive.commit()
    assert service.read(archive, "journey")["snapshot"]["status"] == "ready"
    assert service.ensure(archive)["published"] == ["cohorts", "returns", "discovery"]


def test_counter_noop_rollback_and_schema_repair(archive):
    before = family_revision(archive, "cohorts")
    archive.execute("UPDATE plays SET ms_played=ms_played")
    archive.commit()
    assert family_revision(archive, "cohorts") == before
    archive.execute("UPDATE plays SET ms_played=ms_played+1")
    archive.rollback()
    assert family_revision(archive, "cohorts") == before
    service.ensure(archive)
    archive.execute("DROP TRIGGER archive_rev_plays_update")
    archive.execute("UPDATE plays SET ms_played=ms_played+1")
    archive.commit()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        service.read(archive, "cohorts")
    assert error.value.status_code == 503
    install_revision_tracking(archive)
    archive.commit()
    assert family_revision(archive, "cohorts") != before
    assert service.read(archive, "cohorts")["snapshot"]["status"] == "warming"


def test_four_maintenance_calls_one_build_and_public_lkg(archive, monkeypatch):
    from backend.domains.account_archive import source_data

    service.ensure(archive)
    archive.execute("UPDATE plays SET ms_played=ms_played+1 WHERE play_id=1")
    archive.commit()
    original = source_data.load_effective_archive_plays
    started, release = Event(), Event()
    calls = []

    def slow(*args):
        calls.append(1)
        started.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(source_data, "load_effective_archive_plays", slow)
    with ThreadPoolExecutor(4) as pool:
        futures = [pool.submit(service.ensure, archive) for _ in range(4)]
        assert started.wait(10)
        assert service.read(archive, "cohorts")["snapshot"]["freshness"] == "last_known_good"
        release.set()
        results = [f.result() for f in futures]
    assert len(calls) == 1
    assert sum(bool(r["published"]) for r in results) == 1


def test_drift_and_sql_failure_preserve_previous(archive, monkeypatch):
    from backend.domains.account_archive import cohorts

    service.ensure(archive)
    archive.execute("UPDATE plays SET ms_played=ms_played+1 WHERE play_id=1")
    archive.commit()
    original = cohorts.build_collection_cohorts

    def drift(*args, **kwargs):
        result = original(*args, **kwargs)
        archive.execute(
            "UPDATE saved_tracks SET added_date='2024-02-01' WHERE spotify_track_id='a'"
        )
        archive.commit()
        return result

    monkeypatch.setattr(cohorts, "build_collection_cohorts", drift)
    with pytest.raises(ValueError, match="changed"):
        service.ensure(archive)
    assert service.read(archive, "cohorts")["snapshot"]["freshness"] == "last_known_good"
    monkeypatch.setattr(cohorts, "build_collection_cohorts", original)
    assert service.ensure(archive)["published"]
    archive.execute("UPDATE plays SET ms_played=ms_played+1 WHERE play_id=1")
    archive.commit()
    original_connect = store.connect

    def failing_connect(**kwargs):
        conn = original_connect(**kwargs)
        if conn is not None and kwargs.get("write"):
            conn.execute(
                "CREATE TEMP TRIGGER fail_publication BEFORE INSERT ON publications BEGIN SELECT RAISE(ABORT,'fault'); END"
            )
        return conn

    monkeypatch.setattr(store, "connect", failing_connect)
    with pytest.raises(sqlite3.IntegrityError):
        service.ensure(archive)
    assert service.read(archive, "cohorts")["snapshot"]["build_status"] == "failed"


def test_public_exact_lkg_missing_zero_writes_or_builders(archive, monkeypatch, tmp_path):
    from fastapi import HTTPException

    from backend.core import config
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )
    from backend.domains.account_archive import source_data

    service.ensure(archive)
    original = store.connect
    writes = []

    def connect(**kwargs):
        conn = original(**kwargs)
        if conn:

            def authorizer(action, *args):
                if action in {
                    sqlite3.SQLITE_INSERT,
                    sqlite3.SQLITE_UPDATE,
                    sqlite3.SQLITE_DELETE,
                    sqlite3.SQLITE_CREATE_TABLE,
                }:
                    writes.append(action)
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            conn.set_authorizer(authorizer)
        return conn

    monkeypatch.setattr(store, "connect", connect)
    monkeypatch.setattr(
        source_data, "load_effective_archive_plays", lambda *a: pytest.fail("GET cannot build")
    )
    before = sorted(p.name for p in tmp_path.iterdir())
    token = set_public_readonly_db_guard(True)
    try:
        for family in FAMILIES:
            assert service.read(archive, family)["snapshot"]["status"] == "ready"
        with pytest.raises(PermissionError):
            service.ensure(archive)
        assert service.enqueue_defaults("public") == []
        with pytest.raises(HTTPException):
            service.read(archive, "cohorts", {"min_ms": 12})
        monkeypatch.setattr(
            config, "SPOTIFY_STATS_ARCHIVE_CACHE_PATH", str(tmp_path / "absent" / "archive.db")
        )
        with pytest.raises(HTTPException):
            service.read(archive, "cohorts")
        assert not (tmp_path / "absent").exists()
        assert writes == []
        assert sorted(p.name for p in tmp_path.iterdir()) == before
    finally:
        reset_public_readonly_db_guard(token)


def test_previous_generation_corruption_repair_and_size_guard(archive, monkeypatch):
    service.ensure(archive)
    archive.execute("UPDATE plays SET ms_played=ms_played+1 WHERE play_id=1")
    archive.commit()
    service.ensure(archive)
    with store.connect(write=True) as c:
        c.execute(
            "UPDATE publications SET payload=x'00' WHERE generation=(SELECT generation FROM active WHERE family='cohorts')"
        )
    assert service.read(archive, "cohorts")["snapshot"]["freshness"] == "last_known_good"
    assert service.ensure(archive)["published"] == ["cohorts"]
    assert service.read(archive, "cohorts")["snapshot"]["status"] == "ready"
    for _ in range(2):
        archive.execute("UPDATE plays SET ms_played=ms_played+1 WHERE play_id=1")
        archive.commit()
        service.ensure(archive)
    with store.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM publications").fetchone()[0] <= 12
        assert (
            c.execute("SELECT COUNT(*) FROM active WHERE previous IS NOT NULL").fetchone()[0] == 4
        )
    archive.execute("UPDATE plays SET ms_played=ms_played+1 WHERE play_id=1")
    archive.commit()
    monkeypatch.setattr(store, "MAX_DISK_BYTES", 1)
    with pytest.raises(ValueError, match="30 MiB"):
        service.ensure(archive)
    assert service.read(archive, "cohorts")["snapshot"]["build_status"] == "failed"


def test_failed_without_lkg_is_explicit(archive, monkeypatch):
    from fastapi import HTTPException

    from backend.domains.account_archive import cohorts

    monkeypatch.setattr(
        cohorts,
        "build_collection_cohorts",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("fault")),
    )
    with pytest.raises(ValueError):
        service.ensure(archive)
    with pytest.raises(HTTPException) as error:
        service.read(archive, "cohorts")
    assert error.value.status_code == 503
    assert "构建失败" in error.value.detail["message"]


def test_continuous_same_track_and_shanghai_date(archive):
    archive.execute("INSERT INTO plays VALUES(8,'2024-01-10T00:08:00Z',120000,1,1,'2024-01-10')")
    archive.execute("INSERT INTO plays VALUES(9,'2024-04-01T17:00:00Z',120000,1,1,'2024-04-01')")
    archive.commit()
    for filters in ({}, {"merge_enabled": False}, {"merge_level": 3}):
        test_all_fields_equal_to_independent_builders(archive, filters)
        assert build_archive_filter_context(archive, filters).latest_play_date == "2024-04-02"


def test_unrelated_ddl_and_governance_migration_preserve_archive_revision(archive):
    from backend.core.migrations import _migrate_governance_revisions, migrate_075, migrate_077

    source = [tuple(r) for r in archive.execute("SELECT * FROM plays")]
    migrate_075(archive)
    before = family_revision(archive, "overview")
    _migrate_governance_revisions(archive)
    assert family_revision(archive, "overview") == before
    migrate_077(archive)
    archive.execute("CREATE TABLE unrelated_migration(id INTEGER)")
    install_revision_tracking(archive)
    assert family_revision(archive, "overview") == before
    archive.commit()
    install_revision_tracking(archive)
    assert family_revision(archive, "overview") == before
    assert [tuple(r) for r in archive.execute("SELECT * FROM plays")] == source


@pytest.mark.parametrize(
    "damage",
    [
        "DELETE FROM account_archive_revision_schema",
        "DROP TRIGGER archive_rev_plays_update",
    ],
)
def test_tracking_repair_and_rollback(archive, damage):
    from backend.domains.account_archive.snapshot_revision import ArchiveRevisionUnavailableError

    before = family_revision(archive, "returns")
    source = [tuple(r) for r in archive.execute("SELECT * FROM plays")]
    archive.execute("BEGIN")
    archive.execute(damage)
    with pytest.raises(ArchiveRevisionUnavailableError):
        family_revision(archive, "returns")
    install_revision_tracking(archive)
    assert family_revision(archive, "returns") != before
    archive.rollback()
    assert family_revision(archive, "returns") == before
    archive.execute(damage)
    archive.commit()
    install_revision_tracking(archive)
    archive.commit()
    repaired = family_revision(archive, "returns")
    assert repaired != before
    install_revision_tracking(archive)
    assert family_revision(archive, "returns") == repaired
    assert [tuple(r) for r in archive.execute("SELECT * FROM plays")] == source
