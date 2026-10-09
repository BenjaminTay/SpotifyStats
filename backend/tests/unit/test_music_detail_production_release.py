"""Prepared detail facts are installed on stage before database promotion."""

import hashlib
import shlex
import sqlite3
import subprocess
import sys
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
        restore.index("restore_live_database_inode")
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


def test_live_database_rollback_restores_original_inode_schema_and_fact_bytes(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    live = data / "spotify_stats.db"
    staged = tmp_path / "staged.db"
    for path, version, value in ((live, 89, "original"), (staged, 90, "candidate")):
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE schema_migrations(version INTEGER)")
            conn.execute("INSERT INTO schema_migrations VALUES (?)", (version,))
            conn.execute("CREATE TABLE plays(value TEXT)")
            conn.execute("INSERT INTO plays VALUES (?)", (value,))
    original_inode = live.stat().st_ino
    original_sha = hashlib.sha256(live.read_bytes()).hexdigest()
    sidecar = data / "billboard_cache.db"
    with sqlite3.connect(sidecar) as conn:
        conn.execute("CREATE TABLE billboard_snapshots(cache_key TEXT, payload TEXT)")
        conn.execute("INSERT INTO billboard_snapshots VALUES (?, 'old-v3')", (str(original_inode),))
    sidecar_sha = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    (tmp_path / "backups").mkdir()
    sidecar_backup = tmp_path / "backups/old-sidecar.db"
    sidecar_backup.write_bytes(sidecar.read_bytes())
    checkpoint = (
        HELPER.read_text()
        .split("checkpoint_live_database() {", 1)[1]
        .split("python -c '", 1)[1]
        .split("' /app/data/spotify_stats.db", 1)[0]
    )
    checkpoint_file = tmp_path / "checkpoint.py"
    checkpoint_file.write_text(checkpoint)
    deploy = (ROOT / "deploy/production/deploy.sh").read_text()
    replace = (
        "replace_live_database() {"
        + deploy.split("replace_live_database() {", 1)[1].split("wait_until_healthy() {", 1)[0]
    )
    result = run_helper(
        tmp_path,
        f"""
rollback_live_inode_dir=""
rollback_live_inode_path=""
release_completed=false
database_promoted=false
billboard_sidecar_changed=true
billboard_sidecar_existed=true
billboard_sidecar_backup="$DEPLOY_DIR/backups/old-sidecar.db"
checkpoint_live_database() {{ {shlex.quote(sys.executable)} {shlex.quote(str(checkpoint_file))} "$DEPLOY_DIR/data/spotify_stats.db"; }}
verify_stopped_billboard_exact() {{ return 0; }}
{replace}
preserve_live_database_inode old-image
[[ "$rollback_live_inode_path" -ef "$DEPLOY_DIR/data/spotify_stats.db" ]]
replace_live_database "$DEPLOY_DIR/staged.db"
printf 'candidate-v4' > "$DEPLOY_DIR/data/billboard_cache.db"
[[ ! "$rollback_live_inode_path" -ef "$DEPLOY_DIR/data/spotify_stats.db" ]]
restore_live_database_inode
restore_billboard_release
cleanup_live_database_inode
[[ ! -e "$rollback_live_inode_dir" ]]
""",
    )
    assert result.returncode == 0, result.stderr
    assert live.stat().st_ino == original_inode
    assert hashlib.sha256(live.read_bytes()).hexdigest() == original_sha
    assert hashlib.sha256(sidecar.read_bytes()).hexdigest() == sidecar_sha
    with sqlite3.connect(sidecar) as conn:
        assert conn.execute("SELECT cache_key,payload FROM billboard_snapshots").fetchone() == (
            str(live.stat().st_ino),
            "old-v3",
        )
    with sqlite3.connect(live) as conn:
        assert conn.execute("SELECT version FROM schema_migrations").fetchone()[0] == 89
        assert conn.execute("SELECT value FROM plays").fetchone()[0] == "original"


@pytest.mark.parametrize("failure", ["checkpoint", "link", "exact_gate"])
def test_original_inode_preservation_fails_closed_before_promotion(tmp_path, failure):
    (tmp_path / "data").mkdir()
    live = tmp_path / "data/spotify_stats.db"
    live.write_bytes(b"original")
    extra = {
        "checkpoint": "checkpoint_live_database() { return 1; }",
        "link": "ln() { return 1; }",
        "exact_gate": "verify_stopped_billboard_exact() { return 1; }",
    }[failure]
    result = run_helper(
        tmp_path,
        f"""
rollback_live_inode_dir=""
rollback_live_inode_path=""
release_completed=false
checkpoint_live_database() {{ return 0; }}
verify_stopped_billboard_exact() {{ return 0; }}
{extra}
if preserve_live_database_inode old-image; then exit 99; fi
cleanup_live_database_inode
[[ "$(cat "$DEPLOY_DIR/data/spotify_stats.db")" == original ]]
""",
    )
    assert result.returncode == 0, result.stderr
    assert live.read_bytes() == b"original"
    assert not list((tmp_path / "data").glob(".rollback-inode.*"))


@pytest.mark.parametrize("completed", [False, True])
def test_cleanup_retains_recoverable_original_on_failure_and_removes_link_on_success(
    tmp_path, completed
):
    (tmp_path / "data").mkdir()
    live = tmp_path / "data/spotify_stats.db"
    live.write_bytes(b"original")
    result = run_helper(
        tmp_path,
        f"""
rollback_live_inode_dir=""
rollback_live_inode_path=""
release_completed=false
checkpoint_live_database() {{ return 0; }}
verify_stopped_billboard_exact() {{ return 0; }}
preserve_live_database_inode old-image
printf 'candidate' > "$DEPLOY_DIR/data/next.db"
mv "$DEPLOY_DIR/data/next.db" "$DEPLOY_DIR/data/spotify_stats.db"
release_completed={str(completed).lower()}
cleanup_live_database_inode
""",
    )
    assert result.returncode == 0, result.stderr
    retained = list((tmp_path / "data").glob(".rollback-inode.*/spotify_stats.db"))
    assert len(retained) == (0 if completed else 1)
    if retained:
        assert retained[0].read_bytes() == b"original"
    assert live.read_bytes() == b"candidate"


def test_old_image_exact_billboard_gate_is_readonly_and_never_builds():
    helper = HELPER.read_text()
    running = helper.split("verify_running_billboard_release() {", 1)[1]
    stopped = helper.split("verify_stopped_billboard_exact() {", 1)[1].split(
        "preserve_live_database_inode() {", 1
    )[0]
    for gate in (running, stopped):
        assert "set_public_readonly_db_guard(True)" in gate
        assert "billboard_default_snapshots_ready()" in gate
        assert "enqueue" not in gate and "force_rebuild" not in gate
    assert "dst=/app/data,readonly" in stopped
    deploy = (ROOT / "deploy/production/deploy.sh").read_text()
    assert deploy.index('if ! preserve_live_database_inode "') < deploy.index(
        'if ! replace_live_database "$staged_database"'
    )
    assert "release_completed=true" in deploy
    restore = deploy.split("restore_previous_release() {", 1)[1].split(
        'backend_was_running="false"', 1
    )[0]
    assert (
        restore.index("restore_billboard_release")
        < restore.index("verify_stopped_billboard_exact")
        < restore.index("activate_mode")
    )


@pytest.mark.parametrize("ready", [False, True])
def test_old_image_running_gate_checks_exact_ready_under_readonly_guard(tmp_path, ready):
    code = (
        HELPER.read_text()
        .split("verify_running_billboard_release() {", 1)[1]
        .split("python -c '", 1)[1]
        .rsplit("'", 1)[0]
    )
    fixture = f"""
import sys, types
state = {{"readonly": False}}
for name in ("backend", "backend.core", "backend.services", "backend.core.access_surface", "backend.services.billboard_snapshot_service"):
    sys.modules[name] = types.ModuleType(name)
def guard(value):
    state["readonly"] = value
def exact_ready():
    assert state["readonly"]
    return {ready}
sys.modules["backend.core.access_surface"].set_public_readonly_db_guard = guard
sys.modules["backend.services.billboard_snapshot_service"].billboard_default_snapshots_ready = exact_ready
"""
    result = subprocess.run(
        [sys.executable, "-c", fixture + code], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == (0 if ready else 1)
    if not ready:
        assert "not exact-ready" in result.stderr
