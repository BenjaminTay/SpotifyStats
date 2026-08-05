from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.main import app

pytestmark = pytest.mark.contract


INFRASTRUCTURE_ROUTES = (
    ("GET", "/api/health"),
    ("GET", "/api/admin/cache-stats"),
    ("POST", "/api/import/streaming"),
    ("POST", "/api/import/account"),
    ("GET", "/api/import/preflight"),
    ("GET", "/api/import/health"),
    ("GET", "/api/import/status/{job_id}"),
    ("GET", "/api/jobs/{job_id}/status"),
)


def _find_route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_infrastructure_routes_declare_response_models():
    for method, path in INFRASTRUCTURE_ROUTES:
        route = _find_route(method, path)

        assert route.response_model is not None, f"{method} {path} missing response_model"


def test_infrastructure_routes_publish_openapi_response_schema():
    schema = app.openapi()
    for method, path in INFRASTRUCTURE_ROUTES:
        operation = schema["paths"][path][method.lower()]
        response = operation["responses"]["200"]

        assert "application/json" in response["content"], f"{method} {path} missing JSON content"
        assert "schema" in response["content"]["application/json"], (
            f"{method} {path} missing response schema"
        )
