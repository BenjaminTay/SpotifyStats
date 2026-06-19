from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_control_inventory_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_control_inventory_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_control_inventory_smoke.mjs" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-base-url" in result.stdout
    assert "--routes" in result.stdout
    assert "--viewport" in result.stdout
    assert "--include-detail-routes" in result.stdout
    assert "--max-violations" in result.stdout


def test_frontend_control_inventory_smoke_checks_interactive_control_contracts():
    source = (ROOT / "scripts" / "frontend_control_inventory_smoke.mjs").read_text(encoding="utf-8")

    assert "collectControlInventory" in source
    assert "interactive control inventory" in source
    assert "missing accessible name" in source
    assert "nested interactive control" in source
    assert "disabled but tabbable" in source
    assert "input without label" in source
    assert "duplicate id" in source
    assert "resolveDetailRoutes" in source
    assert "/api/billboard/entity-lists" in source
    assert "/api/community/feed" in source
    assert "track_id" in source
    assert "album_name" in source
    assert "artist_name" in source
    assert "account_handle" in source
    assert "Could not resolve all control inventory detail routes" in source


def test_frontend_control_inventory_smoke_can_rewrite_preview_api_requests():
    source = (ROOT / "scripts" / "frontend_control_inventory_smoke.mjs").read_text(encoding="utf-8")

    assert "apiBaseUrl" in source
    assert "setupApiRequestRewrite" in source
    assert "Fetch.requestPaused" in source
    assert "Fetch.continueRequest" in source
    assert "'/api'" in source
    assert "'/covers'" in source


def test_frontend_control_inventory_smoke_waits_for_chrome_before_cleanup():
    source = (ROOT / "scripts" / "frontend_control_inventory_smoke.mjs").read_text(encoding="utf-8")

    assert "waitForProcessExit" in source
    assert "chromeProcess.kill('SIGTERM')" in source
    assert "await waitForProcessExit(chromeProcess)" in source


def test_frontend_control_inventory_smoke_resets_page_between_viewport_passes():
    source = (ROOT / "scripts" / "frontend_control_inventory_smoke.mjs").read_text(encoding="utf-8")

    assert "about:blank" in source
    assert "Reset same-route viewport passes" in source
    assert "Retrying control inventory route" in source
    assert "const DEFAULT_WAIT_MS = 8000" in source
