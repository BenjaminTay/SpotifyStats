"""Unit tests for ranking math — Power Score components and all-time ranking."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestBaseScore:
    def test_rank1_returns_highest(self):
        from backend.domains.community.feed_ranking import _base_score

        score1 = _base_score(1)
        score2 = _base_score(2)
        score10 = _base_score(10)
        assert score1 > score2
        assert score2 > score10

    def test_score_is_positive(self):
        from backend.domains.community.feed_ranking import _base_score

        for rank in [1, 5, 10, 20, 50, 100]:
            assert _base_score(rank) >= 1


class TestCompFactor:
    def test_average_returns_near_1(self):
        from backend.domains.community.feed_ranking import _comp_factor

        # When week_total equals baseline, ratio is 1, result should be ~1
        result = _comp_factor(1000.0, 1000.0)
        assert 0.9 <= result <= 1.1

    def test_high_competition_increases_factor(self):
        from backend.domains.community.feed_ranking import _comp_factor

        low = _comp_factor(500.0, 1000.0)
        high = _comp_factor(5000.0, 1000.0)
        assert high > low

    def test_clamped_within_bounds(self):
        from backend.domains.community.feed_ranking import _comp_factor

        # Very extreme values should be clamped
        assert _comp_factor(0.001, 1000.0) >= 0.7
        assert _comp_factor(1000000.0, 1000.0) <= 1.5


class TestIndivFactor:
    def test_number1_gets_boost(self):
        from backend.domains.community.feed_ranking import _indiv_factor

        # #1 with high plays relative to runner-up
        result = _indiv_factor(1, 5000.0, 3000.0, 2000.0)
        assert result > 1.0

    def test_lower_rank_gets_lower_factor(self):
        from backend.domains.community.feed_ranking import _indiv_factor

        high = _indiv_factor(1, 5000.0, 3000.0, 2000.0)
        low = _indiv_factor(10, 1000.0, 5000.0, 2000.0)
        assert high > low


class TestComputeRealPowerScore:
    def test_returns_components(self):
        from backend.domains.community.feed_ranking import _compute_real_power_score

        result = _compute_real_power_score(
            track_id=1,
            raw_score_sum={1: 500.0},
            track_weeks_on_chart={1: 20},
            track_peak_rank={1: 1},
            track_is_debut_no1={1: True},
            track_top5_weeks={1: 15},
            track_top10_weeks={1: 20},
        )
        assert result > 0
        assert isinstance(result, float)

    def test_lower_peak_ranks_give_higher_score(self):
        from backend.domains.community.feed_ranking import _compute_real_power_score

        score_peak1 = _compute_real_power_score(
            1, {1: 500.0}, {1: 20}, {1: 1}, {}, {1: 15}, {1: 20}
        )
        score_peak10 = _compute_real_power_score(
            2, {2: 500.0}, {2: 20}, {2: 10}, {}, {2: 15}, {2: 20}
        )
        assert score_peak1 > score_peak10

    def test_more_weeks_give_higher_score(self):
        from backend.domains.community.feed_ranking import _compute_real_power_score

        score_short = _compute_real_power_score(1, {1: 500.0}, {1: 5}, {1: 1}, {}, {1: 3}, {1: 5})
        score_long = _compute_real_power_score(1, {1: 500.0}, {1: 30}, {1: 1}, {}, {1: 15}, {1: 25})
        assert score_long > score_short


class TestMakeAlltimeRanking:
    def test_returns_sorted_by_score(self):
        from backend.domains.community.feed_ranking import _make_alltime_ranking

        raw_score_sum = {1: 800.0, 2: 500.0, 3: 950.0}
        total_weeks = {1: 30, 2: 20, 3: 40}
        peak_rank = {1: 1, 2: 2, 3: 1}
        is_debut_no1 = {1: True, 2: False, 3: True}
        top5_weeks = {1: 25, 2: 15, 3: 30}
        top10_weeks = {1: 30, 2: 20, 3: 40}

        ranking = _make_alltime_ranking(
            raw_score_sum, total_weeks, peak_rank, is_debut_no1, top5_weeks, top10_weeks, top_n=50
        )
        assert len(ranking) == 3
        # Returns list of (track_id, score) tuples sorted by score descending
        assert ranking[0][0] == 3  # Highest score
        assert ranking[2][0] == 2  # Lowest score

    def test_top_n_limits_results(self):
        from backend.domains.community.feed_ranking import _make_alltime_ranking

        n = 20
        raw_score_sum = {i: float(i * 100) for i in range(1, n + 1)}
        total_weeks = {i: i * 2 for i in range(1, n + 1)}
        peak_rank = {i: i for i in range(1, n + 1)}
        is_debut_no1: dict[int, bool] = {}
        top5_weeks: dict[int, int] = {}
        top10_weeks: dict[int, int] = {}

        ranking = _make_alltime_ranking(
            raw_score_sum, total_weeks, peak_rank, is_debut_no1, top5_weeks, top10_weeks, top_n=5
        )
        assert len(ranking) == 5


class TestGenAlbumNo1Post:
    def test_debut_album_no1(self):
        from backend.domains.community.feed_ranking import _gen_album_no1_post

        entries = [_album_entry(1, "New Album", "Artist X")]
        post = _gen_album_no1_post(entries, None, set(), {}, "2024-01-13T12:00:00", "2024-01-06")
        assert post is not None
        assert "New Album" in post.content
        assert post.account_handle == "@billboardcharts"

    def test_empty_entries_returns_none(self):
        from backend.domains.community.feed_ranking import _gen_album_no1_post

        post = _gen_album_no1_post([], None, set(), {}, "2024-01-13T12:00:00", "2024-01-06")
        assert post is None


def _album_entry(rank, album_name, artist_name):
    return {"rank": rank, "album_name": album_name, "artist_name": artist_name}
