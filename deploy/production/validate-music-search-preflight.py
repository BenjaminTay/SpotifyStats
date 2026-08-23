#!/usr/bin/env python3
"""Validate a staged production database and persist a non-sensitive report."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

# This validator is also shipped as a standalone host-side file, so it cannot
# import the backend package in production.  Keep this release contract in
# lockstep with MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION.
EXPECTED_BUILDER_VERSION = "music_search_snapshot_v3"
REQUIRED_MIGRATION_VERSION = 42
EXPECTED_VARIANTS = {
    (1, False),
    (1, True),
    (2, False),
    (2, True),
    (3, False),
    (3, True),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--rebuild-report", type=Path, required=True)
    parser.add_argument("--capacity-report", type=Path, required=True)
    parser.add_argument("--resume-report", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"music-search production preflight failed: {message}")


def load_rebuild_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("music-search production preflight failed: invalid rebuild JSON") from exc
    require(isinstance(payload, dict), "rebuild report must be an object")
    return payload


def validate_rebuild_report(
    payload: dict[str, Any],
) -> tuple[str, dict[tuple[int, bool], str]]:
    require(payload.get("status") == "ready", "rebuild status is not ready")
    semantic_base_key = payload.get("semantic_base_key")
    require(
        isinstance(semantic_base_key, str) and bool(semantic_base_key),
        "rebuild report has no semantic base key",
    )
    builder = payload.get("builder")
    require(isinstance(builder, dict), "missing builder report")
    require(
        builder.get("snapshot_builder_version") == EXPECTED_BUILDER_VERSION,
        "snapshot report builder version is not current",
    )
    migration = payload.get("migration")
    require(isinstance(migration, dict), "missing migration report")
    require(
        migration.get("up_to_date") is True
        and int(migration.get("applied_version") or 0) >= REQUIRED_MIGRATION_VERSION,
        f"migration report does not include migration {REQUIRED_MIGRATION_VERSION}",
    )
    gate = payload.get("gate")
    require(isinstance(gate, dict), "missing rebuild gate report")
    require(gate.get("require_all_ready") is True, "require-all-ready gate was not enabled")
    require(gate.get("expected_variant_count") == 6, "expected variant count is not 6")
    require(gate.get("reported_variant_count") == 6, "reported variant count is not 6")
    require(gate.get("ready_variant_count") == 6, "ready variant count is not 6")
    require(gate.get("exact_variant_set") is True, "variant set gate did not pass")
    require(gate.get("all_six_ready") is True, "all-six-ready gate did not pass")
    require(gate.get("passed") is True, "rebuild gate did not pass")
    idempotency = payload.get("idempotency")
    require(isinstance(idempotency, dict), "missing idempotency report")
    require(idempotency.get("repeat_safe") is True, "rebuild is not repeat safe")

    variants = payload.get("variants")
    require(isinstance(variants, list), "missing snapshot variants")
    require(len(variants) == 6, "snapshot report does not contain exactly six variants")

    reported_variants: dict[tuple[int, bool], str] = {}
    for variant in variants:
        require(isinstance(variant, dict), "invalid snapshot variant report")
        require(variant.get("status") == "ready", "a snapshot variant is not ready")
        merge_level = variant.get("merge_level")
        dynamic_threshold = variant.get("dynamic_threshold")
        require(
            isinstance(merge_level, int) and not isinstance(merge_level, bool),
            "snapshot report merge level is invalid",
        )
        require(
            isinstance(dynamic_threshold, bool),
            "snapshot report dynamic threshold is invalid",
        )
        fingerprint = variant.get("fingerprint")
        require(
            isinstance(fingerprint, str) and bool(fingerprint),
            "snapshot report fingerprint is missing",
        )
        reported_variants[(merge_level, dynamic_threshold)] = fingerprint
    require(
        set(reported_variants) == EXPECTED_VARIANTS,
        "snapshot report variant matrix is invalid",
    )
    require(
        len(set(reported_variants.values())) == 6,
        "snapshot report fingerprints are not unique",
    )
    return semantic_base_key, reported_variants


def load_capacity_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("music-search production preflight failed: invalid capacity JSON") from exc
    require(isinstance(payload, dict), "capacity report must be an object")
    require(payload.get("passed") is True, "host capacity gate did not pass")
    require(isinstance(payload.get("before"), dict), "capacity report has no before sample")
    require(isinstance(payload.get("after"), dict), "capacity report has no after sample")
    require(
        isinstance(payload.get("requirements"), dict),
        "capacity report has no requirements",
    )
    return payload


def validate_database(
    db_path: Path,
    semantic_base_key: str,
    reported_variants: dict[tuple[int, bool], str],
) -> dict[str, Any]:
    require(db_path.is_file(), "database copy does not exist")
    db_uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        required_migration = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=?",
            (REQUIRED_MIGRATION_VERSION,),
        ).fetchone()
        rows = conn.execute(
            """SELECT merge_level, dynamic_threshold, filter_fingerprint,
                      status, builder_version
               FROM music_search_snapshot_meta
               WHERE semantic_base_key=?""",
            (semantic_base_key,),
        ).fetchall()
        orphan_count = int(
            conn.execute(
                """SELECT COUNT(*)
                   FROM music_search_entity_context context
                   LEFT JOIN music_search_snapshot_meta meta
                     ON meta.snapshot_key=context.snapshot_key
                   WHERE meta.snapshot_key IS NULL"""
            ).fetchone()[0]
        )
    except sqlite3.Error as exc:
        raise SystemExit(
            "music-search production preflight failed: database contract query failed"
        ) from exc
    finally:
        conn.close()

    require(integrity == "ok", "database integrity_check failed")
    require(
        required_migration is not None,
        f"migration {REQUIRED_MIGRATION_VERSION} is not applied",
    )
    require(len(rows) == 6, "database does not contain exactly six current variants")
    db_variants = {(int(row[0]), bool(row[1])): str(row[2]) for row in rows}
    require(set(db_variants) == EXPECTED_VARIANTS, "database variant matrix is invalid")
    require(
        db_variants == reported_variants,
        "database fingerprints do not match the rebuild report",
    )
    require(all(row[3] == "ready" for row in rows), "database has a non-ready variant")
    require(
        all(row[4] == EXPECTED_BUILDER_VERSION for row in rows),
        "database has a non-current snapshot builder",
    )
    require(orphan_count == 0, "music-search context orphan count is not zero")
    return {
        "integrity_check": integrity,
        "required_migration_version": REQUIRED_MIGRATION_VERSION,
        "required_migration_applied": True,
        "ready_variants": len(rows),
        "required_variants": 6,
        "builder_version": EXPECTED_BUILDER_VERSION,
        "context_orphan_count": orphan_count,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=False, exist_ok=True)
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


def main() -> int:
    args = parse_args()
    rebuild = load_rebuild_report(args.rebuild_report)
    semantic_base_key, reported_variants = validate_rebuild_report(rebuild)
    host_capacity = load_capacity_report(args.capacity_report)
    validation = validate_database(args.db_path, semantic_base_key, reported_variants)
    output = dict(rebuild)
    if args.resume_report is not None:
        output["resume"] = load_rebuild_report(args.resume_report)
    output["host_capacity"] = host_capacity
    output["production_validation"] = validation
    write_json_atomic(
        args.json_output,
        output,
    )
    print(
        "Music-search production preflight passed: "
        f"migration={REQUIRED_MIGRATION_VERSION} variants=6/6 "
        f"builder={EXPECTED_BUILDER_VERSION} orphans=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
