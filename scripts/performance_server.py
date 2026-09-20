"""Owned local process harness for independent-process observations on temporary copies."""

from __future__ import annotations

import argparse
import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def temporary_path(value):
    path = Path(value).resolve()
    roots = (Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve())
    if not any(root in path.parents for root in roots):
        raise ValueError("State injection/server paths must be inside a temporary directory")
    if path == (ROOT / "data/spotify_stats.db").resolve():
        raise ValueError("live database is prohibited")
    return path


@contextlib.contextmanager
def owned_server(db_path, snapshot_root):
    import httpx

    db_path = temporary_path(db_path)
    snapshot_root = temporary_path(snapshot_root)
    if not db_path.is_file():
        raise ValueError("Existing Online Backup/seed copy required")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--db-path",
            str(db_path),
            "--snapshot-root",
            str(snapshot_root),
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        with httpx.Client(trust_env=False, timeout=1) as client:
            while True:
                if proc.poll() is not None:
                    raise RuntimeError("Owned measurement server exited during startup")
                try:
                    if client.get(url + "/api/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("Owned server startup")
                time.sleep(0.05)  # readiness polling, never a page-completion wait
        yield url, f"{proc.pid}:{time.time_ns()}"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def serve(args):
    db_path = temporary_path(args.db_path)
    root = temporary_path(args.snapshot_root)
    sys.path.insert(0, str(ROOT))
    import dotenv

    dotenv.load_dotenv = lambda *a, **kw: False
    os.environ.update(
        SPOTIFY_STATS_WARMUP="0",
        SPOTIFY_STATS_SEARCH_STARTUP_REBUILD="0",
        SPOTIFY_STATS_L3_STARTUP_RECONCILE="0",
        SPOTIFY_STATS_BILLBOARD_CACHE_PATH=str(root / "billboard.db"),
        SPOTIFY_STATS_ANALYSIS_CACHE_PATH=str(root / "analysis.db"),
    )
    from backend.core import db

    db.DB_PATH = str(db_path)
    from backend.domains.yearly_review import artifact_cache

    artifact_cache.YEARLY_REVIEW_CACHE_PATH = str(root / "yearly_review_cache.db")
    from backend.services import home_service

    home_service._HOME_SNAPSHOT_DIR = root / "home"
    connect = socket.socket.connect

    def loopback_only(sock, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("External network disabled in measurement server")
        return connect(sock, address)

    socket.socket.connect = loopback_only
    import uvicorn

    from backend.main import app

    uvicorn.run(app, host="127.0.0.1", port=args.port, lifespan="off")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--snapshot-root", required=True)
    p.add_argument("--port", type=int, required=True)
    serve(p.parse_args())
