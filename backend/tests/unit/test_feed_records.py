"""Unit tests for record and milestone generators."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _entry(rank, track_id, track_name, artist_name):
    return {
        "rank": rank,
        "track_id": track_id,
        "track_name": track_name,
        "artist_name": artist_name,
        "play_count": 1000,
    }


def _album_entry(rank, album_name, artist_name):
    return {"rank": rank, "album_name": album_name, "artist_name": artist_name}


def _artist_entry(rank, artist_name):
    return {"rank": rank, "artist_name": artist_name}


def _make_state():
    from backend.domains.community.historical_state import HistoricalState

    return HistoricalState()


class TestGenRecordPosts:
    def test_longest_no1_record_broken(self):
        from backend.domains.community.feed_records import _gen_record_posts

        state = _make_state()
        # Simulate: song A was #1 for 10 weeks (current record)
        for _ in range(10):
            state.update([_entry(1, 1, "Old Record", "Artist Old")])

        # Now song B breaks the record with its 11th week
        for _ in range(10):
            state.update([_entry(1, 2, "New Record", "Artist New")])
        entries = [_entry(1, 2, "New Record", "Artist New")]
        state.update(entries)

        posts = _gen_record_posts(
            entries,
            state,
            "2024-03-01T12:00:00",
            "2024-02-24",
            track_most_career_weeks=10,
            track_most_career_weeks_artist="Artist Old",
            track_most_top10=0,
            track_most_top10_artist="",
        )
        record_post = [p for p in posts if p.post_type == "record_broken"]
        assert len(record_post) >= 1
        # The record post is about career #1 weeks, content mentions the record holder
        assert "Artist New" in record_post[0].content or any(
            "Artist New" in p.content for p in posts
        )

    def test_no_record_break_returns_empty(self):
        from backend.domains.community.feed_records import _gen_record_posts

        state = _make_state()
        state.update([_entry(1, 1, "Song A", "Artist A")])
        entries = [_entry(1, 1, "Song A", "Artist A")]

        posts = _gen_record_posts(
            entries,
            state,
            "2024-01-13T12:00:00",
            "2024-01-06",
            track_most_career_weeks=5,
            track_most_career_weeks_artist="Other Artist",
            track_most_top10=3,
            track_most_top10_artist="Other Artist",
        )
        record_post = [p for p in posts if p.post_type == "record_broken"]
        assert len(record_post) == 0


class TestGenRecordTiedPosts:
    def test_record_tied_detected(self):
        from backend.domains.community.feed_records import _gen_record_tied_posts

        state = _make_state()
        # Set up: current longest #1 is 5 weeks
        for _ in range(5):
            state.update([_entry(1, 1, "Record Holder", "Artist Old")])

        # New song ties at 5 weeks
        for _ in range(4):
            state.update([_entry(1, 2, "Tying Song", "Artist New")])
        entries = [_entry(1, 2, "Tying Song", "Artist New")]
        state.update(entries)

        posts = _gen_record_tied_posts(entries, state, "2024-02-01T12:00:00", "2024-01-27")
        assert len(posts) >= 1
        assert posts[0].post_type == "record_tied"

    def test_no_tie_returns_empty(self):
        from backend.domains.community.feed_records import _gen_record_tied_posts

        state = _make_state()
        state.update([_entry(1, 1, "Song A", "Artist A")])
        entries = [_entry(1, 1, "Song A", "Artist A")]

        posts = _gen_record_tied_posts(entries, state, "2024-01-13T12:00:00", "2024-01-06")
        assert len(posts) == 0


class TestGenRecordWatchPosts:
    def test_record_watch_close(self):
        from backend.domains.community.feed_records import _gen_record_watch_posts

        state = _make_state()
        # Longest #1 is 10 weeks
        for _ in range(10):
            state.update([_entry(1, 1, "Record Holder", "Artist Old")])

        # Current #1 at 8 weeks (2 away from record)
        for _ in range(7):
            state.update([_entry(1, 2, "Approaching Song", "Artist New")])
        entries = [_entry(1, 2, "Approaching Song", "Artist New")]
        state.update(entries)

        posts = _gen_record_watch_posts(entries, state, "2024-02-15T12:00:00", "2024-02-08")
        assert len(posts) >= 1
        assert posts[0].post_type == "record_watch"

    def test_record_watch_far_returns_empty(self):
        from backend.domains.community.feed_records import _gen_record_watch_posts

        state = _make_state()
        for _ in range(10):
            state.update([_entry(1, 1, "Record Holder", "Artist Old")])

        # Current #1 at only 2 weeks (far from record)
        state.update([_entry(1, 2, "New Song", "Artist New")])
        entries = [_entry(1, 2, "New Song", "Artist New")]
        state.update(entries)

        posts = _gen_record_watch_posts(entries, state, "2024-02-01T12:00:00", "2024-01-27")
        # No watch alert because 2 weeks is far from 10
        assert len(posts) == 0


class TestGenMilestonePosts:
    def test_artist_5th_no1(self):
        from backend.domains.community.feed_records import _gen_milestone_posts

        state = _make_state()
        # Give artist 4 previous #1 songs
        for i in range(4):
            state.update([_entry(1, i + 1, f"Song {i}", "Artist A")])
        # 5th #1
        entries = [_entry(1, 5, "Fifth Hit", "Artist A")]

        posts = _gen_milestone_posts(entries, state, "2024-03-01T12:00:00", "2024-02-24")
        assert len(posts) >= 1
        assert posts[0].post_type == "artist_milestone"

    def test_not_a_milestone_returns_empty(self):
        from backend.domains.community.feed_records import _gen_milestone_posts

        state = _make_state()
        state.update([_entry(1, 1, "Song A", "Artist A")])
        # 2nd #1 is not a milestone
        entries = [_entry(1, 2, "Song B", "Artist A")]

        posts = _gen_milestone_posts(entries, state, "2024-01-13T12:00:00", "2024-01-06")
        # No milestone for count 2
        assert len(posts) == 0


class TestGenSelfReplacement:
    def test_self_replacement_detected(self):
        from backend.domains.community.feed_records import _gen_record_self_replacement

        entries = [_entry(1, 2, "New Song", "Artist A")]
        prev = [_entry(1, 1, "Old Song", "Artist A")]
        post = _gen_record_self_replacement(entries, prev, "2024-02-01T12:00:00", "2024-01-27")

        assert post is not None
        assert post.post_type == "record_broken"
        assert "Artist A" in post.content

    def test_no_self_replacement(self):
        from backend.domains.community.feed_records import _gen_record_self_replacement

        entries = [_entry(1, 2, "New Song", "Artist B")]
        prev = [_entry(1, 1, "Old Song", "Artist A")]
        post = _gen_record_self_replacement(entries, prev, "2024-02-01T12:00:00", "2024-01-27")

        assert post is None

    def test_no_prev_week(self):
        from backend.domains.community.feed_records import _gen_record_self_replacement

        entries = [_entry(1, 1, "Song", "Artist")]
        post = _gen_record_self_replacement(entries, None, "2024-02-01T12:00:00", "2024-01-27")

        assert post is None
