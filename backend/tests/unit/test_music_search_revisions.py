from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_032, migrate_034
from backend.domains.music_search.context import build_music_search_filter_context
from backend.domains.music_search.revisions import (
    bump_music_search_revisions,
    get_music_search_revision_state,
)
from backend.domains.music_search.variants import (
    MUSIC_SEARCH_SNAPSHOT_VARIANTS,
    build_music_search_variant_contexts,
)

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_032(conn)
    migrate_034(conn)
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='generation-v2', status='ready',
               source_revision='index-source-v2' WHERE state_id=1"""
    )
    conn.commit()
    return conn


def _filters() -> dict:
    return {
        "min_ms": 30_000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 5,
        "merge_level": 2,
        "include_compilations": False,
        "bb_top_n": 30,
        "bb_album_top_n": 20,
        "bb_artist_top_n": 20,
        "bb_week_start_dow": 4,
        "bb_week_start_hour": 0,
        "year_start": None,
        "year_end": None,
    }


def test_revision_bump_is_explicit_and_transactional() -> None:
    conn = _conn()

    bump_music_search_revisions(conn, "playback", "billboard", "playback")
    state = get_music_search_revision_state(conn)
    assert state.playback_revision == 1
    assert state.billboard_revision == 1
    assert state.metadata_revision == 0

    conn.rollback()
    rolled_back = get_music_search_revision_state(conn)
    assert rolled_back.playback_revision == 0
    assert rolled_back.billboard_revision == 0


def test_filter_context_reads_persistent_revision_without_scanning_source_tables() -> None:
    conn = _conn()
    bump_music_search_revisions(conn, "settings", "metadata")
    conn.commit()

    # No plays or aggregate tables exist in this fixture.  A request-time scan
    # would fail, while the persisted singleton path remains available.
    context = build_music_search_filter_context(conn, _filters())

    assert context.settings_revision == 1
    assert context.metadata_revision == 1
    assert len(context.semantic_base_key) == 64
    assert len(context.filter_fingerprint) == 64


def test_six_variants_share_base_and_have_unique_fingerprints() -> None:
    conn = _conn()
    contexts = build_music_search_variant_contexts(conn, _filters())

    assert len(contexts) == 6
    assert len({context.semantic_base_key for context in contexts}) == 1
    assert len({context.filter_fingerprint for context in contexts}) == 6
    assert [(context.merge_level, context.dynamic_threshold) for context in contexts] == [
        (variant.merge_level, variant.dynamic_threshold)
        for variant in MUSIC_SEARCH_SNAPSHOT_VARIANTS
    ]
