from __future__ import annotations

from collections import Counter

from backend.domains.yearly_review.record_presenters import present_record_candidate
from backend.domains.yearly_review.records import select_yearly_records
from backend.models.yearly_review import (
    YearlyEntityRef,
    YearlyHighlightCandidate,
    YearlyMetric,
)


def _candidate(
    index: int,
    family: str,
    *,
    artist: str | None = None,
    source: str = "playback_records",
    sample_size: int = 10,
    year: int = 2025,
) -> YearlyHighlightCandidate:
    artist = artist or f"Artist {index}"
    return YearlyHighlightCandidate(
        candidate_id=f"candidate-{source}-{index}-{family}",
        source=source,
        source_family=family,
        record_key=f"{family}.daily_binge.artist"
        if family == "obsession"
        else (
            f"{family}.longest_streak_days.artist"
            if family == "longevity"
            else (
                f"{family}.discovery_day.artist"
                if family == "discovery"
                else f"{family}.playback_milestones"
            )
        ),
        category=family,
        fact_type=f"fact_{index}",
        entity_refs=[
            YearlyEntityRef(entity_type="artist", name=artist, deep_link=f"/music/artists/{artist}")
        ],
        primary_metric=YearlyMetric(
            key=f"metric_{index}", label="记录值", value=10 + index, unit="次"
        ),
        raw_values={
            "sample_size": sample_size,
            "year": year,
            "date": f"2025-{1 + index % 12:02d}-01",
            "span_days": 20 + index,
        },
        source_refs=[f"source:{index}"],
    )


def test_selector_deduplicates_and_enforces_diversity_caps() -> None:
    families = ["obsession", "longevity", "discovery", "behavior"]
    candidates = [
        _candidate(index, family, artist="Dominant" if index < 5 else None)
        for index, family in enumerate(families * 3)
    ]
    duplicate = candidates[0].model_copy(
        update={
            "candidate_id": "duplicate-special-moment",
            "source": "billboard_records",
            "source_refs": ["duplicate"],
        }
    )
    insufficient = _candidate(40, "market", sample_size=1)
    wrong_year = _candidate(41, "movement", year=2024)
    result = select_yearly_records(
        2025,
        [candidates, [duplicate, insufficient, wrong_year]],
    )

    assert 8 <= len(result.featured) <= 12
    categories = Counter(item.category for item in result.featured)
    assert max(categories.values()) <= 2
    entities = Counter(item.entity_refs[0].name for item in result.featured if item.entity_refs)
    assert entities["Dominant"] <= 2
    assert result.catalog_counts["input_total"] == 15
    assert result.catalog_counts["eligible_total"] == 13
    assert result.catalog_counts["deduped_total"] == 12


def test_empty_candidate_pool_keeps_legal_empty_state() -> None:
    result = select_yearly_records(2025, [])

    assert result.featured == []
    assert result.catalog_counts["featured_total"] == 0


def test_unknown_record_key_is_not_projected_by_generic_fallback() -> None:
    candidate = _candidate(1, "obsession").model_copy(update={"record_key": "internal.unknown.key"})

    result = select_yearly_records(2025, [[candidate]])

    assert result.featured == []


def test_public_record_metric_localizes_legacy_units() -> None:
    candidate = _candidate(1, "longevity").model_copy(
        update={
            "record_key": "longevity.comeback_after_sleep.artist",
            "primary_metric": YearlyMetric(
                key="sleep_days", label="旧爱", value=328, unit="天後回歸"
            ),
        }
    )

    presented = present_record_candidate(candidate)

    assert presented is not None
    assert presented.metrics[0].unit == "天后回归"
