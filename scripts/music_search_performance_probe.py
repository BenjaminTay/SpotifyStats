#!/usr/bin/env python3
"""Read-only performance probe for the local music-search pipeline.

The probe deliberately reports only query identifiers, lengths, timings, and
aggregate result counts. It never serializes matching entity names or the raw
search query into its report.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sqlite3
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.db import DB_PATH  # noqa: E402

PROBE_VERSION = "music_search_performance_probe_v2"
DEFAULT_QUERY_CASES: tuple[dict[str, Any], ...] = (
    {"query": "love", "query_class": "exact", "kind": None, "page": 1},
    {"query": "tay", "query_class": "prefix", "kind": None, "page": 1},
    {
        "query": "taylor swift",
        "query_class": "multi_token_cross_field",
        "kind": None,
        "page": 1,
    },
    {"query": "the", "query_class": "high_hit_three_char", "kind": None, "page": 1},
    {"query": "ＡＢＢＡ", "query_class": "unicode_nfkc", "kind": None, "page": 1},
    {"query": "周", "query_class": "single_cjk", "kind": None, "page": 1},
    {"query": "love", "query_class": "single_kind_page_2", "kind": "track", "page": 2},
)
COUNTED_TABLES = ("plays", "tracks", "albums", "artists")
CONTEXT_UNAVAILABLE_REASON = (
    "No exact ready music-search context snapshot exists for the current filter fingerprint."
)
_HTTP_CLIENT: Any | None = None


def _server_timing_values(header: str) -> dict[str, float]:
    phases: dict[str, float] = {}
    for item in header.split(","):
        name, _, attributes = item.strip().partition(";")
        for attribute in attributes.split(";"):
            key, _, value = attribute.partition("=")
            if key.strip() == "dur":
                try:
                    phases[name] = float(value)
                except ValueError:
                    pass
    return phases


def _http_client():
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        from fastapi.testclient import TestClient

        from backend.main import app

        # Deliberately do not enter the context manager: lifespan startup owns
        # maintenance workers, while the HTTP performance probe must remain a
        # pure reader against the supplied database copy.
        _HTTP_CLIENT = TestClient(app)
    return _HTTP_CLIENT


def _run_http_query(
    *,
    query: str,
    mode: str,
    limit_per_type: int,
    kind: str | None,
    page: int,
) -> dict[str, Any]:
    client = _http_client()
    params: dict[str, Any] = {
        "q": query,
        "response_mode": "candidates",
        "eligibility": "current",
        "page": page,
        "page_size": limit_per_type,
        "dynamic_threshold": True,
        "merge_level": 2,
    }
    if kind:
        params["kind"] = kind
    if mode == "http-context":
        candidate_response = client.get("/api/music/search", params=params)
        if candidate_response.status_code != 200:
            return {"status": "error", "error_type": "CandidateHTTPError"}
        candidate_payload = candidate_response.json()
        if candidate_payload.get("snapshot_status") != "ready":
            return {
                "status": "unavailable",
                "unavailable_reason": CONTEXT_UNAVAILABLE_REASON,
            }
        entity_keys = [
            item["entity_key"]
            for group in ("tracks", "albums", "artists")
            for item in candidate_payload.get(group, [])
        ][:30]
        context_params: list[tuple[str, Any]] = [
            ("dynamic_threshold", True),
            ("merge_level", 2),
            *(("entity_key", value) for value in entity_keys),
        ]
        started_at = time.perf_counter()
        response = client.get("/api/music/search/context", params=context_params)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        if response.status_code != 200:
            return {"status": "error", "error_type": "ContextHTTPError"}
        payload = response.json()
        return {
            "status": "ok",
            "elapsed_ms": round(elapsed_ms, 3),
            "phase_ms": _server_timing_values(response.headers.get("server-timing", "")),
            "result_count": len(payload.get("items", {})),
            "result_counts": {"context_items": len(payload.get("items", {}))},
            "response_bytes": len(response.content),
        }

    started_at = time.perf_counter()
    response = client.get("/api/music/search", params=params)
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    if response.status_code != 200:
        return {"status": "error", "error_type": "CandidateHTTPError"}
    payload = response.json()
    if payload.get("snapshot_status") != "ready":
        return {
            "status": "unavailable",
            "unavailable_reason": CONTEXT_UNAVAILABLE_REASON,
        }
    return {
        "status": "ok",
        "elapsed_ms": round(elapsed_ms, 3),
        "phase_ms": _server_timing_values(response.headers.get("server-timing", "")),
        "result_count": int(payload["total"]),
        "result_counts": {
            "tracks": len(payload["tracks"]),
            "albums": len(payload["albums"]),
            "artists": len(payload["artists"]),
        },
        "response_bytes": len(response.content),
    }


def open_readonly_database(path: Path) -> sqlite3.Connection:
    """Open an existing SQLite database without allowing writes or creation."""

    resolved = path.expanduser().resolve()
    uri = f"{resolved.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def sqlite_capabilities(conn: sqlite3.Connection) -> dict[str, Any]:
    """Inspect SQLite and safely exercise FTS tokenizers in an in-memory DB."""

    sqlite_version = str(conn.execute("SELECT sqlite_version()").fetchone()[0])
    compile_options = {str(row[0]) for row in conn.execute("PRAGMA compile_options").fetchall()}
    fts5_runtime = False
    trigram_runtime = False
    errors: dict[str, str] = {}
    capability_conn = sqlite3.connect(":memory:")
    try:
        try:
            capability_conn.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(body)")
            fts5_runtime = True
        except sqlite3.Error as exc:
            errors["fts5"] = type(exc).__name__
        if fts5_runtime:
            try:
                capability_conn.execute(
                    "CREATE VIRTUAL TABLE trigram_probe USING fts5(body, tokenize='trigram')"
                )
                trigram_runtime = True
            except sqlite3.Error as exc:
                errors["fts5_trigram"] = type(exc).__name__
    finally:
        capability_conn.close()
    return {
        "sqlite_version": sqlite_version,
        "fts5_compile_option": "ENABLE_FTS5" in compile_options,
        "fts5_runtime": fts5_runtime,
        "fts5_trigram_runtime": trigram_runtime,
        "capability_errors": errors,
    }


def database_metadata(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    conn = open_readonly_database(resolved)
    try:
        table_counts = {
            table_name: (
                int(conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0])
                if _table_exists(conn, table_name)
                else None
            )
            for table_name in COUNTED_TABLES
        }
        query_only = bool(conn.execute("PRAGMA query_only").fetchone()[0])
        capabilities = sqlite_capabilities(conn)
    finally:
        conn.close()
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "open_mode": "ro",
        "query_only": query_only,
        "size_bytes": stat.st_size,
        "size_mib": round(stat.st_size / (1024 * 1024), 3),
        "table_counts": table_counts,
        **capabilities,
    }


def machine_metadata() -> dict[str, Any]:
    """Return useful but non-identifying runtime facts for baseline comparison."""

    return {
        "system": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
    }


def _query_descriptors(cases: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [
        {
            "query_id": f"q{index}",
            "length": len(str(case["query"])),
            "source": source,
            "query_class": str(case["query_class"]),
            "kind": case["kind"] or "all",
            "page": int(case["page"]),
        }
        for index, case in enumerate(cases, start=1)
    ]


def _load_search_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    from backend.domains.settings.repository import SettingsRepository

    return SettingsRepository(conn).load_all()


def run_query_on_connection(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    query: str,
    mode: str,
    limit_per_type: int,
    include_chart: bool,
    kind: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    """Run one query and retain aggregate evidence only."""

    import backend.core.db as core_db
    from backend.domains.music_search.context import build_music_search_filter_context
    from backend.domains.music_search.snapshot import (
        get_music_search_snapshot_status,
        get_ready_music_search_snapshot_key,
        lookup_music_search_context,
    )
    from backend.domains.music_search.timing import MusicSearchTiming
    from backend.services.music_search_candidate_service import search_music_candidates
    from backend.services.music_search_maintenance_service import _current_filter_values
    from backend.services.music_search_service import search_music_entities

    previous_db_path = core_db.DB_PATH
    core_db.DB_PATH = str(db_path.expanduser().resolve())
    try:
        if mode in {"http-candidate", "http-context"}:
            return _run_http_query(
                query=query,
                mode=mode,
                limit_per_type=limit_per_type,
                kind=kind,
                page=page,
            )
        settings = _load_search_settings(conn)
        timing = MusicSearchTiming()
        if mode in {"candidate", "context"}:
            mode_started_at = time.perf_counter()
            snapshot_tables_ready = _table_exists(conn, "music_search_snapshot_meta")
            if mode == "context" and not snapshot_tables_ready:
                return {
                    "status": "unavailable",
                    "unavailable_reason": CONTEXT_UNAVAILABLE_REASON,
                }
            with timing.measure("fingerprint"):
                search_context = (
                    build_music_search_filter_context(
                        conn,
                        _current_filter_values(conn),
                    )
                    if snapshot_tables_ready
                    else None
                )
                snapshot_status = (
                    get_music_search_snapshot_status(
                        conn,
                        search_context.filter_fingerprint,
                    )
                    if search_context is not None
                    else "unavailable"
                )
                snapshot_key = (
                    get_ready_music_search_snapshot_key(
                        conn,
                        search_context.filter_fingerprint,
                    )
                    if search_context is not None
                    else None
                )
            if mode == "context" and snapshot_status != "ready":
                return {
                    "status": "unavailable",
                    "unavailable_reason": CONTEXT_UNAVAILABLE_REASON,
                }
            if mode == "context":
                candidate = search_music_candidates(
                    conn,
                    query=query,
                    kinds=(kind,) if kind else None,
                    page=page,
                    page_size=limit_per_type,
                    eligibility="current",
                    filter_fingerprint=search_context.filter_fingerprint,
                    snapshot_status=snapshot_status,
                    merge_level=2,
                    snapshot_key=snapshot_key,
                )
                entity_keys = [
                    item.entity_key
                    for item in [*candidate.tracks, *candidate.albums, *candidate.artists]
                ][:30]
                started_at = time.perf_counter()
                with timing.measure("total"):
                    context_result = lookup_music_search_context(
                        conn,
                        filter_fingerprint=search_context.filter_fingerprint,
                        entity_keys=entity_keys,
                    )
                elapsed_ms = (time.perf_counter() - started_at) * 1000.0
                response_bytes = len(context_result.model_dump_json().encode("utf-8"))
                return {
                    "status": "ok",
                    "elapsed_ms": round(elapsed_ms, 3),
                    "phase_ms": timing.as_dict(),
                    "result_count": len(context_result.items),
                    "result_counts": {"context_items": len(context_result.items)},
                    "response_bytes": response_bytes,
                }
            started_at = mode_started_at
            eligibility: Literal["current", "any_local"] = (
                "current" if snapshot_key is not None else "any_local"
            )
            with timing.measure("total"):
                candidate_result = search_music_candidates(
                    conn,
                    query=query,
                    kinds=(kind,) if kind else None,
                    page=page,
                    page_size=limit_per_type,
                    eligibility=eligibility,
                    filter_fingerprint=(
                        search_context.filter_fingerprint if search_context else None
                    ),
                    snapshot_status=snapshot_status,
                    merge_level=2,
                    snapshot_key=snapshot_key,
                    timing=timing,
                )
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            response_bytes = len(candidate_result.model_dump_json().encode("utf-8"))
            return {
                "status": "ok",
                "elapsed_ms": round(elapsed_ms, 3),
                "phase_ms": timing.as_dict(),
                "result_count": int(candidate_result.total),
                "result_counts": {
                    "tracks": len(candidate_result.tracks),
                    "albums": len(candidate_result.albums),
                    "artists": len(candidate_result.artists),
                },
                "response_bytes": response_bytes,
                "eligibility": eligibility,
            }
        started_at = time.perf_counter()
        with timing.measure("total"):
            legacy_result = search_music_entities(
                conn,
                query=query,
                kinds=(kind,) if kind else None,
                limit_per_type=limit_per_type,
                min_ms=int(settings["min_ms"]),
                music_only=bool(settings["music_only"]),
                merge_enabled=bool(settings["merge_enabled"]),
                dynamic_threshold=True,
                max_merge_gap_minutes=int(settings["max_merge_gap_minutes"]),
                merge_level=2,
                use_filtered_counts=mode == "end-to-end",
                include_chart=include_chart if mode == "end-to-end" else False,
                bb_top_n=int(settings["bb_top_n"]),
                bb_album_top_n=int(settings["bb_album_top_n"]),
                bb_artist_top_n=int(settings["bb_artist_top_n"]),
                bb_week_start_dow=int(settings["bb_week_start_dow"]),
                bb_week_start_hour=int(settings["bb_week_start_hour"]),
                timing=timing,
            )
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        # Serialize transiently to measure payload size, then discard the payload.
        response_bytes = len(legacy_result.model_dump_json().encode("utf-8"))
        return {
            "status": "ok",
            "elapsed_ms": round(elapsed_ms, 3),
            "phase_ms": timing.as_dict(),
            "result_count": int(legacy_result.total),
            "result_counts": {
                "tracks": len(legacy_result.tracks),
                "albums": len(legacy_result.albums),
                "artists": len(legacy_result.artists),
            },
            "response_bytes": response_bytes,
        }
    finally:
        core_db.DB_PATH = previous_db_path


def _error_result(exc: BaseException) -> dict[str, Any]:
    return {
        "status": "error",
        "error_type": type(exc).__name__,
    }


def worker_main() -> int:
    """Internal fresh-process worker. Its request travels over stdin, not argv."""

    try:
        request = json.load(sys.stdin)
        db_path = Path(request["db_path"])
        conn = open_readonly_database(db_path)
        try:
            result = run_query_on_connection(
                conn,
                db_path=db_path,
                query=str(request["query"]),
                mode=str(request["mode"]),
                limit_per_type=int(request["limit_per_type"]),
                include_chart=bool(request["include_chart"]),
                kind=str(request["kind"]) if request.get("kind") else None,
                page=int(request.get("page", 1)),
            )
        finally:
            conn.close()
    except BaseException as exc:  # pragma: no cover - parent tests error envelope
        result = _error_result(exc)
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["status"] in {"ok", "unavailable"} else 1


def run_cold_query(
    *,
    db_path: Path,
    query: str,
    mode: str,
    limit_per_type: int,
    include_chart: bool,
    kind: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    request = {
        "db_path": str(db_path.expanduser().resolve()),
        "query": query,
        "mode": mode,
        "limit_per_type": limit_per_type,
        "include_chart": include_chart,
        "kind": kind,
        "page": page,
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--_worker"],
        input=json.dumps(request, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
        cwd=PROJECT_ROOT,
    )
    if result.returncode not in {0, 1}:
        return {"status": "error", "error_type": "WorkerProcessError"}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "error_type": "WorkerProtocolError"}
    if not isinstance(payload, dict):
        return {"status": "error", "error_type": "WorkerProtocolError"}
    return payload


def _percentile_nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    ok_samples = [sample for sample in samples if sample.get("status") == "ok"]
    durations = [float(sample["elapsed_ms"]) for sample in ok_samples]
    response_sizes = [int(sample["response_bytes"]) for sample in ok_samples]
    errors = [sample for sample in samples if sample.get("status") == "error"]
    if not durations:
        return {
            "sample_count": len(samples),
            "ok_count": 0,
            "error_count": len(errors),
            "min_ms": None,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
            "max_response_bytes": None,
            "phase_p95_ms": {},
        }
    phase_names = sorted(
        {phase for sample in ok_samples for phase in (sample.get("phase_ms") or {})}
    )
    phase_p95_ms = {
        phase: round(
            _percentile_nearest_rank(
                [
                    float(sample["phase_ms"][phase])
                    for sample in ok_samples
                    if phase in (sample.get("phase_ms") or {})
                ],
                0.95,
            )
            or 0.0,
            3,
        )
        for phase in phase_names
    }
    return {
        "sample_count": len(samples),
        "ok_count": len(ok_samples),
        "error_count": len(errors),
        "min_ms": round(min(durations), 3),
        "mean_ms": round(statistics.fmean(durations), 3),
        "p50_ms": round(statistics.median(durations), 3),
        "p95_ms": round(_percentile_nearest_rank(durations, 0.95) or 0.0, 3),
        "max_ms": round(max(durations), 3),
        "max_response_bytes": max(response_sizes),
        "phase_p95_ms": phase_p95_ms,
    }


def collect_warm_profile(
    *,
    db_path: Path,
    cases: list[dict[str, Any]],
    repeat: int,
    mode: str,
    limit_per_type: int,
    include_chart: bool,
) -> dict[str, Any]:
    conn = open_readonly_database(db_path)
    samples: list[dict[str, Any]] = []
    try:
        # One unrecorded call per query establishes an explicit warm baseline.
        warmups = []
        for case in cases:
            warmups.append(
                run_query_on_connection(
                    conn,
                    db_path=db_path,
                    query=str(case["query"]),
                    mode=mode,
                    limit_per_type=limit_per_type,
                    include_chart=include_chart,
                    kind=case["kind"],
                    page=int(case["page"]),
                )
            )
        if any(sample["status"] == "unavailable" for sample in warmups):
            return {
                "condition": "warm",
                "strategy": "same_process_same_connection",
                "status": "unavailable",
                "repeat": repeat,
                "unavailable_reason": CONTEXT_UNAVAILABLE_REASON,
                "samples": [],
                "summary": summarize_samples([]),
            }
        for iteration in range(1, repeat + 1):
            for index, case in enumerate(cases, start=1):
                sample = run_query_on_connection(
                    conn,
                    db_path=db_path,
                    query=str(case["query"]),
                    mode=mode,
                    limit_per_type=limit_per_type,
                    include_chart=include_chart,
                    kind=case["kind"],
                    page=int(case["page"]),
                )
                sample.update({"query_id": f"q{index}", "iteration": iteration})
                samples.append(sample)
    finally:
        conn.close()
    return {
        "condition": "warm",
        "strategy": "same_process_same_connection",
        "status": "ok" if all(sample["status"] == "ok" for sample in samples) else "error",
        "repeat": repeat,
        "warmup_calls_per_query": 1,
        "samples": samples,
        "summary": summarize_samples(samples),
    }


def collect_cold_profile(
    *,
    db_path: Path,
    cases: list[dict[str, Any]],
    repeat: int,
    mode: str,
    limit_per_type: int,
    include_chart: bool,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for iteration in range(1, repeat + 1):
        for index, case in enumerate(cases, start=1):
            sample = run_cold_query(
                db_path=db_path,
                query=str(case["query"]),
                mode=mode,
                limit_per_type=limit_per_type,
                include_chart=include_chart,
                kind=case["kind"],
                page=int(case["page"]),
            )
            sample.update({"query_id": f"q{index}", "iteration": iteration})
            samples.append(sample)
    if samples and all(sample["status"] == "unavailable" for sample in samples):
        return {
            "condition": "cold",
            "strategy": "fresh_python_process_per_sample",
            "status": "unavailable",
            "repeat": repeat,
            "unavailable_reason": CONTEXT_UNAVAILABLE_REASON,
            "samples": [],
            "summary": summarize_samples([]),
        }
    return {
        "condition": "cold",
        "strategy": "fresh_python_process_per_sample",
        "status": "ok" if all(sample["status"] == "ok" for sample in samples) else "error",
        "repeat": repeat,
        "os_page_cache_cleared": False,
        "samples": samples,
        "summary": summarize_samples(samples),
    }


def evaluate_budgets(
    profiles: list[dict[str, Any]],
    *,
    max_p50_ms: float | None,
    max_p95_ms: float | None,
    max_warm_p95_ms: float | None,
    max_cold_p95_ms: float | None,
    max_response_kib: float | None,
    max_fingerprint_p95_ms: float | None = None,
    max_candidate_sql_p95_ms: float | None = None,
) -> list[str]:
    failures: list[str] = []
    for profile in profiles:
        if profile.get("status") != "ok":
            continue
        condition = str(profile["condition"])
        summary = profile["summary"]
        p50_ms = summary.get("p50_ms")
        p95_ms = summary.get("p95_ms")
        response_bytes = summary.get("max_response_bytes")
        phase_p95 = summary.get("phase_p95_ms") or {}
        if max_p50_ms is not None and p50_ms is not None and p50_ms > max_p50_ms:
            failures.append(f"{condition} p50 {p50_ms:.3f}ms exceeds budget {max_p50_ms:.3f}ms")
        if max_p95_ms is not None and p95_ms is not None and p95_ms > max_p95_ms:
            failures.append(f"{condition} p95 {p95_ms:.3f}ms exceeds budget {max_p95_ms:.3f}ms")
        condition_p95_budget = max_warm_p95_ms if condition == "warm" else max_cold_p95_ms
        if (
            condition_p95_budget is not None
            and p95_ms is not None
            and p95_ms > condition_p95_budget
        ):
            failures.append(
                f"{condition} p95 {p95_ms:.3f}ms exceeds condition budget "
                f"{condition_p95_budget:.3f}ms"
            )
        if (
            max_response_kib is not None
            and response_bytes is not None
            and response_bytes > max_response_kib * 1024
        ):
            failures.append(
                f"{condition} response {response_bytes} bytes exceeds budget "
                f"{max_response_kib:.3f}KiB"
            )
        for phase, budget in (
            ("fingerprint", max_fingerprint_p95_ms),
            ("candidate_query", max_candidate_sql_p95_ms),
        ):
            phase_value = phase_p95.get(phase)
            if budget is not None and phase_value is not None and phase_value > budget:
                failures.append(
                    f"{condition} {phase} p95 {phase_value:.3f}ms exceeds budget {budget:.3f}ms"
                )
    return failures


def _format_value(value: Any, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value}{suffix}"


def render_table(report: dict[str, Any]) -> str:
    database = report["database"]
    capabilities = (
        f"FTS5={'yes' if database['fts5_runtime'] else 'no'}, "
        f"trigram={'yes' if database['fts5_trigram_runtime'] else 'no'}"
    )
    lines = [
        "Music Search Performance Probe",
        f"Mode: {report['mode']} | Status: {report['status']} | Read-only: yes",
        f"Database: {database['size_mib']} MiB | SQLite {database['sqlite_version']} | "
        f"{capabilities}",
        "Table rows: "
        + ", ".join(
            f"{name}={_format_value(count)}" for name, count in database["table_counts"].items()
        ),
        f"Queries: {report['queries']['count']} ({report['queries']['source']}; raw text omitted)",
        "",
        "| Condition | Query | Run | Status | Total | Tracks | Albums | Artists | Time (ms) |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    had_samples = False
    for profile in report["profiles"]:
        for sample in profile["samples"]:
            had_samples = True
            counts = sample.get("result_counts") or {}
            lines.append(
                f"| {profile['condition']} | {sample['query_id']} | {sample['iteration']} | "
                f"{sample['status']} | {_format_value(sample.get('result_count'))} | "
                f"{_format_value(counts.get('tracks'))} | {_format_value(counts.get('albums'))} | "
                f"{_format_value(counts.get('artists'))} | "
                f"{_format_value(sample.get('elapsed_ms'))} |"
            )
    if not had_samples:
        lines.append("| n/a | n/a | 0 | unavailable | n/a | n/a | n/a | n/a | n/a |")
    lines.extend(
        [
            "",
            "| Condition | Samples | P50 (ms) | P95 (ms) | Max (ms) | Max response |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for profile in report["profiles"]:
        summary = profile["summary"]
        lines.append(
            f"| {profile['condition']} | {summary['ok_count']} | "
            f"{_format_value(summary['p50_ms'])} | {_format_value(summary['p95_ms'])} | "
            f"{_format_value(summary['max_ms'])} | "
            f"{_format_value(summary['max_response_bytes'], ' B')} |"
        )
        if profile.get("unavailable_reason"):
            lines.append(f"\nUnavailable: {profile['unavailable_reason']}")
        phase_p95 = summary.get("phase_p95_ms") or {}
        if phase_p95:
            lines.append(
                "Phase P95: " + ", ".join(f"{name}={value}ms" for name, value in phase_p95.items())
            )
    if report["budget_failures"]:
        lines.append("\nBudget failures:")
        lines.extend(f"- {failure}" for failure in report["budget_failures"])
    lines.extend(
        [
            "",
            "Privacy: raw queries, result names, links, and listening-history rows are omitted.",
            "Cold means a fresh Python process per sample; the operating-system page cache is not cleared.",
        ]
    )
    return "\n".join(lines)


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_int(value: str) -> int:
    parsed = _non_negative_int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be numeric") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="music_search_performance_probe.py",
        description="Measure music search without printing private result content.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(DB_PATH),
        help="Existing SQLite database (opened with URI mode=ro)",
    )
    parser.add_argument(
        "--mode",
        choices=("candidate", "context", "http-candidate", "http-context", "end-to-end"),
        default="candidate",
    )
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Explicit query; repeatable and omitted from all report output",
    )
    parser.add_argument("--limit-per-type", type=_positive_int, default=5)
    parser.add_argument(
        "--warm-repeat",
        type=_non_negative_int,
        default=None,
        help="Measured repeats in one warmed process/connection (default: 3 unless cold-only)",
    )
    parser.add_argument(
        "--cold",
        action="store_true",
        help="Run one cold sample per query in a fresh Python process",
    )
    parser.add_argument(
        "--cold-repeat",
        type=_non_negative_int,
        default=0,
        help="Cold fresh-process repeats per query",
    )
    parser.add_argument(
        "--exclude-chart",
        action="store_true",
        help="Exclude current Billboard calculation from end-to-end mode",
    )
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--max-p50-ms", type=_non_negative_float, default=None)
    parser.add_argument("--max-p95-ms", type=_non_negative_float, default=None)
    parser.add_argument("--max-warm-p95-ms", type=_non_negative_float, default=None)
    parser.add_argument("--max-cold-p95-ms", type=_non_negative_float, default=None)
    parser.add_argument("--max-response-kib", type=_non_negative_float, default=None)
    parser.add_argument("--max-fingerprint-p95-ms", type=_non_negative_float, default=None)
    parser.add_argument("--max-candidate-sql-p95-ms", type=_non_negative_float, default=None)
    parser.add_argument(
        "--require-available",
        action="store_true",
        help="Exit non-zero when the requested mode is unavailable",
    )
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _validated_query_cases(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser | None = None,
) -> tuple[list[dict[str, Any]], str]:
    cases = (
        [
            {
                "query": query,
                "query_class": "explicit",
                "kind": None,
                "page": 1,
            }
            for query in args.query
        ]
        if args.query
        else [dict(case) for case in DEFAULT_QUERY_CASES]
    )
    source = "explicit" if args.query else "fixed-default"
    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, int]] = set()
    for case in cases:
        value = str(case["query"]).strip()
        if not value:
            message = "queries must not be blank"
            if parser is not None:
                parser.error(message)
            raise ValueError(message)
        if len(value) > 120:
            message = "queries must not exceed 120 characters"
            if parser is not None:
                parser.error(message)
            raise ValueError(message)
        identity = (value, case["kind"], int(case["page"]))
        if identity not in seen:
            seen.add(identity)
            cleaned.append({**case, "query": value})
    return cleaned, source


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"database not found: {db_path}")
    query_cases, query_source = _validated_query_cases(args)
    cold_repeat = max(args.cold_repeat, 1 if args.cold else 0)
    warm_repeat = args.warm_repeat
    if warm_repeat is None:
        warm_repeat = 0 if cold_repeat else (60 if args.mode != "end-to-end" else 3)
    if warm_repeat == 0 and cold_repeat == 0:
        raise ValueError("at least one of --warm-repeat or --cold-repeat must be positive")

    profiles: list[dict[str, Any]] = []
    include_chart = not args.exclude_chart
    if warm_repeat:
        profiles.append(
            collect_warm_profile(
                db_path=db_path,
                cases=query_cases,
                repeat=warm_repeat,
                mode=args.mode,
                limit_per_type=args.limit_per_type,
                include_chart=include_chart,
            )
        )
    if cold_repeat:
        profiles.append(
            collect_cold_profile(
                db_path=db_path,
                cases=query_cases,
                repeat=cold_repeat,
                mode=args.mode,
                limit_per_type=args.limit_per_type,
                include_chart=include_chart,
            )
        )

    status = "ok"
    if profiles and all(profile["status"] == "unavailable" for profile in profiles):
        status = "unavailable"
    elif any(profile["status"] == "error" for profile in profiles):
        status = "error"
    budget_failures = evaluate_budgets(
        profiles,
        max_p50_ms=args.max_p50_ms,
        max_p95_ms=args.max_p95_ms,
        max_warm_p95_ms=args.max_warm_p95_ms,
        max_cold_p95_ms=args.max_cold_p95_ms,
        max_response_kib=args.max_response_kib,
        max_fingerprint_p95_ms=args.max_fingerprint_p95_ms,
        max_candidate_sql_p95_ms=args.max_candidate_sql_p95_ms,
    )
    return {
        "probe_version": PROBE_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": args.mode,
        "status": status,
        "measurement_scope": (
            "legacy_search_service_with_filtered_counts_and_optional_chart"
            if args.mode == "end-to-end"
            else "candidate_http_route_with_middleware"
            if args.mode == "http-candidate"
            else "context_http_route_with_middleware"
            if args.mode == "http-context"
            else "candidate_search_service_without_filtered_counts_or_chart"
            if args.mode == "candidate"
            else "context_snapshot_lookup"
        ),
        "database": database_metadata(db_path),
        "machine": machine_metadata(),
        "queries": {
            "source": query_source,
            "count": len(query_cases),
            "raw_text_included": False,
            "descriptors": _query_descriptors(query_cases, query_source),
        },
        "configuration": {
            "limit_per_type": args.limit_per_type,
            "include_chart": include_chart if args.mode == "end-to-end" else False,
            "warm_repeat": warm_repeat,
            "cold_repeat": cold_repeat,
            "database_open_mode": "ro",
        },
        "profiles": profiles,
        "budget_failures": budget_failures,
        "privacy": {
            "raw_query_emitted": False,
            "result_content_emitted": False,
            "listening_history_rows_emitted": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args._worker:
        return worker_main()
    try:
        report = build_report(args)
    except (FileNotFoundError, ValueError, sqlite3.Error) as exc:
        print(f"music search probe error: {exc}", file=sys.stderr)
        return 2

    print(render_table(report), flush=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"JSON report written to {args.json_output}")

    if report["budget_failures"]:
        return 1
    if report["status"] == "error":
        return 1
    if args.require_available and report["status"] == "unavailable":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
