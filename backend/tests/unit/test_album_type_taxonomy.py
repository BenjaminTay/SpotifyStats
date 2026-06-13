"""Unit tests for album type taxonomy."""

from __future__ import annotations

import pytest

from backend.domains.playback.album_type import classify_album, is_album_chart_eligible

pytestmark = pytest.mark.unit


class TestClassifyAlbum:
    def test_single_one_track(self):
        assert classify_album("single", total_tracks=1, total_ms=180_000) == "single"

    def test_single_two_tracks(self):
        assert classify_album("single", total_tracks=2, total_ms=360_000) == "single"

    def test_ep_from_single_type_with_many_tracks(self):
        assert classify_album("single", total_tracks=5, total_ms=900_000) == "ep"

    def test_lp_from_album_type(self):
        assert classify_album("album", total_tracks=12, total_ms=2_400_000) == "lp"

    def test_lp_by_track_count_even_if_short(self):
        # 7 tracks but short duration → still LP
        assert classify_album("album", total_tracks=7, total_ms=600_000) == "lp"

    def test_compilation(self):
        assert classify_album("compilation", total_tracks=18, total_ms=3_600_000) == "compilation"

    def test_ep_few_tracks_short_duration(self):
        assert classify_album("album", total_tracks=5, total_ms=1_200_000) == "ep"

    def test_lp_long_duration_few_tracks(self):
        # 5 tracks but 30 min → LP
        assert classify_album("album", total_tracks=5, total_ms=1_800_000) == "lp"

    def test_unknown_when_no_data(self):
        assert classify_album(None, total_tracks=0, total_ms=0) == "unknown"

    def test_single_without_track_info_defaults_to_single(self):
        # Fallback: when we lack track/duration data, trust Spotify's label
        assert classify_album("single", total_tracks=0, total_ms=0) == "single"


class TestIsAlbumChartEligible:
    def test_lp_is_eligible(self):
        assert is_album_chart_eligible("lp") is True

    def test_ep_is_eligible(self):
        assert is_album_chart_eligible("ep") is True

    def test_compilation_is_eligible(self):
        assert is_album_chart_eligible("compilation") is True

    def test_single_is_not_eligible(self):
        assert is_album_chart_eligible("single") is False

    def test_unknown_is_eligible_for_safety(self):
        # Unclassified albums pass through to avoid excluding albums without metadata
        assert is_album_chart_eligible("unknown") is True
