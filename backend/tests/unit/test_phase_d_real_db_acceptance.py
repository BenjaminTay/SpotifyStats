from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts import phase_d_real_db_acceptance as acceptance

pytestmark = pytest.mark.unit


def test_validate_workdir_rejects_source_directory_and_repository_targets(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    source_dir = project / "data"
    source_dir.mkdir(parents=True)
    source = source_dir / "live.db"
    source.touch()
    outside = tmp_path / "outside-work"

    original_root = acceptance.PROJECT_ROOT
    acceptance.PROJECT_ROOT = project.resolve()
    try:
        with pytest.raises(acceptance.AcceptanceError):
            acceptance.validate_workdir(source, source_dir / "benchmark")
        with pytest.raises(acceptance.AcceptanceError):
            acceptance.validate_workdir(source, project / "benchmark")
        resolved_source, resolved_outside = acceptance.validate_workdir(source, outside)
    finally:
        acceptance.PROJECT_ROOT = original_root

    assert resolved_source == source.resolve()
    assert resolved_outside == outside.resolve()


def test_managed_workdir_cleans_by_default_and_preserves_on_request(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "live.db"
    source.touch()
    cleanup_target = tmp_path / "cleanup-work"

    with acceptance.managed_workdir(source, cleanup_target, keep=False) as workdir:
        marker = workdir / "private-copy.db"
        marker.touch()
        assert marker.exists()
    assert not cleanup_target.exists()

    keep_target = tmp_path / "keep-work"
    with acceptance.managed_workdir(source, keep_target, keep=True) as workdir:
        (workdir / "private-copy.db").touch()
    assert keep_target.is_dir()
    assert (keep_target / "private-copy.db").is_file()


def test_online_backup_does_not_mutate_source_database(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "copy.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE evidence(value INTEGER)")
    conn.execute("INSERT INTO evidence VALUES (7)")
    conn.commit()
    conn.close()
    before = source.stat()

    acceptance._online_backup(source, target)

    after = source.stat()
    assert (after.st_size, after.st_mtime_ns, after.st_ino) == (
        before.st_size,
        before.st_mtime_ns,
        before.st_ino,
    )
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT value FROM evidence").fetchone()[0] == 7
    conn.close()


def test_build_final_report_marks_skipped_search_partial(monkeypatch) -> None:
    monkeypatch.setattr(
        acceptance,
        "_git_evidence",
        lambda: {"head": "test", "dirty": False, "status_lines": 0},
    )
    report = acceptance.build_final_report(
        source_profile={"play_count": 10, "quick_check": "ok"},
        backup_profile={"play_count": 10, "quick_check": "ok"},
        baseline_build={"elapsed_ms": 1.0},
        append_scope={"added_count": 1, "billboard_scope_exact": True},
        billboard={"status": "passed", "passed": True},
        search=None,
        keep_workdir=False,
    )

    assert report["schema_version"] == acceptance.REPORT_SCHEMA_VERSION
    assert report["status"] == "partial"
    assert report["gate"] == {
        "billboard_equivalent": True,
        "search_equivalent": None,
        "requested_checks_passed": True,
        "complete_phase_d": False,
    }
    assert report["search"] == {"status": "skipped", "passed": None}
    assert report["synthetic_baseline"]["validates_phase_b_fingerprints"] is False
    assert report["privacy"] == acceptance.PRIVACY_REPORT


def test_parse_args_rejects_invalid_trial_count() -> None:
    with pytest.raises(SystemExit):
        acceptance.parse_args(["--trials", "0"])


def test_billboard_comparison_requires_credit_membership_digest(tmp_path: Path) -> None:
    partition = tmp_path / "partition.db"
    full = tmp_path / "full.db"
    for path in (partition, full):
        conn = sqlite3.connect(path)
        for table in acceptance.BILLBOARD_TABLES:
            conn.execute(f'CREATE TABLE "{table}"(billboard_week TEXT, value INTEGER)')
            conn.execute(f'INSERT INTO "{table}" VALUES ("2026-01-02", 1)')
        conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany(
            "INSERT INTO agg_config(key, value) VALUES (?, 'present')",
            [
                (key,)
                for key in (
                    "data_generation_id",
                    "source_dataset_digest",
                    "builder_version",
                    "playback_policy_version",
                    "identity_revision",
                    "track_credit_revision",
                    "album_project_revision",
                    "duration_revision",
                )
            ],
        )
        conn.commit()
        conn.close()

    missing = acceptance._compare_billboard(partition, full)
    assert missing["partition_config_complete"] is False
    assert missing["passed"] is False

    for path in (partition, full):
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO agg_config(key, value) VALUES ('credit_membership_revision', 'present')"
        )
        conn.commit()
        conn.close()

    complete = acceptance._compare_billboard(partition, full)
    assert complete["partition_config_complete"] is True
    assert complete["full_config_complete"] is True
    assert complete["semantic_config_equal"] is True
    assert complete["passed"] is True
