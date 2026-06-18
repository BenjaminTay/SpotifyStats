from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.providers.base import (
    ProviderAuthError,
    ProviderHTTPError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderRateLimitError,
    ProviderServerError,
)

pytestmark = pytest.mark.contract


def test_provider_errors_return_structured_response_with_request_id():
    errors = {
        "network": ProviderNetworkError("spotify", "connect timeout"),
        "auth": ProviderAuthError("spotify", "upstream token expired", 401),
        "rate-limit": ProviderRateLimitError("spotify", "slow down", 429),
        "server": ProviderServerError("spotify", "upstream outage", 503),
        "parse": ProviderParseError("wikipedia", "invalid json"),
        "http": ProviderHTTPError("genius", "not found", 404),
    }

    async def raise_provider_error(kind: str):
        raise errors[kind]

    original_routes = list(app.router.routes)
    app.get("/api/__test/provider-error/{kind}")(raise_provider_error)
    app.openapi_schema = None

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            cases = {
                "network": (503, "provider_network_error", "spotify", None),
                "auth": (502, "provider_auth_error", "spotify", 401),
                "rate-limit": (429, "provider_rate_limited", "spotify", 429),
                "server": (502, "provider_server_error", "spotify", 503),
                "parse": (502, "provider_parse_error", "wikipedia", None),
                "http": (502, "provider_http_error", "genius", 404),
            }
            for kind, (status_code, error_code, provider, upstream_status) in cases.items():
                request_id = f"provider-error-{kind}"
                response = client.get(
                    f"/api/__test/provider-error/{kind}",
                    headers={"X-Request-ID": request_id},
                )

                assert response.status_code == status_code
                assert response.headers["X-Request-ID"] == request_id
                detail = response.json()["detail"]
                assert detail["error"] == error_code
                assert detail["provider"] == provider
                assert detail["status"] == upstream_status
                assert "connect timeout" not in response.text
                assert "upstream token expired" not in response.text
    finally:
        app.router.routes[:] = original_routes
        app.openapi_schema = None
