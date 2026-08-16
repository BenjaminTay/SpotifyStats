"""Stable vectors for the backend music-search normalizer."""

from __future__ import annotations

from typing import cast

import pytest

from backend.domains.music_search.normalization import (
    SEARCH_NORMALIZATION_VERSION,
    ChineseSearchVariantExpander,
    QueryScriptCategory,
    analyze_search_query,
    build_search_text_variants,
    classify_query_script,
    is_search_query_eligible,
    minimum_query_length,
    normalize_search_text,
    query_character_length,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "  \uff34\uff41\uff59\uff4c\uff4f\uff52\u3000\uff33\uff57\uff49\uff46\uff54  ",
            "taylor swift",
        ),
        ("Stra\u00dfe", "strasse"),
        ("  Taylor\t\n  Swift\u2003Live  ", "taylor swift live"),
        ("\u201cDon\u2019t\u201d", '"don\'t"'),
        ("A\u2014B\u2011C\u2212D", "a-b-c-d"),
        ("\uff21\uff0c\uff22\u3002\uff23\uff1a\uff24", "a,b.c:d"),
        ("A\u30fbB\uff65C\u2026", "a\u00b7b\u00b7c..."),
        ("", ""),
    ],
)
def test_normalize_search_text_uses_stable_vectors(source: str, expected: str) -> None:
    assert normalize_search_text(source) == expected


def test_normalization_version_is_explicit() -> None:
    assert SEARCH_NORMALIZATION_VERSION == "nfkc_casefold_ws_punctuation_v1"


def test_normalizer_rejects_non_string_input() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        normalize_search_text(None)  # type: ignore[arg-type]


def test_variants_preserve_original_and_do_not_guess_chinese_conversion() -> None:
    result = build_search_text_variants("  \u5f8c\u4f86  ")

    assert result.original == "  \u5f8c\u4f86  "
    assert result.normalized == "\u5f8c\u4f86"
    assert result.variants == ("\u5f8c\u4f86",)


def test_injected_chinese_variants_share_normalization_and_stable_deduplication() -> None:
    def explicit_fixture_expander(_: str) -> list[str]:
        return [" \u540e\u6765 ", "\u5f8c\u4f86", "\uff28\uff25\uff2c\uff2c\uff2f", "hello", ""]

    result = build_search_text_variants(
        "\u5f8c\u4f86",
        chinese_variant_expander=cast(
            ChineseSearchVariantExpander,
            explicit_fixture_expander,
        ),
    )

    assert result.variants == ("\u5f8c\u4f86", "\u540e\u6765", "hello")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("  ", QueryScriptCategory.EMPTY),
        ("Taylor", QueryScriptCategory.LATIN),
        ("\uff11\uff12\uff13", QueryScriptCategory.NUMERIC),
        ("\u5468\u6770\u502b", QueryScriptCategory.CJK),
        ("\u304b\u306a", QueryScriptCategory.CJK),
        ("\u30ab\u30ca", QueryScriptCategory.CJK),
        ("\ud55c\uae00", QueryScriptCategory.CJK),
        ("Taylor\u5468", QueryScriptCategory.MIXED),
        ("B2", QueryScriptCategory.MIXED),
        ("\u0411\u044c", QueryScriptCategory.OTHER),
        ("!!!", QueryScriptCategory.OTHER),
    ],
)
def test_classify_query_script(query: str, expected: QueryScriptCategory) -> None:
    assert classify_query_script(query) is expected


def test_punctuation_does_not_turn_latin_query_into_mixed_script() -> None:
    assert classify_query_script("Don't-stop!") is QueryScriptCategory.LATIN


def test_minimum_query_length_matches_product_policy() -> None:
    assert minimum_query_length(QueryScriptCategory.CJK) == 1
    for category in (
        QueryScriptCategory.EMPTY,
        QueryScriptCategory.LATIN,
        QueryScriptCategory.NUMERIC,
        QueryScriptCategory.MIXED,
        QueryScriptCategory.OTHER,
    ):
        assert minimum_query_length(category) == 2


@pytest.mark.parametrize(
    ("query", "expected_length", "expected_eligible"),
    [
        ("", 0, False),
        ("a", 1, False),
        ("12", 2, True),
        ("\u5468", 1, True),
        ("\u304b", 1, True),
        ("\ud55c", 1, True),
        ("\u0411", 1, False),
        ("\u0411\u044c", 2, True),
        ("!!", 2, True),
        (" \uff21\u3000\uff22 ", 2, True),
    ],
)
def test_short_query_gate(query: str, expected_length: int, expected_eligible: bool) -> None:
    assert query_character_length(query) == expected_length
    assert is_search_query_eligible(query) is expected_eligible


def test_query_analysis_exposes_normalized_final_fact() -> None:
    analysis = analyze_search_query("  \uff34\uff21\uff39\uff2c\uff2f\uff32  ")

    assert analysis.normalized_query == "taylor"
    assert analysis.script_category is QueryScriptCategory.LATIN
    assert analysis.character_length == 6
    assert analysis.minimum_length == 2
    assert analysis.eligible is True
