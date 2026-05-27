"""Shared fixtures for backend tests.

All tests use the real SQLite database in read-only mode. Since this
is a single-user local app, there is no separate test database — the
tests validate correctness against the actual data.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


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
def client(warm_default_caches):
    """FastAPI TestClient — shared across all tests in a module."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def default_params():
    """Default filter parameters matching the Streamlit app defaults."""
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
        min_ms=30000, music_only=True,
        bb_top_n=30, bb_album_top_n=20, bb_artist_top_n=20,
        bb_week_start_dow=4, bb_week_start_hour=0,
        year_start=None, year_end=None,
    )
