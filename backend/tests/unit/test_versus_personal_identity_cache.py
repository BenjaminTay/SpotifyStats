"""Exact, bounded immutable identity sharing for personal facts and ranks."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Barrier, Event

import pytest
from fastapi import HTTPException

from backend.core import db
from backend.services import versus_personal_context as service
from backend.tests.unit import test_versus_rank_context

base_isolated = test_versus_rank_context.base_isolated
rank_isolated = test_versus_rank_context.isolated
pytestmark = pytest.mark.unit


@pytest.fixture
def isolated(rank_isolated):
    service._SELECTION_CACHE.cache_clear()
    yield rank_isolated
    service._SELECTION_CACHE.cache_clear()


def _items(conn):
    known = conn.execute("SELECT l1_id FROM track_l1_identities ORDER BY l1_id LIMIT 1").fetchone()[
        0
    ]
    return [int(known), 999999999]


def test_concurrent_readers_resolve_one_immutable_scope_and_restore_order(isolated, monkeypatch):
    original = service._resolve_selection_uncached
    entered, release = Event(), Event()
    barrier = Barrier(3)
    calls = []

    def resolve(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_resolve_selection_uncached", resolve)

    def read(index):
        conn = db.get_db(readonly=True)
        try:
            items = _items(conn)
            barrier.wait(timeout=10)
            return service.resolve_selection(
                conn, "track", items if index % 2 == 0 else items[::-1]
            )
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(read, i) for i in range(3)]
        assert entered.wait(10)
        release.set()
        first, reversed_rows, third = [future.result() for future in futures]
    assert len(calls) == 1
    assert first == third == reversed_rows[::-1]
    assert first[0] is third[0] is reversed_rows[1]
    assert first[1].rank_key == "" and first[1].entity_key.startswith("unavailable:")
    first.clear()
    assert len(third) == 2
    with pytest.raises(FrozenInstanceError):
        third[0].rank_key = "tampered"
    assert isinstance(next(iter(service._SELECTION_CACHE.values.values())), tuple)
    assert service._SELECTION_CACHE.cache_stats()["size"] == 1


def test_source_drift_during_resolution_is_503_and_never_cached(isolated, monkeypatch):
    original = service._resolve_selection_uncached

    def resolve(*args, **kwargs):
        result = original(*args, **kwargs)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        return result

    monkeypatch.setattr(service, "_resolve_selection_uncached", resolve)
    conn = db.get_db(readonly=True)
    try:
        with pytest.raises(HTTPException) as drift:
            service.resolve_selection(conn, "track", _items(conn))
        assert drift.value.status_code == 503
        assert service._SELECTION_CACHE.cache_stats()["size"] == 0
    finally:
        conn.close()


def test_cache_hit_still_fences_source_and_stale_metadata(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        items = _items(conn)
        params = service.normalise_filters(conn)
        metadata = service.context(conn, params)
        service.resolve_selection(conn, "track", items, filters=params, metadata=metadata)
        original = service._selection_for_work

        def hit_then_drift(work):
            result = original(work)
            with sqlite3.connect(isolated[0]) as writer:
                writer.execute(
                    "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
                )
            return result

        monkeypatch.setattr(service, "_selection_for_work", hit_then_drift)
        with pytest.raises(HTTPException) as drift:
            service.resolve_selection(conn, "track", items, filters=params, metadata=metadata)
        assert drift.value.status_code == 503
        assert service._SELECTION_CACHE.cache_stats()["hits"] == 1
        with pytest.raises(HTTPException) as stale:
            service.resolve_selection(conn, "track", items, filters=params, metadata=metadata)
        assert stale.value.status_code == 503
    finally:
        conn.close()


def test_seven_filters_and_source_revision_partition_scope_keys(isolated, monkeypatch):
    original = service._resolve_selection_uncached
    calls = []

    def resolve(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_resolve_selection_uncached", resolve)
    conn = db.get_db(readonly=True)
    try:
        items = _items(conn)
        params = service.normalise_filters(conn)
        variants = [params] + [
            {**params, key: value}
            for key, value in dict(
                min_ms=params["min_ms"] + 1,
                music_only=not params["music_only"],
                merge_enabled=not params["merge_enabled"],
                dynamic_threshold=not params["dynamic_threshold"],
                max_merge_gap_minutes=params["max_merge_gap_minutes"] + 1,
                merge_level=3,
                include_compilations=not params["include_compilations"],
            ).items()
        ]
        for filters in variants:
            service.resolve_selection(conn, "track", items, filters["merge_level"], filters=filters)
        assert len(calls) == 8
        assert service._SELECTION_CACHE.cache_stats()["size"] == 8
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE tracks SET track_name=track_name || ' updated' WHERE track_id=(SELECT MIN(track_id) FROM tracks)"
            )
        service.resolve_selection(conn, "track", items, filters=params)
        assert len(calls) == 9
        assert service._SELECTION_CACHE.cache_stats()["size"] == 8
        # The oldest exact key was evicted; key tuples and immutable entities
        # contain no caller connection, frame or mutable source containers.
        for key, entities in service._SELECTION_CACHE.values.items():
            assert isinstance(key, tuple) and isinstance(entities, tuple)
            assert all(isinstance(entity, service.SelectedEntity) for entity in entities)
            assert all(isinstance(entity.track_ids, tuple) for entity in entities)
    finally:
        conn.close()


def test_online_backup_with_same_revision_has_separate_inode_cache_key(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    copy_path = isolated[1] / "identity-copy.db"
    copied = sqlite3.connect(copy_path)
    copied.row_factory = sqlite3.Row
    calls = []
    original = service._resolve_selection_uncached

    def resolve(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_resolve_selection_uncached", resolve)
    try:
        conn.backup(copied)
        copied.execute("PRAGMA query_only=ON")
        params = service.normalise_filters(conn)
        assert service.context(conn, params) == service.context(copied, params)
        items = _items(conn)
        assert service.resolve_selection(conn, "track", items) == service.resolve_selection(
            copied, "track", items
        )
        assert len(calls) == 2
        assert service._SELECTION_CACHE.cache_stats()["size"] == 2
        assert conn.execute("SELECT 1").fetchone()[0] == 1
        assert copied.execute("SELECT 1").fetchone()[0] == 1
    finally:
        copied.close()
        conn.close()


def test_cached_scope_cannot_bypass_batch_or_canonical_duplicate_validation(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        items = _items(conn)
        service.resolve_selection(conn, "track", items)
        for invalid in ([items[0]], [items[0]] * 2, [items[0]] * 5):
            with pytest.raises(ValueError):
                service.resolve_selection(conn, "track", invalid)
        # Canonical/member album spellings can converge only during resolution;
        # that validation remains in the uncached resolver and no failure is stored.
        row = conn.execute(
            "SELECT ap.canonical_name,ar.artist_name FROM album_projects ap "
            "JOIN artists ar ON ar.artist_id=ap.artist_id LIMIT 1"
        ).fetchone()
        assert row is not None
        from backend.domains.playback.album_project_identity import resolve_album_project_identity

        identity = resolve_album_project_identity(conn, album_name=row[0], artist_name=row[1])
        assert identity is not None
        monkeypatch.setattr(
            service, "resolve_album_project_identities", lambda *a, **kw: [identity, identity]
        )
        with pytest.raises(ValueError, match="归并后重复"):
            service.resolve_selection(
                conn,
                "album",
                [
                    dict(album_name="Canonical spelling", artist_name=row[1]),
                    dict(album_name="Member spelling", artist_name=row[1]),
                ],
            )
        assert service._SELECTION_CACHE.cache_stats()["size"] == 1
    finally:
        conn.close()


@pytest.mark.parametrize("level", [2, 3])
def test_album_batch_scopes_membership_and_maps_canonical_graph_once(isolated, monkeypatch, level):
    import pandas as pd

    from backend.domains.playback import album_projects
    from backend.domains.playback.album_project_identity import resolve_album_project_identity
    from backend.domains.playback.l3_album_attribution import load_l3_song_album_attributions

    conn = db.get_db(readonly=True)
    try:
        candidates = pd.read_sql_query(
            "SELECT i.l1_id AS track_id,t.track_name FROM track_l1_identities i "
            "JOIN tracks t ON t.track_id=i.representative_track_id "
            "WHERE i.identity_status IN ('active','unresolved')",
            conn,
        )
        expected_candidates = album_projects.apply_canonical_song_keys(candidates, conn, level)
        if level == 3:
            membership = load_l3_song_album_attributions(conn)
            membership = membership[membership["include_in_charts"] == 1]
        else:
            membership = pd.read_sql_query(
                "SELECT DISTINCT apt.project_id, COALESCE(links.l1_id,apt.track_id) AS track_id,"
                "COALESCE(rep.track_name,t.track_name) AS track_name "
                "FROM album_project_tracks apt JOIN tracks t ON t.track_id=apt.track_id "
                "LEFT JOIN track_l1_source_links links ON links.track_id=apt.track_id "
                "LEFT JOIN track_l1_identities li ON li.l1_id=links.l1_id "
                "LEFT JOIN tracks rep ON rep.track_id=li.representative_track_id "
                "WHERE apt.min_merge_level<=?",
                conn,
                params=(level,),
            )
            membership = album_projects.apply_canonical_song_keys(membership, conn, level)
        items, identities = [], []
        for row in conn.execute(
            "SELECT ap.canonical_name, ar.artist_name FROM album_projects ap "
            "JOIN artists ar ON ar.artist_id=ap.artist_id ORDER BY ap.project_id"
        ):
            item = dict(album_name=row[0], artist_name=row[1])
            identity = resolve_album_project_identity(conn, **item, merge_level=level)
            if identity and identity.project_id not in {value.project_id for value in identities}:
                items.append(item)
                identities.append(identity)
            if len(items) == 2:
                break
        assert len(items) == 2
        expected = []
        for item, identity in zip(items, identities):
            keys = set(
                membership.loc[
                    membership["project_id"] == identity.project_id, "canonical_song_key"
                ].dropna()
            )
            ids = tuple(
                sorted(
                    set(
                        expected_candidates.loc[
                            expected_candidates["canonical_song_key"].isin(keys), "track_id"
                        ].astype(int)
                    )
                )
            )
            expected.append(
                service.SelectedEntity(
                    service.requested_key("album", item),
                    f"album:{identity.project_id}",
                    str(identity.project_id),
                    service._source_tracks(conn, ids),
                    album_name=identity.canonical_name,
                    artist_name=identity.artist_name,
                    artist_id=identity.artist_id,
                    project_id=identity.project_id,
                    song_keys=tuple(sorted(keys)),
                )
            )
        calls, statements = [], []
        original = album_projects.apply_canonical_song_keys

        def canonical(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(album_projects, "apply_canonical_song_keys", canonical)
        conn.set_trace_callback(statements.append)
        actual = service._resolve_selection_uncached(conn, "album", items, level)
        conn.set_trace_callback(None)
        assert actual == expected
        assert calls == [1]
        membership_queries = [
            sql
            for sql in statements
            if (
                "FROM album_project_tracks apt" in sql
                if level == 2
                else "FROM l3_song_album_attributions attribution" in sql
            )
        ]
        assert len(membership_queries) == 1
        assert "project_id IN (" in membership_queries[0]
        assert all(str(identity.project_id) in membership_queries[0] for identity in identities)
    finally:
        conn.close()


@pytest.mark.parametrize("level", [2, 3])
def test_unknown_album_batch_retains_unavailable_identity_without_writes(isolated, level):
    conn = db.get_db(readonly=True)
    try:
        before = conn.total_changes
        rows = service._resolve_selection_uncached(
            conn,
            "album",
            [
                dict(album_name="missing-one", artist_name="missing"),
                dict(album_name="missing-two", artist_name="missing"),
            ],
            level,
        )
        assert all(not row.rank_key and not row.track_ids for row in rows)
        assert conn.total_changes == before
    finally:
        conn.close()


@pytest.mark.parametrize(
    "column,value",
    [
        ("missing_row", None),
        ("status", "empty"),
        ("policy_version", "obsolete"),
        ("track_identity_revision", -1),
        ("album_project_revision", -1),
    ],
)
def test_l3_selected_and_full_reads_share_readiness_rejection(isolated, column, value):
    from backend.domains.playback.l3_album_attribution import load_l3_song_album_attributions

    with sqlite3.connect(isolated[0]) as writer:
        if column == "missing_row":
            writer.execute("DELETE FROM l3_album_attribution_revision_state")
        else:
            writer.execute(f"UPDATE l3_album_attribution_revision_state SET {column}=?", (value,))
    conn = db.get_db(readonly=True)
    try:
        with pytest.raises(RuntimeError, match="missing or stale"):
            load_l3_song_album_attributions(conn)
        with pytest.raises(HTTPException) as missing:
            service._resolve_selection_uncached(
                conn,
                "album",
                [
                    dict(album_name="missing-one", artist_name="missing"),
                    dict(album_name="missing-two", artist_name="missing"),
                ],
                3,
            )
        assert missing.value.status_code == 503
    finally:
        conn.close()


def test_missing_l3_projection_table_rejects_required_reads_without_bootstrap(isolated):
    from backend.domains.playback.l3_album_attribution import (
        load_l3_song_album_attributions,
        validate_l3_song_album_attributions,
    )

    with sqlite3.connect(isolated[0]) as writer:
        writer.execute("DROP TABLE l3_song_album_attributions")
    conn = db.get_db(readonly=True)
    try:
        before = conn.total_changes
        assert not validate_l3_song_album_attributions(conn, require_ready=False)
        assert load_l3_song_album_attributions(conn, require_ready=False).empty
        with pytest.raises(RuntimeError, match="has not been built"):
            load_l3_song_album_attributions(conn)
        with pytest.raises(HTTPException) as missing:
            service._resolve_selection_uncached(
                conn,
                "album",
                [
                    dict(album_name="missing-one", artist_name="missing"),
                    dict(album_name="missing-two", artist_name="missing"),
                ],
                3,
            )
        assert missing.value.status_code == 503
        assert conn.total_changes == before
        assert not service._table_exists(conn, "l3_song_album_attributions")
    finally:
        conn.close()


def test_artist_batch_reads_effective_credits_once_and_expands_same_l1_sources(
    isolated, monkeypatch
):
    from backend.domains.metadata.artist_identity import resolve_artist_name

    conn = db.get_db(readonly=True)
    try:
        items, artists = [], []
        for row in conn.execute("SELECT artist_name FROM artists ORDER BY artist_id"):
            artist = resolve_artist_name(conn, row[0])
            if artist and artist.canonical_artist_id not in {
                value.canonical_artist_id for value in artists
            }:
                items.append(row[0])
                artists.append(artist)
            if len(items) == 4:
                break
        assert len(items) >= 2
        original = service.get_effective_track_credits
        credits = original(conn)
        expected_ids = [
            tuple(
                sorted(
                    {
                        int(credit["track_id"])
                        for credit in credits
                        if credit["artist_id"] == artist.canonical_artist_id
                    }
                )
            )
            for artist in artists
        ]
        calls = []

        def effective(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(service, "get_effective_track_credits", effective)
        rows = service._resolve_selection_uncached(conn, "artist", items)
        assert calls == [1]
        for row, artist, ids in zip(rows, artists, expected_ids):
            assert row.credited_track_ids == ids
            assert row.artist_id == artist.canonical_artist_id
            assert row.rank_key == artist.display_name
            assert row.track_ids == service._source_tracks(conn, service._l1_tracks(conn, ids))
    finally:
        conn.close()
