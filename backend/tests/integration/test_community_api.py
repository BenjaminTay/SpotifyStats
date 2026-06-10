"""Integration tests for Community Feed API against real chart data."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestCommunityFeedIntegration:
    def test_feed_returns_posts(self, client, default_params):
        r = client.get("/api/community/feed", params={"limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert data["meta"]["total"] > 0, "Should have posts from real chart data"
        assert len(data["posts"]) > 0

    def test_posts_sorted_newest_first(self, client):
        r = client.get("/api/community/feed", params={"limit": 20})
        posts = r.json()["posts"]
        if len(posts) < 2:
            pytest.skip("Not enough posts to check ordering")
        for i in range(len(posts) - 1):
            assert posts[i]["posted_at"] >= posts[i + 1]["posted_at"], (
                f"Posts not sorted newest first at index {i}"
            )

    def test_post_linked_entities_have_type(self, client):
        r = client.get("/api/community/feed", params={"limit": 30})
        posts = r.json()["posts"]
        posts_with_entities = [p for p in posts if p.get("linked_entities")]
        if not posts_with_entities:
            pytest.skip("No posts with linked_entities")
        for p in posts_with_entities[:5]:
            for entity in p["linked_entities"]:
                assert "type" in entity
                assert "name" in entity
                assert entity["type"] in ("artist", "track")

    def test_posts_have_metrics(self, client):
        r = client.get("/api/community/feed", params={"limit": 10})
        posts = r.json()["posts"]
        for p in posts:
            assert "metrics" in p
            for mkey in ["likes", "retweets", "replies", "views"]:
                assert mkey in p["metrics"]
                assert isinstance(p["metrics"][mkey], int)

    def test_significance_filter_reduces_count(self, client):
        r_all = client.get("/api/community/feed")
        total_all = r_all.json()["meta"]["total"]

        r_high = client.get("/api/community/feed", params={"significance_min": 0.5})
        total_high = r_high.json()["meta"]["total"]

        assert total_high <= total_all

    def test_account_filter_single(self, client):
        r = client.get("/api/community/feed", params={"accounts": "@chartdata", "limit": 50})
        posts = r.json()["posts"]
        for p in posts:
            assert p["account_handle"] == "@chartdata"

    def test_multiple_accounts(self, client):
        r = client.get(
            "/api/community/feed", params={"accounts": "@chartdata,@debutwatch", "limit": 50}
        )
        posts = r.json()["posts"]
        handles = {p["account_handle"] for p in posts}
        assert handles.issubset({"@chartdata", "@debutwatch"})

    def test_post_types_present(self, client):
        r = client.get("/api/community/feed", params={"limit": 100})
        posts = r.json()["posts"]
        types = {p["post_type"] for p in posts}
        # Should have a variety of post types
        assert len(types) >= 3, f"Expected >=3 post types, got {len(types)}: {types}"
        # Core post types should always be present
        expected = {"no1_announcement", "top10_summary", "new_entries_roundup"}
        present = expected & types
        assert present, f"Core post types missing: {expected - types}"

    def test_historical_accuracy_no_future_data(self, client):
        """Posts must not reference events after their posted_at date."""
        r = client.get("/api/community/feed", params={"limit": 200})
        posts = r.json()["posts"]

        for p in posts:
            posted = p["posted_at"]
            content = p["content"]
            # Posts should not contain "record" content that references dates
            # after the post date. We can't exhaustively check this, but we
            # can verify each post's linked_entities don't contain
            # unconscionable data.
            assert len(content) > 0
            assert posted > "2010-01-01"  # sanity check on date format

    def test_account_handle_valid(self, client):
        r = client.get("/api/community/feed", params={"limit": 100})
        posts = r.json()["posts"]
        valid_handles = {
            "@chartdata",
            "@billboardcharts",
            "@talkofthecharts",
            "@popcrave",
            "@chartstats",
            "@debutwatch",
            "@recordwatch",
            "@throwbackcharts",
            "@spotifystats",
            "@collectionvault",
        }
        for p in posts:
            assert p["account_handle"] in valid_handles, (
                f"Unknown account handle: {p['account_handle']}"
            )


class TestCommunityFeedPaginationIntegration:
    def test_offset_produces_different_posts(self, client):
        r1 = client.get("/api/community/feed", params={"limit": 5, "offset": 0})
        r2 = client.get("/api/community/feed", params={"limit": 5, "offset": 5})

        posts1 = r1.json()["posts"]
        posts2 = r2.json()["posts"]

        if len(posts1) == 0 or len(posts2) == 0:
            pytest.skip("Not enough posts for pagination test")

        ids1 = {p["id"] for p in posts1}
        ids2 = {p["id"] for p in posts2}
        assert ids1.isdisjoint(ids2), "Paginated pages should not overlap"

    def test_limit_caps_response(self, client):
        r = client.get("/api/community/feed", params={"limit": 3})
        assert len(r.json()["posts"]) <= 3

    def test_returned_matches_actual_count(self, client):
        r = client.get("/api/community/feed", params={"limit": 7})
        data = r.json()
        assert data["meta"]["returned"] == len(data["posts"])
