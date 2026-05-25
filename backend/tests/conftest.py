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
