from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_032, migrate_034, migrate_035
from backend.domains.music_search import context as context_module
from backend.domains.music_search import index as index_module
from backend.domains.music_search import normalization as normalization_module
from backend.domains.music_search.context import build_music_search_filter_context
from backend.domains.music_search.index import expected_candidate_index_version
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
    migrate_035(conn)
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


def test_random_index_generation_does_not_change_statistics_fingerprint() -> None:
    conn = _conn()
    first = build_music_search_filter_context(conn, _filters())
    conn.execute(
        "UPDATE music_search_index_state SET active_generation_id='another-random-generation'"
    )
    second = build_music_search_filter_context(conn, _filters())

    assert first.semantic_base_key == second.semantic_base_key
    assert first.filter_fingerprint == second.filter_fingerprint


def test_candidate_revision_changes_index_version_but_not_statistics() -> None:
    conn = _conn()
    before_statistics = build_music_search_filter_context(conn, _filters())
    before_index = expected_candidate_index_version(conn)

    bump_music_search_revisions(conn, "candidate")

    after_statistics = build_music_search_filter_context(conn, _filters())
    after_index = expected_candidate_index_version(conn)
    assert before_statistics.filter_fingerprint == after_statistics.filter_fingerprint
    assert before_index != after_index


@pytest.mark.parametrize(
    ("column", "value"),
    (
        ("active_generation_id", "random-generation-v3"),
        ("normalization_version", "candidate-normalization-v3"),
        ("tokenizer", "candidate-tokenizer-v3"),
        ("candidate_index_version", "candidate-builder-v3"),
        ("content_digest", "candidate-content-v3"),
        ("source_revision", "candidate-source-v3"),
    ),
)
def test_candidate_index_state_is_not_part_of_statistics_identity(column, value) -> None:
    conn = _conn()
    before = build_music_search_filter_context(conn, _filters())

    conn.execute(f'UPDATE music_search_index_state SET "{column}"=? WHERE state_id=1', (value,))

    after = build_music_search_filter_context(conn, _filters())
    assert after.semantic_base_key == before.semantic_base_key
    assert after.filter_fingerprint == before.filter_fingerprint
    assert after.source_revision == before.source_revision


@pytest.mark.parametrize("revision_kind", ("playback", "billboard", "metadata", "settings"))
def test_real_statistics_revision_changes_statistics_identity(revision_kind) -> None:
    conn = _conn()
    before = build_music_search_filter_context(conn, _filters())

    bump_music_search_revisions(conn, revision_kind)

    after = build_music_search_filter_context(conn, _filters())
    assert after.semantic_base_key != before.semantic_base_key
    assert after.filter_fingerprint != before.filter_fingerprint
    assert after.source_revision != before.source_revision


@pytest.mark.parametrize(
    ("table_name", "create_sql"),
    (
        (
            "artist_identity_state",
            """CREATE TABLE artist_identity_state(
                   state_id INTEGER PRIMARY KEY,
                   current_revision INTEGER NOT NULL,
                   active_aggregate_revision INTEGER NOT NULL,
                   rebuild_status TEXT NOT NULL,
                   last_error TEXT,
                   updated_at TEXT
               )""",
        ),
        (
            "track_credit_state",
            """CREATE TABLE track_credit_state(
                   state_id INTEGER PRIMARY KEY,
                   current_revision INTEGER NOT NULL,
                   active_aggregate_revision INTEGER NOT NULL,
                   rebuild_status TEXT NOT NULL,
                   last_error TEXT,
                   updated_at TEXT
               )""",
        ),
    ),
)
def test_real_identity_or_credit_revision_changes_statistics_identity(
    table_name,
    create_sql,
) -> None:
    conn = _conn()
    conn.execute(create_sql)
    conn.execute(
        f"""INSERT INTO {table_name}(
               state_id, current_revision, active_aggregate_revision, rebuild_status
           ) VALUES (1, 0, 0, 'ready')"""
    )
    before = build_music_search_filter_context(conn, _filters())

    conn.execute(
        f"""UPDATE {table_name}
            SET current_revision=1, active_aggregate_revision=1
            WHERE state_id=1"""
    )

    after = build_music_search_filter_context(conn, _filters())
    assert after.semantic_base_key != before.semantic_base_key
    assert after.filter_fingerprint != before.filter_fingerprint
    assert after.source_revision != before.source_revision


@pytest.mark.parametrize(
    "constant_name",
    ("MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION", "MUSIC_SEARCH_CHART_BUILDER_VERSION"),
)
def test_statistics_builder_version_changes_statistics_identity(
    monkeypatch,
    constant_name,
) -> None:
    conn = _conn()
    before = build_music_search_filter_context(conn, _filters())

    monkeypatch.setattr(context_module, constant_name, "statistics-builder-next")

    after = build_music_search_filter_context(conn, _filters())
    assert after.semantic_base_key != before.semantic_base_key
    assert after.filter_fingerprint != before.filter_fingerprint


@pytest.mark.parametrize("component", ("builder", "normalization", "tokenizer"))
def test_candidate_persistent_builder_changes_only_candidate_version(
    monkeypatch,
    component,
) -> None:
    conn = _conn()
    before_statistics = build_music_search_filter_context(conn, _filters())
    before_candidate = expected_candidate_index_version(conn)

    if component == "builder":
        monkeypatch.setattr(index_module, "INDEX_SCHEMA_VERSION", "candidate-builder-next")
    elif component == "normalization":
        monkeypatch.setattr(index_module, "SEARCH_NORMALIZATION_VERSION", "normalization-next")
    else:
        monkeypatch.setattr(
            index_module,
            "inspect_search_index_runtime",
            lambda _conn: index_module.SearchIndexRuntime(
                fts5=False,
                trigram=False,
                status="degraded",
                tokenizer="tokenizer-next",
            ),
        )

    after_statistics = build_music_search_filter_context(conn, _filters())
    after_candidate = expected_candidate_index_version(conn)
    assert after_candidate != before_candidate
    assert after_statistics.semantic_base_key == before_statistics.semantic_base_key
    assert after_statistics.filter_fingerprint == before_statistics.filter_fingerprint


def test_query_only_expansion_version_reuses_both_persisted_identities(monkeypatch) -> None:
    conn = _conn()
    before_statistics = build_music_search_filter_context(conn, _filters())
    before_candidate = expected_candidate_index_version(conn)

    monkeypatch.setattr(
        normalization_module,
        "CHINESE_SEARCH_EXPANSION_VERSION",
        "query-only-expansion-next",
    )

    after_statistics = build_music_search_filter_context(conn, _filters())
    after_candidate = expected_candidate_index_version(conn)
    assert after_candidate == before_candidate
    assert after_statistics.semantic_base_key == before_statistics.semantic_base_key
    assert after_statistics.filter_fingerprint == before_statistics.filter_fingerprint
