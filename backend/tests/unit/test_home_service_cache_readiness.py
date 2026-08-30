from __future__ import annotations

import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

from backend.services import home_service

pytestmark = pytest.mark.unit


def test_composite_cache_refreshes_when_preview_readiness_changes(monkeypatch):
    calls = []
    context = SimpleNamespace(
        model_dump_json=lambda: "{}",
        filter_fingerprint="fp",
    )

    class ContextModel:
        @classmethod
        def model_validate_json(cls, _value):
            return context

    def fake_build(_conn, _context):
        calls.append("build")
        return {"generation": len(calls)}

    monkeypatch.setattr(home_service, "YearlyReviewFilterContext", ContextModel)
    monkeypatch.setattr(
        home_service,
        "get_db",
        lambda readonly=True: sqlite3.connect(":memory:"),
    )
    monkeypatch.setattr(home_service, "build_home_overview", fake_build)
    home_service._get_home_overview_cached.cache_clear()

    first = home_service._get_home_overview_cached("{}", "db", "day", 0, "2026:key:0")
    again = home_service._get_home_overview_cached("{}", "db", "day", 0, "2026:key:0")
    billboard_ready = home_service._get_home_overview_cached("{}", "db", "day", 1, "2026:key:0")
    yearly_ready = home_service._get_home_overview_cached("{}", "db", "day", 1, "2026:key:1")

    assert first == again == {"generation": 1}
    assert billboard_ready == {"generation": 2}
    assert yearly_ready == {"generation": 3}


def test_revision_miss_serves_last_good_while_exact_snapshot_rebuilds(monkeypatch, tmp_path):
    context = SimpleNamespace(
        min_ms=30000,
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
        bb_week_start_hour=12,
        display_taxonomy_version="v1",
    )

    class ContextModel:
        @classmethod
        def model_validate_json(cls, _value):
            return context

    rebuild_started = threading.Event()
    release_rebuild = threading.Event()
    calls = 0

    def fake_build(_conn, _context):
        nonlocal calls
        calls += 1
        if calls > 1:
            rebuild_started.set()
            assert release_rebuild.wait(timeout=2)
        return {"generation": calls}

    monkeypatch.setattr(home_service, "YearlyReviewFilterContext", ContextModel)
    monkeypatch.setattr(home_service, "get_db", lambda readonly=True: sqlite3.connect(":memory:"))
    monkeypatch.setattr(home_service, "_is_primary_connection", lambda _conn: True)
    monkeypatch.setattr(home_service, "_HOME_SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(home_service, "build_home_overview", fake_build)
    home_service._get_home_overview_cached.cache_clear()

    assert home_service._lkg_snapshot_path(context).name.startswith("lkg-home-facts-v4-")

    first = home_service._get_home_overview_cached("{}", "rev-1", "facts", 1, "yearly")
    home_service._get_home_overview_cached.cache_clear()
    stale = home_service._get_home_overview_cached("{}", "rev-2", "facts", 1, "yearly")

    assert first == {"generation": 1, "cache_state": "fresh"}
    assert stale == {"generation": 1, "cache_state": "warming"}
    assert rebuild_started.wait(timeout=1)
    release_rebuild.set()
    deadline = time.time() + 2
    while time.time() < deadline:
        with home_service._rebuild_guard:
            rebuilding = bool(home_service._rebuild_paths)
        if calls == 2 and not rebuilding:
            break
        time.sleep(0.01)
    assert calls == 2 and not rebuilding
