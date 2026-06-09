"""Unit tests for _parse_featured_artists in backend.core.import_data."""

import pytest

from backend.core.import_data import _parse_featured_artists


@pytest.mark.unit
class TestParseFeaturedArtists:
    def test_feat_dot(self):
        result = _parse_featured_artists("WAP (feat. Megan Thee Stallion)")
        assert "Megan Thee Stallion" in result

    def test_feat_no_dot(self):
        result = _parse_featured_artists("Song (feat Artist Name)")
        assert "Artist Name" in result

    def test_ft(self):
        result = _parse_featured_artists("Track (ft. Someone)")
        assert "Someone" in result

    def test_with(self):
        result = _parse_featured_artists("Rain On Me (with Ariana Grande)")
        assert "Ariana Grande" in result

    def test_bracket_feat(self):
        result = _parse_featured_artists("Song [feat. Artist]")
        assert "Artist" in result

    def test_bracket_ft(self):
        result = _parse_featured_artists("Song [ft. Someone]")
        assert "Someone" in result

    def test_bracket_with(self):
        result = _parse_featured_artists("Song [with Collab]")
        assert "Collab" in result

    def test_multiple_comma(self):
        result = _parse_featured_artists("Track (feat. Artist A, Artist B)")
        assert "Artist A" in result
        assert "Artist B" in result

    def test_multiple_ampersand(self):
        result = _parse_featured_artists("Track (feat. Artist A & Artist B)")
        assert "Artist A" in result
        assert "Artist B" in result

    def test_deduplicate(self):
        result = _parse_featured_artists("Track (feat. X) (feat. X)")
        assert len(result) == 1

    def test_no_feat(self):
        assert _parse_featured_artists("Plain Track Name") == []

    def test_empty(self):
        assert _parse_featured_artists("") == []
        assert _parse_featured_artists(None) == []

    def test_skip_remix(self):
        assert _parse_featured_artists("Track (Remix)") == []
        assert _parse_featured_artists("Track (Live)") == []
        assert _parse_featured_artists("Track (Acoustic)") == []

    def test_skip_taylors_version(self):
        assert _parse_featured_artists("Track (Taylor's Version)") == []

    def test_skip_from_the_vault(self):
        assert _parse_featured_artists("Nothing New (From The Vault)") == []

    def test_skip_radio_edit(self):
        assert _parse_featured_artists("Track (Radio Edit)") == []

    def test_skip_deluxe(self):
        assert _parse_featured_artists("Track (Deluxe)") == []

    def test_feat_inside_other_parens(self):
        """Track with (feat. X) and (Remix) — only feat should be extracted."""
        result = _parse_featured_artists("Song (feat. Drake) (Remix)")
        assert "Drake" in result
        assert len(result) == 1

    def test_multiple_feat_groups(self):
        result = _parse_featured_artists("Track (feat. A) (feat. B)")
        assert "A" in result
        assert "B" in result

    def test_feat_with_version(self):
        """(feat. X) alongside (Taylor's Version)."""
        result = _parse_featured_artists(
            "Nothing New (feat. Phoebe Bridgers) (Taylor's Version) (From The Vault)"
        )
        assert "Phoebe Bridgers" in result

    def test_case_insensitive(self):
        result = _parse_featured_artists("Song (FEAT. ARTIST)")
        assert "ARTIST" in result
        result = _parse_featured_artists("Song (Feat. Someone)")
        assert "Someone" in result
