#!/usr/bin/env python3
"""Measure host capacity for the production music-search one-shot rebuild."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

MIB = 1024 * 1024
GIB = 1024 * MIB
DISK_COPY_MULTIPLIER = 4


def required_disk_bytes(database_bytes: int) -> int:
    return max(GIB, max(0, database_bytes) * DISK_COPY_MULTIPLIER)


def parse_mem_available_bytes(meminfo: str) -> int:
    for line in meminfo.splitlines():
        key, separator, raw_value = line.partition(":")
        if key == "MemAvailable" and separator:
            parts = raw_value.strip().split()
            if len(parts) == 2 and parts[1] == "kB" and parts[0].isdigit():
                return int(parts[0]) * 1024
    raise ValueError("MemAvailable is missing from /proc/meminfo")


def parse_vm_stat_available_bytes(vm_stat: str) -> int:
    lines = vm_stat.splitlines()
    if not lines or "page size of" not in lines[0]:
        raise ValueError("vm_stat page size is missing")
    try:
        page_size = int(lines[0].split("page size of", 1)[1].split("bytes", 1)[0])
    except (IndexError, ValueError) as exc:
        raise ValueError("vm_stat page size is invalid") from exc

    pages: dict[str, int] = {}
    for line in lines[1:]:
        key, separator, raw_value = line.partition(":")
        if not separator:
            continue
        normalized = raw_value.strip().rstrip(".")
        if normalized.isdigit():
            pages[key.strip()] = int(normalized)
    available_pages = sum(
        pages.get(key, 0)
        for key in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable")
    )
    if available_pages <= 0:
        raise ValueError("vm_stat available pages are missing")
    return available_pages * page_size


def available_memory_bytes() -> int:
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        return parse_mem_available_bytes(meminfo.read_text(encoding="utf-8"))
    if sys.platform == "darwin":
        completed = subprocess.run(
            ["vm_stat"],
            check=True,
            capture_output=True,
            text=True,
        )
        return parse_vm_stat_available_bytes(completed.stdout)
    raise RuntimeError("available-memory probe is unsupported on this host")


def capacity_sample(db_path: Path) -> dict[str, int]:
    available_memory = available_memory_bytes()
    available_disk = shutil.disk_usage(db_path.parent).free
    return {
        "available_memory_bytes": available_memory,
        "available_memory_mib": available_memory // MIB,
        "available_disk_bytes": available_disk,
        "available_disk_mib": available_disk // MIB,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--min-available-mib", type=int, required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--previous-report", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.min_available_mib <= 0:
        raise SystemExit("music-search preflight capacity failed: minimum memory must be positive")
    db_path = args.db_path.expanduser().resolve(strict=True)
    if not db_path.is_file():
        raise SystemExit("music-search preflight capacity failed: database copy is missing")

    database_bytes = db_path.stat().st_size
    sample = capacity_sample(db_path)
    minimum_memory_bytes = args.min_available_mib * MIB
    minimum_disk_bytes = required_disk_bytes(database_bytes)
    sample_passed = (
        sample["available_memory_bytes"] >= minimum_memory_bytes
        and sample["available_disk_bytes"] >= minimum_disk_bytes
    )

    if args.phase == "before":
        payload: dict[str, Any] = {
            "requirements": {
                "minimum_available_memory_bytes": minimum_memory_bytes,
                "minimum_available_memory_mib": args.min_available_mib,
                "minimum_disk_floor_bytes": GIB,
                "disk_copy_multiplier": DISK_COPY_MULTIPLIER,
                "database_bytes_before": database_bytes,
                "required_disk_bytes_before": minimum_disk_bytes,
            },
            "before": sample,
            "passed": sample_passed,
        }
    else:
        if args.previous_report is None:
            raise SystemExit(
                "music-search preflight capacity failed: after phase needs previous report"
            )
        try:
            payload = json.loads(args.previous_report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(
                "music-search preflight capacity failed: invalid previous report"
            ) from exc
        requirements = payload.get("requirements")
        if not isinstance(requirements, dict) or not isinstance(payload.get("before"), dict):
            raise SystemExit("music-search preflight capacity failed: incomplete previous report")
        requirements["database_bytes_after"] = database_bytes
        requirements["required_disk_bytes_after"] = minimum_disk_bytes
        payload["after"] = sample
        payload["passed"] = bool(payload.get("passed")) and sample_passed

    write_json_atomic(args.json_output, payload)
    if not payload["passed"]:
        print(
            "music-search preflight capacity failed: "
            f"MemAvailable={sample['available_memory_mib']}MiB "
            f"required={args.min_available_mib}MiB "
            f"disk_available={sample['available_disk_mib']}MiB "
            f"disk_required={minimum_disk_bytes // MIB}MiB",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
