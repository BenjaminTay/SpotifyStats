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
    assert "--web-vitals-max-lcp-ms" in result.stdout
    assert "--web-vitals-max-cls" in result.stdout
    assert "--web-vitals-max-tbt-ms" in result.stdout
    assert "--web-vitals-max-resource-count" in result.stdout
    assert "--web-vitals-max-encoded-resource-kb" in result.stdout
    assert "--resource-snapshot" in result.stdout
    assert "--resource-snapshot-json" in result.stdout


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
    assert "scripts/runtime_resource_probe.py" in source


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
    assert 'run_web_vitals_probe "$PREVIEW_URL" "$PREVIEW_API_URL"' in source
    assert '--api-base-url "$api_base_url"' in source


def test_fullstack_verification_check_treats_route_console_warnings_as_failures():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert (
        'scripts/frontend_route_smoke.mjs --base-url "$FRONTEND_URL" '
        "--viewport both --max-scroll-overflow 0 --fail-on-console-warning"
    ) in source
    assert (
        'scripts/frontend_route_smoke.mjs --base-url "$PREVIEW_URL" '
        '--api-base-url "$PREVIEW_API_URL" --viewport both '
        "--max-scroll-overflow 0 --fail-on-console-warning"
    ) in source


def test_fullstack_verification_check_preserves_python_with_playwright_across_venv_activation():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "detect_playwright_python()" in source
    assert "import playwright.sync_api" in source
    assert "export PYTHON_PLAYWRIGHT" in source
    assert (
        'scripts/frontend_cross_browser_smoke.mjs --base-url "$FRONTEND_URL" --python "$PYTHON_PLAYWRIGHT"'
        in source
    )


def test_fullstack_verification_check_forwards_web_vitals_budgets():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "WEB_VITALS_MAX_LCP_MS" in source
    assert "WEB_VITALS_MAX_CLS" in source
    assert "WEB_VITALS_MAX_TBT_MS" in source
    assert "WEB_VITALS_MAX_RESOURCE_COUNT" in source
    assert "WEB_VITALS_MAX_ENCODED_RESOURCE_KB" in source
    assert "--max-lcp-ms" in source
    assert "--max-cls" in source
    assert "--max-tbt-ms" in source
    assert "--max-resource-count" in source
    assert "--max-encoded-resource-kb" in source
    assert "run_web_vitals_probe" in source


def test_fullstack_verification_check_can_capture_runtime_resource_snapshot():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "RUN_RESOURCE_SNAPSHOT" in source
    assert "RESOURCE_SNAPSHOT_JSON" in source
    assert "--resource-snapshot" in source
    assert "--resource-snapshot-json" in source
    assert "scripts/runtime_resource_probe.py" in source
    assert '--backend-url "$BACKEND_URL"' in source
    assert '--frontend-url "$FRONTEND_URL"' in source
    assert '--preview-url "$PREVIEW_URL"' in source
