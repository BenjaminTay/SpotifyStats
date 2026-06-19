from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.main import app

pytestmark = pytest.mark.contract

JSON_RESPONSE_ROUTES = (
    ("POST", "/api/billboard/release-cycle/compare"),
    ("GET", "/api/lyrics/{track_id}"),
    ("GET", "/api/lyrics/{track_id}/url"),
)


def _find_route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_remaining_json_routes_declare_response_models():
    for method, path in JSON_RESPONSE_ROUTES:
        route = _find_route(method, path)

        assert route.response_model is not None, f"{method} {path} missing response_model"


def test_remaining_json_routes_publish_openapi_response_schema():
    schema = app.openapi()
    for method, path in JSON_RESPONSE_ROUTES:
        operation = schema["paths"][path][method.lower()]
        response = operation["responses"]["200"]

        assert "application/json" in response["content"], f"{method} {path} missing JSON content"
        assert "schema" in response["content"]["application/json"], (
            f"{method} {path} missing response schema"
        )
