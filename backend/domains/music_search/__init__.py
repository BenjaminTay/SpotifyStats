"""Music search domain primitives."""

from backend.domains.music_search.normalization import (
    SEARCH_NORMALIZATION_VERSION,
    ChineseSearchVariantExpander,
    QueryScriptCategory,
    SearchQueryAnalysis,
    SearchTextVariants,
    analyze_search_query,
    build_search_text_variants,
    classify_query_script,
    is_search_query_eligible,
    minimum_query_length,
    normalize_search_text,
    query_character_length,
)

__all__ = [
    "SEARCH_NORMALIZATION_VERSION",
    "ChineseSearchVariantExpander",
    "QueryScriptCategory",
    "SearchQueryAnalysis",
    "SearchTextVariants",
    "analyze_search_query",
    "build_search_text_variants",
    "classify_query_script",
    "is_search_query_eligible",
    "minimum_query_length",
    "normalize_search_text",
    "query_character_length",
]
