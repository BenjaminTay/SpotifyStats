from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import HTTPException

from backend.core.access_surface import reset_public_readonly_db_guard, set_public_readonly_db_guard
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services import home_service as home

pytestmark = pytest.mark.unit


def _context():
    return YearlyReviewFilterContext(
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        display_taxonomy_version="v1",
        artist_metadata_revision="1",
        artist_identity_revision=1,
        track_credit_revision=1,
        track_group_revision="1",
        album_project_revision="1",
        filter_fingerprint="fp",
    )


@pytest.mark.parametrize(
    "state", ["exact", "lkg", "missing", "incompatible", "key_error", "corrupt"]
)
def test_public_home_only_reads_published_files(tmp_path, monkeypatch, state):
    context = _context()
    parts = (context.model_dump_json(), "source", "facts", 1, "yearly")
    monkeypatch.setattr(home, "_HOME_SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(home, "_cache_parts", lambda _context: parts)
    exact = home._snapshot_path(tuple(str(part) for part in parts))
    lkg = home._lkg_snapshot_path(context)
    payload = {
        "generated_at": "2026-09-19T00:00:00Z",
        "filter_fingerprint": "real-filter",
        "state": "ready",
        "coverage": {},
        "archive": {
            "total_plays": 17,
            "total_hours": 1,
            "unique_tracks": 2,
            "unique_artists": 1,
            "unique_albums": 1,
            "active_days": 2,
        },
        "headline": {"kind": "archive", "title": "Archive", "statement": "17 plays"},
        "billboard": {"state": "unavailable"},
        "yearly_review": {"state": "not_generated"},
    }
    if state == "exact":
        exact.write_text(json.dumps(payload))
    elif state in {"lkg", "key_error"}:
        lkg.write_text(json.dumps(payload))
    elif state == "incompatible":
        other = context.model_copy(update={"merge_level": 3})
        home._lkg_snapshot_path(other).write_text(json.dumps(payload))
    elif state == "corrupt":
        exact.write_text('{"incomplete":true}')
        lkg.write_text("broken")

    def forbidden(*_args, **_kwargs):
        pytest.fail("public Home attempted a calculation, private LRU, write or thread")

    for name in (
        "build_home_overview",
        "_get_home_overview_cached",
        "_write_snapshot",
        "_start_snapshot_rebuild",
    ):
        monkeypatch.setattr(home, name, forbidden)
    if state == "key_error":

        def bad_key(_context):
            raise ValueError("revision unavailable")

        monkeypatch.setattr(home, "_cache_parts", bad_key)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()}
    token = set_public_readonly_db_guard(True)
    conn = sqlite3.connect(":memory:")
    try:
        if state in {"exact", "lkg"}:
            result = home.get_home_overview(conn, context)
            assert result.archive.total_plays == 17
            assert result.snapshot.target_revision == exact.stem
            assert result.snapshot.source_revision == (exact.stem if state == "exact" else None)
            assert result.snapshot.freshness == (
                "current" if state == "exact" else "last_known_good"
            )
        else:
            with pytest.raises(HTTPException) as error:
                home.get_home_overview(conn, context)
            assert error.value.status_code == 503
            assert error.value.detail["status"] == "unavailable"
    finally:
        conn.close()
        reset_public_readonly_db_guard(token)
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()} == before


def test_home_writer_and_thread_helpers_also_reject_public_calls(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("public helper started a thread")

    monkeypatch.setattr(home.threading, "Thread", forbidden)
    token = set_public_readonly_db_guard(True)
    try:
        home._write_snapshot(tmp_path / "new-dir" / "snapshot.json", {})
        home._start_snapshot_rebuild(
            exact_path=tmp_path / "exact.json",
            lkg_path=tmp_path / "lkg.json",
            context=_context(),
        )
    finally:
        reset_public_readonly_db_guard(token)
    assert not list(tmp_path.iterdir())


def test_home_key_ignores_process_preview_counters(tmp_path, monkeypatch):
    from backend.domains.billboard import persistent_cache as cache
    from backend.domains.billboard.latest_snapshot_cache import (
        clear_latest_snapshots,
        store_latest_snapshot,
    )

    context = _context()
    monkeypatch.setattr(home, "database_revision", lambda: "source:1")
    monkeypatch.setattr(home, "yearly_review_cache_state", lambda _context: "yearly:1")
    monkeypatch.setattr(home, "build_cache_context", lambda family, params: {"cache_key": "stable"})
    monkeypatch.setattr(cache, "BILLBOARD_CACHE_PATH", str(tmp_path / "billboard.db"))
    conn = sqlite3.connect(cache.BILLBOARD_CACHE_PATH)
    conn.execute("CREATE TABLE billboard_snapshots(cache_key TEXT PRIMARY KEY,payload_sha256 TEXT)")
    conn.execute("INSERT INTO billboard_snapshots VALUES('stable','content:1')")
    conn.commit()
    before = home._cache_parts(context)
    store_latest_snapshot(("other",), {"meta": {"all_weeks_desc": []}})
    clear_latest_snapshots()
    assert home._cache_parts(context) == before
    conn.execute("UPDATE billboard_snapshots SET payload_sha256='content:2'")
    conn.commit()
    assert home._cache_parts(context) != before
    conn.close()
