from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.core import db as db_mod
from scripts import api_boundary_probe, api_smoke_probe


@pytest.mark.parametrize(
    "configure",
    [
        api_smoke_probe._configure_database_path,
        api_boundary_probe._configure_database_path,
    ],
)
def test_probe_database_copy_disables_background_work_and_isolates_derived_caches(
    configure,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "spotify_stats.db"
    database.touch()
    monkeypatch.setenv("SPOTIFY_STATS_WARMUP", "1")
    monkeypatch.setenv("SPOTIFY_STATS_SEARCH_STARTUP_REBUILD", "1")
    monkeypatch.setenv("SPOTIFY_STATS_L3_STARTUP_RECONCILE", "1")
    cache_paths = {
        "SPOTIFY_STATS_BILLBOARD_CACHE_PATH": "billboard_cache.db",
        "SPOTIFY_STATS_ANALYSIS_CACHE_PATH": "analysis_cache.db",
        "SPOTIFY_STATS_YEARLY_CACHE_PATH": "yearly_review_cache.db",
        "SPOTIFY_STATS_COMMUNITY_CACHE_PATH": "community_cache.db",
        "SPOTIFY_STATS_ARCHIVE_CACHE_PATH": "account_archive_cache.db",
        "SPOTIFY_STATS_GOVERNANCE_CACHE_PATH": "governance_cache.db",
    }
    for key in cache_paths:
        monkeypatch.delenv(key, raising=False)
    original_db_path = db_mod.DB_PATH

    try:
        configure(str(database))

        assert db_mod.DB_PATH == str(database)
        assert os.environ["SPOTIFY_STATS_WARMUP"] == "0"
        assert os.environ["SPOTIFY_STATS_SEARCH_STARTUP_REBUILD"] == "0"
        assert os.environ["SPOTIFY_STATS_L3_STARTUP_RECONCILE"] == "0"
        for key, filename in cache_paths.items():
            assert os.environ[key] == str(tmp_path / filename)
    finally:
        db_mod.DB_PATH = original_db_path


@pytest.mark.parametrize(
    "configure",
    [
        api_smoke_probe._configure_database_path,
        api_boundary_probe._configure_database_path,
    ],
)
def test_probe_database_copy_respects_explicit_yearly_cache_path(
    configure,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "spotify_stats.db"
    database.touch()
    explicit_cache = tmp_path / "explicit-yearly.db"
    monkeypatch.setenv("SPOTIFY_STATS_YEARLY_CACHE_PATH", str(explicit_cache))
    original_db_path = db_mod.DB_PATH

    try:
        configure(str(database))

        assert os.environ["SPOTIFY_STATS_YEARLY_CACHE_PATH"] == str(explicit_cache)
    finally:
        db_mod.DB_PATH = original_db_path
