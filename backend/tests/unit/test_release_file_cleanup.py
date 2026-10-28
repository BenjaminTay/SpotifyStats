import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "deploy/production/cleanup-release-files.py"
SPEC = importlib.util.spec_from_file_location("release_cleanup", SOURCE)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
NOW = 1_800_000_000


def setup_root(tmp_path):
    for name in ("backups", "releases/state", "releases/locks", "releases/incoming"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    state = {"schema_version": 1}
    for slot, tag in (("current", "a" * 40), ("previous", "b" * 40)):
        archive = tmp_path / f"releases/{slot}.tar"
        archive.write_bytes(b"image")
        state[slot] = {"revision": tag, "archive_path": str(archive)}
    (tmp_path / "releases/state/retention.json").write_text(json.dumps(state))
    (tmp_path / ".current-image-tag").write_text("a" * 40)
    for i, char in enumerate("abcdef"):
        write(tmp_path, f"spotify-stats-pre-release-{char * 12}-202610{20 - i:02}T000000Z.db")
    return tmp_path


def write(root, name, age=3 * 86400):
    p = root / "backups" / name
    p.write_bytes(b"backup")
    os.utime(p, (NOW - age, NOW - age))
    return p


def test_bounded_versions_preserve_manual_weekly_and_recent_preparations(tmp_path):
    root = setup_root(tmp_path)
    weekly = write(root, "spotify-stats-20260922T192402Z.db")
    manual = write(root, "spotify-stats-pre-import-20260922T192402Z.db")
    resume = write(root, "music-search-resume.db")
    old_manifest = write(root, f"billboard-{'f' * 40}.json")
    new_manifest = write(root, f"music-detail-{'9' * 40}.json", age=60)
    retained_manifest = write(root, f"versus-ranks-{'b' * 40}.json")
    outside = tmp_path / "outside"
    outside.write_bytes(b"do not delete")
    (root / "backups" / f"billboard-{'8' * 40}.json").symlink_to(outside)
    result = module.plan(root, "a" * 40, NOW)
    paths = {row["path"] for row in result["files"]}
    assert result["keep_release_prefixes"] == [char * 12 for char in "ab"]
    assert str(old_manifest) in paths
    assert all(
        str(p) not in paths for p in (weekly, manual, resume, new_manifest, retained_manifest)
    )
    assert len(paths) == 7
    assert old_manifest.exists()  # Preview never mutates.


def test_apply_skips_open_files_and_nonempty_wal(tmp_path, monkeypatch):
    root = setup_root(tmp_path)
    busy = write(root, f"billboard-{'1' * 40}.json")
    wal_db = write(root, "spotify-stats-pre-release-eeeeeeeeeeee-20261001T000000Z.db")
    Path(str(wal_db) + "-wal").write_bytes(b"pending")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kw: SimpleNamespace(returncode=0 if str(busy) in args else 1),
    )
    result = module.apply_plan(module.plan(root, "a" * 40, NOW))
    assert str(busy) in result["skipped"] and str(wal_db) in result["skipped"]
    assert busy.exists() and wal_db.exists()
    assert result["deleted"]


def test_refuses_stale_state_and_changed_file(tmp_path, monkeypatch):
    root = setup_root(tmp_path)
    with pytest.raises(ValueError, match="does not match"):
        module.plan(root, "f" * 40, NOW)
    result = module.plan(root, "a" * 40, NOW)
    Path(result["files"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        module.apply_plan(result)


def test_old_incoming_archive_is_pruned_but_records_and_cas_stay(tmp_path):
    root = setup_root(tmp_path)
    p = root / "releases/incoming" / ("f" * 40) / "release/docker-save.tar"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"old upload")
    os.utime(p, (NOW - 3 * 86400, NOW - 3 * 86400))
    result = module.plan(root, "a" * 40, NOW)
    assert str(p) in {row["path"] for row in result["files"]}
    assert all(
        "/records/" not in row["path"] and "/blobs/" not in row["path"] for row in result["files"]
    )


def test_missing_recovery_archive_refuses_cleanup(tmp_path):
    root = setup_root(tmp_path)
    (root / "releases/previous.tar").unlink()
    with pytest.raises(ValueError, match="archive is missing"):
        module.plan(root, "a" * 40, NOW)


def test_workflow_packages_helper_and_cleans_only_after_success():
    root = SOURCE.parents[2]
    workflow = (root / ".github/workflows/production-release.yml").read_text()
    assert "activate-release-images.sh cleanup-release-files.py README.md" in workflow
    assert workflow.index("Clean obsolete generated release files") > workflow.index(
        "Activate CAS current and previous retention after successful deploy"
    )
    assert "cleanup-release-files.py --revision '$GITHUB_SHA' --apply" in workflow
    for name in ("backup.sh", "install-backup-timer.sh", ".env.example"):
        assert f'      - "deploy/production/{name}"' in workflow.split("permissions:")[0]


def marked_tmp(root, name, age=3 * 86400):
    folder = root / "backups" / name / "tmp"
    folder.mkdir(parents=True)
    candidate = folder / "candidate.db"
    candidate.write_bytes(b"temporary")
    os.utime(candidate, (NOW - 4 * 86400, NOW - 4 * 86400))
    marker = folder / ".cleanup-ready"
    marker.touch()
    os.utime(marker, (NOW - age, NOW - age))
    return candidate, marker


def test_completed_tmp_is_pruned_without_touching_recovery_and_logs(tmp_path):
    root = setup_root(tmp_path)
    candidate, marker = marked_tmp(root, "import-example")
    recovery = root / "backups/import-example/originals-20261001"
    recovery.mkdir()
    original = recovery / "spotify_stats.db"
    original.write_bytes(b"recovery")
    log = root / "backups/import-example/acceptance.json"
    log.write_text("{}")
    result = module.plan(root, "a" * 40, NOW)
    paths = {row["path"] for row in result["files"]}
    assert str(candidate) in paths
    assert all(str(p) not in paths for p in (marker, original, log))


def test_tmp_sqlite_sidecars_are_removed_with_database_once(tmp_path, monkeypatch):
    root = setup_root(tmp_path)
    candidate, marker = marked_tmp(root, "operation")
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(candidate) + suffix)
        sidecar.touch()
        os.utime(sidecar, (NOW - 4 * 86400, NOW - 4 * 86400))
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kw: SimpleNamespace(returncode=1))
    result = module.apply_plan(module.plan(root, "a" * 40, NOW))
    assert str(candidate) in {row["path"] for row in result["deleted"]}
    assert not candidate.exists() and marker.exists()
    assert not Path(str(candidate) + "-shm").exists()


@pytest.mark.parametrize("condition", ["fresh", "unmarked", "modified", "symlink", "recovery"])
def test_unsafe_or_unfinished_tmp_is_kept(tmp_path, condition):
    root = setup_root(tmp_path)
    candidate, marker = marked_tmp(root, "operation", age=60 if condition == "fresh" else 3 * 86400)
    if condition == "unmarked":
        marker.unlink()
    elif condition == "modified":
        os.utime(candidate, (NOW, NOW))
    elif condition == "symlink":
        (candidate.parent / "external").symlink_to(tmp_path / "outside")
    elif condition == "recovery":
        (candidate.parent / "originals-backup").mkdir()
    paths = {row["path"] for row in module.plan(root, "a" * 40, NOW)["files"]}
    assert str(candidate) not in paths


def test_release_scratch_expires_even_for_current_previous(tmp_path):
    root = setup_root(tmp_path)
    old = write(root, f"spotify-stats-pre-release-{'a' * 12}-20261001T000000Z.db")
    duplicate = write(root, f"spotify-stats-pre-release-{'a' * 12}-20261020T000000Z.db.gz")
    analysis = write(root, f"analysis-pre-release-{'a' * 12}-20261020T000000Z.db")
    recent = write(root, f"spotify-stats-pre-release-{'a' * 12}-20261002T000000Z.db", age=60)
    result = module.plan(root, "a" * 40, NOW)
    paths = {row["path"] for row in result["files"]}
    assert str(old) in paths and str(duplicate) in paths
    assert str(analysis) in paths
    assert str(recent) not in paths
    analysis.rename(analysis.with_name(analysis.name.replace("20261020", "20261019")))
    module.plan(root, "a" * 40, NOW)


def test_completed_recovery_expires_after_grace_for_all_versions(tmp_path):
    root = setup_root(tmp_path)
    files = {}
    for char in "abc":
        folder = root / "backups" / f"operation-{char}"
        original = folder / "originals-example/spotify_stats.db"
        original.parent.mkdir(parents=True)
        original.write_bytes(b"original")
        os.utime(original, (NOW - 4 * 86400, NOW - 4 * 86400))
        marker = folder / ".recovery-revision"
        marker.write_text(char * 40)
        os.utime(marker, (NOW - 3 * 86400, NOW - 3 * 86400))
        (folder / "acceptance.json").write_text("{}")
        files[char] = original
    paths = {row["path"] for row in module.plan(root, "a" * 40, NOW)["files"]}
    assert str(files["a"]) in paths and str(files["b"]) in paths
    assert str(files["c"]) in paths
    assert not any(path.endswith("acceptance.json") for path in paths)
    marker = files["c"].parent.parent / ".recovery-revision"
    os.utime(marker, (NOW - 60, NOW - 60))
    assert str(files["c"]) not in {row["path"] for row in module.plan(root, "a" * 40, NOW)["files"]}
    os.utime(marker, (NOW - 3 * 86400, NOW - 3 * 86400))
    os.utime(files["c"], (NOW, NOW))
    assert str(files["c"]) not in {row["path"] for row in module.plan(root, "a" * 40, NOW)["files"]}


def test_registered_recovery_refuses_invalid_revision_and_skips_symlinks(tmp_path):
    root = setup_root(tmp_path)
    operation = root / "backups/old-operation"
    operation.mkdir()
    marker = operation / ".recovery-revision"
    marker.write_text("invalid")
    with pytest.raises(ValueError, match="Invalid recovery revision"):
        module.plan(root, "a" * 40, NOW)
    marker.write_text("f" * 40)
    os.utime(marker, (NOW - 3 * 86400, NOW - 3 * 86400))
    original = operation / "originals-example"
    original.mkdir()
    (original / "external").symlink_to(tmp_path / "outside")
    candidate = original / "spotify_stats.db"
    candidate.write_bytes(b"recovery")
    os.utime(candidate, (NOW - 4 * 86400, NOW - 4 * 86400))
    assert str(candidate) not in {row["path"] for row in module.plan(root, "a" * 40, NOW)["files"]}


def test_scheduled_rotation_keeps_two_compressed_ordinary_backups_only(tmp_path):
    script = tmp_path / "backup.sh"
    shutil.copyfile(SOURCE.parent / "backup.sh", script)
    (tmp_path / ".env").touch()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    names = [
        "spotify-stats-20260901T000000Z.db",
        "spotify-stats-20260902T000000Z.db.gz",
        "spotify-stats-pre-import-20260901T000000Z.db.gz",
        "spotify-stats-20261020T000000Z.db.gz",
    ]
    for name in names:
        p = backup_dir / name
        p.write_bytes(b"fixture")
        age = 1 if "20261020" in name else 40
        timestamp = time.time() - age * 86400
        os.utime(p, (timestamp, timestamp))
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(
        '#!/bin/bash\nif [[ "$*" == *"ps --status running --services"* ]]; then\n'
        'echo backend\nelse\ncat >/dev/null\nlast="${!#}"\ntouch "backups/${last##*/}"\nfi\n'
    )
    docker.chmod(0o755)
    subprocess.run(
        ["bash", str(script)],
        env={**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]},
        check=True,
        capture_output=True,
    )
    assert not (backup_dir / names[0]).exists() and not (backup_dir / names[1]).exists()
    assert (backup_dir / names[2]).exists() and (backup_dir / names[3]).exists()
    assert len(list(backup_dir.glob("*.db.gz"))) == 3
    assert not list(backup_dir.glob("*.db"))


def test_empty_and_partially_reset_database_backup_history_are_valid(tmp_path):
    root = setup_root(tmp_path)
    for p in (root / "backups").glob("*.db"):
        p.unlink()
    assert module.plan(root, "a" * 40, NOW)["files"] == []
    recent = write(root, f"spotify-stats-pre-release-{'a' * 12}-20261020T000000Z.db", age=60)
    assert module.plan(root, "a" * 40, NOW)["files"] == []
    assert recent.exists()


def test_new_release_backup_with_preserved_old_mtime_gets_full_grace(tmp_path):
    root = setup_root(tmp_path)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(NOW - 60))
    p = write(root, f"spotify-stats-pre-release-{'a' * 12}-{stamp}.db", age=10 * 86400)
    assert str(p) not in {row["path"] for row in module.plan(root, "a" * 40, NOW)["files"]}


def test_single_operation_marker_cleans_scratch_and_recovery_but_keeps_logs(tmp_path):
    root = setup_root(tmp_path)
    candidate, legacy_marker = marked_tmp(root, "finished")
    legacy_marker.unlink()
    operation = candidate.parent.parent
    marker = operation / ".cleanup-ready"
    marker.touch()
    os.utime(marker, (NOW - 3 * 86400, NOW - 3 * 86400))
    code = operation / "tmp/code/backend/domains/agent_runtime/recovery.py"
    original = operation / "originals-example/spotify_stats.db"
    for p in (code, original):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fixture")
        os.utime(p, (NOW - 4 * 86400, NOW - 4 * 86400))
    log = operation / "acceptance.json"
    log.write_text("{}")
    paths = {row["path"] for row in module.plan(root, "a" * 40, NOW)["files"]}
    assert all(str(p) in paths for p in (candidate, code, original))
    assert str(log) not in paths and str(marker) not in paths


def test_daily_command_defaults_to_installed_revision_and_runs_without_backup_history(tmp_path):
    root = setup_root(tmp_path)
    for p in (root / "backups").glob("*.db"):
        p.unlink()
    result = subprocess.run(
        [sys.executable, str(SOURCE), "--deploy-dir", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["files"] == []


def test_daily_timer_reuses_one_service_and_checks_weekly_backup_only(tmp_path):
    installer = (SOURCE.parent / "install-backup-timer.sh").read_text()
    assert "OnCalendar=*-*-* 03:20:00" in installer
    assert (
        "ExecStartPre=+/usr/bin/python3 $DEPLOY_DIR/cleanup-release-files.py --apply" in installer
    )
    assert "ExecStart=$DEPLOY_DIR/backup.sh --scheduled" in installer
    script = tmp_path / "backup.sh"
    shutil.copyfile(SOURCE.parent / "backup.sh", script)
    (tmp_path / ".env").touch()
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "spotify-stats-20261028T000000Z.db.gz").touch()
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text("#!/bin/sh\nexit 77\n")
    docker.chmod(0o755)
    result = subprocess.run(
        ["bash", str(script), "--scheduled"],
        env={**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0  # No Docker call when this week's snapshot exists.
    old = time.time() - 8 * 86400
    snapshot = next(backups.iterdir())
    os.utime(snapshot, (old, old))
    result = subprocess.run(
        ["bash", str(script), "--scheduled"],
        env={**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
    )
    assert result.returncode != 0  # A missed week attempts Docker rather than skipping.
