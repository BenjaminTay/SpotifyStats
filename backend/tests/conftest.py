"""Shared fixtures for backend tests.

When the local production-shaped database exists, integration tests preserve
its data distribution without connecting writable services or the persistent
JobQueue to the user's real file.  Clean CI checkouts fall back to the tracked
portable seed.  Either source is copied into a session-scoped SQLite database;
contract tests may temporarily replace it with their own function-scoped copy.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.integration


def _resolve_test_database_source(configured_path: str) -> Path:
    """Choose an existing read-only source without creating the live DB path."""
    configured = Path(configured_path).resolve()
    if configured.is_file():
        return configured
    seed = Path(__file__).resolve().parent / "fixtures" / "seed.db"
    if seed.is_file():
        return seed
    raise FileNotFoundError(
        f"backend test database source is missing: configured={configured} fallback={seed}"
    )


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database(tmp_path_factory: pytest.TempPathFactory):
    """Route the whole backend test session through a recoverable DB copy.

    This is deliberately an Online Backup instead of ``shutil.copy`` so a
    concurrently running WAL-backed development server cannot leave the test
    fixture with a torn main-file snapshot.
    """

    from backend.core import db as db_mod

    original_path = str(Path(db_mod.DB_PATH).resolve())
    configured_source = os.environ.get("SPOTIFY_STATS_TEST_SOURCE_DB", original_path)
    source_path = _resolve_test_database_source(configured_source)
    isolated_path = tmp_path_factory.mktemp("backend-session-db") / "spotify_stats-test.db"
    seed_path = (Path(__file__).resolve().parent / "fixtures" / "seed.db").resolve()
    immutable = "&immutable=1" if source_path == seed_path else ""
    source_uri = f"file:{quote(str(source_path), safe='/')}?mode=ro{immutable}"
    source = sqlite3.connect(source_uri, uri=True)
    target = sqlite3.connect(isolated_path)
    try:
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            pytest.fail("isolated backend test database failed integrity_check")
    finally:
        target.close()
        source.close()

    db_mod.DB_PATH = str(isolated_path)
    try:
        yield str(isolated_path)
    finally:
        db_mod.DB_PATH = original_path


@pytest.fixture(scope="session")
def warm_default_caches(default_params):
    """Prime expensive default caches once for correctness tests."""
    from backend.core.db import get_db, load_plays
    from backend.services.billboard_service import compute_billboard_data

    conn = get_db()
    try:
        load_plays(
            conn,
            min_ms=default_params["min_ms"],
            music_only=default_params["music_only"],
            merge_enabled=default_params["merge_enabled"],
        )
    finally:
        conn.close()

    compute_billboard_data(
        min_ms=default_params["min_ms"],
        music_only=default_params["music_only"],
        bb_top_n=default_params["bb_top_n"],
        bb_album_top_n=default_params["bb_album_top_n"],
        bb_artist_top_n=default_params["bb_artist_top_n"],
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        year_start=None,
        year_end=None,
    )


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient — shared across all tests in a module.

    Keep this fixture lightweight so focused selections like
    ``pytest -k Wrapped`` do not pay Billboard warmup costs. Tests that need
    expensive shared data should request their own warming fixture explicitly.
    The integration suite intentionally reads the real database, so derived
    search invalidation and rebuild jobs must remain disabled here as well.
    """
    with (
        patch("backend.services.music_search_maintenance_service.mark_music_search_for_rebuild"),
        patch(
            "backend.services.music_search_maintenance_service.enqueue_music_search_snapshot_rebuild",
            return_value=None,
        ),
        TestClient(app) as c,
    ):
        yield c


@pytest.fixture(scope="session")
def default_params():
    """Default filter parameters used by the API and analysis tests."""
    return {
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "bb_top_n": 30,
        "bb_album_top_n": 20,
        "bb_artist_top_n": 20,
    }


@pytest.fixture(scope="module")
def billboard_data(warm_default_caches):
    """Module-scoped shared Billboard result — computed once per module.

    compute_billboard_data() is the most expensive call in the test suite.
    Caching it at module scope avoids recomputing for every test method,
    cutting total test time by ~60%.
    """
    from backend.services.billboard_service import compute_billboard_data

    return compute_billboard_data(
        min_ms=30000,
        music_only=True,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        year_start=None,
        year_end=None,
    )
