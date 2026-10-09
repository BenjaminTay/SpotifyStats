"""Prepared detail facts are installed on stage before database promotion."""

import hashlib
import json
import os
import shlex
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from backend.tests.unit import test_versus_rank_context

base_isolated = test_versus_rank_context.base_isolated
rank_isolated = test_versus_rank_context.isolated

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


def test_maintenance_containers_use_host_owner_and_only_closed_stage_reads(tmp_path):
    result = run_helper(
        tmp_path,
        f"""
docker() {{ {shlex.quote(sys.executable)} -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$@"; }}
music_detail_command image validate "$DEPLOY_DIR/spotify_stats.db" "$DEPLOY_DIR/manifest.json"
music_detail_command image import "$DEPLOY_DIR/spotify_stats.db" "$DEPLOY_DIR/manifest.json"
music_detail_command image verify "$DEPLOY_DIR/spotify_stats.db"
billboard_release_command image import "$DEPLOY_DIR/spotify_stats.db" "$DEPLOY_DIR/cache.db" "$DEPLOY_DIR/manifest.json"
billboard_release_command image verify "$DEPLOY_DIR/spotify_stats.db" "$DEPLOY_DIR/cache.db"
checkpoint_live_database image
source {ROOT / "deploy/production/versus-rank-release.sh"}
versus_rank_command image install "$DEPLOY_DIR/spotify_stats.db" "$DEPLOY_DIR/manifest.json" abcdef
""",
    )
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in result.stdout.splitlines()]
    for args in calls[:5]:
        assert args[args.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"
    assert "--user" not in calls[5] and "--user" not in calls[6]
    assert "--closed-source" in calls[0] and "--closed-source" in calls[2]
    assert "--closed-source" not in calls[1]
    for args in calls[3:5]:
        assert "--closed-source" in args
        assert any("dst=/app/data/spotify_stats.db,readonly" in item for item in args)
    live_verify = (
        HELPER.read_text()
        .split("verify_running_music_detail() {", 1)[1]
        .split("billboard_release_enabled=", 1)[0]
    )
    assert "--closed-source" not in live_verify


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


@pytest.mark.parametrize("remaining_wal", [None, "spotify_stats.db", "billboard_cache.db"])
def test_stopped_gate_reads_actual_closed_wal_headers_and_rejects_any_remaining_wal(
    tmp_path, remaining_wal
):
    # The ready callback is a fixture; the shipped SQLite boundary runs intact.
    # Production old-code exact publications are checked by the owned rehearsal.
    files = []
    for name in ("spotify_stats.db", "billboard_cache.db", "analysis_cache.db"):
        path = tmp_path / name
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL").close()
        conn.execute("CREATE TABLE facts(value INTEGER)").close()
        conn.execute("INSERT INTO facts VALUES (7)").close()
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").close()
        conn.close()
        Path(str(path) + "-wal").unlink(missing_ok=True)
        Path(str(path) + "-shm").unlink(missing_ok=True)
        files.append(path)
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in files]
    if remaining_wal:
        (tmp_path / (remaining_wal + "-wal")).touch()
    code = (
        HELPER.read_text()
        .split("verify_stopped_billboard_exact() {", 1)[1]
        .split("python -c '", 1)[1]
        .split("'\n}", 1)[0]
        .replace("/app/data", str(tmp_path))
    )
    fixture_code = f"""
import sys, types, sqlite3
from pathlib import Path
fixture_guard_state = {{'guard': False}}
for name in ('backend','backend.core','backend.services','backend.core.access_surface','backend.services.billboard_snapshot_service'):
    sys.modules[name] = types.ModuleType(name)
def guard(value): fixture_guard_state['guard'] = value
def ready():
    assert fixture_guard_state['guard']
    for path in {str([str(path) for path in files])}:
        conn = sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)
        assert conn.execute('SELECT value FROM facts').fetchone()[0] == 7
        assert conn.execute('PRAGMA query_only').fetchone()[0] == 1
        conn.close()
    return True
sys.modules['backend.core.access_surface'].set_public_readonly_db_guard = guard
sys.modules['backend.services.billboard_snapshot_service'].billboard_default_snapshots_ready = ready
"""
    result = subprocess.run(
        [sys.executable, "-c", fixture_code + code], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == (0 if remaining_wal is None else 1), result.stderr
    if remaining_wal:
        assert "requires no WAL" in result.stderr
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in files] == before
    assert not list(tmp_path.glob("*-shm"))


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


def _closed_checkpoint(path):
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        assert connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
    # These are owned fixture files; every connection above has closed. Retain
    # the real WAL-mode header, but never let the stopped gate ignore a WAL.
    for suffix in ("-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    assert path.read_bytes()[18:20] == b"\x02\x02"


def _closed_publications(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        return conn.execute("SELECT * FROM analysis_snapshots ORDER BY publication_id").fetchall()


def _closed_file_states(data):
    result = {}
    for path in data.iterdir():
        stat = path.stat()
        result[path.name] = (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return result


@pytest.fixture
def actual_stopped_ranks(rank_isolated, monkeypatch):
    from backend.core import config, db
    from backend.services import analysis_snapshot_store as store
    from backend.services import versus_rank_context_service as ranks

    original, owned = rank_isolated
    data = owned / "data"
    data.mkdir()
    main = data / "spotify_stats.db"
    _closed_checkpoint(original)
    original.rename(main)
    analysis = data / "analysis_cache.db"
    billboard = data / "billboard_cache.db"
    monkeypatch.setattr(db, "DB_PATH", str(main))
    monkeypatch.setattr(config, "SPOTIFY_STATS_ANALYSIS_CACHE_PATH", str(analysis))
    with closing(db.get_db(readonly=True)) as conn:
        variants = ranks.default_configurations(conn)
        for filters in variants:
            ranks.ensure(conn, filters)
        expected = [ranks.read(conn, filters)[1] for filters in variants]
    assert len(expected) == 4 and len({row["request_key"] for row in expected}) == 4
    # Use the real generic store, retaining unrelated publication payloads and
    # every metadata column rather than recreating only the rank family.
    for family in ("fixture_archive", "fixture_sidebar"):
        store.publish(family, family + "-key", "side-source", "side-v1", {"fact": family})
    with closing(sqlite3.connect(billboard)) as conn:
        conn.execute("CREATE TABLE fixture_billboard(value INTEGER)")
        conn.execute("INSERT INTO fixture_billboard VALUES (7)")
        conn.commit()
    for path in (main, analysis, billboard):
        _closed_checkpoint(path)
    code = (
        HELPER.read_text()
        .split("verify_stopped_billboard_exact() {", 1)[1]
        .split("python -c '", 1)[1]
        .split("'\n}", 1)[0]
        .replace("/app/data", str(data))
    )
    gate = owned / "actual-stopped-gate.py"
    # Only the Billboard ready callback is a fixture. The shipped stopped
    # SQLite/stat fence and real default configurations/context/rank reads run
    # intact, in a fresh process with the actual CLI capability present.
    gate.write_text(
        f"""
import sys
sys.path.insert(0, {str(ROOT)!r})
from backend.core.access_surface import public_readonly_db_guard_active
from backend.services import billboard_snapshot_service as billboard

def fixture_billboard_ready():
    import sqlite3
    from pathlib import Path
    assert public_readonly_db_guard_active()
    connection = sqlite3.connect(Path({str(billboard)!r}).as_uri() + '?mode=ro', uri=True)
    try:
        assert connection.execute('PRAGMA query_only').fetchone()[0] == 1
        assert connection.execute('SELECT value FROM fixture_billboard').fetchone()[0] == 7
    finally:
        connection.close()
    return True
billboard.billboard_default_snapshots_ready = fixture_billboard_ready
"""
        + code
        + "\nprint('actual-default-ranks-ready:' + str(len(snapshots)))\n"
    )
    env = {
        **os.environ,
        "SPOTIFY_STATS_DB_PATH": str(main),
        "SPOTIFY_STATS_ANALYSIS_CACHE_PATH": str(analysis),
        "SPOTIFY_STATS_BILLBOARD_CACHE_PATH": str(billboard),
    }
    yield dict(
        owned=owned,
        data=data,
        main=main,
        analysis=analysis,
        billboard=billboard,
        gate=gate,
        env=env,
        expected=expected,
        all_publications=_closed_publications(analysis),
    )


def _actual_stopped_gate(source):
    return subprocess.run(
        [sys.executable, str(source["gate"])],
        cwd=ROOT,
        env=source["env"],
        capture_output=True,
        text=True,
    )


def test_original_inode_and_complete_analysis_restore_all_actual_default_ranks(
    actual_stopped_ranks,
):
    source = actual_stopped_ranks
    owned, main, analysis = source["owned"], source["main"], source["analysis"]
    original_inode = main.stat().st_ino
    original_main_hash = hashlib.sha256(main.read_bytes()).hexdigest()
    adapter = owned / "actual-online-backup.py"
    deploy = (ROOT / "deploy/production/deploy.sh").read_text()
    backup_code = (
        deploy.split("create_offline_backup() {", 1)[1]
        .split("python -c '", 1)[1]
        .split('\' "$database_name"', 1)[0]
        .replace("/tmp/offline-source", str(owned / "owned-backup-reader"))
        .replace("/tmp/spotify_stats.backup.db", str(owned / "owned-backup-output.db"))
        .replace("/source", str(source["data"]))
    )
    # The shipped Linux image (SQLite 3.46) can back up a closed WAL-header
    # copy without auxiliary files. Local SQLite 3.51 needs a WAL/SHM reader
    # condition: establish it only on this adapter's disposable internal copy,
    # retaining the original ordinary-RO connection and real Online Backup.
    # The mounted fixture source stays closed and has no auxiliary files.
    backup_code = backup_code.replace(
        "source = sqlite3.connect(\n",
        """fixture_reader_holder = None
if sqlite3.sqlite_version_info >= (3, 51, 0):
    fixture_reader_holder = sqlite3.connect(source_dir / database_name)
    fixture_reader_holder.execute("PRAGMA query_only=ON")
    fixture_reader_holder.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
source = sqlite3.connect(
""",
        1,
    ).replace(
        "source.close()\n",
        "source.close()\nif fixture_reader_holder is not None:\n    fixture_reader_holder.close()\n",
        1,
    )
    adapter.write_text(backup_code)
    replace = (
        "replace_live_database() {"
        + deploy.split("replace_live_database() {", 1)[1].split("wait_until_healthy() {", 1)[0]
    )
    staged = owned / "candidate.db"
    staged.write_bytes(main.read_bytes())
    with closing(sqlite3.connect(staged)) as conn:
        conn.execute(
            "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
        )
        conn.commit()
    _closed_checkpoint(staged)
    script = owned / "restore-all.sh"
    script.write_text(
        f"""set -Eeuo pipefail
DEPLOY_DIR={shlex.quote(str(owned))}
NEW_TAG=fixture
release_stamp=actual
mkdir -p "$DEPLOY_DIR/backups" "$DEPLOY_DIR/kept"
source {shlex.quote(str(HELPER))}
source {shlex.quote(str(ROOT / "deploy/production/versus-rank-release.sh"))}
rollback_live_inode_dir="$DEPLOY_DIR/kept"
rollback_live_inode_path="$rollback_live_inode_dir/spotify_stats.db"
ln "$DEPLOY_DIR/data/spotify_stats.db" "$rollback_live_inode_path"
versus_rank_enabled=true
create_offline_backup() {{ {shlex.quote(sys.executable)} {shlex.quote(str(adapter))} "$3" > "$2"; }}
backup_versus_rank_release fixture-image
{replace}
replace_live_database "$DEPLOY_DIR/candidate.db"
[[ ! "$DEPLOY_DIR/data/spotify_stats.db" -ef "$rollback_live_inode_path" ]]
printf 'candidate analysis replaced every family' > "$DEPLOY_DIR/data/analysis_cache.db"
versus_rank_sidecar_changed=true
restore_live_database_inode
restore_versus_rank_release
"""
    )
    restored = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert restored.returncode == 0, restored.stderr
    assert main.stat().st_ino == original_inode
    assert hashlib.sha256(main.read_bytes()).hexdigest() == original_main_hash
    assert _closed_publications(analysis) == source["all_publications"]
    assert {row[1] for row in source["all_publications"]} == {
        "entity_rank_context",
        "fixture_archive",
        "fixture_sidebar",
    }
    before = _closed_file_states(source["data"])
    verified = _actual_stopped_gate(source)
    assert verified.returncode == 0, verified.stderr
    assert verified.stdout.strip() == "actual-default-ranks-ready:4"
    assert _closed_file_states(source["data"]) == before


@pytest.mark.parametrize("fault", ["missing_rank", "corrupt_rank", "wrong_main_inode"])
def test_stopped_gate_rejects_actual_rank_or_main_identity_failure(actual_stopped_ranks, fault):
    source = actual_stopped_ranks
    main, analysis = source["main"], source["analysis"]
    if fault == "wrong_main_inode":
        old_inode = main.stat().st_ino
        replacement = source["owned"] / "same-facts-new-inode.db"
        replacement.write_bytes(main.read_bytes())
        replacement.replace(main)
        assert main.stat().st_ino != old_inode
    else:
        with closing(sqlite3.connect(analysis)) as conn:
            predicate = "WHERE publication_id=(SELECT MIN(publication_id) FROM analysis_snapshots WHERE family='entity_rank_context')"
            if fault == "missing_rank":
                conn.execute("DELETE FROM analysis_snapshots " + predicate)
            else:
                conn.execute("UPDATE analysis_snapshots SET payload=x'00' " + predicate)
            conn.commit()
        _closed_checkpoint(analysis)
    before = _closed_file_states(source["data"])
    result = _actual_stopped_gate(source)
    assert result.returncode != 0
    assert "503" in result.stderr or "not exact-ready" in result.stderr
    assert _closed_file_states(source["data"]) == before
    assert not list(source["data"].glob("*-shm"))


@pytest.mark.parametrize("name", ["spotify_stats.db", "analysis_cache.db", "billboard_cache.db"])
@pytest.mark.parametrize("contents", [b"", b"remaining WAL must never be ignored"])
def test_stopped_actual_rank_gate_rejects_any_wal_without_creating_auxiliary_files(
    actual_stopped_ranks, name, contents
):
    source = actual_stopped_ranks
    (source["data"] / (name + "-wal")).write_bytes(contents)
    before = _closed_file_states(source["data"])
    result = _actual_stopped_gate(source)
    assert result.returncode != 0 and "requires no WAL" in result.stderr
    assert _closed_file_states(source["data"]) == before
    assert not list(source["data"].glob("*-shm"))
