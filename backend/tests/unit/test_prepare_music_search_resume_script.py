from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.services.music_search_maintenance_service import _current_filter_values

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


def _seed_exact_statistics(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    conn.executemany(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status,
               semantic_base_key, merge_level, dynamic_threshold, builder_version
           ) VALUES (?, ?, ?, 'ready', ?, ?, ?, ?)
           ON CONFLICT(snapshot_key) DO UPDATE SET
               filter_fingerprint=excluded.filter_fingerprint,
               source_revision=excluded.source_revision,
               status='ready', semantic_base_key=excluded.semantic_base_key,
               merge_level=excluded.merge_level,
               dynamic_threshold=excluded.dynamic_threshold,
               builder_version=excluded.builder_version""",
        [
            (
                context.filter_fingerprint,
                context.filter_fingerprint,
                context.source_revision,
                context.semantic_base_key,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            )
            for context in contexts
        ],
    )
    conn.commit()
    conn.close()


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
    assert second_payload["resume_reused"] is False
    assert second_payload["reason"] == "resume_statistics_not_exact"

    _seed_exact_statistics(resume)
    third_report = tmp_path / "third.json"
    third = _run(baseline, resume, third_report)
    assert third.returncode == 0, third.stderr
    third_payload = json.loads(third_report.read_text(encoding="utf-8"))
    assert third_payload["resume_reused"] is True
    assert third_payload["reason"] == "source_equivalent_exact_statistics_resume"

    conn = sqlite3.connect(resume)
    conn.execute("UPDATE music_search_revision_state SET playback_revision=playback_revision+1")
    conn.commit()
    conn.close()

    fourth_report = tmp_path / "fourth.json"
    fourth = _run(baseline, resume, fourth_report)
    assert fourth.returncode == 0, fourth.stderr
    fourth_payload = json.loads(fourth_report.read_text(encoding="utf-8"))
    assert fourth_payload["resume_reused"] is False
    assert fourth_payload["reason"] == "resume_source_changed"
    assert fourth_payload["validation"]["context_orphan_count"] == 0
