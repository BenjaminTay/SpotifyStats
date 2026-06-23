from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_long_list_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_long_list_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_long_list_smoke.mjs" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-base-url" in result.stdout
    assert "--scenario" in result.stdout
    assert "--output" in result.stdout


def test_frontend_long_list_smoke_script_covers_named_long_lists():
    source = (ROOT / "scripts" / "frontend_long_list_smoke.mjs").read_text(encoding="utf-8")

    assert "records-mini-rank" in source
    assert "all-time-table" in source
    assert "community-feed" in source
    assert "recent-plays" in source
    assert "saved-tracks" in source
    assert "personal-rank-table" in source
    assert "detectPageText" in source
    assert "assertRowWindowChange" in source
    assert "Input.dispatchMouseEvent" in source
    assert "buttons: 1" in source
    assert "Runtime.consoleAPICalled" in source


def test_frontend_long_list_smoke_script_matches_playback_records_range_pager():
    source = (ROOT / "scripts" / "frontend_long_list_smoke.mjs").read_text(encoding="utf-8")

    assert "'playback-records-mini-rank'" in source
    assert "pagePattern: '\\\\d+\\\\s*—\\\\s*\\\\d+\\\\s*/\\\\s*\\\\d+'" in source
    assert "pagePattern: '\\\\d+\\\\s*/\\\\s*\\\\d+'" not in source


def test_frontend_long_list_smoke_script_can_rewrite_preview_api_requests():
    source = (ROOT / "scripts" / "frontend_long_list_smoke.mjs").read_text(encoding="utf-8")

    assert "apiBaseUrl" in source
    assert "setupApiRequestRewrite" in source
    assert "Fetch.requestPaused" in source
    assert "Fetch.continueRequest" in source
    assert "'/api'" in source
    assert "'/covers'" in source
