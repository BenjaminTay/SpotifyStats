from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[3]


def test_loading_performance_probe_exposes_cold_warm_and_gate_options():
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "loading_performance_probe.py"), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--track-id" in result.stdout
    assert "--other-track-id" in result.stdout
    assert "--summary-first-ms" in result.stdout
    assert "--stats-warm-ms" in result.stdout
    assert "--stats-first-ms" in result.stdout
    assert "--fail-on-slow" in result.stdout
