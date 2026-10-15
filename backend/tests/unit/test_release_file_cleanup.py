import importlib.util
import json
import os
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
    assert result["keep_release_prefixes"] == [char * 12 for char in "abcd"]
    assert str(old_manifest) in paths
    assert all(
        str(p) not in paths for p in (weekly, manual, resume, new_manifest, retained_manifest)
    )
    assert len(paths) == 3
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
