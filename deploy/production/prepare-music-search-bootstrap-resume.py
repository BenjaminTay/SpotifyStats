#!/usr/bin/env python3
"""Prepare a source-compatible partial resume DB for one-time search bootstrap."""

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

CONTAINER_APP_ROOT = Path("/app")
APP_ROOT = (
    CONTAINER_APP_ROOT
    if (CONTAINER_APP_ROOT / "backend").is_dir()
    else Path(__file__).resolve().parents[2]
)
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from backend.domains.music_search.context import (  # noqa: E402
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
)
from backend.domains.music_search.variants import (  # noqa: E402
    build_music_search_variant_contexts,
)
from backend.services.music_search_maintenance_service import (  # noqa: E402
    _current_filter_values,
)
from scripts.prepare_music_search_resume import (  # noqa: E402
    _copy_derived_tables,
    _migrate,
    _recover_resume_artifact,
    _validate_partial,
    source_marker,
)

ALLOWED_PARTIAL_STATUSES = {"pending", "running", "ready", "failed", "stale"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-db", type=Path, required=True)
    parser.add_argument("--resume-db", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    return parser.parse_args(argv)


def _has_compatible_partial_statistics(path: Path) -> bool:
    """Accept only current-fingerprint rows; completed variants remain reusable."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        if len(contexts) != 4:
            return False
        expected = {
            context.filter_fingerprint: (context.merge_level, context.dynamic_threshold)
            for context in contexts
        }
        if len(expected) != 4:
            return False
        semantic_base_keys = {context.semantic_base_key for context in contexts}
        if len(semantic_base_keys) != 1:
            return False
        semantic_base_key = next(iter(semantic_base_keys))
        placeholders = ",".join("?" for _ in expected)
        rows = conn.execute(
            f"""SELECT snapshot_key, filter_fingerprint, status, builder_version,
                       merge_level, dynamic_threshold
                FROM music_search_snapshot_meta
                WHERE semantic_base_key=?
                   OR filter_fingerprint IN ({placeholders})""",
            (semantic_base_key, *expected),
        ).fetchall()
        seen: set[str] = set()
        for row in rows:
            fingerprint = str(row[1])
            if fingerprint in seen or fingerprint not in expected:
                return False
            variant = (int(row[4]), bool(row[5]))
            if (
                str(row[0]) != fingerprint
                or str(row[2]) not in ALLOWED_PARTIAL_STATUSES
                or str(row[3]) != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
                or variant != expected[fingerprint]
            ):
                return False
            seen.add(fingerprint)
        # A source-equivalent resume with zero current rows is a valid starting
        # point; subsequent interrupted runs keep each exact-ready variant.
        return True
    except (sqlite3.Error, TypeError, ValueError):
        return False
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
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.baseline_db.is_file():
        print(
            "music-search bootstrap prepare failed: baseline database is missing", file=sys.stderr
        )
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
        reason = "resume_artifact_missing"
        if args.resume_db.is_file():
            try:
                _recover_resume_artifact(args.resume_db)
                if source_marker(args.resume_db) != baseline_marker:
                    reason = "resume_source_changed"
                elif _has_compatible_partial_statistics(args.resume_db):
                    _copy_derived_tables(temporary, args.resume_db)
                    reused = True
                    reason = "source_equivalent_partial_statistics_resume"
                else:
                    reason = "resume_statistics_incompatible"
            except (OSError, sqlite3.Error, ValueError):
                reason = "resume_artifact_incompatible"
        validation = _validate_partial(temporary)
        os.replace(temporary, args.resume_db)
        _write_json_atomic(
            args.json_output,
            {
                "status": "ready",
                "resume_reused": reused,
                "reason": reason,
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
        print(f"music-search bootstrap prepare failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
