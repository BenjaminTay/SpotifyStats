from __future__ import annotations

# ruff: noqa: UP045
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import MutableMapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_FRONTEND_URL = "http://localhost:5173"
LOCAL_NO_PROXY_HOSTS = ("localhost", "127.0.0.1", "::1")


@dataclass
class HttpResult:
    status: int
    headers: dict[str, str]
    body: str


@dataclass
class StartedProcess:
    name: str
    process: subprocess.Popen
    log_path: Path
    log_handle: TextIO


@dataclass
class CheckTiming:
    label: str
    url: str
    status: int
    elapsed_ms: float
    body_bytes: int
    has_request_id: bool


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="quickstart_smoke.py",
        description="Start or reuse the local backend/frontend and verify the quickstart path.",
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--timeout-sec", type=float, default=90.0)
    parser.add_argument(
        "--log-dir", default=None, help="Directory for backend/frontend startup logs."
    )
    parser.add_argument("--json-output", default=None, help="Write quickstart timing report JSON.")
    parser.add_argument(
        "--require-running",
        action="store_true",
        help="Require backend/frontend services to already be running; do not start them.",
    )
    return parser.parse_args(argv)


def _url_host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Only http/https URLs are supported: {url}")
    if not parsed.hostname or not parsed.port:
        raise ValueError(f"URL must include host and port: {url}")
    return parsed.hostname, parsed.port


def build_backend_command(backend_url: str) -> list[str]:
    host, port = _url_host_port(backend_url)
    python_bin = Path(sys.executable)
    return [
        str(python_bin),
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]


def build_frontend_command(frontend_url: str) -> list[str]:
    host, port = _url_host_port(frontend_url)
    return [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(port),
        "--strictPort",
    ]


def default_env(backend_url: str = DEFAULT_BACKEND_URL) -> dict[str, str]:
    env = dict(os.environ)
    ensure_local_no_proxy(env)
    env.setdefault("SPOTIFY_STATS_WARMUP", "0")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["VITE_BACKEND_URL"] = backend_url
    return env


def _merge_no_proxy(value: str) -> str:
    hosts = [part.strip() for part in value.split(",") if part.strip()]
    normalized = {host.lower() for host in hosts}
    for host in LOCAL_NO_PROXY_HOSTS:
        if host.lower() not in normalized:
            hosts.append(host)
            normalized.add(host.lower())
    return ",".join(hosts)


def ensure_local_no_proxy(env: Optional[MutableMapping[str, str]] = None) -> None:
    """Keep local quickstart probes away from user/system HTTP proxies."""
    target = os.environ if env is None else env
    merged = _merge_no_proxy(target.get("NO_PROXY") or target.get("no_proxy") or "")
    target["NO_PROXY"] = merged
    target["no_proxy"] = merged


def fetch_url(url: str, timeout_sec: float = 5.0) -> HttpResult:
    request = Request(url, headers={"Accept": "text/html,application/json"})
    try:
        with urlopen(request, timeout=timeout_sec) as response:
            body = response.read(512_000).decode("utf-8", errors="replace")
            return HttpResult(
                status=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=body,
            )
    except HTTPError as exc:
        body = exc.read(512_000).decode("utf-8", errors="replace")
        return HttpResult(
            status=exc.code,
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=body,
        )


def is_ready(url: str, expected_status: int = 200, require_text: Optional[str] = None) -> bool:
    try:
        result = fetch_url(url, timeout_sec=2.0)
    except (OSError, URLError):
        return False
    if result.status != expected_status:
        return False
    if require_text and require_text not in result.body:
        return False
    return True


def wait_for_url(
    label: str,
    url: str,
    *,
    timeout_sec: float,
    expected_status: int = 200,
    require_text: Optional[str] = None,
    require_header: Optional[str] = None,
) -> HttpResult:
    deadline = time.monotonic() + timeout_sec
    last_error = ""
    while time.monotonic() < deadline:
        try:
            result = fetch_url(url, timeout_sec=5.0)
            if result.status == expected_status:
                if require_text and require_text not in result.body:
                    last_error = f"missing text {require_text!r}"
                elif require_header and require_header.lower() not in result.headers:
                    last_error = f"missing header {require_header!r}"
                else:
                    print(f"PASS {label}: {url}", flush=True)
                    return result
            else:
                last_error = f"status {result.status}"
        except (OSError, URLError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for {label} at {url}: {last_error}")


def timed_wait_for_url(
    label: str,
    url: str,
    *,
    timeout_sec: float,
    expected_status: int = 200,
    require_text: Optional[str] = None,
    require_header: Optional[str] = None,
) -> tuple[HttpResult, CheckTiming]:
    started_at = time.monotonic()
    result = wait_for_url(
        label,
        url,
        timeout_sec=timeout_sec,
        expected_status=expected_status,
        require_text=require_text,
        require_header=require_header,
    )
    elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)
    timing = CheckTiming(
        label=label,
        url=url,
        status=result.status,
        elapsed_ms=elapsed_ms,
        body_bytes=len(result.body.encode("utf-8")),
        has_request_id="x-request-id" in result.headers,
    )
    return result, timing


def _join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def start_process(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_dir: Path,
) -> StartedProcess:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    print(f"Starting {name}: {' '.join(command)}", flush=True)
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return StartedProcess(name=name, process=process, log_path=log_path, log_handle=log_handle)


def terminate_processes(started_processes: Sequence[StartedProcess]) -> None:
    for started in reversed(started_processes):
        process = started.process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        started.log_handle.close()


def build_timing_report(
    *,
    started_at: float,
    finished_at: float,
    log_dir: Path,
    backend_reused: bool,
    frontend_reused: bool,
    checks: Sequence[CheckTiming],
) -> dict:
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_elapsed_ms": round((finished_at - started_at) * 1000, 1),
        "backend_reused": backend_reused,
        "frontend_reused": frontend_reused,
        "log_dir": str(log_dir),
        "checks": [asdict(check) for check in checks],
    }


def write_json_report(report: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)


def print_timing_summary(report: dict) -> None:
    print(f"Quickstart timings: total={report['total_elapsed_ms']}ms", flush=True)
    for check in report["checks"]:
        print(
            f"- {check['label']}: {check['elapsed_ms']}ms "
            f"status={check['status']} bytes={check['body_bytes']}",
            flush=True,
        )


def run_quickstart_smoke(args: argparse.Namespace) -> dict:
    started_at = time.monotonic()
    ensure_local_no_proxy()
    log_dir = (
        Path(args.log_dir) if args.log_dir else Path(tempfile.mkdtemp(prefix="spotify-quickstart-"))
    )
    env = default_env(args.backend_url)
    started_processes: list[StartedProcess] = []
    checks: list[CheckTiming] = []
    backend_reused = False
    frontend_reused = False
    print(f"Quickstart smoke logs: {log_dir}", flush=True)

    try:
        backend_health_url = _join_url(args.backend_url, "/api/health")
        if is_ready(backend_health_url):
            backend_reused = True
            print(f"Reusing backend: {args.backend_url}", flush=True)
        elif args.require_running:
            raise RuntimeError(f"Backend is not running at {args.backend_url}")
        else:
            started_processes.append(
                start_process(
                    "backend",
                    build_backend_command(args.backend_url),
                    cwd=ROOT,
                    env=env,
                    log_dir=log_dir,
                )
            )

        _, timing = timed_wait_for_url(
            "backend health",
            backend_health_url,
            timeout_sec=args.timeout_sec,
            require_header="x-request-id",
        )
        checks.append(timing)
        _, timing = timed_wait_for_url(
            "backend docs",
            _join_url(args.backend_url, "/docs"),
            timeout_sec=args.timeout_sec,
            require_text="swagger-ui",
        )
        checks.append(timing)

        if is_ready(args.frontend_url, require_text='id="root"'):
            frontend_reused = True
            print(f"Reusing frontend: {args.frontend_url}", flush=True)
        elif args.require_running:
            raise RuntimeError(f"Frontend is not running at {args.frontend_url}")
        else:
            started_processes.append(
                start_process(
                    "frontend",
                    build_frontend_command(args.frontend_url),
                    cwd=ROOT / "frontend",
                    env=env,
                    log_dir=log_dir,
                )
            )

        _, timing = timed_wait_for_url(
            "frontend shell",
            args.frontend_url,
            timeout_sec=args.timeout_sec,
            require_text='id="root"',
        )
        checks.append(timing)
        _, timing = timed_wait_for_url(
            "frontend api proxy",
            _join_url(args.frontend_url, "/api/health"),
            timeout_sec=args.timeout_sec,
            require_header="x-request-id",
        )
        checks.append(timing)

        report = build_timing_report(
            started_at=started_at,
            finished_at=time.monotonic(),
            log_dir=log_dir,
            backend_reused=backend_reused,
            frontend_reused=frontend_reused,
            checks=checks,
        )
        print_timing_summary(report)
        if args.json_output:
            write_json_report(report, Path(args.json_output))
            print(f"Quickstart timing JSON written to {args.json_output}", flush=True)
        print(f"Quickstart smoke completed. Logs: {log_dir}", flush=True)
        return report
    finally:
        terminate_processes(started_processes)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        run_quickstart_smoke(args)
    except Exception as exc:
        print(f"Quickstart smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
