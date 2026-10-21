from __future__ import annotations

import sqlite3

import pytest

from backend.domains.music_search.context import MusicSearchFilterContext
from backend.domains.music_search.track_credit_delta import (
    TrackCreditDeltaIncompatibleError,
    _credit_scopes,
    _load_changed_raw_rows,
    _logical_by_threshold,
    _signed_artist_facts,
    apply_track_credit_statistics_delta,
)

pytestmark = pytest.mark.unit


def _context() -> MusicSearchFilterContext:
    return MusicSearchFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        merge_level=2,
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
        artist_identity_revision=1,
        track_credit_revision=2,
        track_identity_revision=1,
        track_identity_policy="canonical_track_v2",
        semantic_base_key="base",
        filter_fingerprint="target",
        source_revision="source",
    )


def _change(
    *,
    from_revision: int,
    to_revision: int,
    track_id: int = 1,
    canonical: tuple[int, ...] = (1,),
    before: tuple[int, ...] = (10,),
    after: tuple[int, ...] = (20,),
) -> dict:
    return {
        "from_revision": from_revision,
        "to_revision": to_revision,
        "track_id": track_id,
        "canonical_track_ids": list(canonical),
        "before_credits": [{"artist_id": value, "role": "primary"} for value in before],
        "after_credits": [{"artist_id": value, "role": "primary"} for value in after],
    }


def test_credit_scopes_collapse_contiguous_before_after_chain() -> None:
    scopes = _credit_scopes(
        [
            _change(from_revision=3, to_revision=4, before=(10,), after=(10, 20)),
            _change(from_revision=4, to_revision=5, before=(10, 20), after=(20,)),
        ]
    )

    assert len(scopes) == 1
    assert scopes[0].track_id == 1
    assert scopes[0].before_artist_ids == (10,)
    assert scopes[0].after_artist_ids == (20,)


def test_credit_scopes_reject_incomplete_or_overlapping_evidence() -> None:
    with pytest.raises(TrackCreditDeltaIncompatibleError, match="before/after"):
        _credit_scopes(
            [
                _change(from_revision=3, to_revision=4, before=(10,), after=(10, 20)),
                _change(from_revision=4, to_revision=5, before=(10,), after=(20,)),
            ]
        )
    with pytest.raises(TrackCreditDeltaIncompatibleError, match="overlapping"):
        _credit_scopes(
            [
                _change(from_revision=3, to_revision=4, track_id=1, canonical=(9,)),
                _change(from_revision=4, to_revision=5, track_id=2, canonical=(9,)),
            ]
        )


def _raw_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        INSERT INTO artists VALUES (10, 'Before'), (20, 'After'), (30, 'Other');
        CREATE TABLE albums(album_id INTEGER PRIMARY KEY, album_name TEXT NOT NULL);
        INSERT INTO albums VALUES (1, 'Album');
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY, track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL, album_id INTEGER, spotify_track_id TEXT
        );
        INSERT INTO tracks VALUES
            (1, 'Changed', 10, 1, NULL),
            (2, 'Interrupting', 30, 1, NULL);
        CREATE TABLE spotify_track_meta(spotify_track_id TEXT PRIMARY KEY, duration_ms INTEGER);
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY, ts TEXT NOT NULL, ts_date TEXT,
            ts_dow INTEGER, ts_hour INTEGER, ms_played INTEGER NOT NULL,
            track_id INTEGER NOT NULL, source_album_id INTEGER,
            spotify_track_id_at_play TEXT
        );
        INSERT INTO plays VALUES
            (1, '2026-01-02T10:00:00Z', '2026-01-02', 4, 10, 40000, 1, 1, NULL),
            (2, '2026-01-02T10:01:00Z', '2026-01-02', 4, 10, 40000, 1, 1, NULL),
            (3, '2026-01-02T10:02:00Z', '2026-01-02', 4, 10, 40000, 2, 1, NULL),
            (4, '2026-01-02T10:03:00Z', '2026-01-02', 4, 10, 40000, 1, 1, NULL);
        """
    )
    return conn


def test_changed_track_loader_proves_global_adjacency_without_lifetime_artist_scan() -> None:
    conn = _raw_database()
    scopes = _credit_scopes([_change(from_revision=1, to_revision=2)])

    rows = _load_changed_raw_rows(conn, scopes, max_source_rows=10)

    assert rows["play_id"].tolist() == [1, 2, 4]
    assert rows["_global_segment"].tolist() == [0, 0, 1]
    with pytest.raises(TrackCreditDeltaIncompatibleError, match="row cap"):
        _load_changed_raw_rows(conn, scopes, max_source_rows=2)


def test_signed_artist_facts_use_net_membership_and_logical_events() -> None:
    conn = _raw_database()
    scopes = _credit_scopes([_change(from_revision=1, to_revision=2)])
    raw = _load_changed_raw_rows(conn, scopes, max_source_rows=10)
    logical = _logical_by_threshold(raw, _context())[False]

    lifetime, weekly = _signed_artist_facts(
        logical,
        scopes,
        week_start_dow=4,
        week_start_hour=0,
    )

    # Unknown track duration retains one counted event per qualifying raw row;
    # all three events still move exactly once from the old to the new artist.
    assert lifetime == {10: (-3, -120_000), 20: (3, 120_000)}
    assert weekly == {
        ("2026-01-02", 10): (-3, -120_000),
        ("2026-01-02", 20): (3, 120_000),
    }


def test_delta_kill_switch_fails_closed_before_any_write(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.domains.music_search.track_credit_delta.config.MUSIC_SEARCH_TRACK_CREDIT_DELTA",
        False,
    )
    conn = sqlite3.connect(":memory:")

    with pytest.raises(TrackCreditDeltaIncompatibleError, match="kill switch"):
        apply_track_credit_statistics_delta(
            conn,
            (),
            [],
            target_revision=1,
        )

    assert conn.total_changes == 0


@pytest.mark.parametrize("replace_owner", [False, True])
def test_credit_delta_claims_targets_and_rejects_later_owner(monkeypatch, replace_owner) -> None:
    from dataclasses import replace

    import pandas as pd

    from backend.core.migrations import (
        migrate_032,
        migrate_034,
        migrate_035,
        migrate_042,
        migrate_061,
    )
    from backend.domains.music_search import snapshot
    from backend.domains.music_search import track_credit_delta as delta

    conn = _raw_database()
    migrate_032(conn)
    migrate_034(conn)
    migrate_035(conn)
    migrate_042(conn)
    migrate_061(conn)
    conn.executescript(
        "CREATE TABLE track_credit_state(state_id INTEGER PRIMARY KEY, "
        "active_aggregate_revision INTEGER); INSERT INTO track_credit_state VALUES(1,1);"
    )
    contexts = tuple(
        replace(
            _context(),
            merge_level=level,
            dynamic_threshold=dynamic,
            filter_fingerprint=f"target-{level}-{int(dynamic)}",
        )
        for level in (2, 3)
        for dynamic in (False, True)
    )
    conn.executemany(
        "INSERT INTO music_search_snapshot_variant_state(merge_level,dynamic_threshold,active_snapshot_key,active_filter_fingerprint,target_filter_fingerprint) VALUES(?,?,'old','old','old')",
        [(c.merge_level, int(c.dynamic_threshold)) for c in contexts],
    )
    conn.commit()
    monkeypatch.setattr(delta, "_validate_contexts", lambda _contexts: contexts[0])
    monkeypatch.setattr(
        delta, "get_music_search_index_state", lambda _conn: {"active_generation_id": "g1"}
    )
    monkeypatch.setattr(delta, "active_playback_lineage", lambda _conn: ("import-g1", "digest"))
    monkeypatch.setattr(
        delta,
        "_base_snapshot_keys",
        lambda *_args, **_kwargs: {c.filter_fingerprint: "old" for c in contexts},
    )
    monkeypatch.setattr(delta, "_load_changed_raw_rows", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(
        delta,
        "_artist_replacement_ledger",
        lambda *_args, **_kwargs: {c.filter_fingerprint: [] for c in contexts},
    )
    monkeypatch.setattr(delta, "_candidate_keys_for_context", lambda *_args, **_kwargs: set())
    monkeypatch.setattr(delta, "_clone_lifetime_with_artist_delta", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(delta, "_base_weekly_ledger_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(snapshot, "_active_playback_generation", lambda _conn: "import-g1")
    monkeypatch.setattr(
        snapshot,
        "get_music_search_index_state",
        lambda _conn: {"active_generation_id": "g1", "status": "ready"},
    )
    monkeypatch.setattr(
        snapshot,
        "build_music_search_filter_context",
        lambda _conn, filters: next(
            c
            for c in contexts
            if c.merge_level == filters["merge_level"]
            and c.dynamic_threshold == filters["dynamic_threshold"]
        ),
    )

    def publish(target, claimed, *_args, **_kwargs):
        if replace_owner:
            target.execute(
                "UPDATE music_search_snapshot_variant_state SET target_filter_fingerprint='newer-owner' WHERE merge_level=2 AND dynamic_threshold=1"
            )
            target.commit()
        snapshot._assert_shared_full_publish_fence(
            target,
            claimed,
            source_generation_id="import-g1",
            candidate_generation_id="g1",
            semantic_base_key="base",
        )
        assert (
            target.execute(
                "SELECT count(*) FROM music_search_snapshot_variant_state WHERE maintenance_status='pending'"
            ).fetchone()[0]
            == 4
        )
        assert (
            target.execute(
                "SELECT count(*) FROM music_search_snapshot_variant_state WHERE active_snapshot_key='old'"
            ).fetchone()[0]
            == 4
        )

    monkeypatch.setattr(delta, "_publish", publish)
    if replace_owner:
        with pytest.raises(RuntimeError, match="target ownership changed"):
            delta.apply_track_credit_statistics_delta(
                conn, contexts, [_change(from_revision=1, to_revision=2)], target_revision=2
            )
    else:
        result = delta.apply_track_credit_statistics_delta(
            conn, contexts, [_change(from_revision=1, to_revision=2)], target_revision=2
        )
        assert result["strategy"] == "track_credit_delta"
        assert result["lifetime_scan"] is False
