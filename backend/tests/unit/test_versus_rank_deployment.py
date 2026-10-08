"""Deployment orchestration keeps rank reads and installation out of cold builds."""

from __future__ import annotations

import os
import subprocess
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
