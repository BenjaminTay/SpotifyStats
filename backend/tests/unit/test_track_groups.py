"""Unit tests for merge level normalization."""

from __future__ import annotations

import pytest

from backend.domains.playback.merge_levels import normalize_merge_level

pytestmark = pytest.mark.unit


class TestNormalizeMergeLevel:
    def test_defaults_to_2_when_none(self):
        assert normalize_merge_level(None) == 2

    def test_defaults_to_2_when_invalid(self):
        assert normalize_merge_level(0) == 2
        assert normalize_merge_level(4) == 2
        assert normalize_merge_level(-1) == 2

    def test_defaults_to_2_on_unparseable_string(self):
        assert normalize_merge_level("abc") == 2

    def test_parses_valid_string(self):
        assert normalize_merge_level("1") == 2
        assert normalize_merge_level("3") == 3

    def test_passes_valid_integers(self):
        assert normalize_merge_level(1) == 2
        assert normalize_merge_level(2) == 2
        assert normalize_merge_level(3) == 3
