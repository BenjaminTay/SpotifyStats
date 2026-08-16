from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_032, migrate_034, migrate_035
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.services import music_search_maintenance_service as maintenance

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            ts TEXT,
            ms_played INTEGER,
            source_album_id INTEGER
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_id INTEGER,
            album_id INTEGER
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT,
            artist_id INTEGER
        );
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT
        );
        INSERT INTO artists VALUES (1, 'Artist');
        INSERT INTO albums VALUES (2, 'Album', 1);
        INSERT INTO tracks VALUES (3, 'Track', 1, 2);
        INSERT INTO plays VALUES (4, 3, '2026-01-01T00:00:00Z', 180000, 2);
        """
    )
    migrate_032(conn)
    migrate_034(conn)
    migrate_035(conn)
    conn.commit()
    return conn


def test_mark_for_rebuild_fails_closed_and_invalidates_document_revision() -> None:
    conn = _conn()
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='g1', status='ready', source_revision='source'"""
    )
    conn.execute(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status
           ) VALUES ('f1', 'f1', 'source', 'ready')"""
    )
    conn.commit()

    maintenance.mark_music_search_for_rebuild(
        reason="metadata changed",
        documents=True,
        revision_kinds=("metadata",),
        conn=conn,
    )

    assert tuple(
        conn.execute(
            "SELECT status, last_error FROM music_search_snapshot_meta WHERE snapshot_key='f1'"
        ).fetchone()
    ) == ("stale", "metadata changed")
    assert (
        conn.execute(
            "SELECT source_revision FROM music_search_index_state WHERE state_id=1"
        ).fetchone()[0]
        is None
    )
    assert (
        conn.execute(
            "SELECT metadata_revision FROM music_search_revision_state WHERE state_id=1"
        ).fetchone()[0]
        == 1
    )


def test_enqueue_uses_exact_filter_or_document_source_key(monkeypatch) -> None:
    conn = _conn()
    expected_source = maintenance.music_search_source_revision(conn)
    expected_index_version = maintenance.expected_candidate_index_version(conn)
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='g1', status='ready', source_revision=?,
               candidate_index_version=?""",
        (expected_source, expected_index_version),
    )
    conn.commit()
    captured = []

    class Queue:
        def enqueue_if_not_pending(self, job):
            captured.append(job)
            return job.job_id

    monkeypatch.setattr(maintenance, "get_job_queue", lambda: Queue())
    snapshot_job_id = maintenance.enqueue_music_search_snapshot_rebuild(conn=conn)
    document_job_id = maintenance.enqueue_music_search_snapshot_rebuild(
        rebuild_documents=True,
        conn=conn,
    )

    assert snapshot_job_id
    assert document_job_id
    assert captured[0].entity_id.startswith("snapshot-set:")
    assert len(captured[0].entity_id.removeprefix("snapshot-set:")) == 64
    assert captured[1].entity_id == f"documents:{expected_source}"


def test_enqueue_skips_an_existing_ready_exact_snapshot(monkeypatch) -> None:
    conn = _conn()
    expected_source = maintenance.music_search_source_revision(conn)
    expected_index_version = maintenance.expected_candidate_index_version(conn)
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='g1', status='ready', source_revision=?,
               candidate_index_version=?""",
        (expected_source, expected_index_version),
    )
    contexts = build_music_search_variant_contexts(
        conn,
        maintenance._current_filter_values(conn),
    )
    conn.executemany(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status,
               semantic_base_key, merge_level, dynamic_threshold, builder_version
           ) VALUES (?, ?, 'source', 'ready', ?, ?, ?, ?)""",
        [
            (
                context.filter_fingerprint,
                context.filter_fingerprint,
                context.semantic_base_key,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            )
            for context in contexts
        ],
    )
    conn.commit()
    captured = []

    class Queue:
        def enqueue_if_not_pending(self, job):
            captured.append(job)
            return job.job_id

    monkeypatch.setattr(maintenance, "get_job_queue", lambda: Queue())

    assert maintenance.enqueue_music_search_snapshot_rebuild(conn=conn) is None
    assert captured == []

    conn.execute(
        "UPDATE music_search_snapshot_meta SET status='stale' WHERE snapshot_key=?",
        (contexts[-1].filter_fingerprint,),
    )
    conn.commit()

    assert maintenance.enqueue_music_search_snapshot_rebuild(conn=conn)
    assert len(captured) == 1


def test_snapshot_only_revalidates_an_existing_exact_set_without_rebuilding(
    monkeypatch,
) -> None:
    conn = _conn()
    expected_source = maintenance.music_search_source_revision(conn)
    expected_index_version = maintenance.expected_candidate_index_version(conn)
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='g1', status='ready', source_revision=?,
               candidate_index_version=?""",
        (expected_source, expected_index_version),
    )
    contexts = build_music_search_variant_contexts(
        conn,
        maintenance._current_filter_values(conn),
    )
    conn.executemany(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status,
               semantic_base_key, merge_level, dynamic_threshold, builder_version
           ) VALUES (?, ?, ?, 'ready', ?, ?, ?, ?)""",
        [
            (
                context.filter_fingerprint,
                context.filter_fingerprint,
                context.source_revision,
                context.semantic_base_key,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            )
            for context in contexts
        ],
    )
    conn.commit()

    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("ready snapshot set was rebuilt"),
    )

    report = maintenance.rebuild_current_music_search_derived_data(
        conn,
        rebuild_documents=False,
    )

    assert report["status"] == "ready"
    assert report["index"] is None
    assert report["snapshot_set"]["revalidated"] is True


def test_forced_candidate_rebuild_reuses_exact_statistics_set(monkeypatch) -> None:
    conn = _conn()
    maintenance.rebuild_music_search_index(conn)
    contexts = build_music_search_variant_contexts(
        conn,
        maintenance._current_filter_values(conn),
    )
    conn.executemany(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status,
               semantic_base_key, merge_level, dynamic_threshold, builder_version
           ) VALUES (?, ?, ?, 'ready', ?, ?, ?, ?)""",
        [
            (
                context.filter_fingerprint,
                context.filter_fingerprint,
                context.source_revision,
                context.semantic_base_key,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            )
            for context in contexts
        ],
    )
    old_generation = maintenance.get_music_search_index_state(conn)["active_generation_id"]
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("candidate-only rebuild recalculated statistics"),
    )

    report = maintenance.rebuild_current_music_search_derived_data(
        conn,
        rebuild_documents=True,
    )

    assert report["index"]["generation_id"] != old_generation
    assert report["snapshot_set"]["revalidated"] is True


def test_current_legacy_v2_set_is_adopted_without_statistics_recalculation(
    monkeypatch,
) -> None:
    conn = _conn()
    maintenance.rebuild_music_search_index(conn)
    contexts = build_music_search_variant_contexts(
        conn,
        maintenance._current_filter_values(conn),
    )
    legacy = [maintenance.legacy_v2_statistics_identity(conn, context) for context in contexts]
    for context, (legacy_base, legacy_fingerprint) in zip(contexts, legacy):
        conn.execute(
            """INSERT INTO music_search_snapshot_meta(
                   snapshot_key, filter_fingerprint, source_revision, status,
                   semantic_base_key, merge_level, dynamic_threshold, builder_version
               ) VALUES (?, ?, 'legacy-source', 'ready', ?, ?, ?, ?)""",
            (
                legacy_fingerprint,
                legacy_fingerprint,
                legacy_base,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            ),
        )
        conn.execute(
            """INSERT INTO music_search_entity_context(
                   snapshot_key, entity_key, play_events, total_ms
               ) VALUES (?, 'track:3', 1, 180000)""",
            (legacy_fingerprint,),
        )
    conn.commit()
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("compatible legacy statistics were recalculated"),
    )

    report = maintenance.rebuild_current_music_search_derived_data(conn)

    assert report["snapshot_set"]["revalidated"] is True
    assert all(
        conn.execute(
            "SELECT status FROM music_search_snapshot_meta WHERE filter_fingerprint=?",
            (context.filter_fingerprint,),
        ).fetchone()[0]
        == "ready"
        for context in contexts
    )
    assert not any(
        conn.execute(
            "SELECT 1 FROM music_search_snapshot_meta WHERE filter_fingerprint=?",
            (legacy_fingerprint,),
        ).fetchone()
        for _legacy_base, legacy_fingerprint in legacy
    )
    assert report["snapshot_set"]["ready_count"] == 6
    assert all(variant["revalidated"] for variant in report["snapshot_set"]["variants"])
    assert all(variant["duration_ms"] == 0 for variant in report["snapshot_set"]["variants"])


def test_enqueue_does_not_cross_from_temporary_connection_into_main_queue(
    monkeypatch,
) -> None:
    conn = _conn()

    class Queue:
        database_path = "/tmp/spotify-stats-main.db"

        def enqueue_if_not_pending(self, job):
            raise AssertionError(f"unexpected cross-database job: {job.entity_id}")

    monkeypatch.setattr(maintenance, "get_job_queue", lambda: Queue())

    assert maintenance.enqueue_music_search_snapshot_rebuild(conn=conn) is None


def test_enqueue_waits_for_identity_and_credit_aggregate_dependencies(monkeypatch) -> None:
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE artist_identity_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL,
            active_aggregate_revision INTEGER NOT NULL,
            rebuild_status TEXT NOT NULL,
            last_error TEXT,
            updated_at TEXT
        );
        INSERT INTO artist_identity_state VALUES (1, 2, 1, 'pending', NULL, NULL);
        """
    )
    conn.commit()

    class Queue:
        def enqueue_if_not_pending(self, job):
            raise AssertionError(f"dependency-incomplete job escaped: {job.entity_id}")

    monkeypatch.setattr(maintenance, "get_job_queue", lambda: Queue())

    assert maintenance.enqueue_music_search_snapshot_rebuild(conn=conn) is None
    with pytest.raises(RuntimeError, match="dependency is not ready"):
        maintenance.rebuild_current_music_search_derived_data(conn)
