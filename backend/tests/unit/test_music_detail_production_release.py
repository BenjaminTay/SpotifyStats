"""Prepared detail facts are installed on stage before database promotion."""

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "deploy/production/music-detail-release.sh"


def run_helper(tmp_path, body):
    script = tmp_path / "probe.sh"
    script.write_text(f"""set -Eeuo pipefail
DEPLOY_DIR={tmp_path}
NEW_TAG=abcdef
mkdir -p "$DEPLOY_DIR/backups"
source {HELPER}
{body}
""")
    return subprocess.run(["bash", str(script)], capture_output=True, text=True)


def test_billboard_sidecar_is_prepared_on_stage_and_restored_jointly(tmp_path):
    result = run_helper(
        tmp_path,
        """
mkdir -p "$DEPLOY_DIR/data" "$DEPLOY_DIR/stage"
printf 'old' > "$DEPLOY_DIR/data/billboard_cache.db"
printf '{}' > "$DEPLOY_DIR/backups/billboard-abcdef.json"
release_stage_dir="$DEPLOY_DIR/stage"
release_stamp=stamp
target_backend_image=image
music_detail_image_supported() { return 0; }
create_offline_backup() { cp "$DEPLOY_DIR/data/$3" "$2"; }
billboard_release_command() {
  printf '%s\\n' "$2"
  case "$2" in
    verify) [[ "$(cat "$4")" == new ]] ;;
    validate) [[ "$(cat "$DEPLOY_DIR/data/billboard_cache.db")" == old ]] ;;
    import) printf 'new' > "$4" ;;
  esac
}
prepare_billboard_release image "$DEPLOY_DIR/staged.db"
[[ "$(cat "$DEPLOY_DIR/data/billboard_cache.db")" == old ]]
install_billboard_release
[[ "$(cat "$DEPLOY_DIR/data/billboard_cache.db")" == new ]]
restore_billboard_release
[[ "$(cat "$DEPLOY_DIR/data/billboard_cache.db")" == old ]]
""",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["validate", "import", "verify", "import", "verify"]


def test_billboard_gate_precedes_promotion_and_activation():
    deploy = (ROOT / "deploy/production/deploy.sh").read_text()
    assert (
        deploy.index("! prepare_billboard_release")
        < deploy.index('if ! replace_live_database "$staged_database"')
        < deploy.index("if ! install_billboard_release")
        < deploy.index('if ! activate_mode "$target_mode"')
    )
    restore = deploy.split("restore_previous_release() {", 1)[1].split(
        'backend_was_running="false"', 1
    )[0]
    assert (
        restore.index("replace_live_database")
        < restore.index("restore_billboard_release")
        < restore.index("activate_mode")
    )


def test_missing_publication_rejects_without_building_or_promoting(tmp_path):
    result = run_helper(
        tmp_path,
        """
music_detail_image_supported() { return 0; }
music_detail_command() { printf '%s:%s\\n' "$2" "$3"; return 1; }
prepare_music_detail_release image "$DEPLOY_DIR/staged.db"
""",
    )
    assert result.returncode == 1
    assert result.stdout.strip() == f"verify:{tmp_path}/staged.db"
    assert "没有冷建" in result.stderr


def test_manifest_is_validated_installed_and_verified_only_on_stage(tmp_path):
    result = run_helper(
        tmp_path,
        """
touch "$DEPLOY_DIR/backups/music-detail-$NEW_TAG.json"
music_detail_image_supported() { return 0; }
count=0
music_detail_command() {
  printf '%s:%s\\n' "$2" "$3"
  count=$((count+1))
  [[ "$count" -gt 1 ]]
}
prepare_music_detail_release image "$DEPLOY_DIR/staged.db"
""",
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        f"{action}:{tmp_path}/staged.db" for action in ("verify", "validate", "import", "verify")
    ]


def test_old_image_skips_only_when_capability_is_known_absent(tmp_path):
    result = run_helper(
        tmp_path,
        """
music_detail_image_supported() { return 1; }
music_detail_command() { exit 99; }
prepare_music_detail_release old-image "$DEPLOY_DIR/staged.db"
""",
    )
    assert result.returncode == 0
    failed = run_helper(
        tmp_path,
        """
music_detail_image_supported() { return 2; }
prepare_music_detail_release broken-image "$DEPLOY_DIR/staged.db"
""",
    )
    assert failed.returncode == 2


def test_ready_stage_is_reused_without_import(tmp_path):
    result = run_helper(
        tmp_path,
        """
music_detail_image_supported() { return 0; }
music_detail_command() { printf '%s\\n' "$2"; return 0; }
prepare_music_detail_release image "$DEPLOY_DIR/staged.db"
""",
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "verify"
