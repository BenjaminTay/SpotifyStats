from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_phase5_check_exposes_explicit_parent_deduplication_flags():
    script = ROOT / "scripts" / "phase5_check.sh"

    result = subprocess.run(
        ["sh", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--skip-backend-tests" in result.stdout
    assert "Standalone default still runs every Phase 5 check" in result.stdout


def test_phase5_check_keeps_default_ci_commands_and_prints_skip_reasons():
    source = (ROOT / "scripts" / "phase5_check.sh").read_text(encoding="utf-8")

    assert "SKIP_BACKEND_TESTS" in source
    assert "SKIPPED: backend unit/contract" in source
    assert "pytest -m unit -q" in source
    assert "pytest -m contract -q" in source
    assert "ruff check backend/" in source
    assert "npm test" in source
    assert "npm run build" in source
