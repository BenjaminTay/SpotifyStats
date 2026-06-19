from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_interaction_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_interaction_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_interaction_smoke.mjs" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-base-url" in result.stdout
    assert "--scenario" in result.stdout
    assert "--output" in result.stdout


def test_frontend_interaction_smoke_script_covers_core_non_destructive_flows():
    source = (ROOT / "scripts" / "frontend_interaction_smoke.mjs").read_text(encoding="utf-8")

    assert "const DEFAULT_WAIT_MS = 5000" in source
    assert "async function waitForText" in source
    assert "async function waitForAnyText" in source
    assert "async function waitForPath" in source
    assert "analysis-tabs" in source
    assert "billboard-routing" in source
    assert "ai-insights-tabs" in source
    assert "settings-controls" in source
    assert "settings-data-import" in source
    assert "theme-toggle" in source
    assert "assertClickableTextCount" in source
    assert "fetchLlmAvailability" in source
    assert "llm_enabled" in source
    assert "has_llm_key" in source
    assert "AI 功能尚未配置" in source
    assert "过滤参数已更新" in source
    assert "当前数据库记录数" in source
    assert "导入 Spotify 账号数据包" in source
    assert "chineseStyle" in source
    assert "Runtime.consoleAPICalled" in source


def test_frontend_interaction_smoke_script_can_rewrite_preview_api_requests():
    source = (ROOT / "scripts" / "frontend_interaction_smoke.mjs").read_text(encoding="utf-8")

    assert "apiBaseUrl" in source
    assert "setupApiRequestRewrite" in source
    assert "Fetch.requestPaused" in source
    assert "Fetch.continueRequest" in source
    assert "'/api'" in source
    assert "'/covers'" in source
