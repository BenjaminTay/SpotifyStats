"""Unit tests for weekly post generators — #1 announcements, top 10, debuts, jumps."""

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


def _make_state():
    from backend.domains.community.historical_state import HistoricalState

    return HistoricalState()


class TestGenNo1Posts:
    def test_debut_no1_generates_new_post(self):
        from backend.domains.community.feed_weekly import _gen_no1_posts

        state = _make_state()
        entries = [_entry(1, 101, "New Song", "New Artist")]
        posts = _gen_no1_posts(entries, None, state, "2024-01-13T12:00:00", "2024-01-06")

        assert len(posts) == 1
        assert "#1(new)" in posts[0].content
        assert "New Song" in posts[0].content
        assert posts[0].account_handle == "@chartdata"

    def test_no1_stay_generates_equals_post(self):
        from backend.domains.community.feed_weekly import _gen_no1_posts

        state = _make_state()
        # First week: song debuts at #1
        entries_w1 = [_entry(1, 101, "Hit Song", "Artist X")]
        state.update(entries_w1)

        # Second week: song stays at #1
        entries_w2 = [_entry(1, 101, "Hit Song", "Artist X")]
        prev = [_entry(1, 101, "Hit Song", "Artist X")]
        posts = _gen_no1_posts(entries_w2, prev, state, "2024-01-20T12:00:00", "2024-01-13")

        assert len(posts) == 1
        assert "#1(=)" in posts[0].content

    def test_no1_climb_generates_plus_post(self):
        from backend.domains.community.feed_weekly import _gen_no1_posts

        state = _make_state()
        # First week: song at #10
        state.update([_entry(10, 101, "Rising Song", "Artist Y")])

        entries = [_entry(1, 101, "Rising Song", "Artist Y")]
        prev = [_entry(10, 101, "Rising Song", "Artist Y")]
        posts = _gen_no1_posts(entries, prev, state, "2024-01-13T12:00:00", "2024-01-06")

        assert len(posts) == 1
        assert "#1(+9)" in posts[0].content

    def test_no1_re_entry(self):
        from backend.domains.community.feed_weekly import _gen_no1_posts

        state = _make_state()
        # Song was #1 before (had weeks at #1)
        state.update([_entry(1, 101, "Returning Song", "Artist Z")])
        state.update([_entry(2, 101, "Returning Song", "Artist Z")])
        # Week 3: song not in chart
        state.update([_entry(1, 999, "Other Song", "Artist W")])

        # Week 4: song re-enters at #1
        entries = [_entry(1, 101, "Returning Song", "Artist Z")]
        posts = _gen_no1_posts(entries, None, state, "2024-02-03T12:00:00", "2024-01-27")

        assert len(posts) == 1
        assert "#1(re)" in posts[0].content

    def test_linked_entities_present(self):
        from backend.domains.community.feed_weekly import _gen_no1_posts

        state = _make_state()
        entries = [_entry(1, 42, "Test Track", "Test Artist")]
        posts = _gen_no1_posts(entries, None, state, "2024-01-13T12:00:00", "2024-01-06")

        entities = posts[0].linked_entities
        assert any(e["type"] == "track" and e["name"] == "Test Track" for e in entities)
        assert any(e["type"] == "artist" and e["name"] == "Test Artist" for e in entities)


class TestGenTop10Summary:
    def test_generates_top10_list(self):
        from backend.domains.community.feed_weekly import _gen_top10_summary

        state = _make_state()
        entries = [_entry(i, i * 10, f"Song {i}", f"Artist {i}") for i in range(1, 15)]
        post = _gen_top10_summary(entries, state, "2024-01-13T12:00:00", "2024-01-06")

        assert post is not None
        assert post.account_handle == "@billboardcharts"
        # Should contain all 10 entries
        for i in range(1, 11):
            assert f"Song {i}" in post.content

    def test_insufficient_entries_returns_none(self):
        from backend.domains.community.feed_weekly import _gen_top10_summary

        state = _make_state()
        post = _gen_top10_summary([], state, "2024-01-13T12:00:00", "2024-01-06")
        assert post is None


class TestGenDebutPosts:
    def test_single_debut(self):
        from backend.domains.community.feed_weekly import _gen_debut_posts

        state = _make_state()
        entries = [_entry(5, 999, "Fresh Track", "New Artist")]
        posts = _gen_debut_posts(entries, state, "2024-01-13T12:00:00", "2024-01-06")

        assert len(posts) == 1
        assert "Fresh Track" in posts[0].content
        assert posts[0].account_handle == "@debutwatch"

    def test_multiple_debuts(self):
        from backend.domains.community.feed_weekly import _gen_debut_posts

        state = _make_state()
        entries = [
            _entry(10, 1, "Debut 1", "Artist A"),
            _entry(15, 2, "Debut 2", "Artist B"),
            _entry(20, 3, "Debut 3", "Artist C"),
        ]
        posts = _gen_debut_posts(entries, state, "2024-01-13T12:00:00", "2024-01-06")

        assert len(posts) == 1  # One combined post
        assert "Debut 1" in posts[0].content
        assert "Debut 2" in posts[0].content

    def test_no_debuts_returns_empty(self):
        from backend.domains.community.feed_weekly import _gen_debut_posts

        state = _make_state()
        # First add tracks so they're not new
        state.update([_entry(5, 1, "Old Track", "Old Artist")])

        entries = [_entry(5, 1, "Old Track", "Old Artist")]
        posts = _gen_debut_posts(entries, state, "2024-01-13T12:00:00", "2024-01-06")

        assert len(posts) == 0


class TestGenBiggestJump:
    def test_detects_big_jump(self):
        from backend.domains.community.feed_weekly import _gen_biggest_jump_post

        entries = [_entry(5, 101, "Leaping Song", "Artist X")]
        prev = [_entry(30, 101, "Leaping Song", "Artist X")]
        post = _gen_biggest_jump_post(entries, prev, "2024-01-13T12:00:00", "2024-01-06")

        assert post is not None
        assert "Leaping Song" in post.content
        assert post.account_handle == "@chartdata"

    def test_small_jump_ignored(self):
        from backend.domains.community.feed_weekly import _gen_biggest_jump_post

        entries = [_entry(5, 101, "Slow Song", "Artist X")]
        prev = [_entry(8, 101, "Slow Song", "Artist X")]
        post = _gen_biggest_jump_post(entries, prev, "2024-01-13T12:00:00", "2024-01-06")

        assert post is None  # Delta < 10

    def test_no_prev_week_returns_none(self):
        from backend.domains.community.feed_weekly import _gen_biggest_jump_post

        entries = [_entry(1, 101, "Song", "Artist")]
        post = _gen_biggest_jump_post(entries, None, "2024-01-13T12:00:00", "2024-01-06")

        assert post is None


class TestGenBiggestDrop:
    def test_detects_big_drop(self):
        from backend.domains.community.feed_weekly import _gen_biggest_drop_post

        entries = [_entry(30, 101, "Falling Song", "Artist X")]
        prev = [_entry(5, 101, "Falling Song", "Artist X")]
        post = _gen_biggest_drop_post(entries, prev, "2024-01-13T12:00:00", "2024-01-06")

        assert post is not None
        assert "Falling Song" in post.content

    def test_small_drop_ignored(self):
        from backend.domains.community.feed_weekly import _gen_biggest_drop_post

        entries = [_entry(8, 101, "Slow Song", "Artist X")]
        prev = [_entry(5, 101, "Slow Song", "Artist X")]
        post = _gen_biggest_drop_post(entries, prev, "2024-01-13T12:00:00", "2024-01-06")

        assert post is None


class TestGenArtistFirstTop10:
    def test_first_top10_generates_post(self):
        from backend.domains.community.feed_weekly import _gen_artist_first_top10

        state = _make_state()
        # Artist has never been in top 10
        entries = [_entry(8, 101, "New Hit", "Fresh Artist")]
        post = _gen_artist_first_top10(entries, state, "2024-01-13T12:00:00", "2024-01-06")

        assert post is not None
        assert "Fresh Artist" in post.content
        assert post.account_handle == "@popcrave"

    def test_already_in_top10_no_post(self):
        from backend.domains.community.feed_weekly import _gen_artist_first_top10

        state = _make_state()
        state.update([_entry(5, 1, "Old Hit", "Veteran Artist")])

        entries = [_entry(8, 2, "Another Hit", "Veteran Artist")]
        post = _gen_artist_first_top10(entries, state, "2024-01-13T12:00:00", "2024-01-06")

        assert post is None
