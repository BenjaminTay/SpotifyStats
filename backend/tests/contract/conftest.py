"""Contract test fixtures — seed SQLite test DB (no production data)."""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest


@pytest.fixture(scope="function", autouse=True)
def disable_warmup(monkeypatch):
    """Disable backend warmup thread — contract tests must not pollute caches."""
    monkeypatch.setenv("SPOTIFY_STATS_WARMUP", "0")


@pytest.fixture(scope="function")
def use_seed_db():
    """Point DB_PATH at the portable seed database for each contract test."""
    seed_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "seed.db")
    seed_path = os.path.abspath(seed_path)
    if not os.path.exists(seed_path):
        pytest.fail(f"seed.db not found at {seed_path} — run build_seed_db.py first")

    import backend.core.db as db_mod

    fd, test_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy2(seed_path, test_db_path)

    original = db_mod.DB_PATH
    db_mod.DB_PATH = test_db_path

    yield test_db_path

    db_mod.DB_PATH = original
    for path in (test_db_path, f"{test_db_path}-wal", f"{test_db_path}-shm"):
        if os.path.exists(path):
            os.unlink(path)
    # Clear all lru_caches that may have been polluted with seed data
    db_mod._load_plays_cached.cache_clear()
    db_mod._load_plays_for_artists_cached.cache_clear()
    db_mod.get_track_all_artists_map.cache_clear()
    db_mod.get_track_artist_names_map.cache_clear()
    from backend.domains.billboard.chart_compute import (
        _compute_power_scores_cached,
        _compute_records_cached,
        _compute_summaries_cached,
        _compute_weekly_data_cached,
    )
    from backend.domains.billboard.data_loader import load_billboard_raw_for_artists
    from backend.services.analysis_stats_service import (
        _get_analysis_charts_cached,
        _get_analysis_stats_cached,
    )
    from backend.services.billboard_service import (
        _compute_billboard_data_cached,
        _load_album_metadata,
        compute_billboard_data,
        load_billboard_raw,
        load_track_album_map,
    )

    compute_billboard_data.cache_clear()
    _compute_billboard_data_cached.cache_clear()
    _compute_weekly_data_cached.cache_clear()
    _compute_power_scores_cached.cache_clear()
    _compute_summaries_cached.cache_clear()
    _compute_records_cached.cache_clear()
    load_billboard_raw.cache_clear()
    load_billboard_raw_for_artists.cache_clear()
    load_track_album_map.cache_clear()
    _load_album_metadata.cache_clear()
    _get_analysis_stats_cached.cache_clear()
    _get_analysis_charts_cached.cache_clear()


@pytest.fixture(scope="function")
def seed_conn(use_seed_db):
    """Return a read-only connection to the seed database for direct query tests."""
    from backend.core.db import get_db

    conn = get_db(readonly=True)
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def client(use_seed_db):  # noqa: ARG001 — must activate before client
    """Lightweight TestClient — warmup disabled, no cache pollution."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c
