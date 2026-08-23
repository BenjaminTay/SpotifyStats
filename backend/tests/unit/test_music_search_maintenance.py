from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_032, migrate_034, migrate_035
from backend.domains.music_search import context as context_module
from backend.domains.music_search import index as index_module
from backend.domains.music_search import normalization as normalization_module
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.revisions import bump_music_search_revisions
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


def _seed_ready_candidate_and_statistics(
    conn: sqlite3.Connection,
) -> tuple:
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
    conn.commit()
    return contexts


def _built_snapshot_set_report(contexts: tuple) -> dict:
    variants = [
        {
            "status": "ready",
            "snapshot_key": context.filter_fingerprint,
            "filter_fingerprint": context.filter_fingerprint,
            "entity_count": 1,
            "source_revision": context.source_revision,
            "semantic_base_key": context.semantic_base_key,
            "merge_level": context.merge_level,
            "dynamic_threshold": context.dynamic_threshold,
            "builder_version": context_module.MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            "duration_ms": 1.0,
            "revalidated": False,
        }
        for context in contexts
    ]
    return {
        "status": "ready",
        "semantic_base_key": contexts[0].semantic_base_key,
        "ready_count": len(variants),
        "failed_count": 0,
        "duration_ms": 6.0,
        "variants": variants,
        "revalidated": False,
    }


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


def test_deferred_rebuild_publishes_candidates_and_queues_six_snapshots(monkeypatch) -> None:
    conn = _conn()
    queued: list[dict[str, object]] = []

    def fake_enqueue(**kwargs):
        queued.append(kwargs)
        return "snapshot-job"

    monkeypatch.setattr(maintenance, "enqueue_music_search_snapshot_rebuild", fake_enqueue)

    report = maintenance.schedule_current_music_search_derived_data_rebuild(
        conn,
        rebuild_documents=True,
    )

    assert report["status"] == "warming"
    assert report["candidate_index"]["action"] == "rebuilt"
    assert report["snapshot"]["status"] == "warming"
    assert report["job_id"] == "snapshot-job"
    assert queued == [{"conn": conn}]
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM music_search_snapshot_meta WHERE status='pending'"
        ).fetchone()[0]
        == 6
    )


@pytest.mark.parametrize("component", ("source", "builder", "normalization", "tokenizer"))
def test_candidate_version_drift_rebuilds_only_candidates(
    monkeypatch,
    component,
) -> None:
    conn = _conn()
    contexts = _seed_ready_candidate_and_statistics(conn)
    before_generation = maintenance.get_music_search_index_state(conn)["active_generation_id"]
    before_fingerprints = [context.filter_fingerprint for context in contexts]

    if component == "source":
        bump_music_search_revisions(conn, "candidate")
        conn.commit()
    elif component == "builder":
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
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("candidate drift recalculated statistics"),
    )

    report = maintenance.rebuild_current_music_search_derived_data(
        conn,
        statistics_reuse_only=True,
    )

    after_contexts = build_music_search_variant_contexts(
        conn,
        maintenance._current_filter_values(conn),
    )
    assert report["candidate_index"]["action"] == "rebuilt"
    assert report["index"]["generation_id"] != before_generation
    assert [context.filter_fingerprint for context in after_contexts] == before_fingerprints
    assert report["snapshot_set"]["revalidated"] is True
    assert report["snapshot_set"]["duration_ms"] == 0
    assert all(variant["duration_ms"] == 0 for variant in report["snapshot_set"]["variants"])


def test_query_only_change_revalidates_candidate_and_statistics(monkeypatch) -> None:
    conn = _conn()
    _seed_ready_candidate_and_statistics(conn)
    before_state = maintenance.get_music_search_index_state(conn)
    monkeypatch.setattr(
        normalization_module,
        "CHINESE_SEARCH_EXPANSION_VERSION",
        "query-only-expansion-next",
    )
    monkeypatch.setattr(
        maintenance,
        "rebuild_music_search_index",
        lambda *_args, **_kwargs: pytest.fail("query-only change rebuilt candidate index"),
    )
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("query-only change rebuilt statistics"),
    )

    report = maintenance.rebuild_current_music_search_derived_data(
        conn,
        statistics_reuse_only=True,
    )

    assert report["candidate_index"]["action"] == "revalidated"
    assert report["candidate_index"]["generation_id"] == before_state["active_generation_id"]
    assert report["snapshot_set"]["revalidated"] is True
    assert report["snapshot_set"]["duration_ms"] == 0


def test_ordinary_repeated_maintenance_reuses_all_six_statistics_at_zero_ms(
    monkeypatch,
) -> None:
    conn = _conn()
    contexts = _seed_ready_candidate_and_statistics(conn)
    monkeypatch.setattr(
        maintenance,
        "rebuild_music_search_index",
        lambda *_args, **_kwargs: pytest.fail("ordinary maintenance rebuilt candidate index"),
    )
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("ordinary maintenance rebuilt statistics"),
    )

    first = maintenance.rebuild_current_music_search_derived_data(
        conn,
        statistics_reuse_only=True,
    )
    second = maintenance.rebuild_current_music_search_derived_data(
        conn,
        statistics_reuse_only=True,
    )

    assert first["index"] is None
    assert second["index"] is None
    for report in (first, second):
        snapshot_set = report["snapshot_set"]
        assert snapshot_set["ready_count"] == len(contexts) == 6
        assert snapshot_set["revalidated"] is True
        assert snapshot_set["duration_ms"] == 0
        assert all(variant["revalidated"] for variant in snapshot_set["variants"])
        assert all(variant["duration_ms"] == 0 for variant in snapshot_set["variants"])


def test_candidate_only_invalidation_keeps_statistics_ready() -> None:
    conn = _conn()
    contexts = _seed_ready_candidate_and_statistics(conn)

    maintenance.mark_music_search_for_rebuild(
        reason="candidate names changed",
        documents=True,
        revision_kinds=("candidate",),
        conn=conn,
    )

    assert {
        row[0]
        for row in conn.execute(
            "SELECT status FROM music_search_snapshot_meta WHERE semantic_base_key=?",
            (contexts[0].semantic_base_key,),
        )
    } == {"ready"}
    state = maintenance.get_music_search_index_state(conn)
    assert state["source_revision"] is None
    assert state["candidate_index_version"] is None


def test_statistics_reuse_only_fails_before_any_expensive_rebuild(monkeypatch) -> None:
    conn = _conn()
    monkeypatch.setattr(
        maintenance,
        "rebuild_music_search_index",
        lambda *_args, **_kwargs: pytest.fail("reuse-only failure rebuilt candidate index"),
    )
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("reuse-only failure rebuilt statistics"),
    )

    with pytest.raises(maintenance.MusicSearchStatisticsReuseRequiredError):
        maintenance.rebuild_current_music_search_derived_data(
            conn,
            statistics_reuse_only=True,
        )


@pytest.mark.parametrize("revision_kind", ("playback", "billboard", "metadata", "settings"))
def test_statistics_revision_drift_rebuilds_only_statistics(
    monkeypatch,
    revision_kind,
) -> None:
    conn = _conn()
    old_contexts = _seed_ready_candidate_and_statistics(conn)
    old_generation = maintenance.get_music_search_index_state(conn)["active_generation_id"]
    bump_music_search_revisions(conn, revision_kind)
    conn.commit()
    captured = []
    monkeypatch.setattr(
        maintenance,
        "rebuild_music_search_index",
        lambda *_args, **_kwargs: pytest.fail("statistics revision rebuilt candidate index"),
    )

    def build_statistics(_conn, contexts):
        captured.extend(contexts)
        return _built_snapshot_set_report(contexts)

    monkeypatch.setattr(maintenance, "build_music_search_snapshot_set", build_statistics)

    report = maintenance.rebuild_current_music_search_derived_data(conn)

    assert report["index"] is None
    assert maintenance.get_music_search_index_state(conn)["active_generation_id"] == old_generation
    assert len(captured) == 6
    assert captured[0].semantic_base_key != old_contexts[0].semantic_base_key
    assert report["snapshot_set"]["revalidated"] is False


def test_shared_frame_failure_falls_back_to_full_snapshot_set(monkeypatch) -> None:
    conn = _conn()
    _seed_ready_candidate_and_statistics(conn)
    maintenance.mark_music_search_for_rebuild(
        reason="append published",
        revision_kinds=("playback", "billboard"),
        conn=conn,
    )
    new_contexts = build_music_search_variant_contexts(
        conn,
        maintenance._current_filter_values(conn),
    )
    monkeypatch.setattr(
        maintenance,
        "build_shared_full_music_search_snapshot_set",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("shared failed")),
    )
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda _conn, contexts: _built_snapshot_set_report(contexts),
    )

    report = maintenance.rebuild_current_music_search_derived_data(
        conn,
        shared_full_snapshot_plan={
            "schema_version": "music_search_shared_full_snapshot_v1",
            "source_generation_id": "import-g2",
        },
    )

    assert report["snapshot_set"]["strategy"] == "full_fallback"
    assert report["snapshot_set"]["fallback_reason"] == "RuntimeError"
    assert report["snapshot_set"]["semantic_base_key"] == new_contexts[0].semantic_base_key


def test_incompatible_delta_falls_back_to_shared_full_snapshot_set(monkeypatch) -> None:
    conn = _conn()
    _seed_ready_candidate_and_statistics(conn)
    maintenance.mark_music_search_for_rebuild(
        reason="append published",
        revision_kinds=("playback", "billboard"),
        conn=conn,
    )
    calls: list[str] = []

    def reject_delta(*_args, **_kwargs):
        calls.append("delta")
        return None

    def build_shared(_conn, contexts, **_kwargs):
        calls.append("shared")
        report = _built_snapshot_set_report(contexts)
        report["strategy"] = "shared_full_snapshot_rebuild"
        return report

    monkeypatch.setattr(
        maintenance,
        "build_incremental_music_search_snapshot_set",
        reject_delta,
    )
    monkeypatch.setattr(
        maintenance,
        "build_shared_full_music_search_snapshot_set",
        build_shared,
    )
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("shared fallback unexpectedly used ordinary full"),
    )

    report = maintenance.rebuild_current_music_search_derived_data(
        conn,
        shared_full_snapshot_plan={
            "schema_version": "music_search_shared_full_snapshot_v2",
            "source_generation_id": "import-g2",
            "incremental_snapshot_plan": {"schema_version": "invalid-test-plan"},
        },
    )

    assert calls == ["delta", "shared"]
    assert report["snapshot_set"]["strategy"] == "shared_full_snapshot_rebuild"
    assert (
        report["snapshot_set"]["delta_fallback_reason"] == "incompatible_incremental_snapshot_base"
    )


def test_shared_full_plan_rejects_settings_drift() -> None:
    conn = _conn()
    _seed_ready_candidate_and_statistics(conn)

    class ChangeSet:
        strategy = "incremental"
        generation_id = "import-g2"
        track_ids = frozenset({3})
        album_ids = frozenset({2})
        artist_ids = frozenset({1})
        semantic_revisions = {
            "playback_policy": maintenance.PLAYBACK_EVENT_POLICY_VERSION,
            "settings": "wrong-settings",
            "artist_identity": 0,
            "track_credit": 0,
        }

    assert (
        maintenance.build_shared_full_music_search_plan(
            conn,
            change_set=ChangeSet(),
        )
        is None
    )


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
def test_identity_or_credit_revision_rebuilds_both_required_layers(
    monkeypatch,
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
    old_contexts = _seed_ready_candidate_and_statistics(conn)
    old_generation = maintenance.get_music_search_index_state(conn)["active_generation_id"]
    conn.execute(
        f"""UPDATE {table_name}
            SET current_revision=1, active_aggregate_revision=1
            WHERE state_id=1"""
    )
    conn.commit()
    captured = []

    def build_statistics(_conn, contexts):
        captured.extend(contexts)
        return _built_snapshot_set_report(contexts)

    monkeypatch.setattr(maintenance, "build_music_search_snapshot_set", build_statistics)

    report = maintenance.rebuild_current_music_search_derived_data(conn)

    assert report["candidate_index"]["action"] == "rebuilt"
    assert report["index"]["generation_id"] != old_generation
    assert len(captured) == 6
    assert captured[0].semantic_base_key != old_contexts[0].semantic_base_key
    assert report["snapshot_set"]["revalidated"] is False


@pytest.mark.parametrize(
    "constant_name",
    ("MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION", "MUSIC_SEARCH_CHART_BUILDER_VERSION"),
)
def test_statistics_builder_drift_rebuilds_only_statistics(
    monkeypatch,
    constant_name,
) -> None:
    conn = _conn()
    old_contexts = _seed_ready_candidate_and_statistics(conn)
    old_generation = maintenance.get_music_search_index_state(conn)["active_generation_id"]
    monkeypatch.setattr(context_module, constant_name, "statistics-builder-next")
    captured = []
    monkeypatch.setattr(
        maintenance,
        "rebuild_music_search_index",
        lambda *_args, **_kwargs: pytest.fail("statistics builder rebuilt candidate index"),
    )

    def build_statistics(_conn, contexts):
        captured.extend(contexts)
        return _built_snapshot_set_report(contexts)

    monkeypatch.setattr(maintenance, "build_music_search_snapshot_set", build_statistics)

    report = maintenance.rebuild_current_music_search_derived_data(conn)

    assert report["index"] is None
    assert maintenance.get_music_search_index_state(conn)["active_generation_id"] == old_generation
    assert len(captured) == 6
    assert captured[0].semantic_base_key != old_contexts[0].semantic_base_key
    assert report["snapshot_set"]["revalidated"] is False


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


def test_source_equivalent_legacy_set_survives_candidate_generation_change(
    monkeypatch,
) -> None:
    conn = _conn()
    maintenance.rebuild_music_search_index(conn)
    state = maintenance.get_music_search_index_state(conn)
    legacy_index_source = maintenance.legacy_v2_music_search_source_revision(
        conn,
        normalization_version=str(state["normalization_version"]),
    )
    conn.execute(
        "UPDATE music_search_index_state SET source_revision=?",
        (legacy_index_source,),
    )
    contexts = build_music_search_variant_contexts(
        conn,
        maintenance._current_filter_values(conn),
    )
    legacy = [maintenance.legacy_v2_statistics_identity(conn, context) for context in contexts]
    legacy_source = maintenance.legacy_v2_statistics_source_revision(conn, contexts[0])
    for context, (legacy_base, legacy_fingerprint) in zip(contexts, legacy):
        conn.execute(
            """INSERT INTO music_search_snapshot_meta(
                   snapshot_key, filter_fingerprint, source_revision, status,
                   semantic_base_key, merge_level, dynamic_threshold, builder_version
               ) VALUES (?, ?, ?, 'ready', ?, ?, ?, ?)""",
            (
                legacy_fingerprint,
                legacy_fingerprint,
                legacy_source,
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
    old_generation = maintenance.get_music_search_index_state(conn)["active_generation_id"]
    conn.execute(
        "UPDATE music_search_index_state SET active_generation_id='replacement-generation'"
    )
    conn.commit()
    assert maintenance.get_music_search_index_state(conn)["active_generation_id"] != old_generation
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("source-equivalent statistics were recalculated"),
    )

    report = maintenance.rebuild_current_music_search_derived_data(
        conn,
        statistics_reuse_only=True,
    )

    assert report["snapshot_set"]["revalidated"] is True
    assert report["snapshot_set"]["duration_ms"] == 0
    assert all(
        maintenance.get_ready_music_search_snapshot_key(conn, context.filter_fingerprint)
        is not None
        for context in contexts
    )


def test_source_equivalent_legacy_adoption_rejects_wrong_source_revision(monkeypatch) -> None:
    conn = _conn()
    maintenance.rebuild_music_search_index(conn)
    state = maintenance.get_music_search_index_state(conn)
    legacy_index_source = maintenance.legacy_v2_music_search_source_revision(
        conn,
        normalization_version=str(state["normalization_version"]),
    )
    conn.execute(
        "UPDATE music_search_index_state SET source_revision=?",
        (legacy_index_source,),
    )
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
               ) VALUES (?, ?, 'wrong-source', 'ready', ?, ?, ?, ?)""",
            (
                legacy_fingerprint,
                legacy_fingerprint,
                legacy_base,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            ),
        )
    conn.commit()
    conn.execute(
        "UPDATE music_search_index_state SET active_generation_id='replacement-generation'"
    )
    conn.commit()
    monkeypatch.setattr(
        maintenance,
        "build_music_search_snapshot_set",
        lambda *_args, **_kwargs: pytest.fail("wrong-source statistics were recalculated"),
    )

    with pytest.raises(maintenance.MusicSearchStatisticsReuseRequiredError):
        maintenance.rebuild_current_music_search_derived_data(
            conn,
            statistics_reuse_only=True,
        )


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
