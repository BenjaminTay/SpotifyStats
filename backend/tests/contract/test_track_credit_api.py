from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.core.db import get_db
from backend.main import app

pytestmark = pytest.mark.contract


def _route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"route not found: {method} {path}")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/music-metadata/track-credits/status"),
        ("GET", "/api/music-metadata/track-credits/tracks"),
        ("GET", "/api/music-metadata/track-credits/artist-candidates"),
        ("GET", "/api/music-metadata/track-credits/tracks/{track_id}"),
        ("GET", "/api/music-metadata/track-credits/events"),
        ("GET", "/api/music-metadata/track-credits/manual-changes"),
        ("POST", "/api/music-metadata/track-credits/preview"),
        ("POST", "/api/music-metadata/track-credits/overrides"),
        ("PUT", "/api/music-metadata/track-credits/overrides/{override_id}"),
        ("POST", "/api/music-metadata/track-credits/overrides/{override_id}/remove"),
        ("POST", "/api/music-metadata/track-credits/events/{event_id}/undo"),
        ("POST", "/api/music-metadata/track-credits/rebuild"),
    ],
)
def test_track_credit_routes_have_response_contract(method: str, path: str):
    route = _route(method, path)
    assert route.response_model is not None
    operation = app.openapi()["paths"][path][method.lower()]
    assert "schema" in operation["responses"]["200"]["content"]["application/json"]


def test_track_credit_preview_uses_stable_local_ids(client):
    conn = get_db(readonly=False)
    try:
        conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (99042, 'Fixture Elton')")
        conn.execute(
            "INSERT INTO artists(artist_id, artist_name) VALUES (99053, 'Fixture Britney')"
        )
        conn.execute(
            """INSERT INTO tracks(track_id, track_name, artist_id, spotify_track_id)
               VALUES (99175, 'Fixture Hold Me Closer', 99042, 'fixture-hold-me-closer')"""
        )
        conn.execute(
            "INSERT INTO track_artists(track_id, artist_id, role) VALUES (99175, 99042, 'primary')"
        )
        conn.execute(
            """INSERT INTO plays(
                   play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                   platform, ms_played, track_id, content_type
               ) VALUES (
                   99175, '2022-08-26T00:00:00Z', 2022, 8, 34, 4, 0, '2022-08-26',
                   'test', 202245, 99175, 'audio'
               )"""
        )
        conn.commit()
    finally:
        conn.close()
    response = client.post(
        "/api/music-metadata/track-credits/preview",
        json={
            "track_id": 99175,
            "artist_id": 99053,
            "action": "add",
            "role": "featured",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["track"]["spotify_track_id"] == "fixture-hold-me-closer"
    assert body["artist"]["artist_id"] == 99053
    assert body["artist"]["artist_name"] == "Fixture Britney"
    assert body["impact"]["single_track_play_delta"] == 0
    assert [credit["artist_id"] for credit in body["after"]] == [99042, 99053]


def test_track_credit_preview_rejects_name_only_payload(client):
    response = client.post(
        "/api/music-metadata/track-credits/preview",
        json={
            "track_id": 99175,
            "artist_name": "Britney Spears",
            "action": "add",
            "role": "featured",
        },
    )
    assert response.status_code == 422


def test_metadata_write_schemas_do_not_require_reason_or_evidence():
    from backend.api.artist_identity import (
        IdentityCreateRequest,
        IdentityUndoRequest,
        IdentityUpdateRequest,
    )
    from backend.api.track_credits import (
        TrackCreditMutationRequest,
        TrackCreditRemoveRequest,
        TrackCreditRoleUpdateRequest,
        TrackCreditUndoRequest,
    )

    mutation = TrackCreditMutationRequest(
        track_id=175,
        artist_id=53,
        action="add",
        role="featured",
        expected_revision=1,
        idempotency_key="direct-create-key",
    )
    assert mutation.reason is None
    assert mutation.evidence_type is None
    assert (
        TrackCreditRoleUpdateRequest(
            role="primary", expected_revision=1, idempotency_key="direct-role-key"
        ).reason
        is None
    )
    assert (
        TrackCreditRemoveRequest(
            expected_revision=1, idempotency_key="direct-remove-key"
        ).evidence_type
        is None
    )
    assert (
        TrackCreditUndoRequest(expected_revision=1, idempotency_key="direct-undo-key").reason
        is None
    )

    identity = IdentityCreateRequest(
        artist_ids=[1, 2],
        canonical_artist_id=1,
        display_name="Artist",
        expected_revision=1,
        idempotency_key="identity-create-key",
    )
    assert identity.reason is None
    assert (
        IdentityUpdateRequest(expected_revision=1, idempotency_key="identity-update-key").reason
        is None
    )
    assert (
        IdentityUndoRequest(expected_revision=1, idempotency_key="identity-undo-key").reason is None
    )
