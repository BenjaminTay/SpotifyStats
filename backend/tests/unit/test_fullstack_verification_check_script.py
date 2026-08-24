from __future__ import annotations

import json
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
    assert "--openapi-operation-audit-json" in result.stdout
    assert "--openapi-parameter-boundary-audit-json" in result.stdout
    assert "--quickstart-preflight" in result.stdout
    assert "--quickstart-json" in result.stdout
    assert "--web-vitals" in result.stdout
    assert "--web-vitals-max-lcp-ms" in result.stdout
    assert "--web-vitals-max-cls" in result.stdout
    assert "--web-vitals-max-tbt-ms" in result.stdout
    assert "--web-vitals-max-resource-count" in result.stdout
    assert "--web-vitals-max-encoded-resource-kb" in result.stdout
    assert "--web-vitals-max-scroll-overflow-px" in result.stdout
    assert "--resource-snapshot" in result.stdout
    assert "--resource-snapshot-json" in result.stdout
    assert "--resource-max-total-rss-mb" in result.stdout
    assert "--resource-max-total-cpu-percent" in result.stdout
    assert "--list-stages" in result.stdout
    assert "--only" in result.stdout
    assert "--from" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--summary-json" in result.stdout
    assert "default http://localhost:5173" in result.stdout


def test_fullstack_verification_lists_stable_stage_keys():
    script = ROOT / "scripts" / "fullstack_verification_check.sh"

    result = subprocess.run(
        ["sh", str(script), "--list-stages"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "quality",
        "backend",
        "api",
        "browser-routes",
        "browser-interactions",
        "browser-inventory",
        "browser-compat",
        "optional",
    ]


def test_fullstack_verification_rejects_conflicting_stage_selectors():
    script = ROOT / "scripts" / "fullstack_verification_check.sh"

    result = subprocess.run(
        [
            "sh",
            str(script),
            "--only",
            "api",
            "--from",
            "browser-inventory",
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "mutually exclusive" in result.stderr


@pytest.mark.parametrize("stage", ["", "missing-stage", "api,missing-stage"])
def test_fullstack_verification_rejects_unknown_or_empty_stages(stage: str):
    script = ROOT / "scripts" / "fullstack_verification_check.sh"

    result = subprocess.run(
        ["sh", str(script), "--only", stage, "--dry-run"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "stage" in result.stderr.lower()


def test_fullstack_verification_dry_run_writes_partial_stage_summary(tmp_path: Path):
    script = ROOT / "scripts" / "fullstack_verification_check.sh"
    summary = tmp_path / "summary.json"

    result = subprocess.run(
        [
            "sh",
            str(script),
            "--only",
            "api,browser-inventory",
            "--dry-run",
            "--summary-json",
            str(summary),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "PARTIAL"
    assert payload["selection"] == {
        "mode": "only",
        "stages": ["api", "browser-inventory"],
    }
    assert payload["dry_run"] is True
    stage_statuses = {item["name"]: item["status"] for item in payload["stages"]}
    assert stage_statuses["api"] == "NOT_RUN"
    assert stage_statuses["browser-inventory"] == "NOT_RUN"
    assert stage_statuses["browser-compat"] == "NOT_RUN"
    assert "Full-stack status: PARTIAL" in result.stdout


def test_fullstack_verification_from_selects_required_suffix_in_dry_run(tmp_path: Path):
    script = ROOT / "scripts" / "fullstack_verification_check.sh"
    summary = tmp_path / "summary.json"

    result = subprocess.run(
        [
            "sh",
            str(script),
            "--from",
            "browser-inventory",
            "--dry-run",
            "--summary-json",
            str(summary),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["selection"] == {
        "mode": "from",
        "stages": ["browser-inventory", "browser-compat"],
    }
    assert payload["overall_status"] == "PARTIAL"


def test_fullstack_verification_reports_blocked_service_precondition(tmp_path: Path):
    script = ROOT / "scripts" / "fullstack_verification_check.sh"
    summary = tmp_path / "summary.json"

    result = subprocess.run(
        [
            "sh",
            str(script),
            "--only",
            "api",
            "--backend-url",
            "http://127.0.0.1:1",
            "--summary-json",
            str(summary),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "BLOCKED"
    stage_statuses = {item["name"]: item["status"] for item in payload["stages"]}
    assert stage_statuses["api"] == "BLOCKED"
    assert stage_statuses["backend"] == "NOT_RUN"


def test_fullstack_verification_check_script_covers_delivery_matrix():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "FRONTEND_URL=${FRONTEND_URL:-http://localhost:5173}" in source
    assert "BENCHMARK_RUNS=${BENCHMARK_RUNS:-22}" in source
    assert "pytest backend/tests/ -q" in source
    assert "pre-commit run --all-files" in source
    assert "scripts/phase5_check.sh" in source
    assert "scripts/openapi_operation_audit.py" in source
    assert "scripts/openapi_parameter_boundary_audit.py" in source
    assert "scripts/api_smoke_probe.py" in source
    assert "scripts/api_boundary_probe.py" in source
    assert "scripts/benchmark_api.py" in source
    assert "scripts/quickstart_smoke.py" in source
    assert "--fail-on-slow" in source
    assert "scripts/frontend_route_smoke.mjs" in source
    assert "scripts/frontend_interaction_smoke.mjs" in source
    assert "scripts/frontend_chart_interaction_smoke.mjs" in source
    assert "scripts/frontend_control_inventory_smoke.mjs" in source
    assert "scripts/frontend_long_list_smoke.mjs" in source
    assert "scripts/frontend_cross_browser_smoke.mjs" in source
    assert "scripts/frontend_web_vitals_probe.mjs" in source
    assert "scripts/runtime_resource_probe.py" in source


def test_fullstack_verification_check_runs_openapi_operation_audit_with_json_output():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "OPENAPI_OPERATION_AUDIT_JSON" in source
    assert "--openapi-operation-audit-json" in source
    assert (
        'scripts/openapi_operation_audit.py --json-output "$OPENAPI_OPERATION_AUDIT_JSON"' in source
    )


def test_fullstack_verification_check_runs_openapi_parameter_boundary_audit_with_json_output():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON" in source
    assert "--openapi-parameter-boundary-audit-json" in source
    assert (
        "scripts/openapi_parameter_boundary_audit.py "
        '--json-output "$OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON"' in source
    )


def test_fullstack_verification_check_can_run_quickstart_preflight_without_starting_services():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "RUN_QUICKSTART_PREFLIGHT" in source
    assert "QUICKSTART_JSON" in source
    assert "--quickstart-preflight" in source
    assert "--quickstart-json" in source
    assert "run_quickstart_preflight" in source
    assert "scripts/quickstart_smoke.py" in source
    assert "--require-running" in source
    assert '--backend-url "$BACKEND_URL"' in source
    assert '--frontend-url "$FRONTEND_URL"' in source
    assert '--json-output "$QUICKSTART_JSON"' in source


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


def test_fullstack_verification_check_covers_detail_routes_in_route_smoke():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert (
        'scripts/frontend_route_smoke.mjs --base-url "$FRONTEND_URL" '
        "--viewport both --max-scroll-overflow 0 --fail-on-console-warning "
        "--include-detail-routes"
    ) in source
    assert (
        'scripts/frontend_route_smoke.mjs --base-url "$PREVIEW_URL" '
        '--api-base-url "$PREVIEW_API_URL" --viewport both '
        "--max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes"
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


def test_fullstack_verification_check_covers_detail_routes_in_cross_browser_smoke():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert (
        'scripts/frontend_cross_browser_smoke.mjs --base-url "$FRONTEND_URL" '
        '--python "$PYTHON_PLAYWRIGHT" --include-detail-routes'
    ) in source
    assert (
        'scripts/frontend_cross_browser_smoke.mjs --base-url "$PREVIEW_URL" '
        '--api-base-url "$PREVIEW_API_URL" --python "$PYTHON_PLAYWRIGHT" '
        "--include-detail-routes"
    ) in source


def test_fullstack_verification_check_forwards_web_vitals_budgets():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "WEB_VITALS_MAX_LCP_MS" in source
    assert "WEB_VITALS_MAX_CLS" in source
    assert "WEB_VITALS_MAX_TBT_MS" in source
    assert "WEB_VITALS_MAX_RESOURCE_COUNT" in source
    assert "WEB_VITALS_MAX_ENCODED_RESOURCE_KB" in source
    assert "WEB_VITALS_MAX_SCROLL_OVERFLOW_PX" in source
    assert "--max-lcp-ms" in source
    assert "--max-cls" in source
    assert "--max-tbt-ms" in source
    assert "--max-resource-count" in source
    assert "--max-encoded-resource-kb" in source
    assert "--max-scroll-overflow-px" in source
    assert "run_web_vitals_probe" in source


def test_fullstack_verification_check_applies_resource_budgets_only_to_preview():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert 'run_web_vitals_probe "$FRONTEND_URL" "" 0' in source
    assert 'run_web_vitals_probe "$PREVIEW_URL" "$PREVIEW_API_URL" 1' in source
    assert "include_resource_budgets=${3:-0}" in source
    assert (
        '[ "$include_resource_budgets" = "1" ] && [ -n "$WEB_VITALS_MAX_RESOURCE_COUNT" ]'
    ) in source
    assert (
        '[ "$include_resource_budgets" = "1" ] && [ -n "$WEB_VITALS_MAX_ENCODED_RESOURCE_KB" ]'
    ) in source
    assert "Skipping resource count/encoded resource Web Vitals budgets for dev server" in source


def test_fullstack_verification_check_can_capture_runtime_resource_snapshot():
    source = (ROOT / "scripts" / "fullstack_verification_check.sh").read_text(encoding="utf-8")

    assert "RUN_RESOURCE_SNAPSHOT" in source
    assert "RESOURCE_SNAPSHOT_JSON" in source
    assert "RESOURCE_MAX_TOTAL_RSS_MB" in source
    assert "RESOURCE_MAX_TOTAL_CPU_PERCENT" in source
    assert "--resource-snapshot" in source
    assert "--resource-snapshot-json" in source
    assert "--resource-max-total-rss-mb" in source
    assert "--resource-max-total-cpu-percent" in source
    assert "scripts/runtime_resource_probe.py" in source
    assert '--backend-url "$BACKEND_URL"' in source
    assert '--frontend-url "$FRONTEND_URL"' in source
    assert '--preview-url "$PREVIEW_URL"' in source
    assert '--max-total-rss-mb "$RESOURCE_MAX_TOTAL_RSS_MB"' in source
    assert '--max-total-cpu-percent "$RESOURCE_MAX_TOTAL_CPU_PERCENT"' in source
