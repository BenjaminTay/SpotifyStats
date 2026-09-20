from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core import db
from backend.core.job_queue import JobQueue
from backend.domains.billboard import persistent_cache as cache
from backend.domains.yearly_review import artifact_cache
from backend.services import billboard_snapshot_service, home_service
from backend.tests import path_safety

pytestmark = pytest.mark.unit


def test_directory_fd_cleanup_resolves_actual_directory(tmp_path, monkeypatch):
    formal = tmp_path / "workspace" / "data"
    formal.mkdir(parents=True)
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    monkeypatch.chdir(formal.parent)
    fd = os.open(temporary, os.O_RDONLY)
    workspace_fd = os.open(formal.parent, os.O_RDONLY)
    try:
        path_safety.audit_guard("os.rmdir", ("data", fd), formal_root=formal)
        with pytest.raises(path_safety.UnsafeTestPathError):
            path_safety.audit_guard("os.rmdir", ("data", workspace_fd), formal_root=formal)
    finally:
        os.close(fd)
        os.close(workspace_fd)


def test_paths_are_bound_before_collection():
    from backend.domains.account_archive import snapshot_store as archive_store
    from backend.domains.community import snapshot_store as community_store
    from backend.domains.metadata import governance_store

    root = path_safety.SESSION_ROOT
    assert root is not None
    for path in (
        db.DB_PATH,
        cache.BILLBOARD_CACHE_PATH,
        artifact_cache.YEARLY_REVIEW_CACHE_PATH,
        home_service._HOME_SNAPSHOT_DIR,
        archive_store.path(),
        community_store.path(),
        governance_store.path(),
    ):
        assert root in Path(path).resolve().parents
    assert os.environ["SPOTIFY_STATS_BILLBOARD_CACHE_PATH"] == cache.BILLBOARD_CACHE_PATH
    assert os.environ["SPOTIFY_STATS_YEARLY_CACHE_PATH"] == artifact_cache.YEARLY_REVIEW_CACHE_PATH


def test_default_clear_and_rebuild_use_only_session_sidecar(tmp_path):
    from backend.core.cache_manager import invalidate_all

    canary = tmp_path / "simulated-formal.db"
    canary.write_bytes(b"formal snapshot canary")
    before = (canary.read_bytes(), canary.stat().st_mtime_ns)
    invalidate_all()
    cache.clear_persisted_snapshots()
    result = billboard_snapshot_service.rebuild_default_billboard_snapshots()
    with sqlite3.connect(cache.BILLBOARD_CACHE_PATH) as conn:
        families = {r[0] for r in conn.execute("SELECT family FROM billboard_snapshots")}
    assert set(result["families"]) <= families
    assert billboard_snapshot_service.billboard_default_snapshots_ready()
    cache.clear_persisted_snapshots()
    with sqlite3.connect(cache.BILLBOARD_CACHE_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) FROM billboard_snapshots").fetchone()[0] == 0
    assert (canary.read_bytes(), canary.stat().st_mtime_ns) == before
    invalidate_all()


def test_yearly_home_and_queue_writes_are_temporary():
    artifact_cache.store_persisted_artifact(
        "isolation",
        {"report": {}, "record_catalog": []},
        year=2025,
        filter_fingerprint="test",
        source_db_revision="test",
    )
    assert artifact_cache.load_persisted_artifact("isolation") is not None
    home = home_service._HOME_SNAPSHOT_DIR / "isolation.json"
    home_service._write_snapshot(home, {"isolation": True})
    assert json.loads(home.read_text()) == {"isolation": True}
    queue = JobQueue(max_workers=1)
    queue.prepare(db.DB_PATH)
    assert path_safety.SESSION_ROOT in Path(queue.database_path).parents


@pytest.mark.parametrize("operation", ["connect", "write", "clear", "rename", "symlink"])
def test_canary_fail_closed_even_when_module_path_is_overridden(tmp_path, monkeypatch, operation):
    formal = tmp_path / "formal"
    formal.mkdir()
    canary = formal / "billboard.db"
    canary.write_bytes(b"untouched")
    before = (canary.read_bytes(), canary.stat().st_mtime_ns)

    # The guard is intentionally permanent. This unique canary root will not
    # be reused; no formal repository file is involved in this regression.
    def guard(event, args):
        path_safety.audit_guard(event, args, formal_root=formal)

    sys.addaudithook(guard)
    monkeypatch.setattr(cache, "BILLBOARD_CACHE_PATH", str(canary))
    with pytest.raises(path_safety.UnsafeTestPathError):
        if operation == "connect":
            sqlite3.connect(f"file:{canary}?mode=ro", uri=True)
        elif operation == "write":
            canary.write_text("bad")
        elif operation == "clear":
            cache.clear_persisted_snapshots()
        elif operation == "rename":
            os.replace(canary, tmp_path / "moved.db")
        else:
            os.symlink(canary, tmp_path / "alias.db")
    assert (canary.read_bytes(), canary.stat().st_mtime_ns) == before


def test_failure_interrupt_and_teardown_never_restore_formal_paths(tmp_path):
    result = tmp_path / "result.json"
    script = r"""
import json,sys
from pathlib import Path
from backend.tests.path_safety import install_test_paths
root=install_test_paths()
from backend.domains.billboard import persistent_cache as cache
from backend.services import home_service
from pytest import MonkeyPatch
original=cache.BILLBOARD_CACHE_PATH
for error in (RuntimeError,KeyboardInterrupt):
 try:
  with MonkeyPatch.context() as m:
   m.setattr(cache,'BILLBOARD_CACHE_PATH',str(root/'override.db'))
   raise error()
 except error:pass
 assert cache.BILLBOARD_CACHE_PATH==original
 cache.clear_persisted_snapshots()
Path(sys.argv[1]).write_text(json.dumps({'root':str(root),'cache':original,'home':str(home_service._HOME_SNAPSHOT_DIR)}))
"""
    run = subprocess.run(
        [sys.executable, "-c", script, str(result)], capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    value = json.loads(result.read_text())
    assert Path(value["root"]) in Path(value["cache"]).parents
    assert Path(value["root"]) in Path(value["home"]).parents
    assert not Path(value["root"]).exists()  # Only the child-owned directory was cleaned.


def test_resolved_symlink_cannot_escape_to_canary(tmp_path):
    formal = tmp_path / "simulated-formal"
    formal.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(formal, target_is_directory=True)
    with pytest.raises(path_safety.UnsafeTestPathError):
        path_safety.require_test_path(alias / "cache.db", formal_root=formal)


def test_caught_violation_still_fails_session(monkeypatch):
    from types import SimpleNamespace

    from backend.tests import conftest

    monkeypatch.setattr(conftest, "VIOLATIONS", ["simulated canary write rejected"])
    session = SimpleNamespace(
        exitstatus=0,
        config=SimpleNamespace(pluginmanager=SimpleNamespace(get_plugin=lambda _: None)),
    )
    conftest.pytest_sessionfinish(session, 0)
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED


def test_sql_attach_cannot_bypass_path_guard(tmp_path):
    formal = tmp_path / "simulated-formal-attach"
    formal.mkdir()
    canary = formal / "sidecar.db"
    with sqlite3.connect(canary) as conn:
        conn.execute("CREATE TABLE canary(value)")
    before = (canary.read_bytes(), canary.stat().st_mtime_ns)
    conn = sqlite3.connect(":memory:")
    conn.set_authorizer(lambda *args: path_safety.attachment_guard(*args, formal_root=formal))
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("ATTACH DATABASE ? AS wrong_target", (str(canary),))
    conn.close()
    assert (canary.read_bytes(), canary.stat().st_mtime_ns) == before
