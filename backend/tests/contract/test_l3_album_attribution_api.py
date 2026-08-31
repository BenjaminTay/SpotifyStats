from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_l3_album_attribution_openapi_contract_is_auditable_and_bounded() -> None:
    from backend.main import app

    schema = app.openapi()
    paths = schema["paths"]
    listing = paths["/api/version-merge/l3-album-attributions"]["get"]
    query = next(item for item in listing["parameters"] if item["name"] == "q")

    assert query["schema"]["maxLength"] == 200
    assert "200" in listing["responses"]
    assert "/api/version-merge/l3-album-attributions/health" in paths
    assert "/api/version-merge/l3-album-attributions/rebuild" in paths
    assert "/api/version-merge/l3-album-attributions/overrides" in paths
    assert "/api/version-merge/l3-album-attributions/overrides/{override_id}" in paths


def test_l3_album_attribution_override_body_requires_stable_ids_and_reason() -> None:
    from backend.api.version_merge import L3AlbumAttributionOverrideRequest

    payload = L3AlbumAttributionOverrideRequest(
        anchor_track_id=12,
        target_project_id=34,
        reason="人工确认原生专辑",
    )
    assert payload.action == "force_target"
    with pytest.raises(ValueError):
        L3AlbumAttributionOverrideRequest(
            anchor_track_id=0,
            target_project_id=34,
            reason="人工确认原生专辑",
        )
    with pytest.raises(ValueError):
        L3AlbumAttributionOverrideRequest(
            anchor_track_id=12,
            target_project_id=34,
            reason="短",
        )
