from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_chart_interaction_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_chart_interaction_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_chart_interaction_smoke.mjs" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-base-url" in result.stdout
    assert "--scenario" in result.stdout
    assert "--output" in result.stdout
    assert "--chrome" in result.stdout


def test_frontend_chart_interaction_smoke_script_covers_echarts_flows():
    source = (ROOT / "scripts" / "frontend_chart_interaction_smoke.mjs").read_text(encoding="utf-8")

    assert "const DEFAULT_WAIT_MS = 12000" in source
    assert "const DEFAULT_ACCOUNT_CHART_WAIT_MS = 12000" in source
    assert "const DEFAULT_DATAZOOM_WAIT_MS = 12000" in source
    assert "chart-hover-tooltip" in source
    assert "legend-toggle" in source
    assert "datazoom-drag" in source
    assert "apiBaseUrl" in source
    assert "Math.max(waitMs, DEFAULT_ACCOUNT_CHART_WAIT_MS)" in source
    assert "Math.max(waitMs, DEFAULT_DATAZOOM_WAIT_MS)" in source
    assert "MouseEvent.mouseMoved" in source
    assert "MouseEvent.mousePressed" in source
    assert "MouseEvent.mouseReleased" in source
    assert "dataZoom" in source
    assert "legendselectchanged" in source
    assert "document.querySelectorAll('canvas')" in source
    assert "Runtime.consoleAPICalled" in source
    assert "scrollOverflow" in source
