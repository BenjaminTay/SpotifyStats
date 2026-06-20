from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_smoke_scripts_prefer_playwright_chromium_before_system_chrome():
    helper = (ROOT / "scripts" / "lib" / "chrome_executable.mjs").read_text(
        encoding="utf-8",
    )

    assert "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH" in helper
    assert "Library/Caches/ms-playwright" in helper
    assert "listPlaywrightHeadlessShellCandidates()" in helper
    assert "chromium_headless_shell-" in helper
    assert "chrome-headless-shell" in helper
    assert "listPlaywrightChromiumCandidates()" in helper
    assert helper.index("...listPlaywrightHeadlessShellCandidates()") < helper.index(
        "...listPlaywrightChromiumCandidates()",
    )
    assert helper.index("...listPlaywrightChromiumCandidates()") < helper.index(
        "/Applications/Google Chrome.app",
    )


def test_frontend_smoke_scripts_share_chrome_executable_lookup():
    scripts = [
        "frontend_route_smoke.mjs",
        "frontend_chart_interaction_smoke.mjs",
        "frontend_interaction_smoke.mjs",
        "frontend_long_list_smoke.mjs",
        "frontend_control_inventory_smoke.mjs",
        "frontend_web_vitals_probe.mjs",
    ]

    for script_name in scripts:
        source = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")
        assert "import { findChrome } from './lib/chrome_executable.mjs'" in source
        assert "function findChrome(" not in source
        assert "/Applications/Google Chrome.app" not in source
