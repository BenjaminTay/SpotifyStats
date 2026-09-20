from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tests import path_safety
from backend.tests.unit.test_analysis_snapshots import isolated
from scripts import test_storage_guard as guard

pytestmark = pytest.mark.unit


def test_acceptance_environment_does_not_select_pytest_database(tmp_path):
    result = tmp_path / "result.json"
    # An invalid DB proves bootstrap never opens the acceptance source at all.
    acceptance = tmp_path / "acceptance.db"
    acceptance.write_bytes(b"must not be opened")
    script = """
import json, sqlite3, sys
from pathlib import Path
sources=[]
class Counted(sqlite3.Connection):
 def backup(self, target, *a, **k):
  sources.append(self.execute('pragma database_list').fetchone()[2])
  return super().backup(target,*a,**k)
original=sqlite3.connect
def connect(*a,**k):
 k['factory']=Counted
 return original(*a,**k)
sqlite3.connect=connect
from backend.tests.path_safety import install_test_paths
root=install_test_paths()
Path(sys.argv[1]).write_text(json.dumps({'sources':sources,'root':str(root)}))
"""
    env = {**os.environ, "SPOTIFY_STATS_TEST_SOURCE_DB": str(acceptance)}
    run = subprocess.run(
        [sys.executable, "-c", script, str(result)], env=env, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    data = json.loads(result.read_text())
    assert data["sources"] == [str(path_safety.ROOT / "backend/tests/fixtures/seed.db")]
    assert not Path(data["root"]).exists()
    assert acceptance.read_bytes() == b"must not be opened"


@pytest.mark.parametrize("fail", [False, True])
def test_analysis_case_uses_seed_and_cleans_on_success_or_failure(monkeypatch, tmp_path, fail):
    sources = []
    original = sqlite3.connect

    class Counted(path_safety.TestPathConnection):
        def backup(self, target, *args, **kwargs):
            sources.append(self.execute("pragma database_list").fetchone()[2])
            return super().backup(target, *args, **kwargs)

    def connect(*args, **kwargs):
        kwargs["factory"] = Counted
        return original(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)
    fixture = isolated.__wrapped__(monkeypatch, tmp_path)
    database, root = next(fixture)
    assert database.stat().st_size < 2 * 1024**2
    (root / "leftover.db-wal").write_bytes(b"wal")
    (root / "leftover.db-shm").write_bytes(b"shm")
    if fail:
        with pytest.raises(AssertionError):
            fixture.throw(AssertionError("simulated case failure"))
    else:
        with pytest.raises(StopIteration):
            next(fixture)
    assert sources == [str(path_safety.ROOT / "backend/tests/fixtures/seed.db")]
    assert not root.exists()


@pytest.mark.parametrize("exit_code", [0, 3])
def test_guard_cleans_only_owned_files_on_exit(tmp_path, exit_code):
    report = tmp_path / "storage.json"
    canary = tmp_path / "keep"
    canary.write_text("keep")
    command = [
        sys.executable,
        "-c",
        "import os,pathlib,sys; "
        "base=pathlib.Path(os.environ['SPOTIFY_STATS_TEST_BASETEMP']); "
        "assert base.is_dir(); (base/'seed').mkdir(); (base/'integration').mkdir(); "
        "pathlib.Path(os.environ['TMPDIR'],'owned').write_bytes(b'x'*4096); "
        f"sys.exit({exit_code})",
    ]
    assert guard.run_guarded(command, report, min_free=0) == exit_code
    data = json.loads(report.read_text())
    assert data["peak_bytes"] >= 4096
    assert data["cleaned"] and not Path(data["owned_root"]).exists()
    assert canary.read_text() == "keep"


def test_guard_low_space_stops_before_launch(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        guard.shutil, "disk_usage", lambda _: SimpleNamespace(free=12 * guard.GIB - 1)
    )
    sentinel = tmp_path / "launched"
    report = tmp_path / "storage.json"
    command = [sys.executable, "-c", f"open({str(sentinel)!r},'w').close()"]
    assert guard.run_guarded(command, report) == 1
    assert not sentinel.exists()
    data = json.loads(report.read_text())
    assert data["stop_reason"] == "insufficient_free_space"
    assert data["cleaned"] and not Path(data["owned_root"]).exists()


def test_guard_growth_stops_running_child_and_cleans(tmp_path, monkeypatch):
    canary = tmp_path / "other-task"
    canary.write_text("keep")
    measure = guard.tree_bytes
    # Exercise the production 2 GiB boundary without allocating 2 GiB in tests.
    monkeypatch.setattr(
        guard,
        "tree_bytes",
        lambda root: 2 * guard.GIB + 1 if (root / "large").exists() else measure(root),
    )
    report = tmp_path / "storage.json"
    command = [
        sys.executable,
        "-c",
        "import os,pathlib,time; "
        "pathlib.Path(os.environ['TMPDIR'],'large').write_bytes(b'x'*8192); "
        "time.sleep(30)",
    ]
    assert guard.run_guarded(command, report, min_free=0) == 1
    data = json.loads(report.read_text())
    assert data["stop_reason"] == "temporary_limit_exceeded"
    assert data["cleaned"] and data["peak_bytes"] > 2 * guard.GIB
    assert canary.read_text() == "keep"


def test_integration_opt_in_rejects_unit_selection_before_copy(tmp_path):
    env = {**os.environ, "SPOTIFY_STATS_TEST_SOURCE_DB": str(tmp_path / "not-a-database")}
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "backend.tests.real_data_integration",
            "backend/tests/unit/test_test_storage.py",
            "--collect-only",
            "-q",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == pytest.ExitCode.USAGE_ERROR
    assert "integration-only test paths" in run.stderr


def test_guard_interrupt_cleans_owned_root_and_preserves_other_task(tmp_path):
    canary = tmp_path / "other-task"
    canary.write_text("keep")
    report = tmp_path / "interrupted.json"
    command = [
        sys.executable,
        "-c",
        "import os,signal,time; os.kill(os.getppid(),signal.SIGINT); time.sleep(30)",
    ]
    assert guard.run_guarded(command, report, min_free=0) == 1
    data = json.loads(report.read_text())
    assert data["stop_reason"] == "signal_2" and data["cleaned"]
    assert not Path(data["owned_root"]).exists()
    assert canary.read_text() == "keep"
