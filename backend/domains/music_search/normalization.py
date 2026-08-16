"""Deterministic normalization and short-query policy for music search.

These helpers are deliberately independent of SQLite, the current locale, and
optional transliteration libraries.  The backend is the final source of truth
for normalized query values; clients may mirror the stable test vectors for
cache keys and request gating.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

SEARCH_NORMALIZATION_VERSION = "nfkc_casefold_ws_punctuation_v1"


# NFKC already converts most full-width ASCII punctuation.  This table covers
# punctuation that remains distinct after NFKC but is commonly entered as a
# visual variant of an ASCII search character.
_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        # Curly, full-width, and prime-style single quotes.
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u2035": "'",
        "\u275b": "'",
        "\u275c": "'",
        "\uff07": "'",
        # Curly, full-width, and prime-style double quotes.
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2033": '"',
        "\u2036": '"',
        "\u275d": '"',
        "\u275e": '"',
        "\u301d": '"',
        "\u301e": '"',
        "\u301f": '"',
        "\uff02": '"',
        # Hyphen, dash, and minus variants.
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2043": "-",
        "\u2212": "-",
        "\ufe58": "-",
        "\ufe63": "-",
        "\uff0d": "-",
        # Common CJK/full-width punctuation search variants.
        "\u3001": ",",
        "\u3002": ".",
        "\uff61": ".",
        "\u301c": "~",
        "\u2026": "...",
        "\u30fb": "\u00b7",
        "\uff65": "\u00b7",
    }
)


class QueryScriptCategory(str, Enum):
    """Coarse script category used only by the short-query request gate."""

    EMPTY = "empty"
    CJK = "cjk"
    LATIN = "latin"
    NUMERIC = "numeric"
    MIXED = "mixed"
    OTHER = "other"


class ChineseSearchVariantExpander(Protocol):
    """Optional boundary for an approved Simplified/Traditional converter.

    The normalization module never guesses Chinese variants.  A future caller
    may inject a deterministic converter and remains responsible for its
    versioning and provenance.
    """

    def __call__(self, normalized_text: str) -> Iterable[str]: ...


@dataclass(frozen=True)
class SearchTextVariants:
    """Original text plus deterministic, de-duplicated searchable variants."""

    original: str
    normalized: str
    variants: tuple[str, ...]


@dataclass(frozen=True)
class SearchQueryAnalysis:
    """Normalized query and the complete short-query gating decision."""

    normalized_query: str
    script_category: QueryScriptCategory
    character_length: int
    minimum_length: int
    eligible: bool


def normalize_search_text(text: str) -> str:
    """Return the canonical search representation without changing display text.

    The stable pipeline is Unicode NFKC, punctuation unification,
    Unicode-aware casefold, then trim and Unicode whitespace folding.
    """

    if not isinstance(text, str):
        raise TypeError("search text must be a string")

    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(_PUNCTUATION_TRANSLATION)
    normalized = normalized.casefold()
    return " ".join(normalized.split())


def build_search_text_variants(
    text: str,
    *,
    chinese_variant_expander: ChineseSearchVariantExpander | None = None,
) -> SearchTextVariants:
    """Build ordered search variants while preserving the supplied source text.

    Without an injected expander, ``variants`` contains only the normalized
    source.  This makes the absence of Simplified/Traditional conversion
    explicit instead of silently inferring variants from character shapes.
    Every injected variant passes through the same canonical normalizer.
    """

    normalized = normalize_search_text(text)
    candidates: list[str] = [normalized] if normalized else []

    if normalized and chinese_variant_expander is not None:
        candidates.extend(chinese_variant_expander(normalized))

    variants: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized_candidate = normalize_search_text(candidate)
        if normalized_candidate and normalized_candidate not in seen:
            seen.add(normalized_candidate)
            variants.append(normalized_candidate)

    return SearchTextVariants(
        original=text,
        normalized=normalized,
        variants=tuple(variants),
    )


def classify_query_script(text: str) -> QueryScriptCategory:
    """Classify a query as CJK, Latin, numeric, mixed, other, or empty.

    Whitespace and punctuation do not turn an otherwise single-script query
    into ``mixed``.  Han, Hiragana, Katakana, and Hangul share the ``cjk``
    policy because each is allowed to issue a one-character candidate query.
    """

    normalized = normalize_search_text(text)
    if not normalized:
        return QueryScriptCategory.EMPTY

    categories: set[QueryScriptCategory] = set()
    for character in normalized:
        unicode_category = unicodedata.category(character)
        if character.isspace() or unicode_category.startswith("P"):
            continue
        if _is_cjk_character(character):
            categories.add(QueryScriptCategory.CJK)
        elif character.isdecimal():
            categories.add(QueryScriptCategory.NUMERIC)
        elif _is_latin_character(character):
            categories.add(QueryScriptCategory.LATIN)
        else:
            categories.add(QueryScriptCategory.OTHER)

    if not categories:
        return QueryScriptCategory.OTHER
    if len(categories) == 1:
        return next(iter(categories))
    return QueryScriptCategory.MIXED


def minimum_query_length(script_category: QueryScriptCategory) -> int:
    """Return the minimum non-whitespace character count for a script policy."""

    if not isinstance(script_category, QueryScriptCategory):
        raise TypeError("script_category must be a QueryScriptCategory")
    return 1 if script_category is QueryScriptCategory.CJK else 2


def query_character_length(text: str) -> int:
    """Count normalized non-whitespace characters for request gating."""

    normalized = normalize_search_text(text)
    return sum(not character.isspace() for character in normalized)


def analyze_search_query(text: str) -> SearchQueryAnalysis:
    """Normalize a query once and return its deterministic gating policy."""

    normalized = normalize_search_text(text)
    script_category = classify_query_script(normalized)
    character_length = query_character_length(normalized)
    minimum_length = minimum_query_length(script_category)
    return SearchQueryAnalysis(
        normalized_query=normalized,
        script_category=script_category,
        character_length=character_length,
        minimum_length=minimum_length,
        eligible=bool(normalized) and character_length >= minimum_length,
    )


def is_search_query_eligible(text: str) -> bool:
    """Return whether a query is long enough to request remote candidates."""

    return analyze_search_query(text).eligible


def _is_latin_character(character: str) -> bool:
    return unicodedata.name(character, "").startswith("LATIN ")


def _is_cjk_character(character: str) -> bool:
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in _CJK_RANGES)


_CJK_RANGES = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x2E80, 0x2FFF),  # CJK radicals and ideographic description characters
    (0x3040, 0x30FF),  # Hiragana and Katakana
    (0x3130, 0x318F),  # Hangul compatibility Jamo
    (0x31A0, 0x31BF),  # Bopomofo extended
    (0x31F0, 0x31FF),  # Katakana phonetic extensions
    (0x3400, 0x4DBF),  # CJK unified ideographs extension A
    (0x4E00, 0x9FFF),  # CJK unified ideographs
    (0xA960, 0xA97F),  # Hangul Jamo extended A
    (0xAC00, 0xD7AF),  # Hangul syllables
    (0xD7B0, 0xD7FF),  # Hangul Jamo extended B
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
    (0xFF65, 0xFF9F),  # Half-width Katakana
    (0x20000, 0x2FA1F),  # CJK extensions B-F and compatibility supplement
    (0x30000, 0x323AF),  # CJK extensions G-H
)
