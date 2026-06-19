from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_openapi_parameter_boundary_audit_exposes_reusable_cli():
    script = ROOT / "scripts" / "openapi_parameter_boundary_audit.py"

    result = subprocess.run(
        [".venv/bin/python", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "openapi_parameter_boundary_audit.py" in result.stdout
    assert "--json-output" in result.stdout


def test_openapi_parameter_boundary_audit_accounts_for_all_obligations():
    from backend.main import app
    from scripts.openapi_parameter_boundary_audit import (
        assert_parameter_boundary_audit,
        build_parameter_boundary_audit,
    )

    audit = build_parameter_boundary_audit(app)

    assert audit.obligation_count >= 30
    assert audit.unaccounted_obligations == ()
    assert audit.category_counts["boundary_probe"] >= 25
    assert audit.category_counts["controlled_stateful_or_external"] >= 1
    assert_parameter_boundary_audit(audit)


def test_openapi_parameter_boundary_audit_records_evidence_for_high_risk_parameters():
    from backend.main import app
    from scripts.openapi_parameter_boundary_audit import build_parameter_boundary_audit

    audit = build_parameter_boundary_audit(app)
    obligations = audit.obligations_by_key

    assert obligations[("query", "merge_level", "integer|maximum=3|minimum=1")].category == (
        "boundary_probe"
    )
    assert (
        "analysis_charts_merge_level_low"
        in obligations[("query", "merge_level", "integer|maximum=3|minimum=1")].evidence
    )
    assert obligations[
        ("query", "bb_week_start_hour", "integer|maximum=23|minimum=0")
    ].category == ("boundary_probe")
    assert (
        "billboard_week_start_hour_high"
        in obligations[("query", "bb_week_start_hour", "integer|maximum=23|minimum=0")].evidence
    )
    assert obligations[("path", "session_id", "integer")].category == "boundary_probe"
    assert "chat_session_path_nonint" in obligations[("path", "session_id", "integer")].evidence
    assert obligations[
        ("query", "overlap_threshold", "number|maximum=1.0|minimum=0.1")
    ].category == ("controlled_stateful_or_external")


def test_openapi_parameter_boundary_audit_renders_markdown_summary():
    from backend.main import app
    from scripts.openapi_parameter_boundary_audit import (
        build_parameter_boundary_audit,
        render_markdown_report,
    )

    markdown = render_markdown_report(build_parameter_boundary_audit(app))

    assert "OpenAPI parameter boundary audit" in markdown
    assert "Unaccounted obligations | 0" in markdown
    assert "boundary_probe" in markdown
    assert "controlled_stateful_or_external" in markdown
