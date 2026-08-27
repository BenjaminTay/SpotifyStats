#!/usr/bin/env python3
"""Read-only production gate for the active music-search semantic base."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from typing import Any

from backend.core.db import get_db
from backend.core.migrations import LATEST_SCHEMA_VERSION
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.normalization import expand_chinese_search_variants
from backend.domains.music_search.repository import (
    MusicSearchRepositoryResult,
    search_music_index,
)
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.services.music_search_maintenance_service import _current_filter_values


def _result_items(result: MusicSearchRepositoryResult) -> Iterable[Any]:
    yield from result.tracks
    yield from result.albums
    yield from result.artists


def _target_result(
    result: MusicSearchRepositoryResult,
    entity_key: str,
) -> Any | None:
    return next((item for item in _result_items(result) if item.entity_key == entity_key), None)


def _search(
    conn: Any,
    *,
    query: str,
    snapshot_key: str,
) -> MusicSearchRepositoryResult:
    return search_music_index(
        conn,
        query=query,
        kind=None,
        page=1,
        page_size=20,
        merge_level=2,
        snapshot_key=snapshot_key,
    )


def _verify_live_search_semantics(conn: Any, snapshot_key: str) -> dict[str, str]:
    """Exercise the active index without printing personal labels or entity keys."""
    generation_row = conn.execute(
        "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
    ).fetchone()
    generation_id = str(generation_row[0] or "") if generation_row else ""
    if not generation_id:
        raise SystemExit("music-search runtime gate failed: active candidate index missing")

    rows = conn.execute(
        """SELECT DISTINCT d.entity_key, d.normalized_label
           FROM music_search_documents d
           JOIN music_search_entity_context context
             ON context.snapshot_key=? AND context.entity_key=d.entity_key
           WHERE d.generation_id=?
             AND d.kind IN ('track', 'album_project', 'artist')
             AND (d.kind!='track' OR d.merge_level=2)
             AND d.normalized_label!=''
           ORDER BY d.entity_key""",
        (snapshot_key, generation_id),
    ).fetchall()
    if not rows:
        raise SystemExit("music-search runtime gate failed: no eligible indexed documents")

    exact_passed = False
    for entity_key, normalized_label in rows[:50]:
        result = _search(conn, query=str(normalized_label), snapshot_key=snapshot_key)
        if _target_result(result, str(entity_key)) is not None:
            exact_passed = True
            break
    if not exact_passed:
        raise SystemExit("music-search runtime gate failed: exact candidate lookup failed")

    fuzzy_passed = False
    latin_rows = [
        (str(entity_key), str(label))
        for entity_key, label in rows
        if re.fullmatch(r"[a-z]{6,12}", str(label))
    ][:25]
    for entity_key, label in latin_rows:
        positions = tuple(dict.fromkeys((1, len(label) // 2, len(label) - 2)))
        for position in positions:
            replacement = "q" if label[position] != "q" else "x"
            typo = f"{label[:position]}{replacement}{label[position + 1 :]}"
            target = _target_result(
                _search(conn, query=typo, snapshot_key=snapshot_key),
                entity_key,
            )
            if target is not None and target.match_quality == "fuzzy":
                fuzzy_passed = True
                break
        if fuzzy_passed:
            break
    if latin_rows and not fuzzy_passed:
        raise SystemExit("music-search runtime gate failed: bounded fuzzy lookup failed")

    cjk_status = "not_applicable"
    short_cjk_status = "not_applicable"
    for entity_key, label_value in rows:
        label = str(label_value)
        variants = tuple(dict.fromkeys((label, *expand_chinese_search_variants(label))))
        if len(variants) <= 1 or len(label) > 2:
            continue
        targets = [
            _target_result(_search(conn, query=query, snapshot_key=snapshot_key), str(entity_key))
            for query in variants
        ]
        if not all(targets):
            raise SystemExit("music-search runtime gate failed: Chinese variant lookup failed")
        cjk_status = "passed"
        short_cjk_status = "passed"
        break

    return {
        "exact": "passed",
        "fuzzy": "passed" if fuzzy_passed else "not_applicable",
        "cjk": cjk_status,
        "short_cjk": short_cjk_status,
    }


def main() -> int:
    started_at = time.perf_counter()
    conn = get_db(readonly=True)
    try:
        migration = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=?",
            (LATEST_SCHEMA_VERSION,),
        ).fetchone()
        if migration is None:
            raise SystemExit(
                f"music-search runtime gate failed: migration {LATEST_SCHEMA_VERSION} missing"
            )

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
        if len(rows) != 4 or actual != expected:
            raise SystemExit(
                "music-search runtime gate failed: current fingerprint matrix is not exact 4/4"
            )
        if any(str(row[3]) != "ready" for row in rows):
            raise SystemExit("music-search runtime gate failed: a current variant is not ready")
        if any(str(row[4]) != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION for row in rows):
            raise SystemExit("music-search runtime gate failed: builder is not current")

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

        verification_context = next(
            context
            for context in contexts
            if context.merge_level == 2 and context.dynamic_threshold
        )
        snapshot_row = conn.execute(
            """SELECT snapshot_key
               FROM music_search_snapshot_meta
               WHERE filter_fingerprint=? AND status='ready'""",
            (verification_context.filter_fingerprint,),
        ).fetchone()
        if snapshot_row is None:
            raise SystemExit("music-search runtime gate failed: verification snapshot missing")
        search_status = _verify_live_search_semantics(conn, str(snapshot_row[0]))
    finally:
        conn.close()

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    print(
        "Music-search runtime gate passed: "
        f"migration={LATEST_SCHEMA_VERSION} variants=4/4 "
        f"builder={MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION} orphans=0 "
        f"exact={search_status['exact']} fuzzy={search_status['fuzzy']} "
        f"cjk={search_status['cjk']} short_cjk={search_status['short_cjk']} "
        f"semantic_smoke_ms={elapsed_ms:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
