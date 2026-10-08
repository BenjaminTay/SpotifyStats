"""Bounded comparison HTTP contracts and their public read-only boundary."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.core import db
from backend.core.access_surface import SURFACE_HEADER
from backend.core.job_queue import JobQueue
from backend.infrastructure.http.client import HttpClient
from backend.main import app
from backend.services import analysis_snapshot_store as store
from backend.services import versus_rank_context_service as ranks
from backend.services.versus_personal_context import resolve_selection
from backend.tests.unit import test_versus_rank_context as rank_tests

base_isolated = rank_tests.base_isolated
isolated = rank_tests.isolated

pytestmark = pytest.mark.contract


def track_ids():
    conn = db.get_db(readonly=True)
    try:
        result = []
        keys = set()
        for row in conn.execute("SELECT l1_id FROM track_l1_identities ORDER BY l1_id"):
            item = resolve_selection(conn, "track", [int(row[0]), 999999], 2)[0]
            if item.entity_key not in keys:
                keys.add(item.entity_key)
                result.append(int(row[0]))
            if len(result) == 4:
                return result
    finally:
        conn.close()
    raise AssertionError("Seed requires four distinct songs")


@pytest.mark.parametrize("suffix", ["personal-stats", "personal-ranks"])
@pytest.mark.parametrize(
    "kind,body",
    [
        ("track", {"track_ids": [1]}),
        ("track", {"track_ids": [1, 2, 3, 4, 5]}),
        ("track", {"track_ids": [True, 2]}),
        ("track", {"track_ids": ["1", 2]}),
        ("track", {"track_ids": [0, 2]}),
        ("track", {"track_ids": [1, 2], "sql": "SELECT 1"}),
        ("album", {"albums": [{"album_name": "", "artist_name": "A"}] * 2}),
        ("artist", {"artist_names": ["A", "B"], "url": "https://example.org"}),
        ("artist", {"track_ids": [1, 2]}),
        ("invalid", {"track_ids": [1, 2]}),
    ],
)
def test_invalid_selection_rejected_before_service(isolated, monkeypatch, suffix, kind, body):
    from backend.api.billboard import personal_comparison as api

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid input entered a statistics service")

    monkeypatch.setattr(api, "build_personal_stats", forbidden)
    monkeypatch.setattr(api, "read_personal_ranks", forbidden)
    response = TestClient(app).post(f"/api/billboard/versus/{kind}/{suffix}", json=body)
    assert response.status_code == 422


def test_public_stats_and_ready_ranks_preserve_sources_and_cache(isolated, monkeypatch):
    ids = track_ids()
    conn = db.get_db(readonly=True)
    try:
        ranks.ensure(conn, {"include_compilations": False})
    finally:
        conn.close()
    source = isolated[0].read_bytes()
    cache = store.path().read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("Public read attempted publication, queueing or global ranks")

    monkeypatch.setattr(ranks, "build_payload", forbidden)
    monkeypatch.setattr(store, "publish", forbidden)
    monkeypatch.setattr(JobQueue, "enqueue_if_not_pending", forbidden)
    monkeypatch.setattr(HttpClient, "_request", forbidden)
    client = TestClient(app)
    headers = {SURFACE_HEADER: "public-readonly"}
    stats = client.post(
        "/api/billboard/versus/track/personal-stats", json={"track_ids": ids}, headers=headers
    )
    rank = client.post(
        "/api/billboard/versus/track/personal-ranks", json={"track_ids": ids}, headers=headers
    )
    assert stats.status_code == rank.status_code == 200, (stats.text, rank.text)
    for key in ("source_revision", "filter_fingerprint", "statistics_contract_version"):
        assert stats.json()[key] == rank.json()[key]
    assert len(stats.json()["entities"]) == len(rank.json()["entities"]) == 4
    assert rank.json()["snapshot"]["status"] == "ready"
    assert "personal_stats;dur=" in stats.headers["server-timing"]
    assert "personal_ranks;dur=" in rank.headers["server-timing"]
    assert isolated[0].read_bytes() == source
    assert store.path().read_bytes() == cache


def test_missing_rank_stays_503_while_basic_is_available(isolated):
    ids = track_ids()[:2]
    client = TestClient(app)
    headers = {SURFACE_HEADER: "public-readonly"}
    body = {"track_ids": ids}
    rank = client.post("/api/billboard/versus/track/personal-ranks", json=body, headers=headers)
    stats = client.post("/api/billboard/versus/track/personal-stats", json=body, headers=headers)
    assert rank.status_code == 503
    assert rank.json()["detail"]["error"] == "snapshot_unavailable"
    assert stats.status_code == 200, stats.text


def test_duplicate_canonical_rejected_and_unknown_not_fabricated(isolated):
    first = track_ids()[0]
    client = TestClient(app)
    duplicate = client.post(
        "/api/billboard/versus/track/personal-stats", json={"track_ids": [first, first]}
    )
    assert duplicate.status_code == 422
    unknown = client.post(
        "/api/billboard/versus/track/personal-stats", json={"track_ids": [first, 999999]}
    )
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["entities"][1]["status"] == "unavailable"
    assert unknown.json()["entities"][1]["metrics"] is None


@pytest.mark.parametrize("suffix", ["personal-stats", "personal-ranks"])
def test_missing_source_revision_is_unavailable_not_invalid_selection(isolated, suffix):
    ids = track_ids()[:2]
    with sqlite3.connect(isolated[0]) as conn:
        conn.execute("DELETE FROM analysis_source_revisions WHERE source_table='plays'")
    result = TestClient(app).post(
        f"/api/billboard/versus/track/{suffix}",
        json={"track_ids": ids},
        headers={SURFACE_HEADER: "public-readonly"},
    )
    assert result.status_code == 503, result.text
    assert result.json()["detail"]["error"] == "snapshot_unavailable"
