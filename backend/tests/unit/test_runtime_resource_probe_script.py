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
    assert "--max-total-rss-mb" in result.stdout
    assert "--max-total-cpu-percent" in result.stdout
    assert "--max-service-rss-mb" in result.stdout
    assert "--max-service-cpu-percent" in result.stdout


def test_runtime_resource_probe_extracts_port_from_urls():
    from scripts.runtime_resource_probe import DEFAULT_FRONTEND_URL, url_port

    assert DEFAULT_FRONTEND_URL == "http://localhost:5173"
    assert url_port("http://127.0.0.1:8000") == 8000
    assert url_port("http://localhost:5173/path") == 5173

    with pytest.raises(ValueError):
        url_port("http://127.0.0.1")


def test_runtime_resource_probe_parses_ps_rows_and_sums_rss_and_cpu():
    from scripts.runtime_resource_probe import parse_ps_rows, summarize_processes

    rows = parse_ps_rows(
        """
          PID  PPID   RSS  %CPU COMMAND
        1010     1 51200   2.5 /usr/bin/python -m uvicorn backend.main:app
        2020  1010 25600   0.7 /usr/bin/python worker child
        """,
    )
    summary = summarize_processes("backend", "http://127.0.0.1:8000", rows)

    assert summary["label"] == "backend"
    assert summary["port"] == 8000
    assert summary["status"] == "ok"
    assert summary["process_count"] == 2
    assert summary["pids"] == [1010, 2020]
    assert summary["rss_mb"] == 75.0
    assert summary["cpu_percent"] == 3.2
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
            "cpu_percent": 2.5,
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
            "cpu_percent": 0.0,
            "commands": [],
        },
    ]

    report = build_json_report(snapshots)

    assert report["snapshot_count"] == 2
    assert report["missing_count"] == 1
    assert report["total_rss_mb"] == 50.0
    assert report["total_cpu_percent"] == 2.5
    assert report["snapshots"] == snapshots


def test_runtime_resource_probe_evaluates_resource_budgets():
    from scripts.runtime_resource_probe import evaluate_budgets

    report = {
        "total_rss_mb": 75.0,
        "total_cpu_percent": 4.2,
        "snapshots": [
            {
                "label": "backend",
                "rss_mb": 50.0,
                "cpu_percent": 3.5,
            },
            {
                "label": "frontend",
                "rss_mb": 25.0,
                "cpu_percent": 0.7,
            },
        ],
    }

    failures = evaluate_budgets(
        report,
        max_total_rss_mb=70.0,
        max_total_cpu_percent=4.0,
        service_rss_budgets={"backend": 40.0},
        service_cpu_budgets={"frontend": 0.5},
    )

    assert "total RSS 75.0MB exceeds budget 70.0MB" in failures
    assert "total CPU 4.2% exceeds budget 4.0%" in failures
    assert "backend RSS 50.0MB exceeds budget 40.0MB" in failures
    assert "frontend CPU 0.7% exceeds budget 0.5%" in failures


def test_runtime_resource_probe_parses_service_budget_specs():
    from scripts.runtime_resource_probe import parse_service_budget

    assert parse_service_budget("backend=700") == ("backend", 700.0)

    with pytest.raises(ValueError):
        parse_service_budget("backend")
