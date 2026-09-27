#!/usr/bin/env python3
"""Own one isolated backend/frontend startup matrix run and its idle window."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


class CorePagePendingError(RuntimeError):
    """The route is reachable but required business publications are not ready yet."""


def _free(port: int) -> None:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"measurement port is already in use: {port}") from exc


def _event(path: Path, name: str, **details: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "monotonic": time.monotonic(),
        "event": name,
        **details,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _external_competitors() -> list[str]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,command="],
        check=False,
        capture_output=True,
        text=True,
    )
    markers = ("pytest", "playwright", "vitest", "vite build", "fullstack_verification")
    own = {os.getpid(), os.getppid()}
    rows = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        command = parts[2].lower()
        if pid not in own and any(marker in command for marker in markers):
            rows.append(line.strip())
    return rows


def _wait_http(url: str, processes: list[subprocess.Popen], timeout: float) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        failed = next((process for process in processes if process.poll() is not None), None)
        if failed is not None:
            raise RuntimeError(f"owned process exited during startup: {failed.args!r}")
        try:
            with opener.open(url, timeout=1) as response:
                if response.status < 500:
                    return
        except (OSError, URLError):
            pass
        time.sleep(0.1)
    raise TimeoutError(url)


def _stop(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


CRITICAL_JOB_TYPES = (
    "playback_import_maintenance",
    "artist_identity_rebuild",
    "track_credit_rebuild",
    "music_search_snapshot_rebuild",
    "billboard_snapshot_rebuild",
    "analysis_snapshot_rebuild",
    "community_snapshot_rebuild",
    "account_archive_snapshot_rebuild",
    "governance_snapshot_rebuild",
    "artist_rank_context_rebuild",
    "startup_cache_warmup",
)


def _maintenance_rows(root: Path) -> list[dict[str, object]]:
    database = root / "data" / "spotify_stats.db"
    placeholders = ",".join("?" for _ in CRITICAL_JOB_TYPES)
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True, timeout=2) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""SELECT job_id, job_type, entity_type, entity_id, payload_json,
                       status, attempts, error, created_at, updated_at
                FROM background_jobs
                WHERE job_type IN ({placeholders})
                ORDER BY created_at, job_id""",
            CRITICAL_JOB_TYPES,
        ).fetchall()
    result = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            payload = {"invalid_payload": True}
        result.append(
            {
                "job_id": str(row["job_id"]),
                "job_type": str(row["job_type"]),
                "entity_type": str(row["entity_type"] or ""),
                "entity_id": str(row["entity_id"] or ""),
                "target_revision": payload.get("target_revision", payload.get("revision")),
                "target_key": payload.get("__job_queue_target_key", row["entity_id"]),
                "status": str(row["status"]),
                "attempts": int(row["attempts"] or 0),
                "error": row["error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return result


def _maintenance_baseline(root: Path) -> set[str]:
    """Remember only terminal history; active startup work remains in scope."""
    return {
        str(row["job_id"])
        for row in _maintenance_rows(root)
        if row["status"] not in {"pending", "running"}
    }


def _wait_maintenance(
    root: Path,
    processes: list[subprocess.Popen],
    timeout: float,
    baseline_terminal_ids: set[str] | None = None,
) -> dict[str, object]:
    baseline = baseline_terminal_ids or set()
    deadline = time.monotonic() + timeout
    quiet_polls = 0
    relevant: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("owned process exited while maintenance was active")
        relevant = [row for row in _maintenance_rows(root) if str(row["job_id"]) not in baseline]
        failures = [row for row in relevant if row["status"] not in {"pending", "running", "done"}]
        if failures:
            failure = failures[0]
            raise RuntimeError(
                "startup maintenance job "
                f"{failure['job_id']} failed: type={failure['job_type']} "
                f"target={failure['target_key']} status={failure['status']} "
                f"error={failure['error']}"
            )
        active = [row for row in relevant if row["status"] in {"pending", "running"}]
        if active:
            quiet_polls = 0
        else:
            quiet_polls += 1
            if quiet_polls >= 3:
                return {"jobs": relevant, "quiet_polls": quiet_polls}
        time.sleep(0.25)
    raise TimeoutError("critical startup maintenance did not become idle")


def _probe_core_page(
    frontend_url: str,
    backend_url: str,
    output: Path,
    timeout: float,
    *,
    require_exact: bool = False,
) -> dict[str, object]:
    context = output.with_suffix(".context.json")
    context.write_text(
        json.dumps(
            {
                "schema_version": "spotify-performance/1",
                "dataset": "isolated-runtime",
                "measurement": "core-page-ready",
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "node",
            str(ROOT / "scripts" / "frontend_web_vitals_probe.mjs"),
            "--base-url",
            frontend_url,
            "--api-base-url",
            backend_url,
            "--routes",
            "/",
            "--viewport",
            "desktop",
            "--wait-ms",
            str(max(500, int(timeout * 1000))),
            "--context-file",
            str(context),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if not output.is_file():
        raise RuntimeError(
            "core page browser probe failed: " + (result.stderr or result.stdout)[-1000:]
        )
    payload = json.loads(output.read_text(encoding="utf-8"))
    samples = payload.get("samples") or payload.get("results") or []
    business_ready = next(
        (
            item
            for item in reversed(samples)
            if (item.get("core_ready") or {}).get("ready")
            and (item.get("api_terminal") or {}).get("success")
            and not any(
                "/api/" in str(request.get("url") or "")
                and (request.get("error_type") or int(request.get("status") or 0) >= 400)
                for request in item.get("waterfall", [])
            )
        ),
        None,
    )
    if result.returncode != 0:
        pending = bool(samples) and all(
            (item.get("core_ready") or {}).get("route_ready")
            and (
                (item.get("core_ready") or {}).get("failure") == "HTTP503"
                or (item.get("http") or {}).get("error_type") == "HTTP503"
            )
            for item in samples
        )
        if pending:
            raise CorePagePendingError("core page publications are pending (HTTP503)")
        if business_ready is None:
            raise RuntimeError(
                "core page browser probe failed: " + (result.stderr or result.stdout)[-1000:]
            )
    sample = business_ready or next(
        (item for item in reversed(samples) if item.get("success")), None
    )
    if sample is None or not (sample.get("core_ready") or {}).get("ready"):
        raise RuntimeError("core page browser probe did not reach business-ready DOM/API state")
    api_snapshots = [
        request.get("snapshot") or {}
        for request in sample.get("waterfall", [])
        if "/api/home/overview" in str(request.get("url") or "")
    ]
    if not api_snapshots and sample.get("snapshot"):
        api_snapshots = [sample["snapshot"]]
    states = {str(snapshot.get("state") or "unknown") for snapshot in api_snapshots}
    if require_exact and states == {"LKG"}:
        raise CorePagePendingError("core page is still serving LKG while exact refresh is pending")
    allowed = {"exact"} if require_exact else {"exact", "LKG"}
    if not states or not states.issubset(allowed):
        raise RuntimeError(f"core page snapshot state is not ready: {sorted(states)}")
    return {
        "snapshot_states": sorted(states),
        "core_ready_ms": sample.get("core_ready_ms"),
        "api_terminal": sample.get("api_terminal"),
        "output": str(output),
    }


def _validate_maintenance_publications(root: Path, output: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "runtime_measurement.py"),
            "validate",
            "--root",
            str(root),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if not output.is_file():
        raise RuntimeError(
            "maintenance publication validation produced no evidence: "
            + (result.stderr or result.stdout)[-1000:]
        )
    payload = json.loads(output.read_text(encoding="utf-8"))
    if result.returncode != 0 or not payload.get("ready"):
        failed = [
            name for name, check in (payload.get("checks") or {}).items() if not check.get("ready")
        ]
        raise RuntimeError(
            "maintenance target publications are not exact-ready: " + ", ".join(failed)
        )
    return payload


def _wait_exact_core_page(
    frontend_url: str,
    backend_url: str,
    output: Path,
    timeout: float,
    processes: list[subprocess.Popen],
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("owned process exited while exact core page was pending")
        try:
            return _probe_core_page(
                frontend_url,
                backend_url,
                output,
                min(30, max(1, deadline - time.monotonic())),
                require_exact=True,
            )
        except CorePagePendingError:
            time.sleep(0.5)
    raise TimeoutError("core page did not become exact before the maintenance deadline")


def _probe_spa_page_comparison(
    frontend_url: str,
    output: Path,
    timeout: float,
) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "frontend_spa_ready_probe.py"),
            "--base-url",
            frontend_url,
            "--wait-ms",
            str(max(500, int(timeout * 1000))),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if not output.is_file():
        raise RuntimeError(
            "same-SPA browser probe produced no evidence: "
            + (result.stderr or result.stdout)[-1000:]
        )
    payload = json.loads(output.read_text(encoding="utf-8"))
    samples = payload.get("samples") or []
    phases = {str(sample.get("phase")): sample for sample in samples}
    if (
        result.returncode != 0
        or not payload.get("success")
        or not payload.get("same_document")
        or not {"first", "transition", "revisit"}.issubset(phases)
    ):
        raise RuntimeError(
            "same-SPA browser probe failed: " + (result.stderr or result.stdout)[-1000:]
        )
    for phase in ("first", "revisit"):
        sample = phases[phase]
        if not (sample.get("api_terminal") or {}).get("success"):
            raise RuntimeError(f"same-SPA {phase} API did not reach a successful terminal state")
        if sample.get("snapshot_state") not in {"exact", "LKG"}:
            raise RuntimeError(
                f"same-SPA {phase} snapshot is not ready: {sample.get('snapshot_state')}"
            )
    return {
        "first": phases["first"],
        "transition": phases["transition"],
        "revisit": phases["revisit"],
        "same_document": True,
        "output": str(output),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--frontend-port", type=int, required=True)
    parser.add_argument("--frontend-mode", choices=("dev", "preview"), required=True)
    parser.add_argument("--warmup-mode", choices=("full", "minimal", "off"), default="full")
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--idle-seconds", type=float, default=300)
    parser.add_argument("--startup-timeout", type=float, default=180)
    parser.add_argument("--maintenance-timeout", type=float, default=1800)
    parser.add_argument("--phase-file", type=Path, required=True)
    parser.add_argument("--events-output", type=Path, required=True)
    parser.add_argument("--backend-pid-file", type=Path)
    parser.add_argument("--frontend-pid-file", type=Path)
    parser.add_argument(
        "--spa-comparison-output",
        type=Path,
        help="Measure first/revisit core readiness in one SPA document after exact publication",
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=Path(tempfile.gettempdir()) / "spotify-fullstack-verification.lock",
    )
    return parser.parse_args(argv)


def _run(args: argparse.Namespace) -> int:
    _free(args.backend_port)
    _free(args.frontend_port)
    if args.frontend_mode == "preview" and not (FRONTEND / "dist" / "index.html").is_file():
        raise FileNotFoundError("frontend/dist/index.html is required for preview measurement")
    args.phase_file.parent.mkdir(parents=True, exist_ok=True)
    args.phase_file.write_text("process_start", encoding="utf-8")
    external_competitors = _external_competitors()
    _event(
        args.events_output,
        "process_start",
        external_competitors=external_competitors,
    )
    if external_competitors:
        args.phase_file.write_text("blocked", encoding="utf-8")
        _event(
            args.events_output,
            "blocked_by_external_competitors",
            external_competitors=external_competitors,
        )
        return 4
    maintenance_baseline = _maintenance_baseline(Path(args.root))
    environment = os.environ.copy()
    environment["VITE_BACKEND_URL"] = f"http://127.0.0.1:{args.backend_port}"
    backend = [
        sys.executable,
        str(ROOT / "scripts" / "runtime_measurement.py"),
        "serve",
        "--root",
        args.root,
        "--port",
        str(args.backend_port),
        "--frontend-origin",
        f"http://127.0.0.1:{args.frontend_port}",
        "--warmup-mode",
        args.warmup_mode,
    ]
    if args.reload:
        backend.append("--reload")
    frontend = [
        "npm",
        "run",
        args.frontend_mode,
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.frontend_port),
        "--strictPort",
    ]
    processes: list[subprocess.Popen] = []
    stopped = False

    def request_stop(_signum, _frame):
        nonlocal stopped
        stopped = True

    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        processes.append(
            subprocess.Popen(backend, cwd=ROOT, env=environment, start_new_session=True)
        )
        if args.backend_pid_file:
            args.backend_pid_file.write_text(str(processes[0].pid), encoding="utf-8")
        processes.append(
            subprocess.Popen(frontend, cwd=FRONTEND, env=environment, start_new_session=True)
        )
        if args.frontend_pid_file:
            args.frontend_pid_file.write_text(str(processes[1].pid), encoding="utf-8")
        _wait_http(
            f"http://127.0.0.1:{args.backend_port}/api/health",
            processes,
            args.startup_timeout,
        )
        args.phase_file.write_text("health_ready", encoding="utf-8")
        _event(args.events_output, "health_ready")
        _wait_http(
            f"http://127.0.0.1:{args.frontend_port}/",
            processes,
            args.startup_timeout,
        )
        args.phase_file.write_text("static_frontend_ready", encoding="utf-8")
        _event(args.events_output, "static_frontend_ready")
        args.phase_file.write_text("maintenance", encoding="utf-8")
        _event(args.events_output, "maintenance_start")
        initial_page_ready = False
        if args.spa_comparison_output:
            startup_spa_output = args.spa_comparison_output.with_name(
                args.spa_comparison_output.stem + "-startup" + args.spa_comparison_output.suffix
            )
            comparison = _probe_spa_page_comparison(
                f"http://127.0.0.1:{args.frontend_port}",
                startup_spa_output,
                args.startup_timeout,
            )
            first_page = comparison["first"]
            initial_page_ready = True
            _event(
                args.events_output,
                "core_page_ready",
                snapshot_states=[first_page["snapshot_state"]],
                core_ready_ms=first_page["core_ready_ms"],
                observed_monotonic=first_page["ready_monotonic"],
                observed_epoch=first_page["ready_at_epoch"],
                api_terminal=first_page["api_terminal"],
                output=str(startup_spa_output),
            )
            _event(args.events_output, "startup_spa_page_comparison", **comparison)
        else:
            try:
                first_page = _probe_core_page(
                    f"http://127.0.0.1:{args.frontend_port}",
                    f"http://127.0.0.1:{args.backend_port}",
                    args.events_output.with_name(args.events_output.stem + "-first-page.json"),
                    args.startup_timeout,
                )
            except CorePagePendingError as exc:
                _event(args.events_output, "core_page_pending", reason=str(exc))
            else:
                initial_page_ready = True
                _event(args.events_output, "core_page_ready", **first_page)
        maintenance = _wait_maintenance(
            Path(args.root),
            processes,
            args.maintenance_timeout,
            maintenance_baseline,
        )
        _event(args.events_output, "necessary_maintenance_complete", maintenance=maintenance)
        publication_readiness = _validate_maintenance_publications(
            Path(args.root),
            args.events_output.with_name(args.events_output.stem + "-publications.json"),
        )
        _event(
            args.events_output,
            "publication_exact_validated",
            publication_readiness=publication_readiness,
        )
        if args.spa_comparison_output:
            exact_comparison = _probe_spa_page_comparison(
                f"http://127.0.0.1:{args.frontend_port}",
                args.spa_comparison_output,
                args.startup_timeout,
            )
            exact_first = exact_comparison["first"]
            exact_revisit = exact_comparison["revisit"]
            if any(sample["snapshot_state"] != "exact" for sample in (exact_first, exact_revisit)):
                raise CorePagePendingError("stable SPA comparison did not consume exact Home facts")
            exact_page = {
                "snapshot_states": [
                    exact_first["snapshot_state"],
                    exact_revisit["snapshot_state"],
                ],
                "core_ready_ms": exact_first["core_ready_ms"],
                "revisit_core_ready_ms": exact_revisit["core_ready_ms"],
                "api_terminal": exact_first["api_terminal"],
                "output": str(args.spa_comparison_output),
            }
            _event(args.events_output, "spa_page_comparison", **exact_comparison)
        else:
            exact_page = _wait_exact_core_page(
                f"http://127.0.0.1:{args.frontend_port}",
                f"http://127.0.0.1:{args.backend_port}",
                args.events_output.with_name(args.events_output.stem + "-exact-page.json"),
                args.maintenance_timeout,
                processes,
            )
        if initial_page_ready:
            _event(args.events_output, "core_page_exact", **exact_page)
        else:
            _event(args.events_output, "core_page_ready", **exact_page)
        _event(
            args.events_output,
            "maintenance_complete",
            maintenance=maintenance,
            publication_readiness=publication_readiness,
            core_page=exact_page,
        )
        args.phase_file.write_text("idle", encoding="utf-8")
        _event(args.events_output, "idle_start", seconds=args.idle_seconds)
        deadline = time.monotonic() + args.idle_seconds
        while not stopped and time.monotonic() < deadline:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("owned process exited during the idle window")
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        _event(args.events_output, "idle_end")
        return 130 if stopped else 0
    finally:
        args.phase_file.write_text("shutdown", encoding="utf-8")
        _stop(processes)
        _event(
            args.events_output,
            "shutdown_complete",
            external_competitors=_external_competitors(),
        )
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.lock_file.parent.mkdir(parents=True, exist_ok=True)
    with args.lock_file.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _event(args.events_output, "blocked_by_performance_lock")
            return 3
        try:
            return _run(args)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    raise SystemExit(main())
