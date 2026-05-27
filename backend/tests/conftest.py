"""Shared fixtures for backend tests.

All tests use the real SQLite database in read-only mode. Since this
is a single-user local app, there is no separate test database — the
tests validate correctness against the actual data.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
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
def billboard_data():
    """Module-scoped shared Billboard result — computed once per module.

    compute_billboard_data() is the most expensive call in the test suite.
    Caching it at module scope avoids recomputing for every test method,
    cutting total test time by ~60%.
    """
    from backend.services.billboard_service import compute_billboard_data
    return compute_billboard_data(
        min_ms=30000, music_only=True,
        bb_top_n=30, bb_album_top_n=20, bb_artist_top_n=20,
    )
