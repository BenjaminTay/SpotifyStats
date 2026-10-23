"""Keep current/previous release recovery and expire explicitly completed operations."""

import argparse
import fcntl
import json
import re
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path

BACKUP = re.compile(
    r"(?:spotify-stats|analysis|billboard)-pre-release-([0-9a-f]{12})-"
    r"([0-9]{8}T[0-9]{6}Z)\.db(?:\.gz)?"
)
MANIFEST = re.compile(r"(?:billboard|music-detail|versus-ranks)-([0-9a-f]{40})\.json")
GRACE_SECONDS = 48 * 3600


def completed_temporary_files(backups, now):
    """Operations opt in by marking only their disposable tmp/ directory as ready."""
    candidates = []
    for operation in backups.iterdir():
        if operation.is_symlink() or not operation.is_dir():
            continue
        temporary = operation / "tmp"
        marker = temporary / ".cleanup-ready"
        if (
            temporary.is_symlink()
            or not temporary.is_dir()
            or marker.is_symlink()
            or not marker.is_file()
        ):
            continue
        marked_at = marker.stat().st_mtime
        if now - marked_at < GRACE_SECONDS:
            continue
        tree = list(temporary.rglob("*"))
        # Refuse mixed recovery directories or a directory reopened after completion.
        if any(
            p.is_symlink()
            or any(
                part.startswith(("originals", "recovery"))
                for part in p.relative_to(temporary).parts
            )
            for p in tree
        ):
            continue
        files = [p for p in tree if p.is_file() and p != marker]
        if any(p.stat().st_mtime > marked_at for p in files):
            continue
        candidates.extend(p for p in files if not p.name.endswith(("-wal", "-shm")))
    return candidates


def retired_recovery_files(backups, retained, now):
    """An explicit revision marker lets old joint recovery points follow retention."""
    candidates = []
    for operation in backups.iterdir():
        if operation.is_symlink() or not operation.is_dir():
            continue
        marker = operation / ".recovery-revision"
        if marker.is_symlink() or not marker.is_file():
            continue
        revision = marker.read_text().strip()
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(f"Invalid recovery revision: {marker}")
        marked_at = marker.stat().st_mtime
        if revision[:12] in retained or now - marked_at < GRACE_SECONDS:
            continue
        for folder in operation.iterdir():
            if folder.name != "recovery" and not folder.name.startswith("originals-"):
                continue
            if folder.is_symlink() or not folder.is_dir():
                continue
            tree = list(folder.rglob("*"))
            if any(p.is_symlink() for p in tree):
                continue
            files = [p for p in tree if p.is_file()]
            if any(p.stat().st_mtime > marked_at for p in files):
                continue
            candidates.extend(p for p in files if not p.name.endswith(("-wal", "-shm")))
    return candidates


def plan(root, revision, now=None):
    now = time.time() if now is None else now
    backups = root / "backups"
    releases = root / "releases"
    for directory in (root, backups, releases, releases / "state"):
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Unsafe directory: {directory}")
    state_path = releases / "state/retention.json"
    if state_path.is_symlink():
        raise ValueError("Unsafe retention state")
    state = json.loads(state_path.read_text())
    if state.get("schema_version") != 1 or state["current"]["revision"] != revision:
        raise ValueError("Current release does not match completed deployment")
    if (root / ".current-image-tag").read_text().strip() != revision:
        raise ValueError("Deployment marker differs from retention state")
    protected = set()
    retained_backups = set()
    for slot in ("current", "previous"):
        record = state.get(slot)
        if not record:
            continue
        tag = record["revision"]
        if not re.fullmatch(r"[0-9a-f]{40}", tag):
            raise ValueError("Invalid retained revision")
        if not Path(record["archive_path"]).is_file():
            raise ValueError("Retained image archive is missing")
        protected.add(tag[:12])
        main_backups = [
            p
            for p in backups.glob(f"spotify-stats-pre-release-{tag[:12]}-*.db*")
            if p.is_file() and not p.is_symlink() and BACKUP.fullmatch(p.name)
        ]
        if not main_backups:
            raise ValueError("Retained database backup is missing")
        stamp = max(BACKUP.fullmatch(p.name)[2] for p in main_backups)
        for family in ("spotify-stats", "analysis", "billboard"):
            copies = [
                p
                for p in backups.glob(f"{family}-pre-release-{tag[:12]}-{stamp}.db*")
                if p.is_file() and not p.is_symlink() and BACKUP.fullmatch(p.name)
            ]
            if copies:
                retained_backups.add(min(copies, key=lambda p: p.name.endswith(".gz")))
            elif any(backups.glob(f"{family}-pre-release-{tag[:12]}-*.db*")):
                raise ValueError("Latest retained backup set is incomplete")
    keep = set(protected)
    candidates = []
    for p in backups.iterdir():
        if BACKUP.fullmatch(p.name) and p not in retained_backups:
            candidates.append(p)
        match = MANIFEST.fullmatch(p.name)
        if match and match[1][:12] not in keep:
            candidates.append(p)
    incoming = releases / "incoming"
    if incoming.is_dir() and not incoming.is_symlink():
        for folder in incoming.iterdir():
            if (
                re.fullmatch(r"[0-9a-f]{40}", folder.name)
                and not folder.is_symlink()
                and folder.name[:12] not in keep
            ):
                for mode in ("release", "smoke"):
                    if not (folder / mode).is_symlink():
                        candidates.append(folder / mode / "docker-save.tar")
    candidates.extend(completed_temporary_files(backups, now))
    candidates.extend(retired_recovery_files(backups, keep, now))
    files = []
    for p in sorted(candidates):
        if p.is_symlink() or not p.is_file():
            continue
        s = p.stat()
        if now - s.st_mtime < GRACE_SECONDS:
            continue
        files.append(
            {"path": str(p), "bytes": s.st_size, "mtime_ns": s.st_mtime_ns, "inode": s.st_ino}
        )
    return {
        "revision": revision,
        "keep_release_prefixes": sorted(keep),
        "retained_backup_files": sorted(str(p) for p in retained_backups),
        "files": files,
        "bytes": sum(row["bytes"] for row in files),
    }


def apply_plan(result):
    deleted = []
    skipped = []
    for row in result["files"]:
        p = Path(row["path"])
        s = p.lstat()
        if p.is_symlink() or (s.st_size, s.st_mtime_ns, s.st_ino) != (
            row["bytes"],
            row["mtime_ns"],
            row["inode"],
        ):
            raise ValueError(f"File changed after preview: {p}")
        sidecars = [Path(str(p) + suffix) for suffix in ("-wal", "-shm")]
        if any(q.is_symlink() for q in sidecars) or (
            sidecars[0].exists() and sidecars[0].stat().st_size
        ):
            skipped.append(str(p))
            continue
        opened = subprocess.run(
            ["fuser", "--", str(p), *[str(q) for q in sidecars if q.exists()]],
            capture_output=True,
        )
        if opened.returncode != 1:
            skipped.append(str(p))
            continue
        p.unlink()
        for q in sidecars:
            q.unlink(missing_ok=True)
        deleted.append(row)
    return {
        "deleted": deleted,
        "skipped": skipped,
        "bytes_released": sum(row["bytes"] for row in deleted),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy-dir", type=Path, default=Path(__file__).absolute().parent)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--apply", action="store_true", help="Delete; default is preview only")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("revision must be a full Git SHA")
    root = args.deploy_dir.absolute()
    with ExitStack() as stack:
        lock_paths = [root / "releases/locks" / name for name in ("cas.lock", "retention.lock")]
        lock_paths += [
            root / "backups/maintenance.lock",
            root / "backups/.versus-release-cycle-maintenance.lock",
        ]
        for path in lock_paths:
            lock = stack.enter_context(path.open("a+b"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = plan(root, args.revision)
        if args.apply:
            result["execution"] = apply_plan(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
