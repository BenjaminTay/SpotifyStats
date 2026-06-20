from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def test_account_summary_uses_shared_cache_for_same_database_file(monkeypatch, tmp_path):
    from backend.services import account_service as svc

    db_path = tmp_path / "account-cache.db"
    conn_a = sqlite3.connect(db_path)
    conn_b = sqlite3.connect(db_path)
    calls = 0

    def fake_build(conn: sqlite3.Connection) -> dict:
        nonlocal calls
        calls += 1
        database_path = conn.execute("PRAGMA database_list").fetchone()[2]
        return {"call": calls, "database_path": database_path}

    svc._get_account_summary_cached.cache_clear()
    monkeypatch.setattr(svc, "_build_account_summary", fake_build)

    try:
        first = svc.get_account_summary(conn_a)
        second = svc.get_account_summary(conn_b)
    finally:
        conn_a.close()
        conn_b.close()
        svc._get_account_summary_cached.cache_clear()

    assert first == second
    assert calls == 1
    assert svc._get_account_summary_cached.cache_stats() == {"hits": 0, "misses": 0, "size": 0}


def test_account_summary_bypasses_cache_for_memory_connection(monkeypatch):
    from backend.services import account_service as svc

    conn = sqlite3.connect(":memory:")
    calls = 0

    def fake_build(conn: sqlite3.Connection) -> dict:
        nonlocal calls
        calls += 1
        return {"call": calls}

    svc._get_account_summary_cached.cache_clear()
    monkeypatch.setattr(svc, "_build_account_summary", fake_build)

    try:
        first = svc.get_account_summary(conn)
        second = svc.get_account_summary(conn)
    finally:
        conn.close()
        svc._get_account_summary_cached.cache_clear()

    assert first == {"call": 1}
    assert second == {"call": 2}


def test_account_summary_cache_is_registered_for_namespace_invalidation():
    from backend.core.cache_manager import get_stats
    from backend.services import account_service as svc

    svc._get_account_summary_cached.cache_clear()

    stats = get_stats()

    assert "account" in stats
    assert "summary" in stats["account"]["ttl"]
