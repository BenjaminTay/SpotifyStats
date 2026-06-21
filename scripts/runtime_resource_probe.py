#!/usr/bin/env python3
"""Capture local runtime process resource snapshots for SpotifyStats services."""

from __future__ import annotations

# ruff: noqa: UP045
import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_FRONTEND_URL = "http://localhost:5173"


@dataclass
class ProcessRow:
    pid: int
    ppid: int
    rss_kb: int
    cpu_percent: float
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
        parts = line.split(None, 4)
        if len(parts) < 4 or parts[0].upper() == "PID":
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            rss_kb = int(parts[2])
            if len(parts) >= 5:
                cpu_percent = float(parts[3])
                command = parts[4]
            else:
                cpu_percent = 0.0
                command = parts[3]
        except ValueError:
            continue
        rows.append(
            ProcessRow(
                pid=pid,
                ppid=ppid,
                rss_kb=rss_kb,
                cpu_percent=cpu_percent,
                command=command,
            )
        )
    return rows


def ps_rows_for_pids(pids: list[int]) -> list[ProcessRow]:
    if not pids:
        return []
    result = run_command(
        ["ps", "-o", "pid=,ppid=,rss=,pcpu=,command=", "-p", ",".join(map(str, pids))]
    )
    if result.returncode != 0:
        return []
    return parse_ps_rows(result.stdout)


def summarize_processes(label: str, url: str, rows: list[ProcessRow]) -> dict:
    port = url_port(url)
    pids = sorted(row.pid for row in rows)
    rss_mb = round(sum(row.rss_kb for row in rows) / 1024, 1)
    cpu_percent = round(sum(row.cpu_percent for row in rows), 1)
    return {
        "label": label,
        "url": url,
        "port": port,
        "status": "ok" if rows else "missing",
        "pids": pids,
        "process_count": len(rows),
        "rss_mb": rss_mb,
        "cpu_percent": cpu_percent,
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
    total_cpu_percent = round(sum(snapshot["cpu_percent"] for snapshot in snapshots), 1)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_count": len(snapshots),
        "missing_count": missing_count,
        "total_rss_mb": total_rss_mb,
        "total_cpu_percent": total_cpu_percent,
        "snapshots": snapshots,
    }


def parse_service_budget(value: str) -> tuple[str, float]:
    if "=" not in value:
        raise ValueError(f"Service budget must use label=value syntax: {value}")
    label, raw_budget = value.split("=", 1)
    label = label.strip()
    if not label:
        raise ValueError(f"Service budget label is empty: {value}")
    try:
        budget = float(raw_budget)
    except ValueError as exc:
        raise ValueError(f"Service budget must be numeric: {value}") from exc
    return label, budget


def collect_service_budgets(values: Optional[list[str]]) -> dict[str, float]:
    budgets: dict[str, float] = {}
    for value in values or []:
        label, budget = parse_service_budget(value)
        budgets[label] = budget
    return budgets


def evaluate_budgets(
    report: dict,
    max_total_rss_mb: Optional[float] = None,
    max_total_cpu_percent: Optional[float] = None,
    service_rss_budgets: Optional[dict[str, float]] = None,
    service_cpu_budgets: Optional[dict[str, float]] = None,
) -> list[str]:
    failures: list[str] = []
    if max_total_rss_mb is not None and report["total_rss_mb"] > max_total_rss_mb:
        failures.append(f"total RSS {report['total_rss_mb']}MB exceeds budget {max_total_rss_mb}MB")
    if max_total_cpu_percent is not None and report["total_cpu_percent"] > max_total_cpu_percent:
        failures.append(
            f"total CPU {report['total_cpu_percent']}% exceeds budget {max_total_cpu_percent}%"
        )

    snapshots_by_label = {snapshot["label"]: snapshot for snapshot in report["snapshots"]}
    for label, budget in (service_rss_budgets or {}).items():
        snapshot = snapshots_by_label.get(label)
        if snapshot is None:
            failures.append(f"{label} RSS budget configured but service snapshot is missing")
        elif snapshot["rss_mb"] > budget:
            failures.append(f"{label} RSS {snapshot['rss_mb']}MB exceeds budget {budget}MB")
    for label, budget in (service_cpu_budgets or {}).items():
        snapshot = snapshots_by_label.get(label)
        if snapshot is None:
            failures.append(f"{label} CPU budget configured but service snapshot is missing")
        elif snapshot["cpu_percent"] > budget:
            failures.append(f"{label} CPU {snapshot['cpu_percent']}% exceeds budget {budget}%")
    return failures


def render_markdown(report: dict) -> str:
    lines = [
        "# Runtime Resource Snapshot",
        "",
        f"> Generated: {report['generated_at']}",
        f"> Total RSS: {report['total_rss_mb']}MB",
        f"> Total CPU: {report['total_cpu_percent']}%",
        "",
        "| Service | URL | Port | Status | PIDs | Processes | RSS | CPU |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for snapshot in report["snapshots"]:
        pids = ", ".join(str(pid) for pid in snapshot["pids"]) or "n/a"
        lines.append(
            f"| {snapshot['label']} | `{snapshot['url']}` | {snapshot['port']} | "
            f"{snapshot['status']} | {pids} | {snapshot['process_count']} | "
            f"{snapshot['rss_mb']}MB | {snapshot['cpu_percent']}% |"
        )
    if report.get("budget_failures"):
        lines.append("")
        lines.append("Budget failures:")
        for failure in report["budget_failures"]:
            lines.append(f"- {failure}")
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
        description="Capture backend/frontend process CPU/RSS snapshots for local verification.",
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--preview-url", default=None)
    parser.add_argument("--json-output", default=None, help="Write machine-readable JSON report")
    parser.add_argument(
        "--fail-on-missing", action="store_true", help="Exit 1 if any service is missing"
    )
    parser.add_argument(
        "--no-children", action="store_true", help="Do not include child process CPU/RSS"
    )
    parser.add_argument(
        "--max-total-rss-mb",
        type=float,
        default=None,
        help="Exit 1 when combined service RSS exceeds this MB budget",
    )
    parser.add_argument(
        "--max-total-cpu-percent",
        type=float,
        default=None,
        help="Exit 1 when combined service CPU percent exceeds this budget",
    )
    parser.add_argument(
        "--max-service-rss-mb",
        action="append",
        default=[],
        metavar="LABEL=MB",
        help="Exit 1 when one service RSS exceeds its MB budget; repeatable",
    )
    parser.add_argument(
        "--max-service-cpu-percent",
        action="append",
        default=[],
        metavar="LABEL=PERCENT",
        help="Exit 1 when one service CPU percent exceeds its budget; repeatable",
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
    try:
        service_rss_budgets = collect_service_budgets(args.max_service_rss_mb)
        service_cpu_budgets = collect_service_budgets(args.max_service_cpu_percent)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    budget_failures = evaluate_budgets(
        report,
        max_total_rss_mb=args.max_total_rss_mb,
        max_total_cpu_percent=args.max_total_cpu_percent,
        service_rss_budgets=service_rss_budgets,
        service_cpu_budgets=service_cpu_budgets,
    )
    report["budget_failures"] = budget_failures
    print(render_markdown(report), flush=True)

    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"JSON report written to {args.json_output}")

    if args.fail_on_missing and report["missing_count"] > 0:
        return 1
    if budget_failures:
        print("Runtime resource budget failures:", file=sys.stderr)
        for failure in budget_failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
