from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_quickstart_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "quickstart_smoke.py"

    result = subprocess.run(
        [".venv/bin/python", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "quickstart_smoke.py" in result.stdout
    assert "--backend-url" in result.stdout
    assert "--frontend-url" in result.stdout
    assert "--timeout-sec" in result.stdout
    assert "--log-dir" in result.stdout
    assert "--json-output" in result.stdout
    assert "--require-running" in result.stdout


def test_quickstart_smoke_constructs_documented_startup_commands():
    from scripts.quickstart_smoke import build_backend_command, build_frontend_command, default_env

    assert build_backend_command("http://127.0.0.1:8000") == [
        str(ROOT / ".venv" / "bin" / "python"),
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    assert build_frontend_command("http://127.0.0.1:5173") == [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
        "--strictPort",
    ]
    assert default_env()["SPOTIFY_STATS_WARMUP"] == "0"


def test_quickstart_smoke_forwards_custom_backend_url_to_vite_proxy():
    from scripts.quickstart_smoke import default_env

    env = default_env("http://127.0.0.1:8123")
    vite_config = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    assert env["VITE_BACKEND_URL"] == "http://127.0.0.1:8123"
    assert "VITE_BACKEND_URL" in vite_config
    assert "'/api': backendUrl" in vite_config
    assert "'/covers': backendUrl" in vite_config


def test_quickstart_smoke_cleans_up_started_processes():
    source = (ROOT / "scripts" / "quickstart_smoke.py").read_text(encoding="utf-8")

    assert "started_processes" in source
    assert "terminate_processes" in source
    assert "process.terminate()" in source


def test_quickstart_smoke_can_require_existing_services():
    source = (ROOT / "scripts" / "quickstart_smoke.py").read_text(encoding="utf-8")

    assert "require_running" in source
    assert "Backend is not running" in source
    assert "Frontend is not running" in source
    assert "build_backend_command" in source
    assert "build_frontend_command" in source


def test_quickstart_smoke_require_running_does_not_start_services(monkeypatch, tmp_path):
    from scripts import quickstart_smoke

    args = quickstart_smoke.parse_args(
        [
            "--backend-url",
            "http://127.0.0.1:8123",
            "--frontend-url",
            "http://127.0.0.1:5123",
            "--log-dir",
            str(tmp_path),
            "--require-running",
        ]
    )

    monkeypatch.setattr(quickstart_smoke, "is_ready", lambda *args, **kwargs: False)

    def fail_start_process(*args, **kwargs):
        raise AssertionError("require-running mode must not start services")

    monkeypatch.setattr(quickstart_smoke, "start_process", fail_start_process)

    with pytest.raises(RuntimeError, match="Backend is not running"):
        quickstart_smoke.run_quickstart_smoke(args)


def test_quickstart_smoke_uses_stable_fastapi_docs_marker():
    source = (ROOT / "scripts" / "quickstart_smoke.py").read_text(encoding="utf-8")

    assert 'require_text="swagger-ui"' in source
    assert 'require_text="Swagger UI"' not in source


def test_quickstart_smoke_builds_machine_readable_timing_report(tmp_path):
    from scripts.quickstart_smoke import CheckTiming, build_timing_report, write_json_report

    checks = [
        CheckTiming(
            label="backend health",
            url="http://127.0.0.1:8000/api/health",
            status=200,
            elapsed_ms=123.4,
            body_bytes=128,
            has_request_id=True,
        ),
        CheckTiming(
            label="frontend shell",
            url="http://127.0.0.1:5173",
            status=200,
            elapsed_ms=456.7,
            body_bytes=2048,
            has_request_id=False,
        ),
    ]

    report = build_timing_report(
        started_at=100.0,
        finished_at=102.345,
        log_dir=tmp_path,
        backend_reused=True,
        frontend_reused=False,
        checks=checks,
    )

    assert report["total_elapsed_ms"] == 2345.0
    assert report["backend_reused"] is True
    assert report["frontend_reused"] is False
    assert report["log_dir"] == str(tmp_path)
    assert report["checks"][0]["label"] == "backend health"
    assert report["checks"][0]["elapsed_ms"] == 123.4
    assert report["checks"][0]["has_request_id"] is True
    assert report["checks"][1]["body_bytes"] == 2048

    output_path = tmp_path / "quickstart.json"
    write_json_report(report, output_path)

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["total_elapsed_ms"] == 2345.0
    assert len(written["checks"]) == 2
