from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_refresh_import_derived_data_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "refresh_import_derived_data.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "refresh_import_derived_data.py" in result.stdout
    assert "--json-output" in result.stdout
    assert "--quiet" in result.stdout


def test_refresh_import_derived_data_script_writes_machine_readable_report(monkeypatch, tmp_path):
    from scripts import refresh_import_derived_data

    calls = []
    migration_calls = []

    def fake_maintenance(progress_callback=None):
        calls.append(progress_callback)
        progress_callback("fixture maintenance", 0.5)
        return {
            "maintenance_status": "ok",
            "tracks_metadata_updated": 2,
            "albums_metadata_updated": 1,
        }

    monkeypatch.setattr(
        refresh_import_derived_data, "run_migrations", lambda: migration_calls.append("migrate")
    )
    monkeypatch.setattr(
        refresh_import_derived_data,
        "run_post_streaming_import_maintenance",
        fake_maintenance,
    )

    output_path = tmp_path / "derived-data.json"
    exit_code = refresh_import_derived_data.main(["--json-output", str(output_path), "--quiet"])

    assert exit_code == 0
    assert migration_calls == ["migrate"]
    assert calls

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["maintenance_status"] == "ok"
    assert report["tracks_metadata_updated"] == 2
    assert report["albums_metadata_updated"] == 1
