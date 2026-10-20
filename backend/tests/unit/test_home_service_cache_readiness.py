from __future__ import annotations

import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

from backend.services import home_service

pytestmark = pytest.mark.unit


def test_maintenance_restores_only_exact_weekly_preview(monkeypatch):
    from backend.domains.billboard import latest_snapshot_cache as preview
    from backend.services.billboard_snapshot_service import configured_billboard_filters

    context = SimpleNamespace(**configured_billboard_filters())
    calls = []
    monkeypatch.setattr(
        home_service,
        "build_cache_context",
        lambda family, params: {"family": family, "params": params},
    )
    payload = {
        "meta": {"all_weeks_desc": ["2026-10-09"]},
        "weekly": [],
        "weekly_album": [],
        "weekly_artist": [],
    }
    monkeypatch.setattr(
        home_service,
        "load_persisted_snapshot",
        lambda key, **kw: calls.append((key, kw)) or payload,
    )
    preview.clear_latest_snapshots()
    assert home_service._restore_billboard_preview(context)
    assert calls[0][0]["family"] == "weekly"
    assert calls[0][1] == {"allow_lkg": False}
    key = preview.snapshot_key(**calls[0][0]["params"])
    assert preview.get_latest_snapshot_if_cached(key)["meta"] == payload["meta"]
    preview.clear_latest_snapshots()
    monkeypatch.setattr(home_service, "load_persisted_snapshot", lambda *a, **k: None)
    assert not home_service._restore_billboard_preview(context)
    assert preview.get_latest_snapshot_if_cached(key) is None
    monkeypatch.setattr(home_service, "public_readonly_db_guard_active", lambda: True)
    monkeypatch.setattr(
        home_service,
        "load_persisted_snapshot",
        lambda *a, **k: pytest.fail("public maintenance read"),
    )
    assert not home_service._restore_billboard_preview(context)


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


def test_private_prewarm_replaces_an_old_unavailable_home_file(monkeypatch, tmp_path):
    from backend.services import yearly_review_service

    context = SimpleNamespace()
    monkeypatch.setattr(
        yearly_review_service, "build_default_yearly_review_context", lambda: context
    )
    monkeypatch.setattr(home_service, "get_db", lambda **kw: sqlite3.connect(":memory:"))
    monkeypatch.setattr(home_service, "_is_primary_connection", lambda conn: True)
    monkeypatch.setattr(home_service, "_HOME_SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(
        home_service, "_cache_parts", lambda ctx: ("context", "rev", "v", "bb", "yr")
    )
    monkeypatch.setattr(home_service, "_lkg_snapshot_path", lambda ctx: tmp_path / "lkg.json")
    monkeypatch.setattr(home_service, "_present_home_payload", lambda payload: payload)
    monkeypatch.setattr(
        home_service, "HomeOverviewResponse", SimpleNamespace(model_validate=lambda p: p)
    )
    restored = []
    monkeypatch.setattr(
        home_service, "_restore_billboard_preview", lambda ctx: restored.append(ctx)
    )
    monkeypatch.setattr(
        home_service, "build_home_overview", lambda conn, ctx: {"billboard": {"state": "ready"}}
    )
    path = home_service._snapshot_path(home_service._cache_parts(context))
    home_service._write_snapshot(path, {"billboard": {"state": "unavailable"}})
    assert home_service.prewarm_default_home_overview()["billboard"]["state"] == "ready"
    assert restored == [context]
    assert home_service._read_snapshot(path)["billboard"]["state"] == "ready"


def test_revision_miss_serves_last_good_while_exact_snapshot_rebuilds(monkeypatch, tmp_path):
    monkeypatch.setattr(home_service, "_restore_billboard_preview", lambda context: False)
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

    assert first["generation"] == 1 and first["cache_state"] == "fresh"
    assert first["snapshot"]["freshness"] == "current"
    assert stale["generation"] == 1 and stale["cache_state"] == "warming"
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
