"""Deployment orchestration keeps rank reads and installation out of cold builds."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "deploy/production/versus-rank-release.sh"


def run_helper(tmp_path, commands, overrides=""):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "backups").mkdir(exist_ok=True)
    (tmp_path / "stage").mkdir(exist_ok=True)
    state = f"""
set -Eeuo pipefail
DEPLOY_DIR="$FIXTURE_DIR"
NEW_TAG=abcdef12
current_tag=1234abcd
release_stage_dir="$DEPLOY_DIR/stage"
release_stamp=fixture
VERSUS_RANK_MANIFEST=""
versus_rank_enabled=false
versus_rank_sidecar_changed=false
versus_rank_sidecar_existed=false
versus_rank_sidecar_backup=""
versus_rank_previous_manifest=""
target_backend_image=target-image
source "$HELPER_FILE"
versus_rank_image_supported() {{ return 0; }}
versus_rank_command() {{ printf '%s\\n' "$2" >> "$DEPLOY_DIR/actions"; }}
backend_image_for_tag() {{ printf 'image-%s' "$1"; }}
create_offline_backup() {{ cp "$DEPLOY_DIR/data/$3" "$2"; }}
{overrides}
{commands}
"""
    result = subprocess.run(
        ["bash", "-c", state],
        env={**os.environ, "FIXTURE_DIR": str(tmp_path), "HELPER_FILE": str(HELPER)},
        capture_output=True,
        text=True,
    )
    actions = (
        (tmp_path / "actions").read_text().splitlines() if (tmp_path / "actions").exists() else []
    )
    return result, actions


def test_no_manifest_reuses_only_exact_export_then_validate_install_verify(tmp_path):
    result, actions = run_helper(
        tmp_path,
        """
prepare_versus_rank_release target-image "$DEPLOY_DIR/staged.db"
install_versus_rank_release
""",
    )
    assert result.returncode == 0, result.stderr
    assert actions == ["export", "validate", "install", "verify"]
    assert "build" not in actions


def test_missing_ready_export_refuses_before_install(tmp_path):
    result, actions = run_helper(
        tmp_path,
        """
prepare_versus_rank_release target-image "$DEPLOY_DIR/staged.db"
install_versus_rank_release
""",
        """
versus_rank_command() { printf '%s\\n' "$2" >> "$DEPLOY_DIR/actions"; [[ "$2" != export ]]; }
""",
    )
    assert result.returncode != 0
    assert actions == ["export"]


def test_explicit_manifest_validates_before_install_without_export(tmp_path):
    manifest = tmp_path / "input.json"
    manifest.write_text("{}")
    result, actions = run_helper(
        tmp_path,
        """
VERSUS_RANK_MANIFEST="$DEPLOY_DIR/input.json"
prepare_versus_rank_release target-image "$DEPLOY_DIR/staged.db"
install_versus_rank_release
""",
    )
    assert result.returncode == 0, result.stderr
    assert actions == ["validate", "install", "verify"]


def test_old_image_without_rank_capability_keeps_original_activation_contract(tmp_path):
    result, actions = run_helper(
        tmp_path,
        """
prepare_versus_rank_release old-image "$DEPLOY_DIR/staged.db"
install_versus_rank_release
[[ "$versus_rank_enabled" == false ]]
""",
        "versus_rank_image_supported() { return 1; }",
    )
    assert result.returncode == 0, result.stderr
    assert actions == []


def test_detection_error_cannot_silently_skip_new_rank_gate(tmp_path):
    result, actions = run_helper(
        tmp_path,
        """
prepare_versus_rank_release target-image "$DEPLOY_DIR/staged.db"
""",
        "versus_rank_image_supported() { return 2; }",
    )
    assert result.returncode == 2
    assert actions == []


def test_sidecar_restore_preserves_existing_families_and_rebases_old_rank_keys(tmp_path):
    (tmp_path / "data").mkdir()
    cache = tmp_path / "data/analysis_cache.db"
    cache.write_bytes(b"previous-sidecar")
    result, actions = run_helper(
        tmp_path,
        """
versus_rank_enabled=true
backup_versus_rank_release target-image
printf 'new-sidecar' > "$DEPLOY_DIR/data/analysis_cache.db"
versus_rank_sidecar_changed=true
restore_versus_rank_release
""",
    )
    assert result.returncode == 0, result.stderr
    assert actions == ["export", "install", "verify"]
    assert cache.read_bytes() == b"previous-sidecar"


def test_deploy_order_has_no_activation_before_rank_ready_and_joint_rollback():
    deploy = (ROOT / "deploy/production/deploy.sh").read_text()
    promote = deploy.index('if ! replace_live_database "$staged_database"')
    prepare = deploy.index("if ! prepare_versus_rank_release")
    install = deploy.index("if ! install_versus_rank_release")
    activate = deploy.index('if ! activate_mode "$target_mode"')
    assert prepare < promote < install < activate
    restore = deploy[
        deploy.index("restore_previous_release() {") : deploy.index('backend_was_running="false"')
    ]
    assert (
        restore.index("replace_live_database")
        < restore.index("restore_versus_rank_release")
        < restore.index("activate_mode")
    )
    assert "quiescent-rollback.db" in deploy
    assert 'source "$DEPLOY_DIR/versus-rank-release.sh"' in deploy
    assert " build " not in HELPER.read_text()


def test_workflow_ships_helper_and_uses_preuploaded_sha_manifest_without_new_secrets():
    workflow = (ROOT / ".github/workflows/production-release.yml").read_text()
    assert "deploy.sh versus-rank-release.sh backup.sh" in workflow
    assert "backups/versus-ranks-${revision}.json" in workflow
    segment = workflow.split("Check pre-staged personal rank manifest", 1)[1].split(
        "- name: Deploy commit", 1
    )[0]
    assert "secrets.SERVER_HOST" in segment
    assert "secrets.SERVER_PORT" in segment
    assert "secrets.SERVER_USER" in segment
    assert "spotify-stats-deploy-key" in segment
    assert "actions/upload-artifact" not in segment


def _offline_backup_function(tmp_path):
    """Execute the deployment function and its actual Python body without Docker."""
    deploy = (ROOT / "deploy/production/deploy.sh").read_text()
    function = (
        "create_offline_backup() {"
        + deploy.split("create_offline_backup() {", 1)[1].split("\nreplace_live_database() {", 1)[0]
    )
    # Only remap the container's filesystem locations. Keep SQL, allowlist,
    # WAL/SHM copy, Online Backup, integrity and shell failure cleanup intact.
    return (
        function.replace('"/tmp/offline-source"', json.dumps(str(tmp_path / "offline-source")))
        .replace('"/source"', json.dumps(str(tmp_path / "data")))
        .replace("file:/tmp/offline-source/", (tmp_path / "offline-source").as_uri() + "/")
        .replace(
            '"/tmp/spotify_stats.backup.db"', json.dumps(str(tmp_path / "container-backup.db"))
        )
    )


def _run_offline_backup(tmp_path, database_name):
    state = (
        _offline_backup_function(tmp_path)
        + r"""
set -Eeuo pipefail
DEPLOY_DIR="$FIXTURE_DIR"
docker() {
  while [[ "$1" != python ]]; do shift; done
  shift
  "$PYTHON_BIN" "$@"
}
create_offline_backup fixture-image "$FIXTURE_DIR/result.db" "$DATABASE_NAME"
"""
    )
    return subprocess.run(
        ["bash", "-c", state],
        env={
            **os.environ,
            "FIXTURE_DIR": str(tmp_path),
            "DATABASE_NAME": database_name,
            "PYTHON_BIN": sys.executable,
        },
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("database_name", ["spotify_stats.db", "analysis_cache.db"])
def test_actual_offline_backup_includes_committed_wal_without_source_mutation(
    tmp_path, database_name
):
    (tmp_path / "data").mkdir()
    source_path = tmp_path / "data" / database_name
    writer = sqlite3.connect(source_path)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE facts(id INTEGER PRIMARY KEY,value TEXT)")
        writer.execute("INSERT INTO facts VALUES(1,'checkpointed')")
        writer.commit()
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute("INSERT INTO facts VALUES(2,'committed-only-in-WAL')")
        writer.commit()
        files = [source_path, Path(str(source_path) + "-wal"), Path(str(source_path) + "-shm")]
        before = {path: path.read_bytes() for path in files}
        assert before[files[1]]
        # A closed, independent main-file copy proves the second row resides
        # only in WAL, rather than accidentally exercising a checkpointed DB.
        main_only = tmp_path / "main-only.db"
        main_only.write_bytes(before[source_path])
        control = sqlite3.connect(main_only.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            assert control.execute("SELECT * FROM facts").fetchall() == [(1, "checkpointed")]
        finally:
            control.close()
        result = _run_offline_backup(tmp_path, database_name)
        assert result.returncode == 0, result.stderr
        assert {path: path.read_bytes() for path in files} == before
        backup = sqlite3.connect(
            (tmp_path / "result.db").as_uri() + "?mode=ro&immutable=1", uri=True
        )
        try:
            assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert backup.execute("SELECT * FROM facts ORDER BY id").fetchall() == [
                (1, "checkpointed"),
                (2, "committed-only-in-WAL"),
            ]
        finally:
            backup.close()
    finally:
        writer.close()


@pytest.mark.parametrize("database_name", ["unsupported.db", "../spotify_stats.db"])
def test_actual_offline_backup_rejects_other_names_and_removes_partial_output(
    tmp_path, database_name
):
    (tmp_path / "data").mkdir()
    result = _run_offline_backup(tmp_path, database_name)
    assert result.returncode != 0
    assert "unsupported offline backup database" in result.stderr
    assert "已移除未完成副本" in result.stderr
    for suffix in ("", "-journal", "-wal", "-shm"):
        assert not (tmp_path / ("result.db" + suffix)).exists()
