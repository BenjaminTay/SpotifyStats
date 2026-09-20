"""Contract tests for Community Feed API — validate response structure."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def published_community(client):
    from backend.core.db import get_db
    from backend.services.community_snapshot_service import ensure

    conn = get_db(readonly=True)
    try:
        ensure(conn)
    finally:
        conn.close()


class TestCommunityFeedStructure:
    def test_feed_returns_200(self, client):
        r = client.get("/api/community/feed")
        assert r.status_code == 200

    def test_feed_has_meta(self, client):
        r = client.get("/api/community/feed")
        data = r.json()
        assert "meta" in data
        assert "posts" in data
        assert isinstance(data["posts"], list)

    def test_meta_structure(self, client):
        r = client.get("/api/community/feed")
        meta = r.json()["meta"]
        for key in ["total", "total_all", "returned", "offset", "limit"]:
            assert key in meta, f"Missing meta key: {key}"
        assert meta["returned"] <= meta["limit"]

    def test_posts_have_required_fields(self, client):
        r = client.get("/api/community/feed")
        posts = r.json()["posts"]
        if posts:
            p = posts[0]
            for key in [
                "id",
                "account_handle",
                "posted_at",
                "content",
                "post_type",
                "significance",
                "tags",
            ]:
                assert key in p, f"Missing post key: {key}"
            assert isinstance(p["significance"], (int, float))
            assert isinstance(p["tags"], list)


class TestCommunityFeedPagination:
    def test_limit_respected(self, client):
        r = client.get("/api/community/feed", params={"limit": 5})
        meta = r.json()["meta"]
        posts = r.json()["posts"]
        assert meta["limit"] == 5
        assert len(posts) <= 5

    def test_offset_0_default(self, client):
        r = client.get("/api/community/feed")
        assert r.json()["meta"]["offset"] == 0

    def test_offset_and_limit(self, client):
        r = client.get("/api/community/feed", params={"offset": 0, "limit": 3})
        data = r.json()
        assert data["meta"]["offset"] == 0
        assert data["meta"]["limit"] == 3


class TestCommunityFeedFilters:
    def test_significance_min_filter(self, client):
        r = client.get("/api/community/feed", params={"significance_min": 1.0})
        assert r.status_code == 200
        posts = r.json()["posts"]
        for p in posts:
            assert p["significance"] >= 1.0

    def test_accounts_filter(self, client):
        r = client.get("/api/community/feed", params={"accounts": "@chartdata"})
        assert r.status_code == 200
        posts = r.json()["posts"]
        for p in posts:
            assert p["account_handle"] == "@chartdata"

    def test_date_range_filter(self, client):
        r = client.get(
            "/api/community/feed", params={"date_from": "2020-01-01", "date_to": "2020-01-31"}
        )
        assert r.status_code == 200

    def test_invalid_significance_clamped(self, client):
        r = client.get("/api/community/feed", params={"significance_min": 5.0})
        # Should return 422 because significance_min max is 1.0
        assert r.status_code == 422


def test_private_refresh_queues_selected_fingerprint_and_public_cannot(client, monkeypatch):
    from backend.services import community_snapshot_service as service

    calls = []
    monkeypatch.setattr(service, "enqueue", lambda params: calls.append(params) or ["job"])
    response = client.post("/api/community/refresh?merge_level=3&bb_week_start_hour=7")
    assert response.status_code == 200
    assert response.json() == {"job_ids": ["job"]}
    assert calls[0]["merge_level"] == 3
    assert calls[0]["bb_week_start_hour"] == 7
    response = client.post(
        "/api/community/refresh", headers={"X-SpotifyStats-Surface": "public-readonly"}
    )
    assert response.status_code in (403, 404)
    assert len(calls) == 1
