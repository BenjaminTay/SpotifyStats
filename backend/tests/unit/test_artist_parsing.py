"""Candidate parsing does not establish identities or track participation."""

import pytest

from backend.core.import_data import _parse_featured_artists
from backend.domains.metadata.title_credit_parser import (
    extract_title_credit_blocks,
    legacy_names_for_block,
    legacy_title_names,
    resolve_block_entities,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "title",
    [
        "Song (feat. Artist)",
        "Song (feat Artist)",
        "Song [ft. Artist]",
        "Song （featuring Artist）",
        "Song ［feat.Artist］",
        "Song 【FEAT. Artist】",
    ],
)
def test_explicit_credit_markers_require_bound_identity(title):
    assert _parse_featured_artists(title) == []
    assert _parse_featured_artists(title, {"Artist": {7}}) == [7]


@pytest.mark.parametrize(
    "text,names,expected",
    [
        ("Tyler, The Creator", {"Tyler, The Creator": 1}, (1,)),
        ("Tegan and Sara", {"Tegan and Sara": 1}, (1,)),
        ("Earth, Wind & Fire", {"Earth, Wind & Fire": 1, "Fire": 8}, (1,)),
        ("Earth, Wind & Fire and Dido", {"Earth, Wind & Fire": 1, "Dido": 2}, (1, 2)),
        ("Years & Years and Jess Glynne", {"Years & Years": 1, "Jess Glynne": 2}, (1, 2)),
        ("Grimes and Dido", {"Grimes": 1, "Dido": 2}, (1, 2)),
        ("Artist A, Artist B", {"Artist A": 1, "Artist B": 2}, (1, 2)),
        ("Artist A & Artist B", {"Artist A": 1, "Artist B": 2}, (1, 2)),
        ("Artist A, and Artist B", {"Artist A": 1, "Artist B": 2}, (1, 2)),
        ("Kacey Musgraves feat. Mark Ronson", {"Kacey Musgraves": 1, "Mark Ronson": 2}, (1, 2)),
        ("BIA ft.Katie Got Bandz", {"BIA": 1, "Katie Got Bandz": 2}, (1, 2)),
        ("A and feat.B", {"A": 1, "B": 2}, (1, 2)),
        ("A, ft. B", {"A": 1, "B": 2}, (1, 2)),
        ("Someone (The Guest)", {"Someone (The Guest)": 1}, (1,)),
        ("Gary Lightbody of Snow Patrol", {"Gary Lightbody": 1, "Snow Patrol": 2}, (1,)),
        ("張靚穎", {"Jane Zhang": 1, "張靚穎": 1}, (1,)),
        ("Artist A & Missing", {"Artist A": 1}, None),
        (
            "Pharrell Williams and Nile Rodgers",
            {"Pharrell Williams and Nile Rodgers": 3, "Pharrell Williams": 1, "Nile Rodgers": 2},
            None,
        ),
        ("Tegan and Sara", {"Tegan and Sara": 1, "Tegan": 2, "Sara": 3}, None),
        ("Earth, Wind & Fire", {"Earth, Wind & Fire": 1, "Earth": 2, "Wind": 3, "Fire": 4}, None),
        ("Someone", {"Someone": {1, 2}}, None),
        ("98º", {"98°": 1}, None),
    ],
)
def test_complete_identity_resolution(text, names, expected):
    (block,) = extract_title_credit_blocks(f"Song (feat. {text})")
    assert resolve_block_entities(block, names) == expected


def test_with_requires_same_track_participation_even_for_real_named_artist():
    assert _parse_featured_artists("Quit Playing Games (With My Heart)", {"My Heart": {7}}) == []
    assert _parse_featured_artists("Rain On Me (with Ariana Grande)", {"Ariana Grande": {7}}) == []
    assert _parse_featured_artists(
        "Rain On Me (with Ariana Grande)", {"Ariana Grande": {7}}, {7}
    ) == [7]


def test_mixed_with_marker_needs_supported_identity():
    names = {"A": {1}, "B": {2}}
    assert _parse_featured_artists("Song (feat. A with B)", names) == []
    assert _parse_featured_artists("Song (feat. A with B)", names, {2}) == [1, 2]
    assert _parse_featured_artists("Song (feat. A and with B)", names) == []
    assert _parse_featured_artists("Song (feat. A and with B)", names, {2}) == [1, 2]
    names["Band"] = {3}
    assert _parse_featured_artists("Song (feat. A of Band with B)", names) == []
    assert _parse_featured_artists("Song (feat. A of Band with B)", names, {2}) == [1, 2]
    assert _parse_featured_artists("Song (with A feat. B)", names, {1}) == []
    assert _parse_featured_artists("Song (with A feat. B)", names, {1, 2}) == [1, 2]


def test_case_and_whitespace_normalization_keeps_punctuation():
    assert _parse_featured_artists("Song (feat. ARTIST   NAME)", {"Artist Name": {4}}) == [4]
    assert _parse_featured_artists("Song (feat. 98º)", {"98º": {4}, "98°": {5}}) == [4]


def test_nested_parentheses_keep_complete_artist_name_and_exact_span():
    title = "Song (feat. Guest (The Singer)) (Remix)"
    (block,) = extract_title_credit_blocks(title)
    assert block.text == "Guest (The Singer)"
    assert title[block.start : block.end] == "(feat. Guest (The Singer))"
    assert _parse_featured_artists(title, {"Guest (The Singer)": {6}}) == [6]
    assert legacy_names_for_block(block, title) == ["Guest (The Singer"]


@pytest.mark.parametrize(
    "title",
    [
        None,
        "",
        "Plain Track",
        "Song (Live)",
        "Song (Taylor's Version)",
        "Song (From The Vault)",
        "Song (feat. Artist]",
        "Song (feat. Artist",
        "Song (feat.)",
        "Song (with)",
        "Song (feat. Unknown [ft. Artist]",
        "Song (feat. Unknown [ft. Artist]]",
    ],
)
def test_non_credit_or_unbalanced_titles_are_not_accepted(title):
    assert extract_title_credit_blocks(title) == ()
    assert _parse_featured_artists(title, {"Artist": {1}}) == []


def test_repeated_blocks_are_identity_deduplicated():
    assert _parse_featured_artists("Song (feat. A) [ft. A]", {"A": {1}}) == [1]


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Song (feat. Earth, Wind & Fire)", ["Earth", "Wind", "Fire"]),
        ("Song (with Years & Years and Jess Glynne)", ["Years", "Years and Jess Glynne"]),
        ("Song (feat. Kacey Musgraves feat. Mark Ronson)", ["Kacey Musgraves feat. Mark Ronson"]),
        ("Song (feat. Guest (The Singer))", ["Guest (The Singer"]),
        ("Song (feat.Artist)", []),
        ("Song （feat. Artist）", []),
        ("Song (featuring Artist)", []),
        ("Song (with B) (feat. A) [ft. C]", ["A", "B", "C"]),
        ("Song (feat. Remix, A, a)", ["A"]),
    ],
)
def test_historical_parser_is_an_exact_reproduction(title, expected):
    assert legacy_title_names(title) == expected
