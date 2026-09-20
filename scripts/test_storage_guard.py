#!/usr/bin/env python3
"""Own, monitor and clean one verification run's temporary files."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

GIB = 1024**3


def tree_bytes(root: Path) -> int:
    total = 0
    for parent, _, files in os.walk(root):
        for name in files:
            try:
                path = Path(parent) / name
                if not path.is_symlink():
                    total += path.stat().st_size
            except FileNotFoundError:
                pass  # A test may finish cleanup during sampling.
    return total


def stop_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # Include descendants left behind after the command itself exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_guarded(command, report: Path, *, max_bytes=2 * GIB, min_free=12 * GIB):
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    owned = Path(tempfile.mkdtemp(prefix="spotifystats-verification-"))
    data = {
        "owned_root": str(owned),
        "max_bytes": max_bytes,
        "min_free_bytes": min_free,
        "peak_bytes": 0,
        "minimum_free_bytes": None,
        "samples": [],
        "stop_reason": None,
    }
    process = None
    received_signal = None

    def interrupted(signum, _frame):
        nonlocal received_signal
        received_signal = signum

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}

    def sample():
        size, free = tree_bytes(owned), shutil.disk_usage(owned).free
        data["samples"].append({"time": time.time(), "bytes": size, "free_bytes": free})
        data["peak_bytes"] = max(data["peak_bytes"], size)
        data["minimum_free_bytes"] = min(data["minimum_free_bytes"] or free, free)
        if size > max_bytes:
            return "temporary_limit_exceeded"
        if free < min_free:
            return "insufficient_free_space"
        if received_signal:
            return f"signal_{received_signal}"
        return None

    code = 1
    try:
        data["stop_reason"] = sample()
        if not data["stop_reason"]:
            pytest_base = owned / "pytest"
            pytest_base.mkdir()
            env = os.environ.copy()
            env.update(
                TMPDIR=str(owned),
                TMP=str(owned),
                TEMP=str(owned),
                SPOTIFY_STATS_STORAGE_GUARDED="1",
                SPOTIFY_STATS_TEST_BASETEMP=str(pytest_base),
            )
            process = subprocess.Popen(command, env=env, start_new_session=True)
            while True:
                data["stop_reason"] = sample()
                if data["stop_reason"]:
                    stop_group(process)
                    break
                status = process.poll()
                if status is not None:
                    code = status
                    break
                # Sampling interval, not a delay added to the measured command.
                time.sleep(0.2)
        if data["stop_reason"]:
            code = 1
            print(f"Test storage guard STOP: {data['stop_reason']}", flush=True)
    finally:
        if process is not None:
            stop_group(process)
        shutil.rmtree(owned)
        data.update(exit_code=code, cleaned=not owned.exists())
        report.write_text(json.dumps(data, indent=2) + "\n")
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required")
    return run_guarded(command, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
