"""Canonical language codes and labels for artist language metadata."""

from __future__ import annotations

LANGUAGE_REGISTRY_VERSION = "artist-language-v3"

LANGUAGE_LABELS = {
    "en": "英文",
    "zh": "中文",
    "ja": "日文",
    "ko": "韩文",
    "es": "西班牙文",
    "fr": "法文",
    "de": "德文",
    "pt": "葡萄牙文",
    "it": "意大利文",
    "ru": "俄文",
    "ar": "阿拉伯文",
    "hi": "印地文",
    "th": "泰文",
    "vi": "越南文",
    "id": "印尼文",
    "ms": "马来文",
    "ca": "加泰罗尼亚文",
    "pcm": "尼日利亚皮钦语",
}

SUPPORTED_LANGUAGE_CODES = tuple(LANGUAGE_LABELS)

LANGUAGE_ALIASES = {
    "english": "en",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "portuguese": "pt",
    "catalan": "ca",
    "nigerian pidgin": "pcm",
}

LANGUAGE_VARIANTS = {
    "zh": {"mandarin", "cantonese", "minnan", "hakka"},
    "pt": {"brazilian", "european"},
}


def normalize_language_claim(code: str, variant: str | None) -> tuple[str, str | None]:
    normalized_code = code.strip().lower()
    normalized_code = LANGUAGE_ALIASES.get(normalized_code, normalized_code)
    if normalized_code not in LANGUAGE_LABELS:
        raise ValueError(f"unsupported language code: {code}")

    normalized_variant = variant.strip().lower() if variant and variant.strip() else None
    if normalized_variant and normalized_variant not in LANGUAGE_VARIANTS.get(
        normalized_code, set()
    ):
        raise ValueError(f"unsupported variant for {normalized_code}: {variant}")
    return normalized_code, normalized_variant


def language_label(code: str) -> str:
    return LANGUAGE_LABELS[code]
