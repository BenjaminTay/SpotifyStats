#!/usr/bin/env python3
"""Capture local runtime process resource snapshots for SpotifyStats services."""

from __future__ import annotations

# ruff: noqa: UP045
import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_FRONTEND_URL = "http://127.0.0.1:5173"


@dataclass
class ProcessRow:
    pid: int
    ppid: int
    rss_kb: int
    command: str


def url_port(url: str) -> int:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Only http/https URLs are supported: {url}")
    if parsed.port is None:
        raise ValueError(f"URL must include an explicit port: {url}")
    return parsed.port


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=False, text=True, capture_output=True)


def process_ids_for_port(port: int) -> list[int]:
    result = run_command(["lsof", "-nP", f"-tiTCP:{port}", "-sTCP:LISTEN"])
    if result.returncode not in {0, 1}:
        return []
    return sorted({int(line) for line in result.stdout.splitlines() if line.strip().isdigit()})


def child_pids(pid: int) -> list[int]:
    result = run_command(["pgrep", "-P", str(pid)])
    if result.returncode not in {0, 1}:
        return []
    return sorted({int(line) for line in result.stdout.splitlines() if line.strip().isdigit()})


def expand_process_tree(pids: list[int]) -> list[int]:
    seen: set[int] = set()
    pending = list(pids)
    while pending:
        pid = pending.pop(0)
        if pid in seen:
            continue
        seen.add(pid)
        pending.extend(child for child in child_pids(pid) if child not in seen)
    return sorted(seen)


def parse_ps_rows(output: str) -> list[ProcessRow]:
    rows: list[ProcessRow] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 4 or parts[0].upper() == "PID":
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            rss_kb = int(parts[2])
        except ValueError:
            continue
        rows.append(ProcessRow(pid=pid, ppid=ppid, rss_kb=rss_kb, command=parts[3]))
    return rows


def ps_rows_for_pids(pids: list[int]) -> list[ProcessRow]:
    if not pids:
        return []
    result = run_command(["ps", "-o", "pid=,ppid=,rss=,command=", "-p", ",".join(map(str, pids))])
    if result.returncode != 0:
        return []
    return parse_ps_rows(result.stdout)


def summarize_processes(label: str, url: str, rows: list[ProcessRow]) -> dict:
    port = url_port(url)
    pids = sorted(row.pid for row in rows)
    rss_mb = round(sum(row.rss_kb for row in rows) / 1024, 1)
    return {
        "label": label,
        "url": url,
        "port": port,
        "status": "ok" if rows else "missing",
        "pids": pids,
        "process_count": len(rows),
        "rss_mb": rss_mb,
        "commands": [row.command for row in sorted(rows, key=lambda item: item.pid)],
    }


def capture_snapshot(label: str, url: str, include_children: bool = True) -> dict:
    pids = process_ids_for_port(url_port(url))
    if include_children:
        pids = expand_process_tree(pids)
    rows = ps_rows_for_pids(pids)
    return summarize_processes(label, url, rows)


def build_json_report(snapshots: list[dict]) -> dict:
    missing_count = sum(1 for snapshot in snapshots if snapshot["status"] != "ok")
    total_rss_mb = round(sum(snapshot["rss_mb"] for snapshot in snapshots), 1)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_count": len(snapshots),
        "missing_count": missing_count,
        "total_rss_mb": total_rss_mb,
        "snapshots": snapshots,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Runtime Resource Snapshot",
        "",
        f"> Generated: {report['generated_at']}",
        f"> Total RSS: {report['total_rss_mb']}MB",
        "",
        "| Service | URL | Port | Status | PIDs | Processes | RSS |",
        "| --- | --- | ---: | --- | --- | ---: | ---: |",
    ]
    for snapshot in report["snapshots"]:
        pids = ", ".join(str(pid) for pid in snapshot["pids"]) or "n/a"
        lines.append(
            f"| {snapshot['label']} | `{snapshot['url']}` | {snapshot['port']} | "
            f"{snapshot['status']} | {pids} | {snapshot['process_count']} | "
            f"{snapshot['rss_mb']}MB |"
        )
    lines.append("")
    lines.append("Notes:")
    lines.append("- RSS is read from local `ps` output and includes child processes by default.")
    lines.append(
        "- Missing services are reported as status `missing`; use `--fail-on-missing` to gate."
    )
    return "\n".join(lines)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="runtime_resource_probe.py",
        description="Capture backend/frontend process RSS snapshots for local verification.",
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--preview-url", default=None)
    parser.add_argument("--json-output", default=None, help="Write machine-readable JSON report")
    parser.add_argument(
        "--fail-on-missing", action="store_true", help="Exit 1 if any service is missing"
    )
    parser.add_argument(
        "--no-children", action="store_true", help="Do not include child process RSS"
    )
    return parser.parse_args(argv)


def collect_snapshots(args: argparse.Namespace) -> list[dict]:
    targets = [
        ("backend", args.backend_url),
        ("frontend", args.frontend_url),
    ]
    if args.preview_url:
        targets.append(("preview", args.preview_url))
    return [
        capture_snapshot(label, url, include_children=not args.no_children)
        for label, url in targets
    ]


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    snapshots = collect_snapshots(args)
    report = build_json_report(snapshots)
    print(render_markdown(report))

    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"JSON report written to {args.json_output}")

    if args.fail_on_missing and report["missing_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
