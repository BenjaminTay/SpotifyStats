"""Unit tests for track group key resolution and merge level normalization."""

from __future__ import annotations

import pytest

from backend.domains.playback.merge_levels import normalize_merge_level

pytestmark = pytest.mark.unit


class TestNormalizeMergeLevel:
    def test_default_is_2(self):
        assert normalize_merge_level(None) == 2

    def test_valid_l1(self):
        assert normalize_merge_level(1) == 1

    def test_valid_l2(self):
        assert normalize_merge_level(2) == 2

    def test_valid_l3(self):
        assert normalize_merge_level(3) == 3

    def test_out_of_range_returns_2(self):
        assert normalize_merge_level(0) == 2
        assert normalize_merge_level(4) == 2
        assert normalize_merge_level(99) == 2

    def test_string_conversion(self):
        assert normalize_merge_level("1") == 1
        assert normalize_merge_level("3") == 3

    def test_invalid_string_returns_2(self):
        assert normalize_merge_level("abc") == 2
