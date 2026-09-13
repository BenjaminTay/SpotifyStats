#!/usr/bin/env python3
"""Hold the host-level lock for one shared full-stack verification stage."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _read_owner(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _parent_exists(parent_pid: int) -> bool:
    try:
        os.kill(parent_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def hold(args: argparse.Namespace) -> int:
    lock_path = Path(args.lock_file)
    metadata_path = Path(args.metadata_file)
    status_path = Path(args.status_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _atomic_json(
                status_path,
                {
                    "status": "blocked",
                    "requested_stage": args.stage,
                    "owner": _read_owner(metadata_path),
                },
            )
            return 3

        holder_pid = os.getpid()
        owner = {
            "run_id": args.run_id,
            "pid": args.parent_pid,
            "holder_pid": holder_pid,
            "worktree": args.worktree,
            "git_sha": args.git_sha or None,
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "stage": args.stage,
        }
        _atomic_json(metadata_path, owner)
        _atomic_json(status_path, {"status": "acquired", "owner": owner})

        stop = False

        def request_stop(_signum: int, _frame: object) -> None:
            nonlocal stop
            stop = True

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        while not stop and _parent_exists(args.parent_pid):
            time.sleep(0.2)

        if (_read_owner(metadata_path) or {}).get("holder_pid") == holder_pid:
            metadata_path.unlink(missing_ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock-file", required=True)
    parser.add_argument("--metadata-file", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--git-sha", default="")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--parent-pid", required=True, type=int)
    return hold(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
