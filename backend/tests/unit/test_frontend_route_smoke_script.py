from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_dev_smoke_scripts_default_to_localhost():
    for script_name in [
        "frontend_route_smoke.mjs",
        "frontend_interaction_smoke.mjs",
        "frontend_chart_interaction_smoke.mjs",
        "frontend_control_inventory_smoke.mjs",
        "frontend_long_list_smoke.mjs",
        "frontend_cross_browser_smoke.mjs",
        "frontend_web_vitals_probe.mjs",
    ]:
        source = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")
        assert "const DEFAULT_BASE_URL = 'http://localhost:5173'" in source


def test_frontend_route_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_route_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_route_smoke.mjs" in result.stdout
    assert "--routes" in result.stdout
    assert "--viewport" in result.stdout
    assert "--max-scroll-overflow" in result.stdout
    assert "--fail-on-console-warning" in result.stdout
    assert "--api-base-url" in result.stdout


def test_frontend_route_smoke_script_does_not_treat_vite_dev_ids_as_overlays():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    assert "vite-error-overlay" in source
    assert "data-vite-dev-id" not in source


def test_frontend_route_smoke_script_checks_route_content_markers():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    assert "ROUTE_READY_MARKERS" in source
    assert "'/billboard/records': ['冠军圣殿']" in source
    assert "'/analysis/records': ['播放记录', '高光时刻']" in source
    assert "'/analysis/records': ['有效播放', '狂热时刻']" not in source
    assert "missing route content marker" in source
    assert "--disable-route-markers" in source


def test_frontend_route_smoke_script_covers_analysis_redirect_aliases():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    for route in [
        "'/analysis'",
        "'/analysis/timeline'",
        "'/analysis/leaderboard'",
        "'/analysis/behavior'",
        "'/analysis/listening-hours'",
        "'/analysis/artists'",
    ]:
        assert route in source


def test_frontend_route_smoke_script_can_rewrite_preview_api_requests():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    assert "apiBaseUrl" in source
    assert "setupApiRequestRewrite" in source
    assert "Fetch.requestPaused" in source
    assert "Fetch.continueRequest" in source
    assert "catch" in source
    assert "'/api'" in source
    assert "'/covers'" in source


def test_frontend_route_smoke_default_wait_allows_cold_route_content():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    assert "const DEFAULT_WAIT_MS = 5000" in source
    assert "const DYNAMIC_ROUTE_WAIT_MS = 12000" in source
    assert "isDynamicRoute(route)" in source


def test_frontend_route_smoke_can_cover_dynamic_detail_routes():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    assert "--include-detail-routes" in source
    assert "resolveDetailRoutes" in source
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


def test_frontend_route_smoke_enforces_exclusive_mobile_and_desktop_shells():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    assert "hasMobileTopBar" in source
    assert "hasMobileBottomNav" in source
    assert "hasDesktopMasthead" in source
    assert "routeShouldHaveMobileBottomNav" in source
    assert "desktop masthead mounted in mobile viewport" in source
    assert "mobile shell mounted in desktop viewport" in source


def test_frontend_route_smoke_covers_the_m7_five_size_matrix():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    for viewport in ["phone-small", "mobile", "phone-large", "tablet", "desktop"]:
        assert viewport in source
    assert "value === 'matrix'" in source
    assert "expectedMode: 'compact'" in source


def test_frontend_m7_smokes_cover_mobile_navigation_touch_and_fullscreen():
    interaction = (ROOT / "scripts" / "frontend_interaction_smoke.mjs").read_text(encoding="utf-8")
    chart = (ROOT / "scripts" / "frontend_chart_interaction_smoke.mjs").read_text(encoding="utf-8")
    controls = (ROOT / "scripts" / "frontend_control_inventory_smoke.mjs").read_text(
        encoding="utf-8"
    )
    cross_browser = (ROOT / "scripts" / "frontend_cross_browser_smoke.mjs").read_text(
        encoding="utf-8"
    )
    fullstack = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    for scenario in ["mobile-bottom-navigation", "mobile-section-sheet", "mobile-time-filter"]:
        assert scenario in interaction
    for scenario in ["mobile-tap-tooltip", "mobile-fullscreen"]:
        assert scenario in chart
    assert "undersized primary touch target" in controls
    assert "rect.width < 43.5 || rect.height < 43.5" in controls
    assert "hasMobileTopBar" in cross_browser
    assert "route_should_have_mobile_bottom_nav" in cross_browser
    assert "--viewport matrix" in fullstack
    assert "mobile-tap-tooltip,mobile-fullscreen" in fullstack


def test_mobile_primary_touch_target_styles_keep_44px_minimums():
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")

    for selector in [
        ".mobile-chart-series-button",
        ".mobile-record-entity-toggle button",
        ".mobile-music-search-kinds button",
        ".mobile-ai-mode-switch button",
    ]:
        start = styles.index(selector)
        rule = styles[start : styles.index("}", start)]
        assert "min-height: 44px" in rule
