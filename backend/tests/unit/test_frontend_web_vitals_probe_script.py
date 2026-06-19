from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_web_vitals_probe_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_web_vitals_probe.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_web_vitals_probe.mjs" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-base-url" in result.stdout
    assert "--routes" in result.stdout
    assert "--viewport" in result.stdout
    assert "--output" in result.stdout
    assert "--max-lcp-ms" in result.stdout
    assert "--max-cls" in result.stdout
    assert "--max-tbt-ms" in result.stdout
    assert "--max-resource-count" in result.stdout
    assert "--max-encoded-resource-kb" in result.stdout


def test_frontend_web_vitals_probe_can_rewrite_preview_api_requests():
    source = (ROOT / "scripts" / "frontend_web_vitals_probe.mjs").read_text(
        encoding="utf-8",
    )

    assert "apiBaseUrl" in source
    assert "setupApiRequestRewrite" in source
    assert "Fetch.requestPaused" in source
    assert "Fetch.continueRequest" in source
    assert "'/api'" in source
    assert "'/covers'" in source


def test_frontend_web_vitals_probe_default_routes_cover_analysis_charts():
    source = (ROOT / "scripts" / "frontend_web_vitals_probe.mjs").read_text(
        encoding="utf-8",
    )

    assert "'/analysis/charts'" in source


def test_frontend_web_vitals_probe_can_fail_on_metric_budgets():
    source = (ROOT / "scripts" / "frontend_web_vitals_probe.mjs").read_text(
        encoding="utf-8",
    )

    assert "evaluateBudgets" in source
    assert "maxLcpMs" in source
    assert "maxCls" in source
    assert "maxTbtMs" in source
    assert "maxResourceCount" in source
    assert "maxEncodedResourceKB" in source
    assert "resourceCount" in source
    assert "encodedResourceKB" in source
    assert "Web Vitals budget failures" in source
    assert "process.exitCode = 1" in source
