"""Real-distribution integration tests require their own explicit pytest process."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def require_real_data_integration(request):
    if not request.config.pluginmanager.hasplugin("backend.tests.real_data_integration"):
        pytest.fail(
            "Run integration with -p backend.tests.real_data_integration and SPOTIFY_STATS_TEST_SOURCE_DB"
        )
