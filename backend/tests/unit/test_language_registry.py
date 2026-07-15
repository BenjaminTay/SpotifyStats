from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domains.metadata.language_registry import (
    LANGUAGE_REGISTRY_VERSION,
    SUPPORTED_LANGUAGE_CODES,
    language_label,
    normalize_language_claim,
)
from backend.models.artist_language_metadata import (
    ArtistLanguageCoverageResponse,
    ArtistLanguageEvidenceInput,
    ArtistLanguageReviewDecisionRequest,
    ArtistLanguageReviewListResponse,
    ArtistLanguageSourceInput,
)


def test_registry_normalizes_legacy_aliases() -> None:
    assert normalize_language_claim("english", None) == ("en", None)
    assert normalize_language_claim(" chinese ", "Mandarin") == (
        "zh",
        "mandarin",
    )
    assert language_label("zh") == "中文"
    assert language_label("ca") == "加泰罗尼亚文"
    assert normalize_language_claim("Catalan", None) == ("ca", None)
    assert language_label("pcm") == "尼日利亚皮钦语"
    assert normalize_language_claim("Nigerian Pidgin", None) == ("pcm", None)
    assert LANGUAGE_REGISTRY_VERSION == "artist-language-v3"


def test_supported_language_codes_have_stable_registry_order() -> None:
    assert SUPPORTED_LANGUAGE_CODES == (
        "en",
        "zh",
        "ja",
        "ko",
        "es",
        "fr",
        "de",
        "pt",
        "it",
        "ru",
        "ar",
        "hi",
        "th",
        "vi",
        "id",
        "ms",
        "ca",
        "pcm",
    )


def test_registry_rejects_unknown_codes_and_invalid_variants() -> None:
    with pytest.raises(ValueError, match="unsupported language code"):
        normalize_language_claim("xx-invalid", None)
    with pytest.raises(ValueError, match="unsupported variant"):
        normalize_language_claim("en", "cantonese")


def test_public_models_reject_values_outside_literal_contracts() -> None:
    with pytest.raises(ValidationError):
        ArtistLanguageSourceInput(classification="unknown")
    with pytest.raises(ValidationError):
        ArtistLanguageEvidenceInput(
            evidence_kind="blog",
            performer_attribution="artist_vocal_confirmed",
            evidence_url="https://example.com",
            evidence_title="Profile",
            evidence_summary="The profile identifies the vocal language.",
        )
    with pytest.raises(ValidationError):
        ArtistLanguageReviewDecisionRequest(
            action="delete",
            resolution_note="Not a supported review action.",
        )


def test_public_model_collection_defaults_are_independent() -> None:
    first_source = ArtistLanguageSourceInput(classification="instrumental")
    second_source = ArtistLanguageSourceInput(classification="instrumental")
    first_source.evidence.append(
        ArtistLanguageEvidenceInput(
            evidence_kind="artist_profile",
            performer_attribution="artist_instrumental_confirmed",
            evidence_url="https://example.com/profile",
            evidence_title="Profile",
            evidence_summary="The profile identifies an instrumental artist.",
        )
    )

    coverage = ArtistLanguageCoverageResponse(
        eligible_hours=0,
        excluded_unattributed_hours=0,
        classified_hours=0,
        unknown_hours=0,
        classified_pct=0,
        unknown_pct=0,
        caveat="No eligible plays.",
    )

    assert len(first_source.evidence) == 1
    assert second_source.evidence == []
    assert coverage.buckets == []
    assert coverage.source_hours == {}
    assert coverage.top_missing == []
    assert ArtistLanguageReviewListResponse().items == []
