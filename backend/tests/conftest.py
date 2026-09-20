"""Shared fixtures for backend tests.

Database and derived paths are isolated before application import. By default
tests use the portable seed; production-shaped tests may explicitly supply an
Online Backup outside repository data/. Contract tests can still replace the
session database with function-scoped copies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.tests.path_safety import VIOLATIONS, install_test_paths

# Must run before backend.main and before test-module collection.
TEST_STATE_ROOT = install_test_paths()

from backend import main as main_module  # noqa: E402

main_module._COVERS_DIR = str(TEST_STATE_ROOT / "covers")
app = main_module.app

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
def isolated_test_database():
    """The import-time bootstrap already copied the source into test ownership."""
    yield str(TEST_STATE_ROOT / "spotify_stats-test.db")


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


def pytest_sessionfinish(session, exitstatus):
    # Even a product catch-all must not turn a blocked formal write into a pass.
    if VIOLATIONS:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_sep("!", "Blocked backend test access to formal data")
            for violation in sorted(set(VIOLATIONS)):
                reporter.write_line(violation)


@pytest.fixture
def published_community_snapshot(client):
    """Read-only smoke probes consume a privately prepared Community publication."""
    from backend.core.db import get_db
    from backend.services.community_snapshot_service import ensure

    conn = get_db(readonly=True)
    try:
        ensure(conn)
    finally:
        conn.close()


@pytest.fixture
def published_analysis_snapshot(client):
    """Prepare real default publications through the private maintenance path."""
    import json

    from backend.core.db import get_db
    from backend.services import analysis_snapshot_service as service

    conn = get_db(readonly=True)
    try:
        for family in service.VERSIONS:
            params, key, revision, _ = service.request_context(conn, family, {})
            service.rebuild(family, json.dumps(params, sort_keys=True), key, revision)
    finally:
        conn.close()


@pytest.fixture
def published_archive_snapshot(client):
    """Publish fixture facts before whole-API read probes; never builds on GET."""
    from backend.core.db import get_db
    from backend.domains.account_archive.snapshot_revision import install_revision_tracking
    from backend.services.account_archive_snapshot_service import ensure

    conn = get_db(readonly=False)
    try:
        with conn:
            install_revision_tracking(conn)
        ensure(conn)
    finally:
        conn.close()


@pytest.fixture
def published_governance_snapshot():
    from backend.core.db import get_db
    from backend.domains.metadata.governance_revision import install_revision_tracking
    from backend.services.governance_snapshot_service import ensure

    conn = get_db(readonly=False)
    try:
        with conn:
            install_revision_tracking(conn)
        ensure(conn)
    finally:
        conn.close()


@pytest.fixture
def published_artist_rank_context(client):
    from backend.core.db import get_db
    from backend.services.entity_rank_context_service import ensure

    conn = get_db(readonly=True)
    try:
        ensure(conn)
    finally:
        conn.close()
