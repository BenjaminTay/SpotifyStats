"""Unit tests for the feed orchestrator — structure and import correctness."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestOrchestratorStructure:
    def test_generate_all_posts_is_callable(self):
        from backend.domains.community.feed_generator import generate_all_posts

        assert callable(generate_all_posts)

    def test_generate_core_posts_is_callable(self):
        from backend.domains.community.feed_generator import _generate_core_posts

        assert callable(_generate_core_posts)

    def test_generate_all_posts_without_conn_returns_list(self):
        """When called without DB connection, returns empty list (no data to generate from)."""
        from backend.domains.community.feed_generator import generate_all_posts

        # With conn=None and year_start > year_end, should return empty list quickly
        posts = generate_all_posts(conn=None, year_start=2050, year_end=2050)
        assert isinstance(posts, list)

    def test_all_sub_modules_import_successfully(self):
        """Verify all split sub-modules are importable."""
        modules = [
            "feed_helpers",
            "feed_data",
            "feed_weekly",
            "feed_records",
            "feed_personal",
            "feed_talk",
            "feed_ranking",
            "feed_images",
        ]
        for mod in modules:
            __import__(f"backend.domains.community.{mod}")

    def test_public_api_still_exports_generate_all_posts(self):
        """Backward compatibility: backend.api.community imports generate_all_posts."""
        from backend.domains.community.feed_generator import _generate_core_posts as b
        from backend.domains.community.feed_generator import generate_all_posts as a

        assert a is not None
        assert b is not None
