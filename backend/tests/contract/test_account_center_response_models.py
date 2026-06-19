from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.main import app

pytestmark = pytest.mark.contract

ACCOUNT_CENTER_ROUTES = (
    ("GET", "/api/search-history"),
    ("GET", "/api/insights/tiers"),
    ("GET", "/api/insights/marquee"),
    ("GET", "/api/podcast"),
    ("GET", "/api/podcast/interactions"),
    ("GET", "/api/podcast/saved-shows"),
    ("GET", "/api/video"),
    ("GET", "/api/profile"),
    ("GET", "/api/profile/inferences"),
    ("GET", "/api/profile/sound-capsule"),
    ("GET", "/api/wrapped-hub/available-years"),
    ("GET", "/api/wrapped-hub"),
)


def _find_route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_account_center_routes_declare_response_models():
    for method, path in ACCOUNT_CENTER_ROUTES:
        route = _find_route(method, path)

        assert route.response_model is not None, f"{method} {path} missing response_model"


def test_account_center_routes_publish_openapi_response_schema():
    schema = app.openapi()
    for method, path in ACCOUNT_CENTER_ROUTES:
        operation = schema["paths"][path][method.lower()]
        response = operation["responses"]["200"]

        assert "application/json" in response["content"], f"{method} {path} missing JSON content"
        assert "schema" in response["content"]["application/json"], (
            f"{method} {path} missing response schema"
        )
