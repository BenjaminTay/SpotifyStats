from __future__ import annotations

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


def test_quickstart_smoke_uses_stable_fastapi_docs_marker():
    source = (ROOT / "scripts" / "quickstart_smoke.py").read_text(encoding="utf-8")

    assert 'require_text="swagger-ui"' in source
    assert 'require_text="Swagger UI"' not in source
