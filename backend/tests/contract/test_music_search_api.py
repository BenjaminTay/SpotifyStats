from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.access_surface import PUBLIC_READONLY_SURFACE, SURFACE_HEADER
from backend.core.db import get_db
from backend.domains.music_search.index import rebuild_music_search_index
from backend.main import app
from backend.services.music_search_maintenance_service import (
    rebuild_current_music_search_derived_data,
)

pytestmark = pytest.mark.contract


@pytest.fixture
def client(use_seed_db: str) -> Iterator[TestClient]:
    del use_seed_db
    with TestClient(app) as test_client:
        yield test_client


def test_music_search_endpoint_returns_grouped_results(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Song 4", "kind": "track"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Alpha Song 4"
    assert data["limit_per_type"] == 5
    assert data["total"] == 1
    assert data["tracks"][0]["label"] == "Alpha Song 4"
    assert data["tracks"][0]["href"] == "/music/tracks/4"
    assert data["tracks"][0]["cover_url"] == "/covers/albums/1.jpg"
    assert data["albums"] == []
    assert data["artists"] == []
    assert response.headers["x-request-id"]
    server_timing = response.headers["server-timing"]
    assert "filtered_frames;dur=" in server_timing
    assert "resolve_track;dur=" in server_timing
    assert "total;dur=" in server_timing
    assert "Alpha Song 4" not in server_timing


def test_music_search_endpoint_accepts_kind_filter(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Debut", "kind": "album"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tracks"] == []
    assert data["albums"][0]["href"] == "/music/albums/Alpha%20Debut?artist=Alpha"
    assert data["albums"][0]["cover_url"] == "/covers/albums/1.jpg"
    assert data["artists"] == []


def test_music_search_endpoint_can_include_chart_shape(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Song 4", "kind": "track", "include_chart": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tracks"][0]["label"] == "Alpha Song 4"
    assert "chart" in data["tracks"][0]


def test_music_search_endpoint_rejects_oversized_limit(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "Alpha Song 4", "limit_per_type": 50})

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_music_search_endpoint_rejects_invalid_kind(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "Alpha Song 4", "kind": "playlist"})

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_music_search_endpoint_is_available_on_public_readonly_surface(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Song 4", "kind": "track"},
        headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
    )

    assert response.status_code == 200
    assert response.headers[SURFACE_HEADER] == PUBLIC_READONLY_SURFACE
    assert response.json()["tracks"][0]["href"] == "/music/tracks/4"


def test_private_candidate_mode_uses_bounded_fallback_without_snapshot(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/music/search",
        params={
            "q": "Alpha Song 4",
            "kind": "track",
            "response_mode": "candidates",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response_version"] == "music_search_v2"
    assert payload["normalized_query"] == "alpha song 4"
    assert payload["snapshot_status"] == "unavailable"
    assert payload["candidate_status"] == "degraded"
    assert payload["candidate_freshness"] == "fallback"
    assert payload["statistics_status"] == "unavailable"
    assert payload["statistics_freshness"] == "unavailable"
    assert payload["total"] == 1
    assert payload["tracks"][0]["entity_key"] == "track:4"
    assert "normalize;dur=" in response.headers["server-timing"]
    assert "total;dur=" in response.headers["server-timing"]


def test_public_candidate_fails_closed_when_active_index_has_no_safe_membership(
    client: TestClient,
) -> None:
    conn = get_db(readonly=False)
    try:
        rebuild_music_search_index(conn)
        conn.execute("DELETE FROM music_search_snapshot_meta")
        conn.execute("DELETE FROM music_search_entity_context")
        conn.commit()
    finally:
        conn.close()

    response = client.get(
        "/api/music/search",
        params={"q": "Alpha Song 4", "kind": "track", "response_mode": "candidates"},
        headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_status"] == "unavailable"
    assert payload["candidate_freshness"] == "unavailable"
    assert payload["target_filter_fingerprint"] is None
    assert payload["total"] == 0
    assert payload["tracks"] == []


@pytest.mark.parametrize("maintenance_status", ("pending", "building", "failed"))
def test_candidate_mode_serves_lkg_generation_during_candidate_maintenance(
    client: TestClient,
    maintenance_status: str,
) -> None:
    conn = get_db(readonly=False)
    try:
        report = rebuild_music_search_index(conn)
        conn.execute(
            """UPDATE music_search_candidate_maintenance_state
                  SET maintenance_status=?, target_source_revision='target-new',
                      target_candidate_index_version='candidate-new',
                      last_error=CASE WHEN ?='failed' THEN 'build failed' ELSE NULL END
                WHERE state_id=1""",
            (maintenance_status, maintenance_status),
        )
        conn.commit()
        before = tuple(
            conn.execute(
                """SELECT active_generation_id, previous_generation_id, status,
                          source_revision, candidate_index_version
                     FROM music_search_index_state WHERE state_id=1"""
            ).fetchone()
        )
    finally:
        conn.close()

    response = client.get(
        "/api/music/search",
        params={
            "q": "Alpha Song 4",
            "kind": "track",
            "response_mode": "candidates",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_status"] in {"ready", "degraded"}
    assert payload["candidate_freshness"] == "last_known_good"
    assert payload["candidate_index_version"] == report["candidate_index_version"]
    assert payload["tracks"][0]["entity_key"] == "track:4"

    conn = get_db()
    try:
        after = tuple(
            conn.execute(
                """SELECT active_generation_id, previous_generation_id, status,
                          source_revision, candidate_index_version
                     FROM music_search_index_state WHERE state_id=1"""
            ).fetchone()
        )
    finally:
        conn.close()
    assert after == before


def test_private_any_local_candidate_mode_returns_no_context_metrics(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/music/search",
        params={
            "q": "Alpha Song 4",
            "kind": "track",
            "response_mode": "candidates",
            "eligibility": "any_local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_status"] == "unavailable"
    assert payload["tracks"][0]["entity_key"] == "track:4"
    assert "play_events" not in payload["tracks"][0]
    assert "total_ms" not in payload["tracks"][0]
    assert "candidate_query;dur=" in response.headers["server-timing"]


def test_deny_overlay_excludes_entity_from_private_and_public_lkg(
    client: TestClient,
) -> None:
    conn = get_db(readonly=False)
    try:
        conn.execute(
            """INSERT INTO music_search_entity_deny_overlay(
                   entity_key, reason, target_source_revision
               ) VALUES ('track:4', 'privacy revocation fixture', 'future-revision')"""
        )
        conn.commit()
    finally:
        conn.close()

    try:
        private = client.get(
            "/api/music/search",
            params={
                "q": "Alpha Song 4",
                "kind": "track",
                "response_mode": "candidates",
                "eligibility": "any_local",
            },
        )
        public = client.get(
            "/api/music/search",
            params={
                "q": "Alpha Song 4",
                "kind": "track",
                "response_mode": "candidates",
            },
            headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
        )

        assert private.status_code == 200
        assert private.json()["tracks"] == []
        assert public.status_code == 200
        assert public.json()["tracks"] == []
    finally:
        conn = get_db(readonly=False)
        try:
            conn.execute("DELETE FROM music_search_entity_deny_overlay WHERE entity_key='track:4'")
            conn.commit()
        finally:
            conn.close()


@pytest.mark.parametrize(
    ("parameter", "value"),
    (
        ("min_ms", "12345"),
        ("music_only", "false"),
        ("merge_enabled", "false"),
        ("max_merge_gap_minutes", "9"),
        ("bb_top_n", "55"),
        ("bb_week_start_hour", "12"),
        ("year_start", "2024"),
        ("year_end", "2025"),
    ),
)
def test_candidate_mode_rejects_unmaintained_filter_combinations(
    client: TestClient,
    parameter: str,
    value: str,
) -> None:
    response = client.get(
        "/api/music/search",
        params={
            "q": "Alpha",
            "response_mode": "candidates",
            parameter: value,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error": "unsupported_candidate_filter",
        "parameters": [parameter],
    }


def test_context_mode_rejects_unmaintained_filter_combination(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/music/search/context",
        params={"entity_key": "track:4", "year_start": 2024},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error": "unsupported_candidate_filter",
        "parameters": ["year_start"],
    }


def test_ready_candidate_and_context_match_legacy_current_metrics(
    client: TestClient,
) -> None:
    conn = get_db(readonly=False)
    try:
        report = rebuild_current_music_search_derived_data(
            conn,
            rebuild_documents=True,
        )
    finally:
        conn.close()
    assert report["snapshot"]["status"] == "ready"
    assert report["snapshot_set"]["ready_count"] == 4
    assert report["snapshot_set"]["failed_count"] == 0
    assert [
        (item["merge_level"], item["dynamic_threshold"])
        for item in report["snapshot_set"]["variants"]
    ] == [
        (2, True),
        (3, True),
        (2, False),
        (3, False),
    ]

    candidate_response = client.get(
        "/api/music/search",
        params={
            "q": "Alpha Song 4",
            "kind": "track",
            "response_mode": "candidates",
        },
    )
    assert candidate_response.status_code == 200
    candidate_payload = candidate_response.json()
    assert candidate_payload["snapshot_status"] == "ready"
    assert candidate_payload["tracks"][0]["entity_key"] == "track:4"

    fingerprint = candidate_payload["filter_fingerprint"]
    context_response = client.get(
        "/api/music/search/context",
        params={"entity_key": "track:4"},
    )
    assert context_response.status_code == 200
    context_payload = context_response.json()
    assert context_payload["snapshot_status"] == "ready"
    assert context_payload["filter_fingerprint"] == fingerprint

    legacy_payload = client.get(
        "/api/music/search",
        params={
            "q": "Alpha Song 4",
            "kind": "track",
            "include_chart": True,
        },
    ).json()
    context_item = context_payload["items"]["track:4"]
    assert context_item["play_events"] == legacy_payload["tracks"][0]["play_events"]
    assert context_item["total_ms"] == legacy_payload["tracks"][0]["total_ms"]
    assert context_item["chart"] == legacy_payload["tracks"][0]["chart"]


def test_public_ready_search_is_cache_only_and_has_no_database_side_effects(
    client: TestClient,
) -> None:
    conn = get_db(readonly=False)
    try:
        rebuild_current_music_search_derived_data(conn, rebuild_documents=True)
        before = {
            "index": tuple(
                conn.execute(
                    """SELECT active_generation_id, previous_generation_id, status,
                              source_revision, document_count
                       FROM music_search_index_state WHERE state_id=1"""
                ).fetchone()
            ),
            "snapshots": [
                tuple(row)
                for row in conn.execute(
                    """SELECT snapshot_key, status, source_revision, activated_at, last_error
                       FROM music_search_snapshot_meta ORDER BY snapshot_key"""
                ).fetchall()
            ],
            "jobs": conn.execute("SELECT COUNT(*) FROM background_jobs").fetchone()[0],
        }
    finally:
        conn.close()

    candidate_response = client.get(
        "/api/music/search",
        params={
            "q": "Alpha Song 4",
            "kind": "track",
            "response_mode": "candidates",
        },
        headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
    )
    assert candidate_response.status_code == 200
    assert candidate_response.json()["tracks"][0]["entity_key"] == "track:4"
    context_response = client.get(
        "/api/music/search/context",
        params={"entity_key": "track:4"},
        headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
    )
    assert context_response.status_code == 200
    assert context_response.json()["items"]["track:4"]["play_events"] > 0

    conn = get_db()
    try:
        after = {
            "index": tuple(
                conn.execute(
                    """SELECT active_generation_id, previous_generation_id, status,
                              source_revision, document_count
                       FROM music_search_index_state WHERE state_id=1"""
                ).fetchone()
            ),
            "snapshots": [
                tuple(row)
                for row in conn.execute(
                    """SELECT snapshot_key, status, source_revision, activated_at, last_error
                       FROM music_search_snapshot_meta ORDER BY snapshot_key"""
                ).fetchall()
            ],
            "jobs": conn.execute("SELECT COUNT(*) FROM background_jobs").fetchone()[0],
        }
    finally:
        conn.close()
    assert after == before


def test_three_entity_kinds_match_details_across_all_four_variants(
    client: TestClient,
) -> None:
    conn = get_db(readonly=False)
    try:
        rebuild_current_music_search_derived_data(conn, rebuild_documents=True)
    finally:
        conn.close()

    cases = (
        ("track", "Alpha Song 4"),
        ("album", "Alpha Debut"),
        ("artist", "Alpha"),
    )
    for merge_level in (2, 3):
        for dynamic_threshold in (True, False):
            for kind, query in cases:
                _assert_search_context_matches_details(
                    client,
                    merge_level=merge_level,
                    dynamic_threshold=dynamic_threshold,
                    kind=kind,
                    query=query,
                )


def _assert_search_context_matches_details(
    client: TestClient,
    *,
    merge_level: int,
    dynamic_threshold: bool,
    kind: str,
    query: str,
) -> None:
    params = {
        "q": query,
        "kind": kind,
        "merge_level": merge_level,
        "dynamic_threshold": dynamic_threshold,
    }
    candidate_payload = client.get(
        "/api/music/search",
        params={**params, "response_mode": "candidates"},
    ).json()
    group = candidate_payload[f"{kind}s"]
    assert candidate_payload["snapshot_status"] == "ready"
    assert group
    entity_key = group[0]["entity_key"]
    context_payload = client.get(
        "/api/music/search/context",
        params={
            "entity_key": entity_key,
            "merge_level": merge_level,
            "dynamic_threshold": dynamic_threshold,
        },
    ).json()
    context_item = context_payload["items"][entity_key]
    candidate = group[0]

    if kind == "track":
        stats_path = f"/api/music/tracks/{candidate['track_id']}/stats"
        plays_path = f"/api/music/tracks/{candidate['track_id']}/plays"
        billboard_path = f"/api/billboard/track/{candidate['track_id']}"
        detail_params = {
            "merge_level": merge_level,
            "dynamic_threshold": dynamic_threshold,
        }
    elif kind == "album":
        stats_path = f"/api/music/albums/{candidate['label']}/stats"
        plays_path = f"/api/music/albums/{candidate['label']}/plays"
        billboard_path = f"/api/billboard/album/{candidate['label']}"
        detail_params = {
            "merge_level": merge_level,
            "dynamic_threshold": dynamic_threshold,
            "artist": candidate["artist_name"],
            "artist_name": candidate["artist_name"],
        }
    else:
        stats_path = f"/api/music/artists/{candidate['label']}/stats"
        plays_path = f"/api/music/artists/{candidate['label']}/plays"
        billboard_path = f"/api/billboard/artist/{candidate['label']}"
        detail_params = {
            "merge_level": merge_level,
            "dynamic_threshold": dynamic_threshold,
        }

    stats = client.get(stats_path, params=detail_params).json()
    plays = client.get(plays_path, params={**detail_params, "limit": 200}).json()
    billboard = client.get(billboard_path, params=detail_params).json()

    assert stats["found"] is True
    assert plays["total"] <= 200
    assert context_item["play_events"] == stats["summary"]["total_plays"]
    assert context_item["play_events"] == plays["total"]
    assert context_item["total_ms"] == sum(row["ms_played"] for row in plays["rows"])

    summary = billboard["summary"] if kind == "track" else billboard["chart_summary"]
    if summary is None:
        assert context_item["chart"] is None
    else:
        assert context_item["chart"] == {
            "peak_position": summary.get("peak_position"),
            "peak_weeks": summary.get("weeks_at_peak" if kind == "track" else "peak_weeks"),
            "weeks_on_chart": summary.get("weeks_on_chart"),
            "weeks_at_no1": summary.get("weeks_at_no1" if kind == "track" else "no1_weeks"),
            "power_score": summary.get("power_score"),
            "power_rank": summary.get("power_rank"),
            "first_week": summary.get("first_week"),
            "latest_week": summary.get("last_week" if kind == "track" else "latest_week"),
            "first_peak_week": summary.get("first_peak_week"),
        }


def test_public_readonly_rejects_any_local_candidate_mode(client: TestClient) -> None:
    response = client.get(
        "/api/music/search",
        params={
            "q": "Alpha Song 4",
            "response_mode": "candidates",
            "eligibility": "any_local",
        },
        headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
    )

    assert response.status_code == 403


def test_context_endpoint_is_public_safe_and_fail_closed(client: TestClient) -> None:
    response = client.get(
        "/api/music/search/context",
        params=[("entity_key", "track:4"), ("entity_key", "artist:1")],
        headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
    )

    assert response.status_code == 200
    assert response.headers[SURFACE_HEADER] == PUBLIC_READONLY_SURFACE
    payload = response.json()
    assert payload == {
        "response_version": "music_search_context_v1",
        "snapshot_status": "unavailable",
        "filter_fingerprint": payload["filter_fingerprint"],
        "statistics_status": "unavailable",
        "statistics_freshness": "unavailable",
        "served_filter_fingerprint": None,
        "target_filter_fingerprint": None,
        "items": {},
    }
    assert len(payload["filter_fingerprint"]) == 64
    assert "snapshot_lookup;dur=" in response.headers["server-timing"]


def test_context_endpoint_rejects_invalid_keys(client: TestClient) -> None:
    response = client.get(
        "/api/music/search/context",
        params={"entity_key": "track:01"},
    )

    assert response.status_code == 422
