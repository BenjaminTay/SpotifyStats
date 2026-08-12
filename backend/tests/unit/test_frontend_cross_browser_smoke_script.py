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
    assert "--api-base-url" in result.stdout
    assert "--browser" in result.stdout
    assert "--scenario" in result.stdout
    assert "--include-detail-routes" in result.stdout
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
    assert "fetch_llm_availability" in source
    assert "llm_enabled" in source
    assert "has_llm_key" in source
    assert "settings-controls" in source
    assert "settings-data-import" in source
    assert "path: '/yearly-review'" in source
    assert "run_yearly_review(browser)" in source
    assert "hasYearlyV2" in source
    assert "hasLegacyYearly" in source
    assert "年度纪录分页" in source
    assert "年度附录分页" in source
    assert "expand_section_for_text" in source
    assert "run_settings_controls(browser)" in source
    assert "run_settings_data_import(browser)" in source
    assert "参数与配置" in source
    assert "Spotify 连接" in source
    assert "数据与显示" in source
    assert "数据导入" in source
    assert "榜单参数" in source
    assert "归并与版本" in source
    assert "SETTINGS / CONFIGURATION" not in source
    assert "00 · SPOTIFY 连接" not in source
    assert "DATA & DISPLAY" not in source
    assert "DATA IMPORT" not in source
    assert "BILLBOARD PARAMETERS" not in source
    assert "VERSION MERGE" not in source
    assert "theme-toggle" in source
    assert "max-scroll-overflow" in source
    assert "const DYNAMIC_ROUTE_WAIT_MS = 20000" in source
    assert "FRONTEND_DYNAMIC_ROUTE_WAIT_MS" in source
    assert "def wait_ms_for_route(route)" in source


def test_frontend_cross_browser_smoke_script_can_rewrite_preview_api_requests():
    source = (ROOT / "scripts" / "frontend_cross_browser_smoke.mjs").read_text(encoding="utf-8")

    assert "FRONTEND_API_BASE_URL" in source
    assert "REWRITE_PATH_PREFIXES" in source
    assert "rewrite_request_url" in source
    assert "page.route" in source
    assert "route.fetch(url=rewritten)" in source
    assert "route.fulfill(response=response)" in source
    assert "except Exception" in source
    assert "route.abort()" in source
    assert "'/api'" in source
    assert "'/covers'" in source


def test_frontend_cross_browser_smoke_script_waits_for_network_before_closing_pages():
    source = (ROOT / "scripts" / "frontend_cross_browser_smoke.mjs").read_text(encoding="utf-8")

    assert "def close_page(page):" in source
    assert 'page.wait_for_load_state("networkidle"' in source
    assert "close_page(page)" in source


def test_frontend_cross_browser_smoke_filters_browser_preload_diagnostics_only():
    source = (ROOT / "scripts" / "frontend_cross_browser_smoke.mjs").read_text(encoding="utf-8")

    assert "IGNORED_CONSOLE_PATTERNS" in source
    assert "preloaded using link preload but not used within a few seconds" in source
    assert "is_ignored_console_message" in source


def test_frontend_cross_browser_smoke_can_cover_dynamic_detail_routes():
    source = (ROOT / "scripts" / "frontend_cross_browser_smoke.mjs").read_text(encoding="utf-8")

    assert "--include-detail-routes" in source
    assert "resolveDetailRoutes" in source
    assert "dynamic: true" in source
    assert "/api/billboard/entity-lists" in source
    assert "/api/community/feed" in source
    for marker in [
        "单曲详情",
        "专辑详情",
        "艺人详情",
        "回复",
        "Posts",
    ]:
        assert marker in source
