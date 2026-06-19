from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.providers.base import ProviderNetworkError

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    ("path", "params", "patched_name"),
    [
        (
            "/api/billboard/enrichment/album/Unknown%20Album",
            {"artist_name": "Unknown Artist"},
            "get_album_wiki",
        ),
        (
            "/api/billboard/enrichment/artist/Unknown%20Artist",
            {},
            "get_artist_wiki",
        ),
        (
            "/api/billboard/enrichment/track/Unknown%20Track",
            {"artist_name": "Unknown Artist", "include_genius": False},
            "get_track_wiki",
        ),
    ],
)
def test_billboard_enrichment_degrades_when_wikipedia_lookup_fails(
    monkeypatch, path, params, patched_name
):
    import backend.api.billboard.enrichment as enrichment_api

    def fail_wiki_lookup(*_args, **_kwargs):
        raise RuntimeError("wikipedia wrapper failed")

    monkeypatch.setattr(enrichment_api, patched_name, fail_wiki_lookup)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path, params=params)

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {"wiki": None, "genius": None}


def test_billboard_enrichment_preserves_provider_error_response(monkeypatch):
    import backend.api.billboard.enrichment as enrichment_api

    def fail_with_provider_error(*_args, **_kwargs):
        raise ProviderNetworkError("wikipedia", "connect timeout")

    monkeypatch.setattr(enrichment_api, "get_artist_wiki", fail_with_provider_error)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/billboard/enrichment/artist/Unknown%20Artist",
            headers={"X-Request-ID": "enrichment-provider-error"},
        )

    assert response.status_code == 503
    assert response.headers["x-request-id"] == "enrichment-provider-error"
    assert response.json()["detail"] == {
        "error": "provider_network_error",
        "provider": "wikipedia",
        "status": None,
    }
