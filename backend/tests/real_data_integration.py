"""Command-level opt-in: pytest -p backend.tests.real_data_integration ..."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.tests.path_safety import ROOT, install_test_paths, require_test_path


def pytest_load_initial_conftests(early_config, parser, args):
    # A CLI plugin runs before parent conftest imports the application. Child
    # conftest must never select a database after that import has happened.
    targets = parser.parse_known_args(args).file_or_dir
    integration = (ROOT / "backend/tests/integration").resolve()
    if not targets or any(
        (path := Path(target.split("::", 1)[0]).resolve()) != integration
        and integration not in path.parents
        for target in targets
    ):
        raise pytest.UsageError("real_data_integration requires integration-only test paths")
    source = require_test_path(os.environ.get("SPOTIFY_STATS_TEST_SOURCE_DB"))
    if source is None or not source.is_file():
        raise pytest.UsageError(
            "real_data_integration requires an existing SPOTIFY_STATS_TEST_SOURCE_DB"
        )
    install_test_paths(source=source)
