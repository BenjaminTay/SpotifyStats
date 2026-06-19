from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_fullstack_verification_check_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "fullstack_verification_check.sh"

    result = subprocess.run(
        ["sh", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "fullstack_verification_check.sh" in result.stdout
    assert "--backend-url" in result.stdout
    assert "--frontend-url" in result.stdout
    assert "--preview-url" in result.stdout
    assert "--web-vitals" in result.stdout


def test_fullstack_verification_check_script_covers_delivery_matrix():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "pytest backend/tests/ -q" in source
    assert "pre-commit run --all-files" in source
    assert "scripts/phase5_check.sh" in source
    assert "scripts/api_smoke_probe.py" in source
    assert "scripts/api_boundary_probe.py" in source
    assert "scripts/benchmark_api.py" in source
    assert "--fail-on-slow" in source
    assert "scripts/frontend_route_smoke.mjs" in source
    assert "scripts/frontend_interaction_smoke.mjs" in source
    assert "scripts/frontend_chart_interaction_smoke.mjs" in source
    assert "scripts/frontend_long_list_smoke.mjs" in source
    assert "scripts/frontend_cross_browser_smoke.mjs" in source
    assert "scripts/frontend_web_vitals_probe.mjs" in source


def test_fullstack_verification_check_rewrites_preview_route_smoke_api_requests():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert (
        'scripts/frontend_route_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL"'
        in source
    )
    assert (
        'scripts/frontend_interaction_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL"'
        in source
    )
    assert (
        'scripts/frontend_cross_browser_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL"'
        in source
    )
    assert (
        'scripts/frontend_web_vitals_probe.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL"'
        in source
    )


def test_fullstack_verification_check_preserves_python_with_playwright_across_venv_activation():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "detect_playwright_python()" in source
    assert "import playwright.sync_api" in source
    assert "export PYTHON_PLAYWRIGHT" in source
    assert (
        'scripts/frontend_cross_browser_smoke.mjs --base-url "$FRONTEND_URL" --python "$PYTHON_PLAYWRIGHT"'
        in source
    )
