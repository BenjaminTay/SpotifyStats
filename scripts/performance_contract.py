"""Shared, observational measurement contract. No product imports or cache mutations."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sqlite3
import statistics
import subprocess
import time
import uuid
import zlib
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

VERSION = "spotify-performance/1"
ROOT = Path(__file__).resolve().parents[1]


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def local_url(url):
    if urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1", "testserver"}:
        raise ValueError("Performance probes only allow loopback URLs")
    return url


def metadata(db_path=None, dataset="unknown"):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    database = {
        "identity": None,
        "dataset": dataset,
        "plays": None,
        "revision": None,
        "fingerprint": None,
        "evidence": "not_observed",
    }
    if db_path:
        path = Path(db_path).resolve()
        # The checked-in seed is a closed, immutable fixture (no WAL). Normal
        # databases always keep WAL visibility; never apply immutable to a live DB.
        immutable_seed = (
            path == (ROOT / "backend/tests/fixtures/seed.db").resolve()
            and not Path(str(path) + "-wal").exists()
        )
        uri = f"{path.as_uri()}?mode=ro" + ("&immutable=1" if immutable_seed else "")
        with sqlite3.connect(uri, uri=True) as conn:
            conn.execute("PRAGMA query_only=ON")
            schema = conn.execute(
                "SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            ).fetchall()
            names = {r[0] for r in schema}
            counts = (
                conn.execute("SELECT COUNT(*),MAX(rowid) FROM plays").fetchone()
                if "plays" in names
                else (0, None)
            )
            revisions = {}
            for table in ("playback_import_state", "music_search_revision_state"):
                if table in names:
                    revisions[table] = conn.execute(f'SELECT * FROM "{table}"').fetchall()
            # No raw play rows, titles, names or credentials are emitted.
            revision = fingerprint(
                {"schema": schema, "plays_count_max_id": counts, "revision_tables": revisions}
            )
            database.update(
                identity=fingerprint(str(path)),
                plays=counts[0],
                revision=revision,
                fingerprint=revision,
                evidence="readonly_count_max_id_schema_revision_tables",
                limitation="not a complete content hash; same-count in-place edits without revision bumps need external provenance",
            )
    return {
        "schema_version": VERSION,
        "git": {"head": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))},
        "database": database,
    }


def add_context_args(parser):
    parser.add_argument(
        "--db-path", type=Path, help="Read-only identity of the DB served by this local service"
    )
    parser.add_argument(
        "--dataset", choices=["seed", "online_backup", "unknown"], default="unknown"
    )
    parser.add_argument(
        "--context-file",
        type=Path,
        help="Shared metadata JSON; caller must bind it to the measured service",
    )


def context_from_args(args):
    if getattr(args, "context_file", None):
        return json.loads(args.context_file.read_text())
    return metadata(getattr(args, "db_path", None), getattr(args, "dataset", "unknown"))


def snapshot_applicable(path):
    path = urlparse(path).path
    return path.startswith(
        ("/api/home/", "/api/billboard/", "/api/music/search", "/api/yearly-review/")
    )


def process_identity(base_url):
    parsed = urlparse(str(base_url))
    try:
        pids = subprocess.check_output(
            ["lsof", "-nP", f"-tiTCP:{parsed.port or 80}", "-sTCP:LISTEN"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).split()
        if len(pids) != 1:
            return None
        start = subprocess.check_output(["ps", "-o", "lstart=", "-p", pids[0]], text=True).strip()
        return f"{pids[0]}:{start}"
    except (OSError, subprocess.SubprocessError):
        return None


def snapshot_state(payload=None, headers=None, applicable=True):
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    payload = payload if isinstance(payload, dict) else {}
    state = {
        "state": "unknown" if applicable else "not_applicable",
        "source_revision": None,
        "target_revision": None,
        "builder_version": None,
        "request_key": None,
        "cache_key": None,
        "evidence": "not_exposed" if applicable else "no_persistent_snapshot_contract",
    }
    source = payload.get("snapshot") or {}
    detail = payload.get("detail") or {}
    if not isinstance(detail, dict):
        detail = {}
    freshness = source.get("freshness", headers.get("x-snapshot-freshness"))
    if freshness in {"current", "last_known_good"}:
        state.update(
            state="exact" if freshness == "current" else "LKG", evidence="response_metadata"
        )
    elif detail.get("error") == "snapshot_unavailable" or payload.get("snapshot_status") in {
        "unavailable",
        "missing",
    }:
        state.update(
            state="missing", evidence="response_unavailable; may_include_unreadable_or_key_error"
        )
    # Warming alone does not prove a background worker is running.
    for key in (
        "source_revision",
        "target_revision",
        "builder_version",
        "request_key",
        "cache_key",
    ):
        state[key] = source.get(
            key, detail.get(key, headers.get("x-snapshot-" + key.replace("_", "-")))
        )
    return state


def sample(
    context,
    target,
    params=None,
    *,
    process=None,
    presentation="not_applicable",
    viewport=None,
    attempt=1,
    sequence=0,
    concurrency_group=None,
    kind="api",
):
    query = list(parse_qsl(urlparse(target).query, keep_blank_values=True))
    parameters = params if params is not None else query
    return {
        **context,
        "sample_id": str(uuid.uuid4()),
        "kind": kind,
        "target": target,
        "params": parameters,
        "filter_fingerprint": fingerprint(parameters),
        "filter_fingerprint_scope": "supplied_request_params; server_defaults_not_observed",
        "presentation": presentation,
        "viewport": viewport or "not_applicable",
        "process": process
        or {"state": "unknown", "id": None, "evidence": "external_service_not_observed"},
        "snapshot": snapshot_state(),
        "attempt": attempt,
        "sequence": sequence,
        "concurrency_group": concurrency_group,
        "started_at": time.time(),
        "ended_at": None,
        "http": {
            "status": None,
            "error_type": None,
            "raw_bytes": None,
            "compressed_bytes": None,
            "content_encoding": None,
            "size_evidence": "not_observed",
        },
        "timing": {"total_ms": None, "phases_ms": {}},
        "success": False,
        "instrumentation": {
            "builder_calls": None,
            "singleflight_calls": None,
            "evidence": "not_exposed",
        },
    }


def phases(header):
    result = {}
    for entry in header.split(","):
        name, _, attrs = entry.strip().partition(";")
        for attr in attrs.split(";"):
            key, _, val = attr.partition("=")
            if key.strip() == "dur":
                try:
                    result[name] = float(val.strip('"'))
                except ValueError:
                    pass
    return result


def request(
    client,
    path,
    params=None,
    *,
    context=None,
    process=None,
    sequence=0,
    attempt=1,
    concurrency_group=None,
    headers=None,
):
    record = sample(
        context or metadata(),
        path,
        params,
        process=process,
        sequence=sequence,
        attempt=attempt,
        concurrency_group=concurrency_group,
    )
    started = time.perf_counter()
    payload = None
    try:
        with client.stream(
            "GET",
            path,
            params=params,
            headers={"Accept-Encoding": "gzip, deflate", **(headers or {})},
        ) as response:
            header_ms = (time.perf_counter() - started) * 1000
            record["http"]["status"] = response.status_code
            record["http"]["server_timing"] = response.headers.get("server-timing")
            wire = b"".join(response.iter_raw())
            body_ms = (time.perf_counter() - started) * 1000
            encoding = response.headers.get("content-encoding", "identity").lower()
            record["http"].update(
                compressed_bytes=len(wire),
                content_encoding=encoding,
                size_evidence="http_stream_body",
            )
            raw = (
                gzip.decompress(wire)
                if encoding == "gzip"
                else zlib.decompress(wire)
                if encoding == "deflate"
                else wire
            )
            record["http"]["raw_bytes"] = len(raw)
            record["timing"]["phases_ms"] = phases(response.headers.get("server-timing", ""))
            record["timing"]["phases_ms"].update(
                client_headers=round(header_ms, 3), client_body_received=round(body_ms, 3)
            )
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                record["http"]["error_type"] = "InvalidJSONResponse"
            if not 200 <= response.status_code < 300:
                record["http"]["error_type"] = f"HTTP{response.status_code}"
            elif isinstance(payload, dict) and (
                payload.get("error") or payload.get("status") in {"error", "unavailable"}
            ):
                record["http"]["error_type"] = "ApplicationError"
            if isinstance(payload, dict) and payload.get("snapshot_status") in {
                "unavailable",
                "missing",
                "error",
            }:
                record["http"]["error_type"] = "SnapshotUnavailable"
            record["snapshot"] = snapshot_state(
                payload, response.headers, applicable=snapshot_applicable(path)
            )
            record["success"] = record["http"]["error_type"] is None
    except Exception as exc:
        record["http"]["error_type"] = type(exc).__name__
    record["ended_at"] = time.time()
    record["timing"]["total_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return record, payload


def summarize(records):
    good = [r for r in records if r["success"] and r["timing"]["total_ms"] is not None]
    values = [r["timing"]["total_ms"] for r in good]
    warm = bool(good) and all(r["process"]["state"] == "warm" for r in good)
    cold_ids = {
        r["process"]["id"]
        for r in records
        if r["process"]["state"] == "cold" and r["process"]["id"]
    }
    homogeneous = (
        len(
            {
                json.dumps(
                    [
                        r["target"],
                        r["filter_fingerprint"],
                        r["presentation"],
                        r["snapshot"]["state"],
                        r["snapshot"].get("source_revision"),
                    ],
                    sort_keys=True,
                )
                for r in good
            }
        )
        <= 1
    )
    eligible = warm and len(values) >= 20 and homogeneous
    return {
        "sample_count": len(records),
        "success_count": len(good),
        "failure_count": len(records) - len(good),
        "min_ms": min(values) if values else None,
        "median_ms": statistics.median(values) if values else None,
        "p95_ms": sorted(values)[math.ceil(0.95 * len(values)) - 1] if eligible else None,
        "max_ms": max(values) if values else None,
        "observed_values_ms": values,
        "attempt_values_ms": [r["timing"]["total_ms"] for r in records],
        "failed_observed_values_ms": [r["timing"]["total_ms"] for r in records if not r["success"]],
        "statistics_scope": "warm_p95" if eligible else "observed_values_only",
        "independent_cold_processes": len(cold_ids),
        "cold_minimum_met": len(cold_ids) >= 3,
    }


def grouped_statistics(records):
    groups = {}
    for r in records:
        key = json.dumps(
            [
                r["target"],
                r["filter_fingerprint"],
                r["presentation"],
                r["process"]["state"],
                r["snapshot"]["state"],
                r["concurrency_group"] is not None,
                r.get("database", {}).get("fingerprint"),
                r["snapshot"].get("source_revision"),
                r["snapshot"].get("builder_version"),
            ],
            ensure_ascii=False,
        )
        groups.setdefault(key, []).append(r)
    return [{"group": json.loads(k), **summarize(v)} for k, v in groups.items()]


def report(tool, context, records, **extra):
    return {
        "schema_version": VERSION,
        "tool": tool,
        "generated_at": time.time(),
        "context": context,
        "samples": records,
        "statistics": grouped_statistics(records),
        **extra,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_context_args(parser)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(context_from_args(args), indent=2)
    if args.output:
        args.output.write_text(text + "\n")
    else:
        print(text)
