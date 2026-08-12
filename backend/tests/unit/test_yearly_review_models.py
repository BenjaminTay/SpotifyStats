from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyEntityRef,
    YearlyHighlightCandidate,
    YearlyPlayCoverage,
    YearlyReviewCoverage,
    YearlyReviewFilterContext,
    YearlyReviewResponse,
    YearlyTasteCoverage,
)


def _filter_context() -> YearlyReviewFilterContext:
    return YearlyReviewFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=None,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=12,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="artist-rev",
        artist_identity_revision=3,
        track_credit_revision=4,
        track_group_revision="track-group-rev",
        album_project_revision="album-project-rev",
        filter_fingerprint="fingerprint",
    )


def _coverage(status: str = "observed_range") -> YearlyReviewCoverage:
    return YearlyReviewCoverage(
        status=status,
        play=YearlyPlayCoverage(status=status),
        billboard=YearlyBillboardCoverage(status="empty", source_status="empty"),
        comparison=YearlyComparisonCoverage(reason="baseline_unavailable"),
        taste=YearlyTasteCoverage(),
    )


def test_response_requires_filter_context_and_coverage() -> None:
    with pytest.raises(ValidationError):
        YearlyReviewResponse(year=2025, status="complete")


def test_response_has_v2_schema_and_legal_empty_chapters() -> None:
    response = YearlyReviewResponse(
        year=2025,
        status="observed_range",
        filter_context=_filter_context(),
        coverage=_coverage(),
    )

    assert response.schema_version == "yearly_review_v2"
    assert response.passport is None
    assert response.headlines == []
    assert response.season.turning_points == []
    assert response.records.featured == []
    assert response.methodology.relationship_policy_version == "relationship_policy_v1"


def test_mutable_defaults_are_not_shared() -> None:
    first = YearlyReviewResponse(
        year=2024,
        status="observed_range",
        filter_context=_filter_context(),
        coverage=_coverage(),
    )
    second = YearlyReviewResponse(
        year=2025,
        status="observed_range",
        filter_context=_filter_context(),
        coverage=_coverage(),
    )

    first.methodology.notes.append("first only")
    first.appendix.monthly_champions.append({"month": 1})
    first.epilogue.new_history_tops.append(YearlyEntityRef(entity_type="artist", name="Only First"))
    first.taste_migration.coverage_notes["scene"] = "样本有限"

    assert second.methodology.notes == []
    assert second.appendix.monthly_champions == []
    assert second.epilogue.new_history_tops == []
    assert second.taste_migration.coverage_notes == {}


def test_schema_publishes_enums_and_nullable_fields() -> None:
    schema = YearlyReviewResponse.model_json_schema()
    status_schema = schema["properties"]["status"]
    passport_schema = schema["properties"]["passport"]

    assert set(status_schema["enum"]) == {
        "complete",
        "year_to_date",
        "observed_range",
        "insufficient",
        "empty",
    }
    assert any(item.get("type") == "null" for item in passport_schema["anyOf"])


def test_invalid_coverage_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _coverage("partial")


def test_highlight_candidate_is_internal_structured_evidence() -> None:
    candidate = YearlyHighlightCandidate(
        candidate_id="candidate-1",
        source="playback_records",
        source_family="obsession",
        record_key="obsession.daily_binge.track",
        category="obsession",
        fact_type="track",
        raw_values={"plays": 18},
        source_refs=["playback_records:obsession.daily_binge.track:0"],
    )

    assert candidate.evidence_grade == "A"
    assert candidate.eligible is True
    assert candidate.secondary_metrics == []
    assert candidate.period == {}
    assert candidate.noteworthiness_components == {}
