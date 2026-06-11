"""Unit tests for HistoricalState — cumulative chart knowledge tracker.

Verifies that state accumulates correctly across weeks without leaking future
knowledge into past posts.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _entry(track_id, rank, artist_name, track_name, week="2024-01-06"):
    return {
        "track_id": track_id,
        "rank": rank,
        "artist_name": artist_name,
        "track_name": track_name,
        "billboard_week": week,
    }


class TestTrackLevelStats:
    def test_debut_week_recorded(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 5, "Artist A", "Song A")])

        assert state.track_debut_week[1] == "2024-01-06"

    def test_debut_week_not_overwritten(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 5, "Artist A", "Song A", "2024-01-06")])
        state.update([_entry(1, 3, "Artist A", "Song A", "2024-01-13")])

        assert state.track_debut_week[1] == "2024-01-06"

    def test_peak_rank_tracks_best(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 5, "Artist A", "Song A")])
        state.update([_entry(1, 2, "Artist A", "Song A")])
        state.update([_entry(1, 10, "Artist A", "Song A")])

        assert state.track_peak_rank[1] == 2

    def test_total_weeks_increments(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        for _ in range(4):
            state.update([_entry(1, 3, "Artist A", "Song A")])

        assert state.track_total_weeks[1] == 4

    def test_weeks_at_no1_only_counts_rank_1(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 1, "Artist A", "Song A")])
        state.update([_entry(1, 1, "Artist A", "Song A")])
        state.update([_entry(1, 2, "Artist A", "Song A")])
        state.update([_entry(1, 1, "Artist A", "Song A")])

        assert state.track_weeks_at_no1[1] == 3


class TestArtistLevelStats:
    def test_artist_no1_count(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        # Week 1: first #1 occurrence — 1st distinct #1 song
        state.update([_entry(1, 1, "Artist A", "Song A")])
        assert state.artist_no1_count_as_of("Artist A") == 1

        # Week 2: same song stays at #1 — still 1 distinct #1 song
        state.update([_entry(1, 1, "Artist A", "Song A")])
        assert state.artist_no1_count_as_of("Artist A") == 1

        # Week 3: new song debuts at #1 — 2nd distinct #1 song
        state.update([_entry(2, 1, "Artist A", "Song B")])
        assert state.artist_no1_count_as_of("Artist A") == 2

    def test_artist_no1_count_zero_for_non_no1(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 5, "Artist A", "Song A")])
        assert state.artist_no1_count_as_of("Artist A") == 0

    def test_artist_first_no1_date(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 5, "Artist A", "Song A", "2024-03-15")])
        assert "Artist A" not in state.artist_first_no1_date

        state.update([_entry(2, 1, "Artist A", "Song B", "2024-03-22")])
        assert state.artist_first_no1_date["Artist A"] == "2024-03-22"

    def test_artist_top5_and_top10_tracking(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 8, "Artist A", "Song A")])

        assert state.artist_top10_count["Artist A"] == 1
        assert state.artist_top5_count.get("Artist A", 0) == 0

        state.update([_entry(2, 3, "Artist A", "Song B")])
        assert state.artist_top5_count["Artist A"] == 1

    def test_artist_career_weeks(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 5, "Artist A", "Song A")])
        state.update([_entry(1, 10, "Artist A", "Song A"), _entry(2, 20, "Artist A", "Song B")])

        # 2 songs appeared across 2 weeks = 3 entry-weeks
        assert state.artist_career_weeks["Artist A"] == 3


class TestGlobalRecords:
    def test_longest_no1_weeks(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 1, "Artist A", "Song A")])
        assert state.longest_no1_weeks == 1
        assert state.longest_no1_track_name == "Song A"

        state.update([_entry(1, 1, "Artist A", "Song A")])
        assert state.longest_no1_weeks == 2

        # Different song gets 1 week at #1, doesn't break record
        state.update([_entry(2, 1, "Artist B", "Song B")])
        assert state.longest_no1_weeks == 2
        assert state.longest_no1_track_name == "Song A"

    def test_most_career_no1s(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 1, "Artist A", "Song A")])
        state.update([_entry(2, 1, "Artist A", "Song B")])
        state.update([_entry(3, 1, "Artist B", "Song C")])

        assert state.most_career_no1s_count == 2
        assert state.most_career_no1s_artist == "Artist A"

    def test_past_no1s_recorded(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 1, "Artist A", "Song A", "2024-01-06")])
        state.update([_entry(2, 1, "Artist B", "Song B", "2024-01-13")])

        assert len(state.past_no1s) == 2
        assert state.past_no1s[0]["track_name"] == "Song A"
        assert state.past_no1s[1]["track_name"] == "Song B"


class TestPersonalStats:
    def test_cumulative_plays_and_ms(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 1, "Artist A", "Song A")], personal_plays=50, personal_ms=180000)
        state.update([_entry(2, 2, "Artist B", "Song B")], personal_plays=30, personal_ms=120000)

        assert state.cumulative_plays == 80
        assert state.cumulative_ms == 300000

    def test_cumulative_tracks_and_artists(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update(
            [_entry(1, 1, "A", "S1")], personal_track_ids={1, 2}, personal_artist_names={"A", "B"}
        )
        state.update(
            [_entry(2, 2, "C", "S3")], personal_track_ids={3, 4}, personal_artist_names={"C"}
        )

        assert len(state.cumulative_tracks) == 4
        assert len(state.cumulative_artists) == 3


class TestNoFutureKnowledge:
    """Historical accuracy: state at week N must not contain data from week N+1."""

    def test_no1_count_snapshot_correct(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        # Week 1: 1 #1
        state.update([_entry(1, 1, "Artist A", "Song A", "2024-01-06")])
        assert state.artist_no1_count_as_of("Artist A") == 1

        # Week 2: still 1
        state.update([_entry(1, 2, "Artist A", "Song A", "2024-01-13")])
        assert state.artist_no1_count_as_of("Artist A") == 1

    def test_record_does_not_leak_future(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 1, "Artist A", "Song A")])

        # At this point, the longest #1 is 1 week. The state should not
        # know that in week 5 this song will have been #1 for 5 weeks.
        assert state.longest_no1_weeks == 1


class TestHelperMethods:
    def test_ordinal(self):
        from backend.domains.community.historical_state import HistoricalState

        s = HistoricalState()
        assert s._ordinal(1) == "1st"
        assert s._ordinal(2) == "2nd"
        assert s._ordinal(3) == "3rd"
        assert s._ordinal(4) == "4th"
        assert s._ordinal(11) == "11th"
        assert s._ordinal(12) == "12th"
        assert s._ordinal(13) == "13th"
        assert s._ordinal(21) == "21st"

    def test_artist_ordinal_no1(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()

        # Before any update: artist not seen → ordinal = 1st (next #1)
        assert state.artist_ordinal_no1("Artist A") == "1st"

        # Simulate pre-update usage: call ordinal BEFORE update() for the current track
        # After 2 updates, count = 2. ordinal returns 3rd — the upcoming 3rd #1.
        state.update([_entry(1, 1, "Artist A", "Song A")])
        state.update([_entry(2, 1, "Artist A", "Song B")])
        assert state.artist_ordinal_no1("Artist A") == "3rd"

        state.update([_entry(3, 1, "Artist A", "Song C")])
        assert state.artist_ordinal_no1("Artist A") == "4th"

    def test_get_past_no1_at_week(self):
        from backend.domains.community.historical_state import HistoricalState

        state = HistoricalState()
        state.update([_entry(1, 1, "Artist A", "Song A", "2024-01-06")])
        state.update([_entry(2, 1, "Artist B", "Song B", "2024-01-13")])

        result = state.get_past_no1_at_week("2024-01-06")
        assert result["track_name"] == "Song A"

        result2 = state.get_past_no1_at_week("2024-01-13")
        assert result2["track_name"] == "Song B"

        result3 = state.get_past_no1_at_week("2025-01-01")
        assert result3 is None
