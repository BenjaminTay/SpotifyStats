#!/usr/bin/env python3
"""Run the interleaved A/B/C/D/F startup matrix on independent E roots."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "A": {"reload": True, "frontend": "dev", "warmup": "full"},
    "B": {"reload": False, "frontend": "dev", "warmup": "full"},
    "C": {"reload": False, "frontend": "dev", "warmup": "minimal"},
    "D": {"reload": False, "frontend": "preview", "warmup": "full"},
    "F": {"reload": False, "frontend": "preview", "warmup": "minimal"},
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        required=True,
        help="Independent exact-ready root; provide 15 in A/B/C/D/F interleaved order",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--idle-seconds", type=float, default=300)
    parser.add_argument("--backend-port", type=int, default=18830)
    parser.add_argument("--frontend-port", type=int, default=14330)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--footprint-interval", type=float, default=15)
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=Path(tempfile.gettempdir()) / "spotify-fullstack-verification.lock",
    )
    return parser.parse_args(argv)


def schedule(roots: list[Path]) -> list[tuple[int, str, Path]]:
    if len(roots) != 15:
        raise ValueError("the formal matrix requires exactly 15 independent roots")
    result = []
    position = 0
    for repetition in range(1, 4):
        for group in GROUPS:
            result.append((repetition, group, roots[position].resolve()))
            position += 1
    if len({str(root) for _, _, root in result}) != 15:
        raise ValueError("every formal matrix run must use a distinct root")
    return result


def _validate_root(root: Path) -> None:
    if not (root / "manifest.json").is_file():
        raise FileNotFoundError(f"manifest missing: {root}")
    if not (root / "data" / "spotify_stats.db").is_file():
        raise FileNotFoundError(f"database missing: {root}")


def run(args: argparse.Namespace) -> int:
    planned = schedule(args.root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "idle_seconds": args.idle_seconds,
        "order": [f"{group}{repetition}" for repetition, group, _ in planned],
        "runs": [],
    }
    summary_path = args.output_root / "summary.json"
    for index, (repetition, group, root) in enumerate(planned, start=1):
        _validate_root(root)
        label = f"{index:02d}-{group}{repetition}"
        output = args.output_root / label
        output.mkdir()
        phase = output / "phase.txt"
        events = output / "events.jsonl"
        backend_pid = output / "backend.pid"
        frontend_pid = output / "frontend.pid"
        resources = output / "resources.json"
        log = output / "run.log"
        config = GROUPS[group]
        matrix_command = [
            sys.executable,
            str(ROOT / "scripts" / "runtime_matrix_run.py"),
            "--root",
            str(root),
            "--backend-port",
            str(args.backend_port),
            "--frontend-port",
            str(args.frontend_port),
            "--frontend-mode",
            str(config["frontend"]),
            "--warmup-mode",
            str(config["warmup"]),
            "--idle-seconds",
            str(args.idle_seconds),
            "--phase-file",
            str(phase),
            "--events-output",
            str(events),
            "--backend-pid-file",
            str(backend_pid),
            "--frontend-pid-file",
            str(frontend_pid),
            "--lock-file",
            str(args.lock_file),
        ]
        if config["reload"]:
            matrix_command.append("--reload")
        command = [
            sys.executable,
            str(ROOT / "scripts" / "runtime_resource_probe.py"),
            "--backend-url",
            f"http://127.0.0.1:{args.backend_port}",
            "--frontend-url",
            f"http://127.0.0.1:{args.frontend_port}",
            "--backend-pid-file",
            str(backend_pid),
            "--frontend-pid-file",
            str(frontend_pid),
            "--phase-file",
            str(phase),
            "--interval",
            str(args.interval),
            "--macos-footprint-interval",
            str(args.footprint_interval),
            "--db-path",
            str(root / "data" / "spotify_stats.db"),
            "--dataset",
            "online_backup",
            "--watch-file",
            str(root / "data" / "spotify_stats.db"),
            "--json-output",
            str(resources),
            "--command",
            *matrix_command,
        ]
        started = time.monotonic()
        with log.open("w", encoding="utf-8") as handle:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        entry = {
            "sequence": index,
            "label": label,
            "group": group,
            "repetition": repetition,
            "root": str(root),
            "returncode": completed.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "resources": str(resources),
            "events": str(events),
            "log": str(log),
        }
        summary["runs"].append(entry)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if completed.returncode != 0:
            summary["completed_at"] = datetime.now(timezone.utc).isoformat()
            summary["status"] = "failed"
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
            return completed.returncode
    summary["completed_at"] = datetime.now(timezone.utc).isoformat()
    summary["status"] = "complete"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.idle_seconds < 0 or args.interval <= 0 or args.footprint_interval < 0:
        raise ValueError("invalid sampling configuration")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
