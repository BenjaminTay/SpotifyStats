from __future__ import annotations

import sqlite3

import pytest

from backend.domains.billboard import persistent_cache

pytestmark = pytest.mark.unit


def _context(cache_key: str, request_key: str = "request-v1") -> dict[str, str]:
    return {
        "cache_key": cache_key,
        "request_key": request_key,
        "family": "year_end",
        "source_revision": cache_key,
        "builder_version": persistent_cache.BILLBOARD_CACHE_BUILDER_VERSION,
    }


def test_snapshot_survives_a_new_read_and_does_not_rebuild(tmp_path, monkeypatch):
    cache_path = tmp_path / "billboard_cache.db"
    monkeypatch.setattr(persistent_cache, "BILLBOARD_CACHE_PATH", str(cache_path))
    persistent_cache.clear_persisted_snapshots(cache_path)
    context = _context("exact-v1")
    payload = {"meta": {"year": 2026}, "tracks": [{"year_end_rank": 1}]}
    persistent_cache.store_persisted_snapshot(context, payload, cache_path=cache_path)

    builds = 0

    def build():
        nonlocal builds
        builds += 1
        return {"unexpected": True}

    monkeypatch.setattr(persistent_cache, "build_cache_context", lambda *_args: context)
    result = persistent_cache.get_or_build_billboard_snapshot(
        "year_end",
        {"year": 2026},
        build,
    )

    assert result == payload
    assert builds == 0


def test_new_revision_returns_the_previous_request_key_as_lkg(tmp_path):
    cache_path = tmp_path / "billboard_cache.db"
    persistent_cache.clear_persisted_snapshots(cache_path)
    old = _context("source-old")
    new = _context("source-new")
    payload = {"meta": {"year": 2025}, "tracks": [{"year_end_rank": 1}]}
    persistent_cache.store_persisted_snapshot(old, payload, cache_path=cache_path)

    assert persistent_cache.load_persisted_snapshot(new, cache_path=cache_path) == payload
    assert (
        persistent_cache.load_persisted_snapshot(
            new,
            allow_lkg=False,
            cache_path=cache_path,
        )
        is None
    )


def test_corrupt_snapshot_is_ignored_and_removed(tmp_path):
    cache_path = tmp_path / "billboard_cache.db"
    persistent_cache.clear_persisted_snapshots(cache_path)
    context = _context("corrupt")
    persistent_cache.store_persisted_snapshot(
        context,
        {"meta": {}, "tracks": []},
        cache_path=cache_path,
    )

    conn = sqlite3.connect(cache_path)
    conn.execute(
        "UPDATE billboard_snapshots SET payload=?, payload_sha256=? WHERE cache_key=?",
        (b"not-zlib", "invalid", context["cache_key"]),
    )
    conn.commit()
    conn.close()

    assert persistent_cache.load_persisted_snapshot(context, cache_path=cache_path) is None
    conn = sqlite3.connect(cache_path)
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM billboard_snapshots WHERE cache_key=?",
            (context["cache_key"],),
        ).fetchone()[0]
        == 0
    )
    conn.close()


def test_force_rebuild_replaces_lkg_for_the_current_revision(tmp_path, monkeypatch):
    cache_path = tmp_path / "billboard_cache.db"
    persistent_cache.clear_persisted_snapshots(cache_path)
    old_context = _context("source-old")
    context = _context("source-current")
    persistent_cache.store_persisted_snapshot(
        old_context,
        {"meta": {"version": "old"}},
        cache_path=cache_path,
    )
    monkeypatch.setattr(persistent_cache, "BILLBOARD_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(persistent_cache, "build_cache_context", lambda *_args: context)

    result = persistent_cache.get_or_build_billboard_snapshot(
        "weekly",
        {"merge_level": 2},
        lambda: {"meta": {"version": "new"}},
        force_rebuild=True,
    )

    assert result == {"meta": {"version": "new"}}
    assert persistent_cache.load_persisted_snapshot(context, cache_path=cache_path) == result


def test_context_key_separates_request_parameters(monkeypatch):
    monkeypatch.setattr(
        persistent_cache,
        "_dependency_state",
        lambda _family, _params: {"source": "same"},
    )

    first = persistent_cache.build_cache_context("weekly", {"merge_level": 2})
    second = persistent_cache.build_cache_context("weekly", {"merge_level": 3})

    assert first["request_key"] != second["request_key"]
    assert first["cache_key"] != second["cache_key"]
