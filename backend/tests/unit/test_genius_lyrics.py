"""Unit tests for Genius lyrics cleaning (no DB, no network)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestLyricsCleaning:
    def test_removes_metadata(self):
        from backend.services.genius_service import _get_client

        client = _get_client()
        if client is None:
            pytest.skip("Genius client not available")

        raw = "130 ContributorsTranslationsTest Song LyricsSome description text… Read More [Verse 1]\nLine one\nLine two\n\nYou Might Also Like"
        cleaned = client._clean_lyrics(raw)
        lines = cleaned.split("\n")
        assert "[Verse 1]" == lines[0].strip()
        assert "Line one" in cleaned
        assert "Contributors" not in cleaned
        assert "You Might Also Like" not in cleaned

    def test_section_spacing(self):
        from backend.services.genius_service import _get_client

        client = _get_client()
        if client is None:
            pytest.skip("Genius client not available")

        raw = "[Verse 1]\nLine one\nLine two\n\n\n[Chorus]\nChorus line"
        cleaned = client._clean_lyrics(raw)
        assert "\n\n\n" not in cleaned
        assert "\n\n[Chorus]" in cleaned
        assert cleaned.startswith("[Verse 1]")
