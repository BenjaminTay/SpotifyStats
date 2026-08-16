from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.core.migrations import migrate_032, migrate_034
from backend.domains.music_search.context import (
    MusicSearchFilterContext,
    build_music_search_filter_context,
)
from backend.domains.music_search.revisions import bump_music_search_revisions
from backend.domains.music_search.snapshot import (
    build_music_search_snapshot,
    build_music_search_snapshot_set,
    get_music_search_snapshot_status,
    get_ready_music_search_entity_keys,
    get_ready_music_search_snapshot_key,
    lookup_music_search_context,
    mark_music_search_derived_data_dirty,
)
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
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='g1', status='ready', source_revision='index-r1'"""
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
        search_index_revision="index-r1",
        artist_identity_revision=0,
        track_credit_revision=0,
        semantic_base_key="base-r1",
        filter_fingerprint=filter_fingerprint,
        source_revision="source-r1",
    )


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
    assert released == ["billboard", "db"] * 3
    assert collected == [True, True, True]


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
