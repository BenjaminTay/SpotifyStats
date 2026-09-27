from __future__ import annotations

import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from urllib.request import ProxyHandler, build_opener

import pytest

from scripts import (
    frontend_spa_ready_probe,
    runtime_df_compare,
    runtime_matrix_run,
    runtime_matrix_suite,
    runtime_measurement,
)

pytestmark = pytest.mark.unit


def test_spa_probe_requires_destination_specific_dom_after_history_transition():
    stale_analysis_dom = {
        "path": "/",
        "text": "PLAYBACK STATS\n播放统计\n独特歌曲\n6,167",
        "alerts": [],
        "errorSkeleton": False,
    }
    rendered_home_dom = {
        "path": "/",
        "text": "YOUR LISTENING HEADLINE\nYOUR LISTENING ARCHIVE\n67,881",
        "alerts": [],
        "errorSkeleton": False,
    }

    assert frontend_spa_ready_probe._dom_ready("/", stale_analysis_dom) is False
    assert frontend_spa_ready_probe._dom_ready("/", rendered_home_dom) is True


def _database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES('bb_top_n','30')")
        conn.commit()


def test_isolated_environment_keeps_all_sqlite_artifacts_under_run_root(tmp_path):
    data = tmp_path / "data"
    environment = runtime_measurement.isolated_environment(data)

    assert set(environment) == {
        "SPOTIFY_STATS_DB_PATH",
        "SPOTIFY_STATS_BILLBOARD_CACHE_PATH",
        "SPOTIFY_STATS_ANALYSIS_CACHE_PATH",
        "SPOTIFY_STATS_YEARLY_CACHE_PATH",
        "SPOTIFY_STATS_COMMUNITY_CACHE_PATH",
        "SPOTIFY_STATS_ARCHIVE_CACHE_PATH",
        "SPOTIFY_STATS_GOVERNANCE_CACHE_PATH",
    }
    assert all(data == Path(value).parent for value in environment.values())


@pytest.mark.parametrize("state", ["E", "M", "D"])
def test_prepare_uses_online_backup_and_records_state(state):
    with tempfile.TemporaryDirectory(prefix="spotify-runtime-source-") as source_name:
        with tempfile.TemporaryDirectory(prefix="spotify-runtime-parent-") as parent_name:
            source = Path(source_name)
            output = Path(parent_name) / "run"
            _database(source / "spotify_stats.db")
            _database(source / "analysis_cache.db")
            with sqlite3.connect(source / "spotify_stats.db") as conn:
                conn.execute(
                    "CREATE TABLE governance_revision_schema("
                    "singleton INTEGER PRIMARY KEY, schema_version INTEGER)"
                )
                source_schema_version = conn.execute("PRAGMA schema_version").fetchone()[0]
                conn.execute(
                    "INSERT INTO governance_revision_schema VALUES(1,?)",
                    (source_schema_version,),
                )
            args = runtime_measurement.parse_args(
                [
                    "prepare",
                    "--source-db",
                    str(source / "spotify_stats.db"),
                    "--output-root",
                    str(output),
                    "--state",
                    state,
                    "--lock-file",
                    str(Path(parent_name) / "lock"),
                ]
            )

            assert runtime_measurement.prepare(args) == 0
            with sqlite3.connect(output / "data" / "spotify_stats.db") as conn:
                value = conn.execute("SELECT value FROM settings WHERE key='bb_top_n'").fetchone()[
                    0
                ]
                schema_version = conn.execute("PRAGMA schema_version").fetchone()[0]
                governance_schema_version = conn.execute(
                    "SELECT schema_version FROM governance_revision_schema WHERE singleton=1"
                ).fetchone()[0]
            assert value == ("31" if state == "D" else "30")
            assert governance_schema_version == schema_version
            assert (output / "data" / "analysis_cache.db").exists() is (state != "M")
            assert '"integrity": "ok"' in (output / "manifest.json").read_text()


def test_prepare_refuses_nonempty_output():
    with tempfile.TemporaryDirectory(prefix="spotify-runtime-source-") as source_name:
        with tempfile.TemporaryDirectory(prefix="spotify-runtime-parent-") as parent_name:
            source = Path(source_name) / "spotify_stats.db"
            output = Path(parent_name) / "run"
            output.mkdir()
            (output / "owned-by-someone-else").write_text("keep")
            _database(source)
            args = runtime_measurement.parse_args(
                ["prepare", "--source-db", str(source), "--output-root", str(output)]
            )

            with pytest.raises(FileExistsError):
                runtime_measurement.prepare(args)


def test_runtime_matrix_cli_requires_explicit_isolated_ports_and_outputs():
    args = runtime_matrix_run.parse_args(
        [
            "--root",
            "/tmp/example",
            "--backend-port",
            "18100",
            "--frontend-port",
            "14173",
            "--frontend-mode",
            "preview",
            "--phase-file",
            "/tmp/example/phase.txt",
            "--events-output",
            "/tmp/example/events.jsonl",
            "--backend-pid-file",
            "/tmp/example/backend.pid",
            "--frontend-pid-file",
            "/tmp/example/frontend.pid",
        ]
    )

    assert args.frontend_mode == "preview"
    assert args.warmup_mode == "full"
    assert args.idle_seconds == 300
    assert args.backend_pid_file.name == "backend.pid"
    assert args.lock_file == (Path(tempfile.gettempdir()) / "spotify-fullstack-verification.lock")

    suite_args = runtime_matrix_suite.parse_args(
        ["--root", "/tmp/matrix", "--output-root", "/tmp/results"]
    )
    assert suite_args.lock_file == args.lock_file


def test_formal_matrix_requires_fifteen_distinct_roots():
    roots = [Path(f"/tmp/runtime-root-{index}") for index in range(15)]

    planned = runtime_matrix_suite.schedule(roots)

    assert [f"{group}{repetition}" for repetition, group, _ in planned] == [
        "A1",
        "B1",
        "C1",
        "D1",
        "F1",
        "A2",
        "B2",
        "C2",
        "D2",
        "F2",
        "A3",
        "B3",
        "C3",
        "D3",
        "F3",
    ]
    with pytest.raises(ValueError):
        runtime_matrix_suite.schedule(roots[:14])
    with pytest.raises(ValueError):
        runtime_matrix_suite.schedule([roots[0]] * 15)


def test_df_comparison_keeps_idle_cpu_out_of_startup_cpu(tmp_path):
    run = tmp_path / "D1"
    run.mkdir()
    events = [
        {
            "event": "process_start",
            "timestamp": "2026-09-27T00:00:00+00:00",
            "monotonic": 10.0,
            "external_competitors": [],
        },
        {"event": "health_ready", "timestamp": "2026-09-27T00:00:01+00:00", "monotonic": 11.0},
        {
            "event": "core_page_ready",
            "timestamp": "2026-09-27T00:00:02+00:00",
            "monotonic": 12.0,
            "observed_monotonic": 11.5,
            "observed_epoch": 1790467201.5,
        },
        {
            "event": "necessary_maintenance_complete",
            "timestamp": "2026-09-27T00:00:03+00:00",
            "monotonic": 13.0,
        },
        {
            "event": "publication_exact_validated",
            "timestamp": "2026-09-27T00:00:03.5+00:00",
            "monotonic": 13.5,
            "publication_readiness": {"ready": True},
        },
        {
            "event": "core_page_exact",
            "timestamp": "2026-09-27T00:00:04+00:00",
            "monotonic": 14.0,
            "snapshot_states": ["exact"],
        },
        {"event": "idle_start", "timestamp": "2026-09-27T00:00:05+00:00", "monotonic": 15.0},
        {"event": "idle_end", "timestamp": "2026-09-27T00:00:15+00:00", "monotonic": 25.0},
        {
            "event": "shutdown_complete",
            "timestamp": "2026-09-27T00:00:16+00:00",
            "monotonic": 26.0,
            "external_competitors": [],
        },
    ]
    (run / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
    service = {
        "label": "backend",
        "role": "application",
        "status": "ok",
        "rss_mb": 200,
        "physical_footprint_mb": 150,
        "cpu_seconds_delta": 1,
    }
    series = [
        {"timestamp": 1790467201.0, "services": [service]},
        {"timestamp": 1790467204.0, "services": [service]},
        {"timestamp": 1790467210.0, "services": [service]},
        {"timestamp": 1790467215.0, "services": [service]},
    ]
    (run / "resources.json").write_text(
        json.dumps(
            {
                "time_series": series,
                "sampling_integrity": {"valid": True},
                "operation_exit": 0,
            }
        )
    )
    (run / "spa.json").write_text(
        json.dumps(
            {
                "same_document": True,
                "samples": [
                    {"phase": "first", "core_ready_ms": 500, "snapshot_state": "exact"},
                    {"phase": "revisit", "core_ready_ms": 50, "snapshot_state": "exact"},
                ],
            }
        )
    )

    result = runtime_df_compare.run_metrics(run)

    assert result["startup_backend_cpu_seconds"] == 2
    assert result["idle_application_cpu_percent"] == 40
    assert result["first_business_ready_seconds"] == 1.5


def test_df_resource_gate_uses_frozen_absolute_or_relative_rule():
    already_light = runtime_df_compare._relative_or_absolute_gate(
        baseline=4.0,
        actual=4.5,
        absolute_limit=5.0,
    )
    needs_reduction = runtime_df_compare._relative_or_absolute_gate(
        baseline=10.0,
        actual=7.0,
        absolute_limit=5.0,
    )

    assert already_light == {
        "baseline_d_median": 4.0,
        "f_median": 4.5,
        "mode": "absolute",
        "limit": 5.0,
        "pass": True,
    }
    assert needs_reduction == {
        "baseline_d_median": 10.0,
        "f_median": 7.0,
        "mode": "relative_30_percent_reduction",
        "limit": 7.0,
        "pass": True,
    }


def _background_jobs_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE background_jobs(
                   job_id TEXT PRIMARY KEY, job_type TEXT, entity_type TEXT,
                   entity_id TEXT, payload_json TEXT, status TEXT,
                   created_at TEXT, updated_at TEXT, attempts INTEGER, error TEXT
               )"""
        )


def _insert_job(
    database: Path,
    *,
    job_id: str,
    status: str,
    job_type: str = "analysis_snapshot_rebuild",
    entity_type: str = "analysis_stats",
    entity_id: str = "request-key",
    payload: dict | None = None,
) -> None:
    with sqlite3.connect(database) as conn:
        conn.execute(
            """INSERT INTO background_jobs(
                   job_id, job_type, entity_type, entity_id, payload_json,
                   status, created_at, updated_at, attempts, error
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                job_type,
                entity_type,
                entity_id,
                json.dumps(payload or {"target_revision": "revision-1"}),
                status,
                "2026-09-23T00:00:00+00:00",
                "2026-09-23T00:00:01+00:00",
                1,
                "boom" if status == "failed" else None,
            ),
        )


def test_wait_maintenance_rejects_current_failed_job_but_ignores_historical_failure(tmp_path):
    root = tmp_path / "run"
    database = root / "data" / "spotify_stats.db"
    _background_jobs_database(database)
    _insert_job(database, job_id="historical", status="failed")
    baseline = runtime_matrix_run._maintenance_baseline(root)
    _insert_job(database, job_id="current", status="failed")

    with pytest.raises(RuntimeError, match="current.*failed"):
        runtime_matrix_run._wait_maintenance(root, [], 0.05, baseline)


def test_wait_maintenance_follows_retry_and_new_critical_jobs(tmp_path, monkeypatch):
    root = tmp_path / "run"
    database = root / "data" / "spotify_stats.db"
    _background_jobs_database(database)
    baseline = runtime_matrix_run._maintenance_baseline(root)
    _insert_job(database, job_id="first", status="pending")
    polls = iter([0, 1, 2])

    def advance(_seconds: float) -> None:
        step = next(polls, None)
        if step is None:
            return
        with sqlite3.connect(database) as conn:
            if step == 0:
                conn.execute(
                    "UPDATE background_jobs SET status='pending', attempts=2 WHERE job_id='first'"
                )
            elif step == 1:
                conn.execute("UPDATE background_jobs SET status='done' WHERE job_id='first'")
                conn.execute(
                    """INSERT INTO background_jobs VALUES(
                           'second','startup_cache_warmup','runtime','minimal','{}',
                           'pending','2026-09-23T00:00:02+00:00',
                           '2026-09-23T00:00:02+00:00',0,NULL
                       )"""
                )
            else:
                conn.execute("UPDATE background_jobs SET status='done' WHERE job_id='second'")

    monkeypatch.setattr(runtime_matrix_run.time, "sleep", advance)
    summary = runtime_matrix_run._wait_maintenance(root, [], 1, baseline)

    assert {job["job_id"] for job in summary["jobs"]} == {"first", "second"}
    assert all(job["status"] == "done" for job in summary["jobs"])
    assert next(job for job in summary["jobs"] if job["job_id"] == "first")["attempts"] == 2


@pytest.mark.parametrize("snapshot_state", ["missing", "unknown"])
def test_core_page_probe_rejects_non_ready_snapshot(tmp_path, monkeypatch, snapshot_state):
    output = tmp_path / "page.json"

    def fake_run(command, **kwargs):
        output.write_text(
            json.dumps(
                {
                    "samples": [
                        {
                            "success": True,
                            "core_ready": {"ready": True},
                            "snapshot": {"state": snapshot_state},
                        }
                    ]
                }
            )
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runtime_matrix_run.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="snapshot"):
        runtime_matrix_run._probe_core_page(
            "http://127.0.0.1:14173",
            "http://127.0.0.1:18100",
            output,
            2,
        )


def test_core_page_probe_classifies_temporary_503_as_pending(tmp_path, monkeypatch):
    output = tmp_path / "page.json"

    def fake_run(command, **kwargs):
        output.write_text(
            json.dumps(
                {
                    "samples": [
                        {
                            "success": False,
                            "http": {"error_type": "HTTP503"},
                            "core_ready": {
                                "ready": False,
                                "route_ready": True,
                                "api_ready": False,
                                "failure": "HTTP503",
                            },
                        }
                    ]
                }
            )
        )
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(runtime_matrix_run.subprocess, "run", fake_run)
    with pytest.raises(runtime_matrix_run.CorePagePendingError, match="503"):
        runtime_matrix_run._probe_core_page(
            "http://127.0.0.1:14173",
            "http://127.0.0.1:18100",
            output,
            2,
        )


def test_core_page_probe_accepts_ready_api_with_missing_isolated_covers(tmp_path, monkeypatch):
    output = tmp_path / "page.json"

    def fake_run(command, **kwargs):
        output.write_text(
            json.dumps(
                {
                    "samples": [
                        {
                            "success": False,
                            "core_ready": {"ready": True},
                            "api_terminal": {"complete": True, "success": True, "failed": []},
                            "waterfall": [
                                {
                                    "url": "http://127.0.0.1:18100/api/home/overview",
                                    "status": 200,
                                    "snapshot": {"state": "exact"},
                                },
                                {
                                    "url": "http://127.0.0.1:18100/covers/albums/1.jpg",
                                    "status": 404,
                                },
                            ],
                        }
                    ]
                }
            )
        )
        return SimpleNamespace(returncode=1, stdout="", stderr="cover 404")

    monkeypatch.setattr(runtime_matrix_run.subprocess, "run", fake_run)
    result = runtime_matrix_run._probe_core_page(
        "http://127.0.0.1:14173",
        "http://127.0.0.1:18100",
        output,
        2,
        require_exact=True,
    )

    assert result["snapshot_states"] == ["exact"]


def test_exact_core_page_probe_classifies_lkg_as_pending(tmp_path, monkeypatch):
    output = tmp_path / "page.json"

    def fake_run(command, **kwargs):
        output.write_text(
            json.dumps(
                {
                    "samples": [
                        {
                            "success": True,
                            "core_ready": {"ready": True},
                            "api_terminal": {"complete": True, "success": True, "failed": []},
                            "snapshot": {"state": "LKG"},
                        }
                    ]
                }
            )
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runtime_matrix_run.subprocess, "run", fake_run)
    with pytest.raises(runtime_matrix_run.CorePagePendingError, match="LKG"):
        runtime_matrix_run._probe_core_page(
            "http://127.0.0.1:14173",
            "http://127.0.0.1:18100",
            output,
            2,
            require_exact=True,
        )


def test_isolated_app_factory_blocks_external_targets_and_clears_proxies(tmp_path):
    root = tmp_path / "runtime"
    (root / "data").mkdir(parents=True)
    (root / "manifest.json").write_text("{}")
    proxy = socket.socket()
    proxy.bind(("127.0.0.1", 0))
    proxy.listen()
    proxy.settimeout(0.1)
    proxy_port = proxy.getsockname()[1]
    code = """
import json, os
from urllib.request import urlopen
from scripts import runtime_measurement
runtime_measurement.configure_isolated_runtime_from_environment()
blocked = False
try:
    urlopen('http://provider.invalid/', timeout=1)
except RuntimeError:
    blocked = True
print(json.dumps({'blocked': blocked, 'proxy': os.environ.get('HTTP_PROXY')}))
"""
    environment = os.environ.copy()
    environment.update(
        SPOTIFY_RUNTIME_MEASUREMENT_ROOT=str(root),
        SPOTIFY_RUNTIME_WARMUP_MODE="minimal",
        SPOTIFY_RUNTIME_FRONTEND_ORIGIN="http://127.0.0.1:14173",
        HTTP_PROXY=f"http://127.0.0.1:{proxy_port}",
        HTTPS_PROXY=f"http://127.0.0.1:{proxy_port}",
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=runtime_measurement.ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {"blocked": True, "proxy": None}
    with pytest.raises(socket.timeout):
        proxy.accept()
    proxy.close()


def test_reload_worker_reinstalls_network_boundary_and_keeps_loopback_health(tmp_path):
    root = tmp_path / "runtime"
    reload_dir = tmp_path / "reload"
    (root / "data").mkdir(parents=True)
    reload_dir.mkdir()
    (root / "manifest.json").write_text("{}")
    (root / "data" / "spotify_stats.db").touch()
    trigger = reload_dir / "trigger.py"
    trigger.write_text("VALUE = 1\n")
    with closing(socket.socket()) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            str(runtime_measurement.ROOT / "scripts" / "runtime_measurement.py"),
            "serve",
            "--root",
            str(root),
            "--port",
            str(port),
            "--warmup-mode",
            "off",
            "--reload",
            "--reload-dir",
            str(reload_dir),
        ],
        cwd=runtime_measurement.ROOT,
        env=os.environ.copy(),
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    opener = build_opener(ProxyHandler({}))

    def isolation(timeout: float = 20) -> dict:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise AssertionError(f"reload server exited: {output}")
            try:
                with opener.open(
                    f"http://127.0.0.1:{port}/api/runtime-measurement/isolation",
                    timeout=1,
                ) as response:
                    return json.loads(response.read())
            except Exception as exc:
                last_error = exc
                time.sleep(0.1)
        raise AssertionError(f"reload isolation endpoint did not become ready: {last_error}")

    try:
        first = isolation()
        assert first["network_guard"] == "installed"
        assert first["external_blocked"] is True
        assert first["proxy_environment_clear"] is True
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            assert response.status == 200

        trigger.write_text("VALUE = 2\n")
        deadline = time.monotonic() + 20
        second = first
        while time.monotonic() < deadline and second["pid"] == first["pid"]:
            time.sleep(0.2)
            try:
                second = isolation(1)
            except AssertionError:
                continue
        assert second["pid"] != first["pid"]
        assert second["network_guard"] == "installed"
        assert second["external_blocked"] is True
        assert second["proxy_environment_clear"] is True
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)


@pytest.mark.parametrize("failed_target", ["analysis", "music_search"])
def test_publication_validation_rejects_missing_or_stale_target(
    tmp_path, monkeypatch, failed_target
):
    output = tmp_path / "publications.json"

    def fake_run(command, **kwargs):
        output.write_text(
            json.dumps(
                {
                    "ready": False,
                    "checks": {
                        failed_target: {
                            "ready": False,
                            "target_revision": "current",
                            "source_revision": "old",
                        }
                    },
                }
            )
        )
        return SimpleNamespace(returncode=4, stdout="", stderr="")

    monkeypatch.setattr(runtime_matrix_run.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match=failed_target):
        runtime_matrix_run._validate_maintenance_publications(tmp_path, output)


def test_matrix_second_spawn_failure_cleans_up_first_owned_process(tmp_path, monkeypatch):
    root = tmp_path / "run"
    database = root / "data" / "spotify_stats.db"
    _background_jobs_database(database)
    first = SimpleNamespace(pid=202, poll=lambda: None)
    calls = iter([first, FileNotFoundError("npm unavailable")])
    stopped: list[list[object]] = []

    def popen(*_args, **_kwargs):
        result = next(calls)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(runtime_matrix_run, "_free", lambda _port: None)
    monkeypatch.setattr(runtime_matrix_run, "_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_matrix_run, "_external_competitors", lambda: [])
    monkeypatch.setattr(runtime_matrix_run.subprocess, "Popen", popen)
    monkeypatch.setattr(
        runtime_matrix_run, "_stop", lambda processes: stopped.append(list(processes))
    )
    monkeypatch.setattr(runtime_matrix_run.signal, "signal", lambda *_args: None)
    args = SimpleNamespace(
        root=str(root),
        backend_port=18100,
        frontend_port=14173,
        frontend_mode="dev",
        warmup_mode="minimal",
        reload=False,
        idle_seconds=0,
        startup_timeout=1,
        maintenance_timeout=1,
        phase_file=tmp_path / "phase.txt",
        events_output=tmp_path / "events.jsonl",
        backend_pid_file=None,
        frontend_pid_file=None,
    )

    with pytest.raises(FileNotFoundError, match="npm unavailable"):
        runtime_matrix_run._run(args)

    assert stopped == [[first]]


def test_matrix_external_competitor_blocks_before_starting_services(tmp_path, monkeypatch):
    root = tmp_path / "run"
    (root / "data").mkdir(parents=True)
    events: list[tuple[str, dict]] = []

    monkeypatch.setattr(runtime_matrix_run, "_free", lambda _port: None)
    monkeypatch.setattr(
        runtime_matrix_run,
        "_event",
        lambda _path, name, **details: events.append((name, details)),
    )
    monkeypatch.setattr(
        runtime_matrix_run,
        "_external_competitors",
        lambda: ["123 pytest backend/tests -q"],
    )
    monkeypatch.setattr(
        runtime_matrix_run.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("service must not start while a competitor exists"),
    )
    args = SimpleNamespace(
        root=str(root),
        backend_port=18100,
        frontend_port=14173,
        frontend_mode="dev",
        warmup_mode="minimal",
        reload=False,
        idle_seconds=0,
        startup_timeout=1,
        maintenance_timeout=1,
        phase_file=tmp_path / "phase.txt",
        events_output=tmp_path / "events.jsonl",
        backend_pid_file=None,
        frontend_pid_file=None,
    )

    assert runtime_matrix_run._run(args) == 4
    assert args.phase_file.read_text(encoding="utf-8") == "blocked"
    assert events[-1] == (
        "blocked_by_external_competitors",
        {"external_competitors": ["123 pytest backend/tests -q"]},
    )
