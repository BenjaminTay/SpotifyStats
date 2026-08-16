from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "prepare_music_search_resume.py"
SEED = ROOT / "backend" / "tests" / "fixtures" / "seed.db"


def _run(baseline: Path, resume: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--baseline-db",
            str(baseline),
            "--resume-db",
            str(resume),
            "--json-output",
            str(report),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_resume_artifact_is_reused_only_for_the_same_search_source(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.db"
    resume = tmp_path / "resume.db"
    shutil.copy2(SEED, baseline)

    first_report = tmp_path / "first.json"
    first = _run(baseline, resume, first_report)
    assert first.returncode == 0, first.stderr
    assert json.loads(first_report.read_text(encoding="utf-8"))["resume_reused"] is False

    second_report = tmp_path / "second.json"
    second = _run(baseline, resume, second_report)
    assert second.returncode == 0, second.stderr
    second_payload = json.loads(second_report.read_text(encoding="utf-8"))
    assert second_payload["resume_reused"] is True
    assert second_payload["reason"] == "source_equivalent_resume_artifact"

    conn = sqlite3.connect(resume)
    conn.execute("UPDATE music_search_revision_state SET playback_revision=playback_revision+1")
    conn.commit()
    conn.close()

    third_report = tmp_path / "third.json"
    third = _run(baseline, resume, third_report)
    assert third.returncode == 0, third.stderr
    third_payload = json.loads(third_report.read_text(encoding="utf-8"))
    assert third_payload["resume_reused"] is False
    assert third_payload["reason"] == "resume_source_changed"
    assert third_payload["validation"]["context_orphan_count"] == 0
