#!/usr/bin/env python3
"""Read-only production gate for the active music-search semantic base."""

from __future__ import annotations

from backend.core.db import get_db
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.services.music_search_maintenance_service import _current_filter_values


def main() -> int:
    conn = get_db(readonly=True)
    try:
        migration = conn.execute("SELECT 1 FROM schema_migrations WHERE version=36").fetchone()
        if migration is None:
            raise SystemExit("music-search runtime gate failed: migration 36 missing")

        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        semantic_base_key = contexts[0].semantic_base_key
        rows = conn.execute(
            """SELECT merge_level, dynamic_threshold, filter_fingerprint,
                      status, builder_version
               FROM music_search_snapshot_meta
               WHERE semantic_base_key=?""",
            (semantic_base_key,),
        ).fetchall()
        expected = {
            (context.merge_level, context.dynamic_threshold): context.filter_fingerprint
            for context in contexts
        }
        actual = {(int(row[0]), bool(row[1])): str(row[2]) for row in rows}
        if len(rows) != 6 or actual != expected:
            raise SystemExit(
                "music-search runtime gate failed: current fingerprint matrix is not exact 6/6"
            )
        if any(str(row[3]) != "ready" for row in rows):
            raise SystemExit("music-search runtime gate failed: a current variant is not ready")
        if any(str(row[4]) != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION for row in rows):
            raise SystemExit("music-search runtime gate failed: builder is not v2")

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
            raise SystemExit("music-search runtime gate failed: context orphan count is not zero")
    finally:
        conn.close()

    print(
        "Music-search runtime gate passed: "
        "migration=36 variants=6/6 builder=music_search_snapshot_v2 orphans=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
