from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_openapi_operation_audit_exposes_reusable_cli():
    script = ROOT / "scripts" / "openapi_operation_audit.py"

    result = subprocess.run(
        [".venv/bin/python", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "openapi_operation_audit.py" in result.stdout
    assert "--json-output" in result.stdout


def test_openapi_operation_audit_accounts_for_all_operations():
    from backend.main import app
    from scripts.openapi_operation_audit import assert_operation_audit, build_operation_audit

    audit = build_operation_audit(app)

    assert audit.operation_count >= 130
    assert audit.unaccounted_operations == ()
    assert audit.category_counts["safe_get_smoke"] >= 90
    assert audit.category_counts["targeted_contract"] >= 30
    assert_operation_audit(audit)


def test_openapi_operation_audit_records_evidence_for_high_risk_operations():
    from backend.main import app
    from scripts.openapi_operation_audit import build_operation_audit

    audit = build_operation_audit(app)
    operations = audit.operations_by_key

    assert operations[("GET", "/api/spotify/auth/login")].category == "targeted_contract"
    assert (
        "test_spotify_auth_contract.py" in operations[("GET", "/api/spotify/auth/login")].evidence
    )
    assert operations[("POST", "/api/import/streaming")].category == "targeted_contract"
    assert "test_import_api_jobs.py" in operations[("POST", "/api/import/streaming")].evidence
    assert operations[("POST", "/api/ai-insights/ask")].category == "targeted_contract"
    assert "test_ai_insights_contract.py" in operations[("POST", "/api/ai-insights/ask")].evidence
    assert operations[("POST", "/api/version-merge/apply")].category == (
        "controlled_external_or_stateful"
    )
    assert (
        "stateful local data mutation" in operations[("POST", "/api/version-merge/apply")].rationale
    )


def test_openapi_operation_audit_renders_markdown_summary():
    from backend.main import app
    from scripts.openapi_operation_audit import build_operation_audit, render_markdown_report

    markdown = render_markdown_report(build_operation_audit(app))

    assert "OpenAPI operation audit" in markdown
    assert "Unaccounted operations | 0" in markdown
    assert "safe_get_smoke" in markdown
    assert "targeted_contract" in markdown
    assert "controlled_external_or_stateful" in markdown
