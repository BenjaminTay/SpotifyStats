"""Music search domain primitives."""

from backend.domains.music_search.normalization import (
    CHINESE_SEARCH_EXPANSION_VERSION,
    SEARCH_NORMALIZATION_VERSION,
    ChineseSearchVariantExpander,
    QueryScriptCategory,
    SearchQueryAnalysis,
    SearchTextVariants,
    analyze_search_query,
    build_default_search_text_variants,
    build_search_text_variants,
    cjk_search_ngrams,
    classify_query_script,
    is_search_query_eligible,
    minimum_query_length,
    normalize_search_text,
    query_character_length,
)

__all__ = [
    "CHINESE_SEARCH_EXPANSION_VERSION",
    "SEARCH_NORMALIZATION_VERSION",
    "ChineseSearchVariantExpander",
    "QueryScriptCategory",
    "SearchQueryAnalysis",
    "SearchTextVariants",
    "analyze_search_query",
    "build_default_search_text_variants",
    "build_search_text_variants",
    "cjk_search_ngrams",
    "classify_query_script",
    "is_search_query_eligible",
    "minimum_query_length",
    "normalize_search_text",
    "query_character_length",
]
