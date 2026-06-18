from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_cross_browser_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_cross_browser_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_cross_browser_smoke.mjs" in result.stdout
    assert "--base-url" in result.stdout
    assert "--browser" in result.stdout
    assert "--scenario" in result.stdout
    assert "--python" in result.stdout
    assert "--output" in result.stdout


def test_frontend_cross_browser_smoke_script_covers_browser_families_and_flows():
    source = (ROOT / "scripts" / "frontend_cross_browser_smoke.mjs").read_text(encoding="utf-8")

    assert "playwright.sync_api" in source
    assert "PYTHON_PLAYWRIGHT" in source
    assert "chromium" in source
    assert "firefox" in source
    assert "webkit" in source
    assert "Safari-family" in source
    assert "route-markers" in source
    assert "core-interactions" in source
    assert "frontend-cross-browser-smoke.py" in source
    assert "analysis-tabs" in source
    assert "billboard-routing" in source
    assert "ai-insights-tabs" in source
    assert 'wait_for_any_text(page, ["AI 功能尚未配置", "对话历史"])' in source
    assert "theme-toggle" in source
    assert "max-scroll-overflow" in source
