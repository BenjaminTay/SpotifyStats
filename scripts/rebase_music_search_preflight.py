#!/usr/bin/env python3
"""Transplant a verified search snapshot onto a newer source-equivalent backup."""

from __future__ import annotations

import argparse
import hashlib
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

from backend.core import db as db_mod  # noqa: E402
from backend.core.migrations import migrate_035, migrate_036, run_migrations  # noqa: E402
from backend.domains.metadata.artist_identity import get_identity_revision  # noqa: E402
from backend.domains.metadata.track_credits import (  # noqa: E402
    TRACK_CREDIT_POLICY_VERSION,
    get_track_credit_revision,
)
from backend.domains.metadata.track_identity import get_track_identity_revision  # noqa: E402
from backend.domains.music_search.context import (  # noqa: E402
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
from backend.services.analysis_snapshot_revision import COMMON, RECORDS, TASTE  # noqa: E402
from backend.services.music_search_maintenance_service import (  # noqa: E402
    _current_filter_values,
)

DERIVED_TABLES = (
    "music_search_documents_fts",
    "music_search_document_ngrams",
    "music_search_documents",
    "music_search_index_state",
    "music_search_snapshot_meta",
    "music_search_entity_context",
    "music_search_candidate_maintenance_state",
    "music_search_snapshot_variant_state",
    "music_search_weekly_chart_context",
    "music_search_year_end_meta",
    "music_search_entity_year_end",
    "music_search_year_end_projection_state",
    "agg_weekly_tracks",
    "agg_weekly_albums",
    "agg_weekly_track_sources",
    "agg_weekly_artists",
    "agg_config",
)
AGGREGATE_TABLES = tuple(table for table in DERIVED_TABLES if table.startswith("agg_"))
SCOPED_SNAPSHOT_TABLES = frozenset(
    {
        "music_search_snapshot_meta",
        "music_search_entity_context",
        "music_search_weekly_chart_context",
        "music_search_year_end_meta",
        "music_search_entity_year_end",
        "music_search_year_end_projection_state",
    }
)
SOURCE_TABLES = tuple(
    dict.fromkeys(
        (
            *COMMON,
            *RECORDS,
            *TASTE,
            "spotify_track_credit_sets",
            "spotify_track_artist_credits",
            "spotify_track_credit_events",
            "spotify_album_credit_sets",
            "spotify_album_credit_events",
            "track_credit_events",
            "track_credit_change_sets",
            "artist_identity_events",
            "track_identity_events",
            "version_governance_events",
            "track_group_migration_audit",
            "settings",
        )
    )
)
EXPECTED_VARIANTS = {(level, dynamic) for level in (2, 3) for dynamic in (False, True)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-db", type=Path, required=True)
    parser.add_argument("--quiescent-db", type=Path, required=True)
    parser.add_argument("--staged-db", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    return parser.parse_args()


def _connect(path: Path, *, readonly: bool, sealed: bool = False) -> sqlite3.Connection:
    if not path.is_file():
        raise ValueError(f"database does not exist: {path.name}")
    if readonly:
        suffix = "&immutable=1" if sealed else ""
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro{suffix}", uri=True)
    else:
        conn = sqlite3.connect(path, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _migration_34_ready(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM schema_migrations WHERE version=34").fetchone() is not None


def _source_contents(conn: sqlite3.Connection) -> dict[str, str]:
    """Offline exact source proof, including governance and its audit history.

    Aggregates and publication readiness are outputs. Their installation may
    change while the raw rows and current human decisions stay identical.
    """
    values = {}
    for table in SOURCE_TABLES:
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        if not info:
            values[table] = "absent"
            continue
        excluded = (
            {"active_aggregate_revision", "rebuild_status", "last_error", "updated_at"}
            if table in {"track_credit_state", "artist_identity_state"}
            else set()
        )
        if table.endswith("_state"):
            # Migration-created state timestamps are administrative, unlike
            # source rows and immutable governance audit timestamps.
            excluded.add("updated_at")
        columns = [str(row[1]) for row in info if row[1] not in excluded]
        quoted = ",".join(f'"{column}"' for column in columns)
        digest = hashlib.sha256(json.dumps(columns).encode())
        cursor = conn.execute(f'SELECT json_array({quoted}) FROM "{table}" ORDER BY {quoted}')
        while rows := cursor.fetchmany(512):
            digest.update(("\n".join(str(row[0]) for row in rows) + "\n").encode())
        values[table] = digest.hexdigest()
    return values


def source_marker(path: Path, *, sealed: bool = False) -> dict[str, Any]:
    conn = _connect(path, readonly=True, sealed=sealed)
    try:
        conn.execute("BEGIN")
        if not _migration_34_ready(conn):
            raise ValueError(f"migration 34 is missing: {path.name}")
        revisions = get_music_search_revision_state(conn)
        return {
            "music_search_revisions": {
                "playback": revisions.playback_revision,
                "billboard": revisions.billboard_revision,
                "metadata": revisions.metadata_revision,
                "settings": revisions.settings_revision,
                "candidate": revisions.candidate_revision,
            },
            "playback_audit": playback_source_revision(conn),
            "source_facts": _source_contents(conn),
            "index_source": music_search_source_revision(conn),
            "identity_revision": get_identity_revision(conn),
            "track_credit_revision": get_track_credit_revision(conn),
            "filters": _current_filter_values(conn),
        }
    finally:
        conn.close()


def _ensure_identity_split_schema(path: Path) -> None:
    conn = _connect(path, readonly=False)
    try:
        has_variant_schema = _migration_34_ready(conn)
    finally:
        conn.close()
    if not has_variant_schema:
        # A still-running pre-search production image can only produce a
        # schema-33 quiescent backup.  Migrate that disposable copy in full;
        # the immutable rollback backup remains untouched.
        db_mod.DB_PATH = str(path.resolve())
        run_migrations()
        return

    conn = _connect(path, readonly=False)
    try:
        columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(music_search_index_state)")
        }
        if "candidate_index_version" not in columns:
            migrate_035(conn)
            conn.execute(
                """INSERT OR IGNORE INTO schema_migrations(version, name)
                   VALUES (35, 'music_search_candidate_statistics_identity_split')"""
            )
        ngram_schema = conn.execute("PRAGMA table_info(music_search_document_ngrams)").fetchall()
        migration_36 = conn.execute("SELECT 1 FROM schema_migrations WHERE version=36").fetchone()
        if not ngram_schema or migration_36 is None:
            # This migration deliberately invalidates the old candidate. Do
            # not rerun it on current backups, especially before drift checks.
            migrate_036(conn)
            conn.execute(
                """INSERT OR IGNORE INTO schema_migrations(version, name)
                   VALUES (36, 'music_search_candidate_ngram_index')"""
            )
        conn.commit()
    finally:
        conn.close()


def _quoted_columns(conn: sqlite3.Connection, schema: str, table: str) -> str:
    rows = conn.execute(f'PRAGMA {schema}.table_info("{table}")').fetchall()
    if not rows:
        raise ValueError(f"missing derived table: {schema}.{table}")
    return ", ".join(f'"{str(row[1])}"' for row in rows)


def _copy_derived_tables(quiescent: Path, staged: Path) -> None:
    # The explicit candidate is an offline writable artifact. Reserve it for
    # the entire proof/copy transaction so even derived-only updates cannot
    # race the aggregate readiness proof without advancing source revisions.
    candidate_lock = _connect(staged, readonly=False)
    conn = None
    attached = False
    try:
        candidate_lock.execute("BEGIN IMMEDIATE")
        expected_source = source_marker(staged)
        conn = _connect(quiescent, readonly=False)
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ATTACH DATABASE ? AS staged", (f"{staged.resolve().as_uri()}?mode=ro",))
        attached = True
        available = {
            row[0] for row in conn.execute("SELECT name FROM main.sqlite_master WHERE type='table'")
        }
        source_available = {
            row[0]
            for row in conn.execute("SELECT name FROM staged.sqlite_master WHERE type='table'")
        }
        if (set(DERIVED_TABLES) & available) != (set(DERIVED_TABLES) & source_available):
            raise ValueError("derived table inventory mismatch")
        tables = tuple(table for table in DERIVED_TABLES if table in available)
        aggregate_ready = current_aggregates_ready(staged)
        if not aggregate_ready:
            raise ValueError("candidate aggregate policy is not exact-ready")
        for table in tables:
            main_columns = _quoted_columns(conn, "main", table)
            staged_columns = _quoted_columns(conn, "staged", table)
            if main_columns != staged_columns:
                raise ValueError(f"derived table schema mismatch: {table}")
        contexts = build_music_search_variant_contexts(
            candidate_lock, _current_filter_values(candidate_lock)
        )
        snapshot_keys = tuple(context.filter_fingerprint for context in contexts)
        if len(set(snapshot_keys)) != 4:
            raise ValueError("candidate current snapshot matrix is not exact")
        placeholders = ",".join("?" for _ in snapshot_keys)
        conn.execute("BEGIN IMMEDIATE")
        with conn:
            if source_marker(quiescent) != expected_source:
                raise ValueError("search source changed before derived installation")
            for table in reversed(tables):
                if table == "music_search_snapshot_meta":
                    # Keep target historical metadata referenced by its old
                    # weekly/year-end caches; their policy keys remain stale.
                    continue
                if table in SCOPED_SNAPSHOT_TABLES:
                    conn.execute(
                        f'DELETE FROM main."{table}" WHERE snapshot_key IN ({placeholders})',
                        snapshot_keys,
                    )
                else:
                    conn.execute(f'DELETE FROM main."{table}"')
            for table in tables:
                columns = _quoted_columns(conn, "main", table)
                scoped = table in SCOPED_SNAPSHOT_TABLES
                where = f" WHERE snapshot_key IN ({placeholders})" if scoped else ""
                conn.execute(
                    f'INSERT OR REPLACE INTO main."{table}" ({columns}) SELECT {columns} FROM staged."{table}"{where}',
                    snapshot_keys if scoped else (),
                )
            for table in tables:
                if table not in SCOPED_SNAPSHOT_TABLES or table == "music_search_snapshot_meta":
                    continue
                orphan = conn.execute(
                    f'SELECT 1 FROM main."{table}" child LEFT JOIN main.music_search_snapshot_meta meta ON meta.snapshot_key=child.snapshot_key WHERE child.snapshot_key IN ({placeholders}) AND meta.snapshot_key IS NULL LIMIT 1',
                    snapshot_keys,
                ).fetchone()
                if orphan is not None:
                    raise ValueError(f"installed current snapshot has orphan rows: {table}")
            if "music_search_entity_year_end" in tables:
                orphan = conn.execute(
                    f"SELECT 1 FROM main.music_search_entity_year_end child LEFT JOIN main.music_search_year_end_meta meta ON meta.snapshot_key=child.snapshot_key AND meta.year=child.year WHERE child.snapshot_key IN ({placeholders}) AND meta.snapshot_key IS NULL LIMIT 1",
                    snapshot_keys,
                ).fetchone()
                if orphan is not None:
                    raise ValueError("installed current Year-End entity has no annual metadata")
            if aggregate_ready:
                for state in ("track_credit_state", "artist_identity_state"):
                    if state in available:
                        conn.execute(
                            f"UPDATE {state} SET active_aggregate_revision=current_revision,rebuild_status='ready',last_error=NULL,updated_at=datetime('now') WHERE state_id=1"
                        )
            if source_marker(staged) != expected_source:
                raise ValueError("search source changed during derived installation")
        conn.execute("DETACH DATABASE staged")
        attached = False
    finally:
        if attached and conn is not None:
            try:
                conn.execute("DETACH DATABASE staged")
            except sqlite3.Error:
                pass
        if conn is not None:
            conn.close()
        candidate_lock.rollback()
        candidate_lock.close()


def current_aggregates_ready(path: Path) -> bool:
    """Require installed proof when aggregates exist; tiny pre-schema fixtures have none."""
    conn = _connect(path, readonly=True)
    try:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not (set(AGGREGATE_TABLES) & tables):
            return True
        if not set(AGGREGATE_TABLES) <= tables:
            return False
        config = dict(conn.execute("SELECT key,value FROM agg_config"))
        if config.get("track_credit_policy") != TRACK_CREDIT_POLICY_VERSION:
            return False
        filters = _current_filter_values(conn)
        param_hash = db_mod._agg_param_hash(
            filters["min_ms"],
            filters["music_only"],
            filters["bb_week_start_dow"],
            filters["bb_week_start_hour"],
            dynamic_threshold=True,
            max_merge_gap_minutes=filters["max_merge_gap_minutes"],
            identity_revision=get_identity_revision(conn),
            track_credit_revision=get_track_credit_revision(conn),
            track_identity_revision=get_track_identity_revision(conn),
        )
        return db_mod.check_agg_valid(conn, param_hash)
    finally:
        conn.close()


def validate_rebased_database(path: Path) -> dict[str, Any]:
    if not current_aggregates_ready(path):
        raise ValueError("rebased aggregate policy is not exact-ready")
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
            raise ValueError("rebased database does not have four exact-ready variants")
        if len(set(ready.values())) != 4:
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
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
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
        if not args.baseline_db.is_file():
            raise ValueError("baseline rollback backup is missing")
        # The staged DB is the exact, already-validated representation of the
        # online baseline after migrations.  Compare its source marker with a
        # fully migrated quiescent copy so schema-33 production can upgrade
        # without ever mutating the rollback backup.
        baseline_marker = source_marker(args.staged_db)
        _ensure_identity_split_schema(args.quiescent_db)
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
    print("Music-search preflight rebase passed: source_equivalent=true variants=4/4 orphans=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
