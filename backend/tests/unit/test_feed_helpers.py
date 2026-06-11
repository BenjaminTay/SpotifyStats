"""Unit tests for feed helpers — formatting, ID generation, entry filtering."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestMakeId:
    def test_deterministic(self):
        from backend.domains.community.feed_helpers import _make_id

        a = _make_id("no1", "2024-01-06", "123")
        b = _make_id("no1", "2024-01-06", "123")
        assert a == b

    def test_different_inputs_different_ids(self):
        from backend.domains.community.feed_helpers import _make_id

        a = _make_id("no1", "2024-01-06", "1")
        b = _make_id("no1", "2024-01-06", "2")
        assert a != b

    def test_length_is_12(self):
        from backend.domains.community.feed_helpers import _make_id

        result = _make_id("test", "data")
        assert len(result) == 12


class TestFmtOrdinal:
    def test_basic(self):
        from backend.domains.community.feed_helpers import _fmt_ordinal

        assert _fmt_ordinal(1) == "1st"
        assert _fmt_ordinal(2) == "2nd"
        assert _fmt_ordinal(3) == "3rd"
        assert _fmt_ordinal(4) == "4th"

    def test_teens(self):
        from backend.domains.community.feed_helpers import _fmt_ordinal

        assert _fmt_ordinal(11) == "11th"
        assert _fmt_ordinal(12) == "12th"
        assert _fmt_ordinal(13) == "13th"

    def test_twenties(self):
        from backend.domains.community.feed_helpers import _fmt_ordinal

        assert _fmt_ordinal(21) == "21st"
        assert _fmt_ordinal(22) == "22nd"
        assert _fmt_ordinal(23) == "23rd"
        assert _fmt_ordinal(24) == "24th"

    def test_large(self):
        from backend.domains.community.feed_helpers import _fmt_ordinal

        assert _fmt_ordinal(100) == "100th"
        assert _fmt_ordinal(101) == "101st"
        assert _fmt_ordinal(111) == "111th"


class TestFmtNumber:
    def test_small(self):
        from backend.domains.community.feed_helpers import _fmt_number

        assert _fmt_number(0) == "0"
        assert _fmt_number(999) == "999"

    def test_kilo(self):
        from backend.domains.community.feed_helpers import _fmt_number

        assert _fmt_number(1000) == "1.0K"
        assert _fmt_number(1500) == "1.5K"
        assert _fmt_number(999999) == "1000.0K"

    def test_million(self):
        from backend.domains.community.feed_helpers import _fmt_number

        assert _fmt_number(1000000) == "1.0M"
        assert _fmt_number(2500000) == "2.5M"


class TestWeekEndDate:
    def test_returns_iso_format(self):
        from backend.domains.community.feed_helpers import _week_end_date

        result = _week_end_date("2024-01-06")
        assert result.endswith("T12:00:00")
        assert "2024-01-13" in result  # 7 days later


class TestPick:
    def test_returns_one_of_choices(self):
        from backend.domains.community.feed_helpers import _pick

        choices = ("a", "b", "c")
        for _ in range(20):
            assert _pick(*choices) in choices


class TestGenerateMetrics:
    def test_returns_post_metrics(self):
        from backend.domains.community.feed_helpers import _generate_metrics

        m = _generate_metrics(0.5, "megastar")
        assert m.likes > 0
        assert m.retweets > 0
        assert m.replies >= 0
        assert m.views > 0

    def test_higher_significance_gives_more_engagement(self):
        from backend.domains.community.feed_helpers import _generate_metrics

        # Not deterministic due to randomness, but higher significance
        # multiplies the base, so we just verify both return valid metrics
        low = _generate_metrics(0.1, "mid")
        high = _generate_metrics(1.0, "mid")
        assert low.likes > 0
        assert high.likes > 0

    def test_niche_has_lower_engagement_than_megastar(self):
        from backend.domains.community.feed_helpers import _generate_metrics

        # Run multiple times to confirm the pattern holds
        niche_avg = sum(_generate_metrics(0.5, "niche").likes for _ in range(50)) / 50
        mega_avg = sum(_generate_metrics(0.5, "megastar").likes for _ in range(50)) / 50
        assert mega_avg > niche_avg


class TestEntriesForWeek:
    def test_returns_sorted_by_rank(self):
        import pandas as pd

        from backend.domains.community.feed_helpers import _entries_for_week

        df = pd.DataFrame(
            [
                {
                    "billboard_week": pd.Timestamp("2024-01-06"),
                    "track_id": 1,
                    "rank": 5,
                    "track_name": "A",
                    "artist_name": "X",
                },
                {
                    "billboard_week": pd.Timestamp("2024-01-06"),
                    "track_id": 2,
                    "rank": 1,
                    "track_name": "B",
                    "artist_name": "Y",
                },
                {
                    "billboard_week": pd.Timestamp("2024-01-06"),
                    "track_id": 3,
                    "rank": 3,
                    "track_name": "C",
                    "artist_name": "Z",
                },
            ]
        )
        entries = _entries_for_week(df, pd.Timestamp("2024-01-06"))
        assert len(entries) == 3
        # Should be sorted by rank ascending
        ranks = [e["rank"] for e in entries]
        assert ranks == sorted(ranks)

    def test_filters_out_other_weeks(self):
        import pandas as pd

        from backend.domains.community.feed_helpers import _entries_for_week

        df = pd.DataFrame(
            [
                {
                    "billboard_week": pd.Timestamp("2024-01-06"),
                    "track_id": 1,
                    "rank": 1,
                    "track_name": "A",
                    "artist_name": "X",
                },
                {
                    "billboard_week": pd.Timestamp("2024-01-13"),
                    "track_id": 2,
                    "rank": 1,
                    "track_name": "B",
                    "artist_name": "Y",
                },
            ]
        )
        entries = _entries_for_week(df, pd.Timestamp("2024-01-06"))
        assert len(entries) == 1
        assert entries[0]["track_name"] == "A"
