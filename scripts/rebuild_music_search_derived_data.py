#!/usr/bin/env python3
"""Rebuild and audit the active six-variant music-search snapshot set."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402
from backend.core.db import get_db  # noqa: E402
from backend.core.migrations import MIGRATIONS, run_migrations  # noqa: E402
from backend.domains.music_search.context import (  # noqa: E402
    MUSIC_SEARCH_CHART_BUILDER_VERSION,
    MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION,
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
)
from backend.services.music_search_maintenance_service import (  # noqa: E402
    rebuild_current_music_search_derived_data,
)

EXPECTED_VARIANTS = frozenset(
    (merge_level, dynamic_threshold)
    for merge_level in (1, 2, 3)
    for dynamic_threshold in (False, True)
)
PRIVACY_REPORT = {
    "raw_query_emitted": False,
    "entity_content_emitted": False,
    "listening_history_rows_emitted": False,
    "database_path_emitted": False,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild music-search documents and the six-variant snapshot set"
    )
    parser.add_argument("--db-path", type=Path, default=Path(db_mod.DB_PATH))
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Deprecated compatibility flag; adaptive reuse is now the default",
    )
    parser.add_argument(
        "--rebuild-documents",
        action="store_true",
        help="Force a candidate-index generation rebuild; statistics still reuse exact fingerprints",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write one privacy-safe JSON report to stdout",
    )
    parser.add_argument(
        "--require-all-ready",
        action="store_true",
        help="Exit non-zero unless exactly all six supported variants are ready",
    )
    parser.add_argument(
        "--statistics-reuse-only",
        action="store_true",
        help=(
            "Fail before rebuilding candidates or statistics unless all six exact "
            "statistics variants can be reused"
        ),
    )
    args = parser.parse_args(argv)
    if args.snapshot_only and args.rebuild_documents:
        parser.error("--snapshot-only and --rebuild-documents cannot be combined")
    return args


def _file_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _storage_sizes(db_path: Path) -> dict[str, int]:
    database_bytes = _file_bytes(db_path)
    wal_bytes = _file_bytes(Path(f"{db_path}-wal"))
    return {
        "database_bytes": database_bytes,
        "wal_bytes": wal_bytes,
        "combined_bytes": database_bytes + wal_bytes,
    }


def _storage_report(before: dict[str, int], after: dict[str, int]) -> dict[str, Any]:
    return {
        "before": before,
        "after": after,
        "delta": {key: after[key] - before[key] for key in before},
    }


def _peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes; Linux (including the production image) reports KiB.
    return peak if sys.platform == "darwin" else peak * 1024


def _resource_report() -> dict[str, int | float | str]:
    peak_bytes = _peak_rss_bytes()
    return {
        "metric": "process_ru_maxrss",
        "peak_rss_bytes": peak_bytes,
        "peak_rss_mib": round(peak_bytes / (1024 * 1024), 3),
    }


def _migration_report(conn: Any) -> dict[str, int | bool]:
    applied_versions = {
        int(row[0]) for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    target_versions = {version for version, _name, _fn in MIGRATIONS}
    applied_version = max(applied_versions, default=0)
    target_version = max(target_versions, default=0)
    missing_count = len(target_versions - applied_versions)
    return {
        "applied_version": applied_version,
        "target_version": target_version,
        "applied_count": len(applied_versions),
        "expected_count": len(target_versions),
        "missing_count": missing_count,
        "up_to_date": missing_count == 0,
    }


def _snapshot_inventory(conn: Any) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """SELECT filter_fingerprint, status, builder_version, semantic_base_key
           FROM music_search_snapshot_meta"""
    ).fetchall()
    return {
        str(row[0]): {
            "status": str(row[1] or "unavailable"),
            "builder_version": str(row[2] or ""),
            "semantic_base_key": str(row[3] or ""),
        }
        for row in rows
    }


def _snapshot_base_counts(conn: Any, semantic_base_key: str) -> dict[str, int]:
    row = conn.execute(
        """SELECT COUNT(*), COUNT(DISTINCT filter_fingerprint)
           FROM music_search_snapshot_meta WHERE semantic_base_key=?""",
        (semantic_base_key,),
    ).fetchone()
    row_count = int(row[0]) if row is not None else 0
    unique_count = int(row[1]) if row is not None else 0
    return {
        "row_count": row_count,
        "unique_fingerprint_count": unique_count,
        "duplicate_fingerprint_count": max(0, row_count - unique_count),
    }


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _safe_variant(raw: dict[str, Any]) -> dict[str, Any]:
    fingerprint = str(raw.get("filter_fingerprint") or raw.get("snapshot_key") or "")
    report: dict[str, Any] = {
        "merge_level": int(raw.get("merge_level") or 0),
        "dynamic_threshold": _as_bool(raw.get("dynamic_threshold")),
        "status": str(raw.get("status") or "unavailable"),
        "fingerprint": fingerprint,
        "entity_count": max(0, int(raw.get("entity_count") or 0)),
        "elapsed_ms": max(0.0, round(float(raw.get("duration_ms") or 0.0), 3)),
        "reused": bool(raw.get("revalidated")),
        "reuse_reason": (
            str(raw.get("reuse_reason") or "exact_statistics_fingerprint_ready")
            if raw.get("revalidated")
            else None
        ),
    }
    if report["status"] != "ready" and raw.get("error_type"):
        report["failure_type"] = str(raw["error_type"])
    return report


def _gate_report(
    variants: list[dict[str, Any]],
    *,
    require_all_ready: bool,
) -> dict[str, Any]:
    reported_keys = {
        (int(variant["merge_level"]), bool(variant["dynamic_threshold"])) for variant in variants
    }
    fingerprints = [str(variant["fingerprint"]) for variant in variants]
    ready_count = sum(variant["status"] == "ready" for variant in variants)
    all_reported_ready = bool(variants) and ready_count == len(variants)
    exact_variant_set = (
        len(variants) == len(EXPECTED_VARIANTS)
        and reported_keys == EXPECTED_VARIANTS
        and len(fingerprints) == len(set(fingerprints))
        and all(fingerprints)
    )
    all_six_ready = all_reported_ready and exact_variant_set
    passed = all_reported_ready and (all_six_ready or not require_all_ready)
    return {
        "require_all_ready": require_all_ready,
        "expected_variant_count": len(EXPECTED_VARIANTS),
        "reported_variant_count": len(variants),
        "ready_variant_count": ready_count,
        "all_reported_ready": all_reported_ready,
        "exact_variant_set": exact_variant_set,
        "all_six_ready": all_six_ready,
        "passed": passed,
    }


def _idempotency_report(
    variants: list[dict[str, Any]],
    *,
    prior_inventory: dict[str, dict[str, Any]],
    base_counts: dict[str, int],
    documents_rebuilt: bool,
) -> dict[str, Any]:
    reused_ready_count = sum(
        bool(variant.get("reused"))
        or (
            prior_inventory.get(str(variant["fingerprint"]), {}).get("status") == "ready"
            and prior_inventory.get(str(variant["fingerprint"]), {}).get("builder_version")
            == MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
        )
        for variant in variants
    )
    all_preexisting = bool(variants) and reused_ready_count == len(variants)
    repeat_safe = base_counts["duplicate_fingerprint_count"] == 0 and base_counts[
        "unique_fingerprint_count"
    ] == len(variants)
    if all_preexisting and documents_rebuilt:
        classification = "rebuilt_candidate_index_revalidated_statistics"
    elif all_preexisting:
        classification = "revalidated_existing_snapshot_set"
    elif documents_rebuilt:
        classification = "rebuilt_documents_and_snapshot_set"
    else:
        classification = "rebuilt_snapshot_set_on_existing_documents"
    return {
        "classification": classification,
        "documents_rebuilt": documents_rebuilt,
        "documents_reused": not documents_rebuilt,
        "preexisting_ready_variant_count": reused_ready_count,
        "all_variants_preexisting_ready": all_preexisting,
        "snapshot_rows_for_semantic_base": base_counts["row_count"],
        "unique_fingerprint_count": base_counts["unique_fingerprint_count"],
        "duplicate_fingerprint_count": base_counts["duplicate_fingerprint_count"],
        "repeat_safe": repeat_safe,
    }


def _success_report(
    raw_report: dict[str, Any],
    *,
    require_all_ready: bool,
    prior_inventory: dict[str, dict[str, Any]],
    base_counts: dict[str, int],
    migration: dict[str, int | bool],
    elapsed_ms: float,
    storage: dict[str, Any],
) -> dict[str, Any]:
    snapshot_set = raw_report.get("snapshot_set") or {}
    variants = [_safe_variant(raw) for raw in snapshot_set.get("variants") or []]
    gate = _gate_report(variants, require_all_ready=require_all_ready)
    semantic_base_key = str(snapshot_set.get("semantic_base_key") or "")
    status = "ready" if gate["all_six_ready"] else ("partial" if variants else "failed")
    idempotency = _idempotency_report(
        variants,
        prior_inventory=prior_inventory,
        base_counts=base_counts,
        documents_rebuilt=raw_report.get("index") is not None,
    )
    gate["migration_up_to_date"] = bool(migration["up_to_date"])
    gate["repeat_safe"] = bool(idempotency["repeat_safe"])
    gate["passed"] = bool(
        gate["passed"]
        and gate["migration_up_to_date"]
        and (gate["repeat_safe"] or not require_all_ready)
    )
    return {
        "status": status,
        "semantic_base_key": semantic_base_key,
        "candidate_index": raw_report.get("candidate_index")
        or {
            "action": "rebuilt" if raw_report.get("index") is not None else "revalidated",
            "reasons": [],
            "candidate_index_version": (raw_report.get("index") or {}).get(
                "candidate_index_version"
            ),
            "content_digest": (raw_report.get("index") or {}).get("content_digest"),
            "generation_id": (raw_report.get("index") or {}).get("generation_id"),
        },
        "builder": {
            "filter_fingerprint_version": MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION,
            "snapshot_builder_version": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            "chart_builder_version": MUSIC_SEARCH_CHART_BUILDER_VERSION,
        },
        "migration": migration,
        "variants": variants,
        "snapshot_elapsed_ms": max(0.0, round(float(snapshot_set.get("duration_ms") or 0.0), 3)),
        "total_elapsed_ms": max(0.0, round(elapsed_ms, 3)),
        "resources": _resource_report(),
        "storage": storage,
        "idempotency": idempotency,
        "gate": gate,
        "privacy": PRIVACY_REPORT,
    }


def _error_report(
    *,
    stage: str,
    error_type: str,
    elapsed_ms: float,
    storage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": {"stage": stage, "type": error_type, "message_emitted": False},
        "total_elapsed_ms": max(0.0, round(elapsed_ms, 3)),
        "resources": _resource_report(),
        "storage": storage,
        "privacy": PRIVACY_REPORT,
    }


def _print_human(report: dict[str, Any]) -> None:
    gate = report["gate"]
    print(
        "Music-search derived data: "
        f"status={report['status']} ready={gate['ready_variant_count']}/"
        f"{gate['expected_variant_count']} total_elapsed_ms={report['total_elapsed_ms']} "
        f"peak_rss_mib={report['resources']['peak_rss_mib']}"
    )
    print(f"  semantic_base={report['semantic_base_key']}")
    print(
        "  migration="
        f"{report['migration']['applied_version']}/{report['migration']['target_version']} "
        f"snapshot_builder={report['builder']['snapshot_builder_version']} "
        f"chart_builder={report['builder']['chart_builder_version']}"
    )
    for variant in report["variants"]:
        print(
            "  "
            f"L{variant['merge_level']} "
            f"dynamic={str(variant['dynamic_threshold']).lower()} "
            f"status={variant['status']} fingerprint={variant['fingerprint']} "
            f"entities={variant['entity_count']} elapsed_ms={variant['elapsed_ms']}"
        )
    storage = report["storage"]
    print(
        "  storage_delta_bytes="
        f"db:{storage['delta']['database_bytes']} "
        f"wal:{storage['delta']['wal_bytes']} "
        f"combined:{storage['delta']['combined_bytes']}"
    )
    print(
        "  idempotency="
        f"{report['idempotency']['classification']} "
        f"repeat_safe={str(report['idempotency']['repeat_safe']).lower()}"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = args.db_path.expanduser().resolve()
    started = time.perf_counter()
    before_storage = _storage_sizes(db_path)
    if not db_path.is_file():
        report = _error_report(
            stage="database_validation",
            error_type="DatabaseNotFound",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            storage=_storage_report(before_storage, _storage_sizes(db_path)),
        )
        if args.json:
            print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        else:
            print("music-search derived rebuild failed: database not found", file=sys.stderr)
        return 2

    db_mod.DB_PATH = str(db_path)
    conn = None
    stage = "migrations"
    try:
        run_migrations()
        stage = "database_open"
        conn = get_db(readonly=False)
        migration = _migration_report(conn)
        prior_inventory = _snapshot_inventory(conn)
        stage = "derived_rebuild"
        if args.statistics_reuse_only:
            raw_report = rebuild_current_music_search_derived_data(
                conn,
                rebuild_documents=args.rebuild_documents,
                statistics_reuse_only=True,
            )
        else:
            raw_report = rebuild_current_music_search_derived_data(
                conn,
                rebuild_documents=args.rebuild_documents,
            )
        semantic_base_key = str(
            (raw_report.get("snapshot_set") or {}).get("semantic_base_key") or ""
        )
        base_counts = _snapshot_base_counts(conn, semantic_base_key)
    except Exception as exc:
        if conn is not None:
            conn.close()
        conn = None
        report = _error_report(
            stage=stage,
            error_type=type(exc).__name__,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            storage=_storage_report(before_storage, _storage_sizes(db_path)),
        )
        if args.json:
            print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        else:
            print(
                f"music-search derived rebuild failed: stage={stage} type={type(exc).__name__}",
                file=sys.stderr,
            )
        return 1
    finally:
        if conn is not None:
            conn.close()

    report = _success_report(
        raw_report,
        require_all_ready=args.require_all_ready,
        prior_inventory=prior_inventory,
        base_counts=base_counts,
        migration=migration,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        storage=_storage_report(before_storage, _storage_sizes(db_path)),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
