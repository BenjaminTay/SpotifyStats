from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_runtime_resource_probe_exposes_reusable_cli():
    script = ROOT / "scripts" / "runtime_resource_probe.py"

    result = subprocess.run(
        [".venv/bin/python", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "runtime_resource_probe.py" in result.stdout
    assert "--backend-url" in result.stdout
    assert "--frontend-url" in result.stdout
    assert "--preview-url" in result.stdout
    assert "--json-output" in result.stdout
    assert "--fail-on-missing" in result.stdout


def test_runtime_resource_probe_extracts_port_from_urls():
    from scripts.runtime_resource_probe import url_port

    assert url_port("http://127.0.0.1:8000") == 8000
    assert url_port("http://localhost:5173/path") == 5173

    with pytest.raises(ValueError):
        url_port("http://127.0.0.1")


def test_runtime_resource_probe_parses_ps_rows_and_sums_rss():
    from scripts.runtime_resource_probe import parse_ps_rows, summarize_processes

    rows = parse_ps_rows(
        """
          PID  PPID   RSS COMMAND
        1010     1 51200 /usr/bin/python -m uvicorn backend.main:app
        2020  1010 25600 /usr/bin/python worker child
        """,
    )
    summary = summarize_processes("backend", "http://127.0.0.1:8000", rows)

    assert summary["label"] == "backend"
    assert summary["port"] == 8000
    assert summary["status"] == "ok"
    assert summary["process_count"] == 2
    assert summary["pids"] == [1010, 2020]
    assert summary["rss_mb"] == 75.0
    assert "uvicorn" in summary["commands"][0]


def test_runtime_resource_probe_builds_machine_readable_report():
    from scripts.runtime_resource_probe import build_json_report

    snapshots = [
        {
            "label": "backend",
            "url": "http://127.0.0.1:8000",
            "port": 8000,
            "status": "ok",
            "pids": [1010],
            "process_count": 1,
            "rss_mb": 50.0,
            "commands": ["python -m uvicorn backend.main:app"],
        },
        {
            "label": "frontend",
            "url": "http://127.0.0.1:5173",
            "port": 5173,
            "status": "missing",
            "pids": [],
            "process_count": 0,
            "rss_mb": 0.0,
            "commands": [],
        },
    ]

    report = build_json_report(snapshots)

    assert report["snapshot_count"] == 2
    assert report["missing_count"] == 1
    assert report["total_rss_mb"] == 50.0
    assert report["snapshots"] == snapshots
