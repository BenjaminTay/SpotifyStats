#!/usr/bin/env python3
"""Run the local daily-use backend plus the already-built frontend."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BUILD_MANIFEST_NAME = ".spotify-stats-build-inputs.json"


def _build_manifest_path() -> Path:
    return FRONTEND / "dist" / BUILD_MANIFEST_NAME


def _build_inputs() -> list[Path]:
    inputs = [
        FRONTEND / "src",
        FRONTEND / "public",
        FRONTEND / "index.html",
        FRONTEND / "package.json",
        FRONTEND / "package-lock.json",
        FRONTEND / "vite.config.ts",
        FRONTEND / "tsconfig.json",
        FRONTEND / "tsconfig.app.json",
        FRONTEND / "tsconfig.node.json",
    ]
    files: list[Path] = []
    for path in inputs:
        if path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            files.append(path)
    return sorted(files)


def _build_input_state() -> dict[str, dict[str, int]]:
    return {
        str(path.relative_to(FRONTEND)): {
            "mtime_ns": path.stat().st_mtime_ns,
            "size": path.stat().st_size,
        }
        for path in _build_inputs()
    }


def write_build_manifest() -> None:
    manifest = _build_manifest_path()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"schema_version": 1, "inputs": _build_input_state()}, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_is_stale() -> bool:
    built = FRONTEND / "dist" / "index.html"
    if not built.is_file():
        return True
    manifest = _build_manifest_path()
    if manifest.is_file():
        try:
            recorded = json.loads(manifest.read_text(encoding="utf-8"))
            return recorded.get("inputs") != _build_input_state()
        except (OSError, ValueError, TypeError):
            return True
    # An ordinary ``npm run build`` does not record the historical input set.
    # Current mtimes therefore cannot prove that an input was not deleted after
    # that build.  Require one managed rebuild before trusting the artifact.
    return True


def _require_free_port(port: int) -> None:
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"127.0.0.1:{port} 已被占用；未停止现有进程") from exc


def _terminate_owned(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    deadline = time.monotonic() + 8
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=4173)
    parser.add_argument("--build", action="store_true", help="构建过期时先重新构建")
    parser.add_argument("--check", action="store_true", help="只检查构建与端口，不启动")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    stale = build_is_stale()
    if stale and args.build:
        result = subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=False)
        if result.returncode:
            return result.returncode
        write_build_manifest()
        stale = build_is_stale()
    if stale:
        print(
            "前端正式构建不存在或已过期；请先运行 scripts/start_daily.py --build", file=sys.stderr
        )
        return 2
    _require_free_port(args.backend_port)
    _require_free_port(args.frontend_port)
    if args.check:
        print("daily startup preflight: ready")
        return 0

    environment = os.environ.copy()
    environment.update(
        SPOTIFY_STATS_WARMUP="1",
        SPOTIFY_STATS_WARMUP_MODE="minimal",
        FRONTEND_ORIGIN=f"http://127.0.0.1:{args.frontend_port}",
        VITE_BACKEND_URL=f"http://127.0.0.1:{args.backend_port}",
    )
    python = ROOT / ".venv" / "bin" / "python"
    python_command = str(python) if python.is_file() else sys.executable
    processes: list[subprocess.Popen] = []
    interrupted = False

    def request_stop(_signum, _frame):
        nonlocal interrupted
        interrupted = True

    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        processes.append(
            subprocess.Popen(
                [
                    python_command,
                    "-m",
                    "uvicorn",
                    "backend.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.backend_port),
                ],
                cwd=ROOT,
                env=environment,
                start_new_session=True,
            )
        )
        processes.append(
            subprocess.Popen(
                [
                    "npm",
                    "run",
                    "preview",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.frontend_port),
                    "--strictPort",
                ],
                cwd=FRONTEND,
                env=environment,
                start_new_session=True,
            )
        )
        while not interrupted and all(process.poll() is None for process in processes):
            time.sleep(0.2)
        return next((process.returncode for process in processes if process.returncode), 0)
    finally:
        _terminate_owned(processes)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
