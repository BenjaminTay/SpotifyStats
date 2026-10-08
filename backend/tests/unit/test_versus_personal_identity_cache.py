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
        identity = service.resolve_album_project_identity(
            conn, album_name=row[0], artist_name=row[1]
        )
        assert identity is not None
        monkeypatch.setattr(service, "resolve_album_project_identity", lambda *a, **kw: identity)
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
