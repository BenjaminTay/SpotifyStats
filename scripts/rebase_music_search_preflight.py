#!/usr/bin/env python3
"""Transplant a verified search snapshot onto a newer source-equivalent backup."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.domains.metadata.artist_identity import get_identity_revision  # noqa: E402
from backend.domains.metadata.track_credits import get_track_credit_revision  # noqa: E402
from backend.domains.music_search.context import (  # noqa: E402
    billboard_aggregation_revision,
    playback_source_revision,
)
from backend.domains.music_search.index import music_search_source_revision  # noqa: E402
from backend.domains.music_search.revisions import (  # noqa: E402
    get_music_search_revision_state,
)
from backend.domains.music_search.snapshot import (  # noqa: E402
    get_ready_music_search_snapshot_key,
)
from backend.domains.music_search.variants import (  # noqa: E402
    build_music_search_variant_contexts,
)
from backend.services.music_search_maintenance_service import (  # noqa: E402
    _current_filter_values,
)

DERIVED_TABLES = (
    "music_search_documents_fts",
    "music_search_documents",
    "music_search_index_state",
    "music_search_snapshot_meta",
    "music_search_entity_context",
)
EXPECTED_VARIANTS = {(level, dynamic) for level in (1, 2, 3) for dynamic in (False, True)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-db", type=Path, required=True)
    parser.add_argument("--quiescent-db", type=Path, required=True)
    parser.add_argument("--staged-db", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    return parser.parse_args()


def _connect(path: Path, *, readonly: bool) -> sqlite3.Connection:
    if not path.is_file():
        raise ValueError(f"database does not exist: {path.name}")
    if readonly:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _migration_34_ready(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM schema_migrations WHERE version=34").fetchone() is not None


def source_marker(path: Path) -> dict[str, Any]:
    conn = _connect(path, readonly=True)
    try:
        if not _migration_34_ready(conn):
            raise ValueError(f"migration 34 is missing: {path.name}")
        revisions = get_music_search_revision_state(conn)
        return {
            "music_search_revisions": {
                "playback": revisions.playback_revision,
                "billboard": revisions.billboard_revision,
                "metadata": revisions.metadata_revision,
                "settings": revisions.settings_revision,
            },
            "playback_audit": playback_source_revision(conn),
            "billboard_audit": billboard_aggregation_revision(conn),
            "index_source": music_search_source_revision(conn),
            "identity_revision": get_identity_revision(conn),
            "track_credit_revision": get_track_credit_revision(conn),
            "filters": _current_filter_values(conn),
        }
    finally:
        conn.close()


def _quoted_columns(conn: sqlite3.Connection, schema: str, table: str) -> str:
    rows = conn.execute(f'PRAGMA {schema}.table_info("{table}")').fetchall()
    if not rows:
        raise ValueError(f"missing derived table: {schema}.{table}")
    return ", ".join(f'"{str(row[1])}"' for row in rows)


def _copy_derived_tables(quiescent: Path, staged: Path) -> None:
    conn = _connect(quiescent, readonly=False)
    attached = False
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ATTACH DATABASE ? AS staged", (str(staged.resolve()),))
        attached = True
        for table in DERIVED_TABLES:
            main_columns = _quoted_columns(conn, "main", table)
            staged_columns = _quoted_columns(conn, "staged", table)
            if main_columns != staged_columns:
                raise ValueError(f"derived table schema mismatch: {table}")
        with conn:
            for table in (
                "music_search_entity_context",
                "music_search_snapshot_meta",
                "music_search_documents_fts",
                "music_search_documents",
                "music_search_index_state",
            ):
                conn.execute(f'DELETE FROM main."{table}"')
            for table in (
                "music_search_index_state",
                "music_search_documents",
                "music_search_documents_fts",
                "music_search_snapshot_meta",
                "music_search_entity_context",
            ):
                columns = _quoted_columns(conn, "main", table)
                conn.execute(
                    f'INSERT INTO main."{table}" ({columns}) SELECT {columns} FROM staged."{table}"'
                )
        conn.execute("DETACH DATABASE staged")
        attached = False
    finally:
        if attached:
            try:
                conn.execute("DETACH DATABASE staged")
            except sqlite3.Error:
                pass
        conn.close()


def validate_rebased_database(path: Path) -> dict[str, Any]:
    conn = _connect(path, readonly=False)
    try:
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        variants = {(context.merge_level, context.dynamic_threshold) for context in contexts}
        if variants != EXPECTED_VARIANTS:
            raise ValueError("current search variant matrix is not exact")
        ready = {
            (context.merge_level, context.dynamic_threshold): context.filter_fingerprint
            for context in contexts
            if get_ready_music_search_snapshot_key(conn, context.filter_fingerprint) is not None
        }
        if set(ready) != EXPECTED_VARIANTS:
            raise ValueError("rebased database does not have six exact-ready variants")
        if len(set(ready.values())) != 6:
            raise ValueError("rebased search fingerprints are not unique")
        orphan_count = int(
            conn.execute(
                """SELECT COUNT(*)
                   FROM music_search_entity_context context
                   LEFT JOIN music_search_snapshot_meta meta
                     ON meta.snapshot_key=context.snapshot_key
                   WHERE meta.snapshot_key IS NULL"""
            ).fetchone()[0]
        )
        if orphan_count != 0:
            raise ValueError("rebased search context contains orphans")
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise ValueError("rebased database integrity_check failed")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
        counts = {
            table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in DERIVED_TABLES
        }
        return {
            "integrity_check": integrity,
            "context_orphan_count": orphan_count,
            "ready_variants": len(ready),
            "unique_fingerprints": len(set(ready.values())),
            "derived_row_counts": counts,
        }
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


def main() -> int:
    args = parse_args()
    try:
        baseline_marker = source_marker(args.baseline_db)
        quiescent_marker = source_marker(args.quiescent_db)
        changed = sorted(
            key for key in baseline_marker if baseline_marker[key] != quiescent_marker[key]
        )
        if changed:
            raise ValueError("search source changed during preflight: " + ",".join(changed))
        _copy_derived_tables(args.quiescent_db, args.staged_db)
        validation = validate_rebased_database(args.quiescent_db)
        report = {
            "status": "ready",
            "source_equivalent": True,
            "source_marker_fields": sorted(baseline_marker),
            "validation": validation,
        }
        _write_json_atomic(args.json_output, report)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"music-search preflight rebase failed: {exc}", file=sys.stderr)
        return 1
    print("Music-search preflight rebase passed: source_equivalent=true variants=6/6 orphans=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
