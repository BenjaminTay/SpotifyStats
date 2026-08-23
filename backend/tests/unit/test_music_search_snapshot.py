from __future__ import annotations

import sqlite3
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from backend.core.migrations import migrate_032, migrate_034, migrate_035, migrate_042
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    MusicSearchFilterContext,
    build_music_search_filter_context,
)
from backend.domains.music_search.revisions import bump_music_search_revisions
from backend.domains.music_search.snapshot import (
    _context_rows,
    _shared_metric_maps,
    build_music_search_snapshot,
    build_music_search_snapshot_set,
    build_shared_full_music_search_snapshot_set,
    get_music_search_snapshot_status,
    get_ready_music_search_entity_keys,
    get_ready_music_search_snapshot_key,
    lookup_music_search_context,
    mark_music_search_derived_data_dirty,
)
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.models.music_search import MusicSearchChartSummary

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
            ms_played INTEGER
        );
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        INSERT INTO plays VALUES (1, 1, '2026-01-01T00:00:00Z', 1000);
        INSERT INTO artists VALUES (3, 'Artist');
        INSERT INTO albums VALUES (2, 'Album', 3);
        INSERT INTO tracks VALUES (1, 'Track', 3, 2);
        """
    )
    migrate_032(conn)
    migrate_034(conn)
    migrate_035(conn)
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='g1', status='ready', source_revision='index-r1'"""
    )
    conn.executescript(
        """CREATE TABLE playback_import_state (
               state_id INTEGER PRIMARY KEY, active_generation_id TEXT
           );
           INSERT INTO playback_import_state VALUES (1, 'import-g2');"""
    )
    documents = [
        (
            "g1",
            "track:1",
            "track",
            2,
            "Track",
            "track",
            "Artist · Album",
            "artist · album",
            "",
            "",
            "track artist album",
            1,
            "/music/tracks/1",
            None,
            1,
            2,
            None,
            3,
            "Album",
            "Artist",
        ),
        (
            "g1",
            "album:2",
            "album",
            1,
            "Album",
            "album",
            "Artist",
            "artist",
            "",
            "",
            "album artist",
            1,
            "/music/albums/2",
            None,
            None,
            2,
            None,
            3,
            "Album",
            "Artist",
        ),
        (
            "g1",
            "album_project:2",
            "album_project",
            0,
            "Album",
            "album",
            "Artist",
            "artist",
            "",
            "",
            "album artist",
            1,
            "/music/albums/Album?artist=Artist",
            None,
            None,
            2,
            2,
            3,
            "Album",
            "Artist",
        ),
        (
            "g1",
            "artist:3",
            "artist",
            0,
            "Artist",
            "artist",
            None,
            "",
            "",
            "",
            "artist",
            1,
            "/music/artists/Artist",
            None,
            None,
            None,
            None,
            3,
            None,
            "Artist",
        ),
    ]
    conn.executemany(
        """INSERT INTO music_search_documents(
               generation_id, entity_key, kind, merge_level, label, normalized_label,
               secondary, normalized_secondary, alias_text, normalized_alias,
               search_text, popularity_tiebreaker, href, cover_url, track_id,
               album_id, album_project_id, artist_id, album_name, artist_name
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        documents,
    )
    conn.execute(
        """INSERT INTO music_search_documents
           SELECT generation_id, entity_key, kind, 1, label, normalized_label,
                  secondary, normalized_secondary, alias_text, normalized_alias,
                  search_text, popularity_tiebreaker, href, cover_url, track_id,
                  album_id, album_project_id, artist_id, album_name, artist_name
           FROM music_search_documents
           WHERE generation_id='g1' AND entity_key='track:1' AND merge_level=2"""
    )
    conn.execute(
        """INSERT INTO music_search_documents
           SELECT generation_id, entity_key, kind, 3, label, normalized_label,
                  secondary, normalized_secondary, alias_text, normalized_alias,
                  search_text, popularity_tiebreaker, href, cover_url, track_id,
                  album_id, album_project_id, artist_id, album_name, artist_name
           FROM music_search_documents
           WHERE generation_id='g1' AND entity_key='track:1' AND merge_level=2"""
    )
    conn.commit()
    return conn


def _context(
    *,
    merge_level: int = 2,
    dynamic_threshold: bool = True,
    filter_fingerprint: str = "fingerprint-r1",
) -> MusicSearchFilterContext:
    return MusicSearchFilterContext(
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=5,
        merge_level=merge_level,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        year_start=None,
        year_end=None,
        playback_revision=1,
        billboard_aggregation_revision=1,
        metadata_revision=1,
        settings_revision=1,
        artist_identity_revision=0,
        track_credit_revision=0,
        semantic_base_key="base-r1",
        filter_fingerprint=filter_fingerprint,
        source_revision="source-r1",
    )


def _shared_contexts(conn: sqlite3.Connection) -> tuple[MusicSearchFilterContext, ...]:
    return build_music_search_variant_contexts(conn, _context().filter_values())


def test_filter_fingerprint_changes_with_semantics_and_playback_revision() -> None:
    conn = _conn()
    baseline = build_music_search_filter_context(conn, _context().filter_values())
    changed_filter = build_music_search_filter_context(
        conn,
        {**_context().filter_values(), "min_ms": 60000},
    )
    bump_music_search_revisions(conn, "playback")
    changed_data = build_music_search_filter_context(conn, _context().filter_values())

    assert baseline.filter_fingerprint != changed_filter.filter_fingerprint
    assert baseline.filter_fingerprint != changed_data.filter_fingerprint


def test_weekly_ledger_uses_candidate_entity_keys() -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module

    context = _context(merge_level=2, dynamic_threshold=True)
    weekly = pd.DataFrame(
        {
            "billboard_week": ["2026-01-02"],
            "track_id": [1],
            "track_name": ["Track"],
            "artist_name": ["Artist"],
            "rank": [1],
            "play_count": [2],
            "total_ms": [2000],
        }
    )
    weekly_album = pd.DataFrame(
        {
            "billboard_week": ["2026-01-02"],
            "album_project_id": [2],
            "album_name": ["Album"],
            "artist_name": ["Artist"],
            "rank": [1],
            "play_count": [2],
            "total_ms": [2000],
        }
    )
    weekly_artist = pd.DataFrame(
        {
            "billboard_week": ["2026-01-02"],
            "artist_id": [3],
            "artist_name": ["Artist"],
            "rank": [1],
            "play_count": [2],
            "total_ms": [2000],
        }
    )

    rows, complete = snapshot_module._weekly_ledger_rows(
        conn,
        context,
        weekly,
        weekly_album,
        weekly_artist,
    )

    assert complete is True
    assert [(row[0], row[2]) for row in rows] == [
        ("track", "track:1"),
        ("album", "album_project:2"),
        ("artist", "artist:3"),
    ]


def test_weekly_ledger_deduplicates_identical_facts_and_rejects_conflicts() -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module

    context = _context(merge_level=1, dynamic_threshold=True)
    album_row = {
        "billboard_week": "2026-01-02",
        "album_project_id": 2,
        "album_name": "Album",
        "artist_name": "Artist",
        "rank": 1,
        "play_count": 2,
        "total_ms": 2000,
    }
    exact_duplicate = pd.DataFrame([album_row, album_row])

    rows, complete = snapshot_module._weekly_ledger_rows(
        conn,
        context,
        pd.DataFrame(),
        exact_duplicate,
        pd.DataFrame(),
    )

    assert complete is True
    assert len(rows) == 1
    assert rows[0][0:3] == ("album", "2026-01-02", "album:2")

    conflicting = pd.DataFrame([album_row, {**album_row, "rank": 2}])
    rows, complete = snapshot_module._weekly_ledger_rows(
        conn,
        context,
        pd.DataFrame(),
        conflicting,
        pd.DataFrame(),
    )

    assert complete is False
    assert len(rows) == 1
    assert rows[0][3] == 1


def test_shared_publish_persists_six_variant_lineage_and_weekly_ledger(monkeypatch) -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module

    migrate_042(conn)
    conn.execute("ALTER TABLE playback_import_state ADD COLUMN dataset_digest TEXT")
    conn.execute("UPDATE playback_import_state SET dataset_digest='dataset-g2' WHERE state_id=1")
    contexts = _shared_contexts(conn)
    snapshot_module.prepare_music_search_snapshot_set(conn, contexts)
    rows_by_fingerprint: dict[str, list[tuple[Any, ...]]] = {
        context.filter_fingerprint: [] for context in contexts
    }
    weekly_by_fingerprint: dict[str, list[tuple[str, str, str, int, int, int, str]]] = {
        context.filter_fingerprint: [] for context in contexts
    }
    weekly_by_fingerprint[contexts[0].filter_fingerprint] = [
        (
            "track",
            "2026-01-02",
            "track:1",
            1,
            2,
            2000,
            '{"entity_id":1}',
        )
    ]
    monkeypatch.setattr(
        snapshot_module,
        "music_search_snapshot_dependency_digest",
        lambda _conn: "dependency-g2",
    )

    snapshot_module._publish_shared_full_snapshot_set(
        conn,
        contexts,
        rows_by_fingerprint,
        weekly_by_fingerprint,
        source_generation_id="import-g2",
        candidate_generation_id="g1",
        semantic_base_key=contexts[0].semantic_base_key,
        source_dataset_digest="dataset-g2",
        dependency_digest="dependency-g2",
    )

    lineage = conn.execute(
        """SELECT COUNT(*), COUNT(DISTINCT policy_key),
                  COUNT(DISTINCT source_generation_id),
                  COUNT(DISTINCT source_dataset_digest),
                  COUNT(DISTINCT dependency_digest),
                  COUNT(DISTINCT build_strategy)
           FROM music_search_snapshot_meta WHERE status='ready'"""
    ).fetchone()
    assert tuple(lineage) == (6, 6, 1, 1, 1, 1)
    assert conn.execute("SELECT COUNT(*) FROM music_search_weekly_chart_context").fetchone()[0] == 1


def test_shared_publish_rechecks_dependency_under_write_lock(monkeypatch) -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module

    migrate_042(conn)
    conn.execute("ALTER TABLE playback_import_state ADD COLUMN dataset_digest TEXT")
    conn.execute("UPDATE playback_import_state SET dataset_digest='dataset-g2' WHERE state_id=1")
    contexts = _shared_contexts(conn)
    snapshot_module.prepare_music_search_snapshot_set(conn, contexts)
    monkeypatch.setattr(
        snapshot_module,
        "music_search_snapshot_dependency_digest",
        lambda _conn: "dependency-changed",
    )

    with pytest.raises(RuntimeError, match="dependencies changed"):
        snapshot_module._publish_shared_full_snapshot_set(
            conn,
            contexts,
            {context.filter_fingerprint: [] for context in contexts},
            {context.filter_fingerprint: [] for context in contexts},
            source_generation_id="import-g2",
            candidate_generation_id="g1",
            semantic_base_key=contexts[0].semantic_base_key,
            source_dataset_digest="dataset-g2",
            dependency_digest="dependency-g2",
        )

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM music_search_snapshot_meta WHERE status='ready'"
        ).fetchone()[0]
        == 0
    )


def test_incremental_snapshot_delta_clones_base_and_applies_lifetime_metrics(
    monkeypatch,
) -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module
    from backend.domains.music_search import snapshot_delta as delta_module

    migrate_042(conn)
    conn.execute("ALTER TABLE playback_import_state ADD COLUMN dataset_digest TEXT")
    conn.execute("UPDATE playback_import_state SET dataset_digest='dataset-g2' WHERE state_id=1")
    base_contexts = _shared_contexts(conn)
    snapshot_module.prepare_music_search_snapshot_set(conn, base_contexts)
    base_rows: dict[str, list[tuple[Any, ...]]] = {
        context.filter_fingerprint: [("track:1", 1, 1000, *(None for _ in range(9)))]
        for context in base_contexts
    }
    empty_ledger: dict[str, list[tuple[str, str, str, int, int, int, str]]] = {
        context.filter_fingerprint: [] for context in base_contexts
    }
    monkeypatch.setattr(
        snapshot_module,
        "music_search_snapshot_dependency_digest",
        lambda _conn: "dependency-stable",
    )
    snapshot_module._publish_shared_full_snapshot_set(
        conn,
        base_contexts,
        base_rows,
        empty_ledger,
        source_generation_id="import-g2",
        candidate_generation_id="g1",
        semantic_base_key=base_contexts[0].semantic_base_key,
        source_dataset_digest="dataset-g2",
        dependency_digest="dependency-stable",
    )
    bump_music_search_revisions(conn, "playback", "billboard")
    conn.execute(
        """UPDATE playback_import_state
           SET active_generation_id='import-g3', dataset_digest='dataset-g3'
           WHERE state_id=1"""
    )
    conn.commit()
    target_contexts = _shared_contexts(conn)
    physical = pd.DataFrame(
        {
            "track_id": [1],
            "source_album_id": pd.Series([2], dtype="Int64"),
            "play_events": [1],
            "total_ms": [2000],
        }
    )
    monkeypatch.setattr(
        delta_module,
        "music_search_snapshot_dependency_digest",
        lambda _conn: "dependency-stable",
    )
    monkeypatch.setattr(
        delta_module,
        "_track_delta_maps",
        lambda *_args, **_kwargs: {1: physical, 2: physical, 3: physical},
    )
    monkeypatch.setattr(
        delta_module,
        "_album_delta_map",
        lambda *_args, **_kwargs: {2: (1, 2000)},
    )
    monkeypatch.setattr(
        delta_module,
        "_artist_delta_map",
        lambda *_args, **_kwargs: {3: (1, 2000)},
    )

    incremental_plan = delta_module.build_music_search_incremental_plan(
        SimpleNamespace(
            strategy="incremental",
            removed_count=0,
            billboard_scope_exact=True,
            previous_dataset_digest="dataset-g2",
            generation_id="import-g3",
            previous_open_week="2026-01-02",
            current_open_week="2026-01-02",
            billboard_weeks={"2026-01-02"},
            added_count=1,
        )
    )
    assert incremental_plan is not None
    report = delta_module.build_incremental_music_search_snapshot_set(
        conn,
        target_contexts,
        incremental_plan,
    )

    assert report is not None
    assert report["strategy"] == "incremental_snapshot_delta"
    assert report["lifetime_scan"] is False
    assert report["ready_count"] == 6
    for context in target_contexts:
        metrics = {
            str(row[0]): (int(row[1]), int(row[2]))
            for row in conn.execute(
                """SELECT entity_key, play_events, total_ms
                   FROM music_search_entity_context WHERE snapshot_key=?""",
                (context.filter_fingerprint,),
            ).fetchall()
        }
        assert metrics["track:1"] == (2, 3000)
        expected_album_key = "album:2" if context.merge_level == 1 else "album_project:2"
        assert metrics[expected_album_key] == (1, 2000)
        assert metrics["artist:3"] == (1, 2000)
        lineage = conn.execute(
            """SELECT build_strategy, base_snapshot_key, source_dataset_digest,
                      change_set_digest
               FROM music_search_snapshot_meta WHERE snapshot_key=?""",
            (context.filter_fingerprint,),
        ).fetchone()
        base_context = next(
            base
            for base in base_contexts
            if base.merge_level == context.merge_level
            and base.dynamic_threshold == context.dynamic_threshold
        )
        assert tuple(lineage) == (
            "delta",
            base_context.filter_fingerprint,
            "dataset-g3",
            incremental_plan["change_set_digest"],
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"strategy": "full"},
        {"removed_count": 1},
        {"billboard_scope_exact": False},
        {"previous_open_week": "2025-12-26"},
        {"billboard_weeks": set()},
        {"billboard_weeks": {"2025-12-26", "2026-01-02"}},
        {"billboard_weeks": {"2026-01-09"}},
        {"added_count": 0},
        {"added_count": 10_001},
    ],
)
def test_incremental_snapshot_plan_fails_closed(overrides: dict[str, Any]) -> None:
    from backend.domains.music_search.snapshot_delta import build_music_search_incremental_plan

    values: dict[str, Any] = {
        "strategy": "incremental",
        "removed_count": 0,
        "billboard_scope_exact": True,
        "previous_dataset_digest": "dataset-g2",
        "generation_id": "import-g3",
        "previous_open_week": "2026-01-02",
        "current_open_week": "2026-01-02",
        "billboard_weeks": {"2026-01-02"},
        "added_count": 1,
    }
    values.update(overrides)

    assert build_music_search_incremental_plan(SimpleNamespace(**values)) is None


def test_incremental_snapshot_plan_rejects_tampering() -> None:
    from backend.domains.music_search.snapshot_delta import (
        _validated_incremental_plan,
        build_music_search_incremental_plan,
    )

    plan = build_music_search_incremental_plan(
        SimpleNamespace(
            strategy="incremental",
            removed_count=0,
            billboard_scope_exact=True,
            previous_dataset_digest="dataset-g2",
            generation_id="import-g3",
            previous_open_week="2026-01-02",
            current_open_week="2026-01-02",
            billboard_weeks={"2026-01-02"},
            added_count=1,
        )
    )
    assert plan is not None
    plan["billboard_weeks"] = ["2025-12-26"]

    assert _validated_incremental_plan(plan) is None


def test_incremental_snapshot_delta_rejects_disabled_logical_merge() -> None:
    from backend.domains.music_search.snapshot_delta import (
        build_incremental_music_search_snapshot_set,
        build_music_search_incremental_plan,
    )

    conn = _conn()
    contexts = tuple(replace(context, merge_enabled=False) for context in _shared_contexts(conn))
    plan = build_music_search_incremental_plan(
        SimpleNamespace(
            strategy="incremental",
            removed_count=0,
            billboard_scope_exact=True,
            previous_dataset_digest="dataset-g2",
            generation_id="import-g3",
            previous_open_week="2026-01-02",
            current_open_week="2026-01-02",
            billboard_weeks={"2026-01-02"},
            added_count=1,
        )
    )
    assert plan is not None

    assert build_incremental_music_search_snapshot_set(conn, contexts, plan) is None


@pytest.mark.parametrize(
    ("album_type", "include_compilations", "expected"),
    [
        ("album", False, {2: (1, 2000)}),
        ("single", True, {}),
        ("compilation", False, {}),
        ("compilation", True, {2: (1, 2000)}),
    ],
)
def test_l1_album_delta_matches_full_album_type_filters(
    album_type: str,
    include_compilations: bool,
    expected: dict[int, tuple[int, int]],
) -> None:
    from backend.domains.music_search.snapshot_delta import _album_delta_map

    conn = _conn()
    conn.execute(
        """CREATE TABLE spotify_album_meta(
               spotify_album_id TEXT PRIMARY KEY, album_name TEXT,
               release_date TEXT, album_type TEXT
           )"""
    )
    conn.execute(
        """CREATE TABLE album_spotify_links(
               album_id INTEGER NOT NULL, spotify_album_id TEXT NOT NULL,
               evidence TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0.0,
               play_count INTEGER NOT NULL DEFAULT 0,
               track_count INTEGER NOT NULL DEFAULT 0,
               PRIMARY KEY(album_id, spotify_album_id, evidence)
           )"""
    )
    conn.execute(
        """INSERT INTO spotify_album_meta
           VALUES ('spotify-album-2', 'Album', '2026-01-01', ?)""",
        (album_type,),
    )
    conn.execute(
        """INSERT INTO spotify_album_meta
           VALUES ('spotify-album-decoy', 'Album', '2025-01-01', 'album')"""
    )
    conn.execute(
        """INSERT INTO album_spotify_links
           VALUES (2, 'spotify-album-2', 'play_track_meta', 0.9, 4, 1)"""
    )
    conn.execute("INSERT INTO artists VALUES (4, 'Other Artist')")
    conn.execute("INSERT INTO albums VALUES (4, 'Album', 4)")
    conn.execute(
        """INSERT INTO album_spotify_links
           VALUES (4, 'spotify-album-decoy', 'play_track_meta', 0.9, 3, 1)"""
    )
    physical_delta = pd.DataFrame(
        {
            "track_id": [1],
            "source_album_id": pd.Series([2], dtype="Int64"),
            "play_events": [1],
            "total_ms": [2000],
        }
    )

    assert (
        _album_delta_map(
            conn,
            physical_delta,
            merge_level=1,
            include_compilations=include_compilations,
        )
        == expected
    )


def test_l1_album_delta_only_uses_unambiguous_legacy_name_metadata() -> None:
    from backend.domains.music_search.snapshot_delta import _album_delta_map

    conn = _conn()
    conn.execute(
        """CREATE TABLE spotify_album_meta(
               spotify_album_id TEXT PRIMARY KEY, album_name TEXT,
               release_date TEXT, album_type TEXT
           )"""
    )
    conn.execute(
        """INSERT INTO spotify_album_meta
           VALUES ('spotify-album-single', 'Album', '2026-01-01', 'single')"""
    )
    physical_delta = pd.DataFrame(
        {
            "track_id": [1],
            "source_album_id": pd.Series([2], dtype="Int64"),
            "play_events": [1],
            "total_ms": [2000],
        }
    )

    assert (
        _album_delta_map(
            conn,
            physical_delta,
            merge_level=1,
            include_compilations=True,
        )
        == {}
    )

    conn.execute(
        """INSERT INTO spotify_album_meta
           VALUES ('spotify-album-decoy', 'Album', '2025-01-01', 'album')"""
    )
    assert _album_delta_map(
        conn,
        physical_delta,
        merge_level=1,
        include_compilations=True,
    ) == {2: (1, 2000)}


def test_snapshot_build_is_exact_lookup_and_stale_never_masquerades_as_ready(
    monkeypatch,
) -> None:
    conn = _conn()
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._metric_maps",
        lambda *_args, **_kwargs: (
            {1: (4, 4000)},
            {2: (5, 5000)},
            {3: (6, 6000)},
        ),
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._build_chart_lookup",
        lambda **_kwargs: {
            "track": {1: MusicSearchChartSummary(peak_position=1, weeks_on_chart=2)},
            "album": {},
            "artist": {},
        },
    )

    report = build_music_search_snapshot(conn, _context())
    assert get_ready_music_search_snapshot_key(conn, "fingerprint-r1") == "fingerprint-r1"
    keys = get_ready_music_search_entity_keys(conn, "fingerprint-r1")
    response = lookup_music_search_context(
        conn,
        filter_fingerprint="fingerprint-r1",
        entity_keys=["track:1", "artist:3"],
    )

    assert report["entity_count"] == 3
    assert keys == {"track:1", "album_project:2", "artist:3"}
    assert response.snapshot_status == "ready"
    assert response.items["track:1"].play_events == 4
    assert response.items["track:1"].chart is not None
    assert response.items["track:1"].chart.peak_position == 1
    assert response.items["artist:3"].total_ms == 6000

    mark_music_search_derived_data_dirty(conn, reason="settings changed")
    conn.commit()
    assert get_music_search_snapshot_status(conn, "fingerprint-r1") == "stale"
    stale = lookup_music_search_context(
        conn,
        filter_fingerprint="fingerprint-r1",
        entity_keys=["track:1"],
    )
    assert stale.snapshot_status == "stale"
    assert stale.items == {}


def test_snapshot_set_keeps_ready_variants_when_one_variant_fails(monkeypatch) -> None:
    conn = _conn()
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._metric_maps",
        lambda *_args, **_kwargs: ({1: (4, 4000)}, {2: (5, 5000)}, {3: (6, 6000)}),
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._build_chart_lookup",
        lambda **_kwargs: {"track": {}, "album": {}, "artist": {}},
    )
    from backend.domains.music_search import snapshot as snapshot_module

    original_context_rows = snapshot_module._context_rows

    def fail_l1_dynamic(target, context):
        if context.merge_level == 1 and context.dynamic_threshold:
            assert (
                target.execute(
                    "SELECT status FROM music_search_snapshot_meta WHERE snapshot_key=?",
                    (context.filter_fingerprint,),
                ).fetchone()[0]
                == "running"
            )
            assert (
                target.execute(
                    "SELECT status FROM music_search_snapshot_meta WHERE snapshot_key='fp-3-1'"
                ).fetchone()[0]
                == "pending"
            )
            raise RuntimeError("fixture failure")
        return original_context_rows(target, context)

    monkeypatch.setattr(snapshot_module, "_context_rows", fail_l1_dynamic)
    contexts = tuple(
        _context(
            merge_level=merge_level,
            dynamic_threshold=dynamic,
            filter_fingerprint=f"fp-{merge_level}-{int(dynamic)}",
        )
        for merge_level, dynamic in ((2, True), (1, True), (3, True), (2, False))
    )

    report = build_music_search_snapshot_set(conn, contexts)

    assert report["status"] == "partial"
    assert report["ready_count"] == 3
    assert report["failed_count"] == 1
    statuses = {
        (row["merge_level"], bool(row["dynamic_threshold"])): row["status"]
        for row in conn.execute(
            "SELECT merge_level, dynamic_threshold, status FROM music_search_snapshot_meta"
        )
    }
    assert statuses[(1, True)] == "failed"
    assert statuses[(2, True)] == "ready"
    assert statuses[(3, True)] == "ready"
    assert statuses[(2, False)] == "ready"
    assert get_music_search_snapshot_status(conn, "fp-1-1") == "failed"


def test_snapshot_set_releases_heavy_caches_after_every_variant(monkeypatch) -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module

    released: list[str] = []
    preserved: list[tuple[str, set[str]]] = []
    collected: list[bool] = []
    monkeypatch.setattr(
        snapshot_module,
        "build_music_search_snapshot",
        lambda _conn, context: {
            "status": "ready",
            "snapshot_key": context.filter_fingerprint,
            "filter_fingerprint": context.filter_fingerprint,
            "entity_count": 1,
            "source_revision": context.source_revision,
        },
    )
    monkeypatch.setattr(snapshot_module, "invalidate", released.append)
    monkeypatch.setattr(
        snapshot_module,
        "invalidate_except",
        lambda namespace, keys: preserved.append((namespace, keys)),
    )
    monkeypatch.setattr(snapshot_module.gc, "collect", lambda: collected.append(True))
    contexts = tuple(
        _context(
            merge_level=merge_level,
            dynamic_threshold=dynamic,
            filter_fingerprint=f"release-{merge_level}-{int(dynamic)}",
        )
        for merge_level, dynamic in ((2, True), (1, True), (3, False))
    )

    report = build_music_search_snapshot_set(conn, contexts)

    assert report["ready_count"] == 3
    assert released == ["db"] * 3
    assert preserved == [("billboard", {"latest_snapshot"})] * 3
    assert collected == [True, True, True]


def test_snapshot_set_resumes_by_skipping_each_exact_ready_variant(monkeypatch) -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module

    contexts = tuple(
        _context(
            merge_level=merge_level,
            dynamic_threshold=dynamic,
            filter_fingerprint=f"resume-{merge_level}-{int(dynamic)}",
        )
        for merge_level, dynamic in (
            (2, True),
            (1, True),
            (3, True),
            (2, False),
            (1, False),
            (3, False),
        )
    )
    first = contexts[0]
    conn.execute(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status,
               semantic_base_key, merge_level, dynamic_threshold, builder_version
           ) VALUES (?, ?, ?, 'ready', ?, ?, ?, ?)""",
        (
            first.filter_fingerprint,
            first.filter_fingerprint,
            first.source_revision,
            first.semantic_base_key,
            first.merge_level,
            int(first.dynamic_threshold),
            MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
        ),
    )
    built: list[str] = []

    def fake_build(_conn, context):
        built.append(context.filter_fingerprint)
        return {
            "status": "ready",
            "snapshot_key": context.filter_fingerprint,
            "filter_fingerprint": context.filter_fingerprint,
            "entity_count": 1,
            "source_revision": context.source_revision,
        }

    monkeypatch.setattr(snapshot_module, "build_music_search_snapshot", fake_build)
    report = build_music_search_snapshot_set(conn, contexts)

    assert built == [context.filter_fingerprint for context in contexts[1:]]
    assert report["variants"][0]["revalidated"] is True
    assert report["variants"][0]["reuse_reason"] == "exact_statistics_fingerprint_ready"


def test_metric_maps_load_primary_and_artist_frames_sequentially(monkeypatch) -> None:
    conn = _conn()
    from backend.domains.music_search import snapshot as snapshot_module

    load_order: list[tuple[str, ...]] = []
    released: list[str] = []
    primary = pd.DataFrame(
        {
            "track_id": [1, 1],
            "ms_played": [1000, 2000],
        }
    )
    artist = pd.DataFrame(
        {
            "artist_id": [3, 3, 4],
            "ms_played": [1000, 2000, 500],
        }
    )

    def load_frames(_conn, selected_kinds, **_kwargs):
        load_order.append(selected_kinds)
        if selected_kinds == ("track", "album"):
            return primary.copy(), None
        if selected_kinds == ("artist",):
            return None, artist.copy()
        raise AssertionError(selected_kinds)

    monkeypatch.setattr(snapshot_module, "_load_filtered_search_frames", load_frames)
    monkeypatch.setattr(
        snapshot_module,
        "compute_album_project_plays",
        lambda *_args, **_kwargs: pd.DataFrame(
            {"album_project_id": [2], "play_count": [2], "total_ms": [3000]}
        ),
    )
    monkeypatch.setattr(snapshot_module, "invalidate", released.append)
    monkeypatch.setattr(snapshot_module.gc, "collect", lambda: 0)

    track_metrics, album_metrics, artist_metrics = snapshot_module._metric_maps(
        conn, _context(merge_level=1)
    )

    assert load_order == [("track", "album"), ("artist",)]
    assert track_metrics == {1: (2, 3000)}
    assert album_metrics == {2: (2, 3000)}
    assert artist_metrics == {3: (2, 3000), 4: (1, 500)}
    assert released == ["db", "db"]


def test_search_frame_loader_skips_unused_duration_slices(monkeypatch) -> None:
    from backend.services import music_search_service

    calls: list[dict[str, object]] = []

    def load_period(*_args, **kwargs):
        calls.append(kwargs)
        return pd.DataFrame(), pd.DataFrame(), {}

    monkeypatch.setattr(music_search_service, "load_period_plays", load_period)

    music_search_service._load_filtered_search_frames(
        _conn(),
        ("track", "album", "artist"),
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
    )

    assert len(calls) == 2
    assert all(call["attach_duration_slices"] is False for call in calls)


def test_shared_frame_snapshot_matches_exact_context_rows(monkeypatch) -> None:
    conn = _conn()
    contexts = _shared_contexts(conn)
    metric_maps = {
        (context.merge_level, context.dynamic_threshold): (
            {1: (4 + context.merge_level, 4000 + context.merge_level)},
            {2: (5 + context.merge_level, 5000 + context.merge_level)},
            {3: (6, 6000)},
        )
        for context in contexts
    }
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._shared_metric_maps",
        lambda *_args, **_kwargs: dict(metric_maps),
    )
    chart_lookup: dict[str, dict[Any, MusicSearchChartSummary]] = {
        "track": {1: MusicSearchChartSummary(power_score=90, power_rank=1)},
        "album": {},
        "artist": {"Artist": MusicSearchChartSummary(power_score=80, power_rank=2)},
    }
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._load_shared_logical_frames",
        lambda _conn, threshold_contexts, _selected_kinds: {
            threshold_contexts[0].dynamic_threshold: (pd.DataFrame(), pd.DataFrame())
        },
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._shared_chart_lookups",
        lambda *_args, **_kwargs: {
            (context.merge_level, context.dynamic_threshold): chart_lookup for context in contexts
        },
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._build_chart_lookup",
        lambda **_kwargs: pytest.fail("shared rebuild performed a per-variant chart history load"),
    )

    report = build_shared_full_music_search_snapshot_set(
        conn,
        contexts,
        source_generation_id="import-g2",
    )

    assert report is not None
    assert report["strategy"] == "shared_full_snapshot_rebuild"
    assert report["shared_logical_frame_sets"] == 2
    for context in contexts:
        expected = _context_rows(
            conn,
            context,
            metric_maps=metric_maps[(context.merge_level, context.dynamic_threshold)],
            chart_lookup=chart_lookup,
        )
        actual = conn.execute(
            """SELECT entity_key, play_events, total_ms, peak_position, peak_weeks,
                      weeks_on_chart, weeks_at_no1, power_score, power_rank,
                      first_week, latest_week, first_peak_week
               FROM music_search_entity_context WHERE snapshot_key=?
               ORDER BY entity_key""",
            (context.filter_fingerprint,),
        ).fetchall()
        assert [tuple(row) for row in actual] == sorted(expected, key=lambda row: row[0])


def test_shared_metric_maps_loads_primary_and_artist_sequentially_per_threshold(
    monkeypatch,
) -> None:
    conn = _conn()
    contexts = tuple(
        _context(
            merge_level=merge_level,
            dynamic_threshold=dynamic,
            filter_fingerprint=f"shared-{merge_level}-{int(dynamic)}",
        )
        for merge_level, dynamic in (
            (2, True),
            (1, True),
            (3, True),
            (2, False),
            (1, False),
            (3, False),
        )
    )
    calls: list[tuple[bool, tuple[str, ...]]] = []

    def load_frames(_conn, kinds, **kwargs):
        calls.append((bool(kwargs["dynamic_threshold"]), kinds))
        return (
            pd.DataFrame({"track_id": [1], "ms_played": [1000]}),
            pd.DataFrame({"artist_id": [3], "ms_played": [1000]}),
        )

    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._load_filtered_search_frames", load_frames
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot.load_track_group_keys",
        lambda *_args, **_kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot.compute_album_project_plays",
        lambda *_args, **_kwargs: pd.DataFrame(
            columns=["album_project_id", "play_count", "total_ms"]
        ),
    )

    maps = _shared_metric_maps(conn, contexts)

    assert calls == [
        (True, ("artist",)),
        (True, ("track", "album")),
        (False, ("artist",)),
        (False, ("track", "album")),
    ]
    assert len(maps) == 6


def test_shared_metric_maps_match_exact_builder_for_all_six_variants(monkeypatch) -> None:
    conn = _conn()
    contexts = _shared_contexts(conn)

    def load_frames(_conn, selected_kinds, **kwargs):
        dynamic = bool(kwargs["dynamic_threshold"])
        primary = pd.DataFrame(
            {
                "track_id": [1, 2, 2],
                "ms_played": [1000, 2000, 3000 + int(dynamic)],
            }
        )
        artists = pd.DataFrame(
            {
                "artist_id": [3, 3, 4],
                "ms_played": [1000, 2000 + int(dynamic), 500],
            }
        )
        return (
            primary if any(kind in selected_kinds for kind in ("track", "album")) else None,
            artists if "artist" in selected_kinds else None,
        )

    def group_keys(_conn, merge_level):
        if merge_level <= 1:
            return pd.DataFrame(columns=["track_id", "track_agg_id"])
        return pd.DataFrame({"track_id": [2], "track_agg_id": [1]})

    def album_plays(frame, _conn, **_kwargs):
        if frame.empty:
            return pd.DataFrame(columns=["album_project_id", "play_count", "total_ms"])
        return pd.DataFrame(
            {
                "album_project_id": [2],
                "play_count": [len(frame)],
                "total_ms": [int(frame["ms_played"].sum())],
            }
        )

    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._load_filtered_search_frames", load_frames
    )
    monkeypatch.setattr("backend.domains.music_search.snapshot.load_track_group_keys", group_keys)
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot.compute_album_project_plays", album_plays
    )

    shared = _shared_metric_maps(conn, contexts)

    from backend.domains.music_search import snapshot as snapshot_module

    for context in contexts:
        assert shared[(context.merge_level, context.dynamic_threshold)] == (
            snapshot_module._metric_maps(conn, context)
        )


def test_shared_chart_artist_weighted_rows_use_raw_grouping_semantics(monkeypatch) -> None:
    from backend.domains.music_search import snapshot as snapshot_module

    context = _context(merge_level=2, dynamic_threshold=True)
    artist_weighted = pd.DataFrame(
        [
            {
                "billboard_week": "2026-01-02",
                "artist_id": 3,
                "artist_name": "Artist A",
                "track_id": 1,
                "play_count": 1,
                "total_ms": 0,
            },
            {
                "billboard_week": "2026-01-02",
                "artist_id": 3,
                "artist_name": "Artist A",
                "track_id": 1,
                "play_count": 0,
                "total_ms": 1000,
            },
            {
                "billboard_week": "2026-01-02",
                "artist_id": 4,
                "artist_name": "Artist B",
                "track_id": 2,
                "play_count": 1,
                "total_ms": 500,
            },
        ]
    )
    primary = pd.DataFrame()
    primary.attrs["weighted_frame"] = pd.DataFrame({"value": [1]})
    artist_weighted.attrs["weighted_frame"] = pd.DataFrame({"value": [1]})
    empty_weekly = pd.DataFrame()

    def rebuild_weighted_without_loader_attrs(frame, **_kwargs):
        assert frame.attrs == {}
        return frame

    monkeypatch.setattr(
        snapshot_module,
        "build_billboard_weighted_frame",
        rebuild_weighted_without_loader_attrs,
    )
    monkeypatch.setattr(snapshot_module, "current_open_billboard_week", lambda **_: None)
    monkeypatch.setattr(snapshot_module, "keep_complete_billboard_weeks", lambda frame, **_: frame)
    monkeypatch.setattr(snapshot_module, "compute_weekly_rankings", lambda *_a, **_k: empty_weekly)
    monkeypatch.setattr(
        snapshot_module, "compute_album_weekly_rankings", lambda *_a, **_k: empty_weekly
    )
    monkeypatch.setattr(snapshot_module, "compute_track_summary", lambda *_a, **_k: empty_weekly)

    lookups = snapshot_module._shared_chart_lookups(
        _conn(),
        (context,),
        {True: (primary, artist_weighted)},
    )

    artists = lookups[(2, True)]["artist"]
    assert artists["Artist A"].peak_position == 1
    assert artists["Artist B"].peak_position == 2
    assert artists["Artist A"].power_rank == 1


def test_shared_chart_frames_match_billboard_source_album_schema(monkeypatch) -> None:
    from backend.domains.music_search import snapshot as snapshot_module

    context = _context(merge_level=1, dynamic_threshold=False)
    primary = pd.DataFrame(
        {
            "track_id": [1, 2],
            "track_album_id": [10, 20],
            "source_album_id": [pd.NA, 21],
            "album_name": ["Track Album", "Other Track Album"],
            "source_album_name": [pd.NA, "Playback Source Album"],
        }
    )
    artist = primary.assign(artist_id=[3, 4], artist_name=["Artist A", "Artist B"])
    captured: list[pd.DataFrame] = []

    def capture_billboard_schema(frame, **_kwargs):
        captured.append(frame.copy())
        return frame.assign(
            billboard_week="2026-01-02",
            play_count=1,
            total_ms=1,
        )

    empty_weekly = pd.DataFrame()
    monkeypatch.setattr(
        snapshot_module,
        "build_billboard_weighted_frame",
        capture_billboard_schema,
    )
    monkeypatch.setattr(snapshot_module, "current_open_billboard_week", lambda **_: None)
    monkeypatch.setattr(snapshot_module, "keep_complete_billboard_weeks", lambda frame, **_: frame)
    monkeypatch.setattr(snapshot_module, "compute_weekly_rankings", lambda *_a, **_k: empty_weekly)
    monkeypatch.setattr(
        snapshot_module, "compute_album_weekly_rankings", lambda *_a, **_k: empty_weekly
    )
    monkeypatch.setattr(
        snapshot_module, "compute_artist_weekly_rankings", lambda *_a, **_k: empty_weekly
    )
    monkeypatch.setattr(snapshot_module, "compute_track_summary", lambda *_a, **_k: empty_weekly)

    snapshot_module._shared_chart_lookups(
        _conn(),
        (context,),
        {False: (primary, artist)},
    )

    assert len(captured) == 2
    for frame in captured:
        assert "track_album_id" not in frame.columns
        assert frame["album_name"].tolist() == ["Track Album", "Playback Source Album"]

    captured.clear()
    dynamic_context = _context(merge_level=1, dynamic_threshold=True)
    monkeypatch.setattr(
        snapshot_module,
        "_ordinary_album_chart_has_track_fallback",
        lambda *_args: True,
    )
    snapshot_module._shared_chart_lookups(
        _conn(),
        (dynamic_context,),
        {True: (primary, artist)},
    )

    assert len(captured) == 2
    for frame in captured:
        assert frame["track_album_id"].tolist() == [10, 20]
        assert frame["album_name"].tolist() == ["Track Album", "Playback Source Album"]


def test_shared_chart_skips_unloaded_primary_or_artist_family(monkeypatch) -> None:
    from backend.domains.music_search import snapshot as snapshot_module

    context = _context(merge_level=2, dynamic_threshold=True)
    primary = pd.DataFrame(
        {
            "billboard_week": ["2026-01-02"],
            "track_id": [1],
            "play_count": [1],
            "total_ms": [1000],
        }
    )
    artist = pd.DataFrame(
        {
            "billboard_week": ["2026-01-02"],
            "track_id": [1],
            "artist_name": ["Artist"],
            "play_count": [1],
            "total_ms": [1000],
        }
    )
    calls: list[str] = []
    empty = pd.DataFrame()

    def record_call(kind: str) -> pd.DataFrame:
        calls.append(kind)
        return empty

    monkeypatch.setattr(snapshot_module, "build_billboard_weighted_frame", lambda frame, **_: frame)
    monkeypatch.setattr(snapshot_module, "current_open_billboard_week", lambda **_: None)
    monkeypatch.setattr(snapshot_module, "keep_complete_billboard_weeks", lambda frame, **_: frame)
    monkeypatch.setattr(
        snapshot_module,
        "compute_weekly_rankings",
        lambda *_a, **_k: record_call("track"),
    )
    monkeypatch.setattr(
        snapshot_module,
        "compute_album_weekly_rankings",
        lambda *_a, **_k: record_call("album"),
    )
    monkeypatch.setattr(
        snapshot_module,
        "compute_artist_weekly_rankings",
        lambda *_a, **_k: record_call("artist"),
    )
    monkeypatch.setattr(snapshot_module, "compute_track_summary", lambda *_a, **_k: empty)

    snapshot_module._shared_chart_lookups(
        _conn(),
        (context,),
        {True: (primary, pd.DataFrame())},
    )
    assert calls == ["track", "album"]

    calls.clear()
    snapshot_module._shared_chart_lookups(
        _conn(),
        (context,),
        {True: (pd.DataFrame(), artist)},
    )
    assert calls == ["artist"]


def test_shared_full_requires_exact_unique_six_variant_matrix() -> None:
    conn = _conn()
    duplicate = _shared_contexts(conn)[0]

    with pytest.raises(ValueError, match="exact six supported variants"):
        build_shared_full_music_search_snapshot_set(
            conn,
            (duplicate,) * 6,
            source_generation_id="import-g2",
        )


def test_shared_full_releases_each_threshold_before_loading_next(monkeypatch) -> None:
    conn = _conn()
    contexts = _shared_contexts(conn)
    from backend.domains.music_search import snapshot as snapshot_module

    frame_sets: list[dict[bool, tuple[pd.DataFrame, pd.DataFrame]]] = []
    load_order: list[tuple[bool, tuple[str, ...]]] = []

    def load_frames(_conn, threshold_contexts, selected_kinds):
        if frame_sets:
            assert frame_sets[-1] == {}
        dynamic = threshold_contexts[0].dynamic_threshold
        load_order.append((dynamic, selected_kinds))
        frames = {dynamic: (pd.DataFrame(), pd.DataFrame())}
        frame_sets.append(frames)
        return frames

    monkeypatch.setattr(snapshot_module, "_load_shared_logical_frames", load_frames)
    monkeypatch.setattr(
        snapshot_module,
        "_shared_metric_maps",
        lambda _conn, threshold_contexts, **_: {
            (context.merge_level, context.dynamic_threshold): ({}, {}, {})
            for context in threshold_contexts
        },
    )
    monkeypatch.setattr(
        snapshot_module,
        "_shared_chart_lookups",
        lambda _conn, threshold_contexts, _frames, **_kwargs: {
            (context.merge_level, context.dynamic_threshold): {
                "track": {},
                "album": {},
                "artist": {},
            }
            for context in threshold_contexts
        },
    )

    report = build_shared_full_music_search_snapshot_set(
        conn,
        contexts,
        source_generation_id="import-g2",
    )

    assert report is not None
    assert report["ready_count"] == 6
    assert load_order == [
        (True, ("artist",)),
        (True, ("track", "album")),
        (False, ("artist",)),
        (False, ("track", "album")),
    ]
    assert frame_sets == [{}, {}, {}, {}]


def test_shared_full_failure_never_partially_activates_variants(monkeypatch) -> None:
    conn = _conn()
    contexts = _shared_contexts(conn)
    from backend.domains.music_search import snapshot as snapshot_module

    monkeypatch.setattr(
        snapshot_module,
        "_load_shared_logical_frames",
        lambda _conn, threshold_contexts, _selected_kinds: {
            threshold_contexts[0].dynamic_threshold: (pd.DataFrame(), pd.DataFrame())
        },
    )
    monkeypatch.setattr(
        snapshot_module,
        "_shared_metric_maps",
        lambda _conn, threshold_contexts, **_: {
            (context.merge_level, context.dynamic_threshold): ({}, {}, {})
            for context in threshold_contexts
        },
    )
    monkeypatch.setattr(
        snapshot_module,
        "_shared_chart_lookups",
        lambda _conn, threshold_contexts, _frames, **_kwargs: {
            (context.merge_level, context.dynamic_threshold): {
                "track": {},
                "album": {},
                "artist": {},
            }
            for context in threshold_contexts
        },
    )
    monkeypatch.setattr(
        snapshot_module,
        "_context_rows",
        lambda _conn, context, **_kwargs: [
            (
                f"track:{context.merge_level}:{int(context.dynamic_threshold)}",
                1,
                1000,
                *(None,) * 9,
            )
        ],
    )
    failed_fingerprint = contexts[3].filter_fingerprint
    conn.execute(
        f"""CREATE TRIGGER fail_shared_snapshot_insert
            BEFORE INSERT ON music_search_entity_context
            WHEN NEW.snapshot_key='{failed_fingerprint}'
            BEGIN SELECT RAISE(ABORT, 'fixture failure'); END"""
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="fixture failure"):
        build_shared_full_music_search_snapshot_set(
            conn,
            contexts,
            source_generation_id="import-g2",
        )

    statuses = conn.execute(
        "SELECT status FROM music_search_snapshot_meta WHERE semantic_base_key=?",
        (contexts[0].semantic_base_key,),
    ).fetchall()
    assert len(statuses) == 6
    assert {row[0] for row in statuses} == {"failed"}
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM music_search_entity_context WHERE snapshot_key IN ({})".format(
                ",".join("?" for _ in contexts)
            ),
            tuple(context.filter_fingerprint for context in contexts),
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("drift", ("playback", "candidate", "semantic"))
def test_shared_full_publish_fence_rejects_mid_build_drift(monkeypatch, drift: str) -> None:
    conn = _conn()
    contexts = _shared_contexts(conn)
    from backend.domains.music_search import snapshot as snapshot_module

    monkeypatch.setattr(
        snapshot_module,
        "_load_shared_logical_frames",
        lambda _conn, threshold_contexts, _selected_kinds: {
            threshold_contexts[0].dynamic_threshold: (pd.DataFrame(), pd.DataFrame())
        },
    )
    monkeypatch.setattr(
        snapshot_module,
        "_shared_metric_maps",
        lambda _conn, threshold_contexts, **_: {
            (context.merge_level, context.dynamic_threshold): ({}, {}, {})
            for context in threshold_contexts
        },
    )
    monkeypatch.setattr(
        snapshot_module,
        "_shared_chart_lookups",
        lambda _conn, threshold_contexts, _frames, **_kwargs: {
            (context.merge_level, context.dynamic_threshold): {
                "track": {},
                "album": {},
                "artist": {},
            }
            for context in threshold_contexts
        },
    )
    calls = 0

    def drift_on_last_context(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 6:
            if drift == "playback":
                conn.execute(
                    "UPDATE playback_import_state SET active_generation_id='import-g3' WHERE state_id=1"
                )
            elif drift == "candidate":
                conn.execute(
                    "UPDATE music_search_index_state SET active_generation_id='g2' WHERE state_id=1"
                )
            else:
                bump_music_search_revisions(conn, "playback")
            conn.commit()
        return []

    monkeypatch.setattr(snapshot_module, "_context_rows", drift_on_last_context)

    with pytest.raises(RuntimeError, match="changed during shared-full snapshot build"):
        build_shared_full_music_search_snapshot_set(
            conn,
            contexts,
            source_generation_id="import-g2",
        )

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM music_search_snapshot_meta WHERE status='ready' AND semantic_base_key=?",
            (contexts[0].semantic_base_key,),
        ).fetchone()[0]
        == 0
    )


def test_shared_full_snapshot_rejects_stale_playback_generation(monkeypatch) -> None:
    conn = _conn()
    conn.execute(
        "UPDATE playback_import_state SET active_generation_id='current-generation' WHERE state_id=1"
    )
    conn.commit()
    contexts = _shared_contexts(conn)
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot._load_shared_logical_frames",
        lambda *_args, **_kwargs: pytest.fail("stale generation loaded playback history"),
    )

    assert (
        build_shared_full_music_search_snapshot_set(
            conn,
            contexts,
            source_generation_id="stale-generation",
        )
        is None
    )


def test_shared_chart_lookup_recomputes_power_rank_within_each_family(monkeypatch) -> None:
    from backend.domains.music_search import snapshot as snapshot_module

    context = _context(merge_level=2, dynamic_threshold=True)
    weekly = pd.DataFrame(
        [
            {
                "billboard_week": "2026-01-02",
                "track_id": 1,
                "track_name": "Track A",
                "artist_name": "Artist A",
                "album_name": "Album A",
                "play_count": 10,
                "total_ms": 1000,
                "rank": 1,
            },
            {
                "billboard_week": "2026-01-02",
                "track_id": 2,
                "track_name": "Track B",
                "artist_name": "Artist B",
                "album_name": "Album B",
                "play_count": 5,
                "total_ms": 500,
                "rank": 2,
            },
        ]
    )
    weekly_album = pd.DataFrame(
        [
            {
                "billboard_week": "2026-01-02",
                "album_project_id": 10,
                "album_name": "Album A",
                "artist_name": "Artist A",
                "play_count": 10,
                "total_ms": 1000,
                "rank": 1,
            }
        ]
    )
    weekly_artist = pd.DataFrame(
        [
            {
                "billboard_week": "2026-01-02",
                "artist_name": "Artist A",
                "play_count": 10,
                "total_ms": 1000,
                "tracks_count": 1,
                "rank": 1,
            }
        ]
    )
    monkeypatch.setattr(snapshot_module, "build_billboard_weighted_frame", lambda frame, **_: frame)
    monkeypatch.setattr(snapshot_module, "current_open_billboard_week", lambda **_: None)
    monkeypatch.setattr(snapshot_module, "keep_complete_billboard_weeks", lambda frame, **_: frame)
    monkeypatch.setattr(snapshot_module, "compute_weekly_rankings", lambda *_a, **_k: weekly)
    monkeypatch.setattr(
        snapshot_module, "compute_album_weekly_rankings", lambda *_a, **_k: weekly_album
    )
    monkeypatch.setattr(
        snapshot_module, "compute_artist_weekly_rankings", lambda *_a, **_k: weekly_artist
    )

    lookups = snapshot_module._shared_chart_lookups(
        _conn(),
        (context,),
        {True: (weekly.copy(), weekly_artist.copy())},
    )
    chart = lookups[(2, True)]

    assert chart["track"][1].power_rank == 1
    assert chart["track"][2].power_rank == 2
    assert chart["album"][("Album A", "Artist A")].power_rank == 1
    assert chart["artist"]["Artist A"].power_rank == 1


def test_legacy_ready_snapshot_is_fail_closed_when_builder_version_mismatches() -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status,
               semantic_base_key, merge_level, dynamic_threshold, builder_version
           ) VALUES ('legacy', 'legacy', 'source', 'ready', 'base', 2, 1, 'v1')"""
    )
    conn.execute(
        """INSERT INTO music_search_entity_context(
               snapshot_key, entity_key, play_events, total_ms
           ) VALUES ('legacy', 'track:1', 99, 999)"""
    )
    conn.commit()

    assert get_music_search_snapshot_status(conn, "legacy") == "stale"
    assert get_ready_music_search_snapshot_key(conn, "legacy") is None
    response = lookup_music_search_context(
        conn,
        filter_fingerprint="legacy",
        entity_keys=["track:1"],
    )
    assert response.snapshot_status == "stale"
    assert response.items == {}


def test_snapshot_prune_removes_context_when_foreign_keys_are_disabled() -> None:
    conn = _conn()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    rows = (
        ("old", "old", "old", "stale", "base-old", "2026-01-01 00:00:00"),
        ("previous", "previous", "previous", "ready", "base-previous", "2026-01-02 00:00:00"),
        ("current", "current", "current", "ready", "base-current", "2026-01-03 00:00:00"),
    )
    conn.executemany(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status,
               semantic_base_key, created_at, builder_version
           ) VALUES (?, ?, ?, ?, ?, ?, 'music_search_snapshot_v2')""",
        rows,
    )
    conn.executemany(
        """INSERT INTO music_search_entity_context(
               snapshot_key, entity_key, play_events, total_ms
           ) VALUES (?, 'track:1', 1, 1000)""",
        (("old",), ("previous",), ("current",)),
    )
    conn.commit()

    from backend.domains.music_search import snapshot as snapshot_module

    snapshot_module._prune_old_music_search_snapshot_bases(conn, "base-current")

    assert {
        row[0] for row in conn.execute("SELECT snapshot_key FROM music_search_snapshot_meta")
    } == {"current", "previous"}
    assert {
        row[0] for row in conn.execute("SELECT snapshot_key FROM music_search_entity_context")
    } == {"current", "previous"}
