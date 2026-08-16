#!/usr/bin/env python3
"""Prepare a source-compatible, persistent music-search rebuild workspace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402
from backend.core.migrations import run_migrations  # noqa: E402
from scripts.rebase_music_search_preflight import (  # noqa: E402
    DERIVED_TABLES,
    _copy_derived_tables,
    source_marker,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-db", type=Path, required=True)
    parser.add_argument("--resume-db", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    return parser.parse_args(argv)


def _migrate(path: Path) -> None:
    db_mod.DB_PATH = str(path.resolve())
    run_migrations()


def _validate_partial(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(path)
    try:
        orphan_count = int(
            conn.execute(
                """SELECT COUNT(*)
                   FROM music_search_entity_context context
                   LEFT JOIN music_search_snapshot_meta meta
                     ON meta.snapshot_key=context.snapshot_key
                   WHERE meta.snapshot_key IS NULL"""
            ).fetchone()[0]
        )
        if orphan_count:
            raise ValueError("resume database contains music-search context orphans")
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise ValueError("resume database integrity_check failed")
        ready_variants = int(
            conn.execute(
                """SELECT COUNT(*) FROM music_search_snapshot_meta
                   WHERE status='ready' AND builder_version='music_search_snapshot_v2'"""
            ).fetchone()[0]
        )
        counts = {
            table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in DERIVED_TABLES
        }
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return {
            "integrity_check": integrity,
            "context_orphan_count": orphan_count,
            "ready_snapshot_rows": ready_variants,
            "derived_row_counts": counts,
        }
    finally:
        conn.close()


def _recover_resume_artifact(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        if str(conn.execute("PRAGMA quick_check").fetchone()[0]) != "ok":
            raise ValueError("resume database quick_check failed")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError("JSON output already exists")
    path.parent.resolve(strict=True)
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.baseline_db.is_file():
        print("music-search resume prepare failed: baseline database is missing", file=sys.stderr)
        return 1
    args.resume_db.parent.resolve(strict=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{args.resume_db.name}.", dir=args.resume_db.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(args.baseline_db, temporary)
        _migrate(temporary)
        baseline_marker = source_marker(temporary)
        reused = False
        reuse_reason = "resume_artifact_missing"
        if args.resume_db.is_file():
            try:
                _recover_resume_artifact(args.resume_db)
                resume_marker = source_marker(args.resume_db)
                if resume_marker == baseline_marker:
                    _copy_derived_tables(temporary, args.resume_db)
                    reused = True
                    reuse_reason = "source_equivalent_resume_artifact"
                else:
                    reuse_reason = "resume_source_changed"
            except (OSError, sqlite3.Error, ValueError):
                reuse_reason = "resume_artifact_incompatible"
        validation = _validate_partial(temporary)
        os.replace(temporary, args.resume_db)
        _write_json_atomic(
            args.json_output,
            {
                "status": "ready",
                "resume_reused": reused,
                "reason": reuse_reason,
                "source_marker_fields": sorted(baseline_marker),
                "validation": validation,
                "privacy": {
                    "database_path_emitted": False,
                    "entity_content_emitted": False,
                    "listening_history_rows_emitted": False,
                },
            },
        )
    except (OSError, sqlite3.Error, ValueError) as exc:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        print(f"music-search resume prepare failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
