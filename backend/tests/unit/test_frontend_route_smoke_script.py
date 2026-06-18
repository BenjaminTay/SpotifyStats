from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_route_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_route_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_route_smoke.mjs" in result.stdout
    assert "--routes" in result.stdout
    assert "--viewport" in result.stdout
    assert "--max-scroll-overflow" in result.stdout
    assert "--fail-on-console-warning" in result.stdout


def test_frontend_route_smoke_script_does_not_treat_vite_dev_ids_as_overlays():
    source = (ROOT / "scripts" / "frontend_route_smoke.mjs").read_text(encoding="utf-8")

    assert "vite-error-overlay" in source
    assert "data-vite-dev-id" not in source
