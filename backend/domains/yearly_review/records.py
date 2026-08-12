"""Deterministic multi-source annual record selector."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from backend.domains.yearly_review.policies import (
    HIGHLIGHT_CATEGORY_CAP,
    HIGHLIGHT_ENTITY_CAP,
    HIGHLIGHT_MAX_COUNT,
    HIGHLIGHT_MIN_COUNT,
    HIGHLIGHT_POLICY_VERSION,
    HIGHLIGHT_RELAXED_CATEGORY_CAP,
    HIGHLIGHT_WEIGHTS,
)
from backend.domains.yearly_review.record_presenters import (
    has_public_record_copy,
    present_record_candidate,
)
from backend.models.yearly_review import (
    YearlyFeaturedRecord,
    YearlyHighlightCandidate,
    YearlyRecordsChapter,
)

_DURATION_KEYS = (
    "span_days",
    "streak_days",
    "weeks_on_chart",
    "weeks_at_no1",
    "active_months",
    "consecutive_days",
)


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _period_key(candidate: YearlyHighlightCandidate) -> str:
    if candidate.period:
        return repr(sorted(candidate.period.items()))
    raw = candidate.raw_values
    return "|".join(
        str(raw.get(key) or "")
        for key in ("date", "start_date", "end_date", "month", "year", "billboard_week")
    )


def _entity_key(candidate: YearlyHighlightCandidate) -> str:
    if not candidate.entity_refs:
        raw = candidate.raw_values
        return f"none:{raw.get('date') or raw.get('month') or raw.get('name') or ''}".casefold()
    ref = candidate.entity_refs[0]
    return f"{ref.entity_type}:{ref.entity_id or ref.name}".casefold()


def _fact_family(candidate: YearlyHighlightCandidate) -> str:
    key = candidate.record_key.casefold()
    for suffix in (".track", ".album", ".artist"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    aliases = {
        "obsession.daily_binge": "obsession.binge",
        "obsession.daily_duration": "obsession.binge",
        "reigns.daily_champion": "reigns.champion",
        "time_patterns.monthly_peak": "time_patterns.peak",
    }
    return aliases.get(key, key)


def _metric_key(candidate: YearlyHighlightCandidate) -> str:
    metric = candidate.primary_metric.key if candidate.primary_metric else "raw"
    return f"{_fact_family(candidate)}:{metric}"


def _semantic_key(candidate: YearlyHighlightCandidate) -> str:
    return "|".join(
        (
            _entity_key(candidate),
            _fact_family(candidate),
            _period_key(candidate),
            _metric_key(candidate),
        )
    )


def _eligible(candidate: YearlyHighlightCandidate, year: int) -> bool:
    if not candidate.eligible or candidate.coverage_status == "unavailable":
        return False
    if candidate.evidence_grade not in {"A", "B", "C"}:
        return False
    if candidate.evidence_grade == "C" and 1 + len(candidate.secondary_metrics) < 2:
        return False
    sample_size = _number(candidate.raw_values.get("sample_size"))
    if sample_size is not None and sample_size < 3:
        return False
    raw_year = candidate.raw_values.get("year")
    if isinstance(raw_year, (int, float)) and int(raw_year) != year:
        return False
    if "year_end_no1" in candidate.record_key:
        return False
    return has_public_record_copy(candidate)


def _component(
    candidate: YearlyHighlightCandidate,
    key: str,
) -> float | None:
    explicit = candidate.noteworthiness_components.get(key)
    if explicit is not None:
        return max(0.0, min(float(explicit), 1.0))
    raw = candidate.raw_values
    if key == "magnitude":
        return _number(candidate.primary_metric.value) if candidate.primary_metric else None
    if key == "duration":
        values = [_number(raw.get(field)) for field in _DURATION_KEYS]
        values = [value for value in values if value is not None]
        return max(values) if values else None
    if key == "historical_rarity":
        return 1.0 if raw.get("is_personal_best") or raw.get("all_time_rank") == 1 else None
    if key == "comparison":
        values = [
            abs(value)
            for value in (
                _number(candidate.comparison.get("change_pct")),
                _number(raw.get("change_pct")),
                _number(raw.get("同比变化")),
            )
            if value is not None
        ]
        return max(values) if values else None
    if key == "specificity":
        return min(
            1.0,
            (0.5 if candidate.entity_refs else 0.0)
            + (0.5 if any(raw.get(field) for field in ("date", "month", "billboard_week")) else 0),
        )
    if key == "evidence":
        return {"A": 1.0, "B": 0.8, "C": 0.6}[candidate.evidence_grade]
    return None


def _normalized_scores(candidates: Sequence[YearlyHighlightCandidate]) -> dict[str, float]:
    raw_components: dict[str, dict[str, float | None]] = {
        candidate.candidate_id: {key: _component(candidate, key) for key in HIGHLIGHT_WEIGHTS}
        for candidate in candidates
    }
    for key in ("magnitude", "duration", "comparison"):
        values = [
            value
            for components in raw_components.values()
            if (value := components[key]) is not None
        ]
        maximum = max(values) if values else 0
        for components in raw_components.values():
            value = components[key]
            if value is not None:
                components[key] = math.log1p(max(value, 0)) / math.log1p(maximum) if maximum else 0

    scores: dict[str, float] = {}
    for candidate in candidates:
        components = raw_components[candidate.candidate_id]
        available = {key: value for key, value in components.items() if value is not None}
        weight_sum = sum(HIGHLIGHT_WEIGHTS[key] for key in available) or 1.0
        score = sum(
            float(value) * HIGHLIGHT_WEIGHTS[key] / weight_sum for key, value in available.items()
        )
        candidate.noteworthiness_components = {
            key: round(float(value), 4) for key, value in available.items()
        }
        scores[candidate.candidate_id] = round(score, 6)
    return scores


def _narrative_family(candidate: YearlyHighlightCandidate) -> str:
    family = candidate.source_family
    if family == "obsession":
        return "peak"
    if family in {"longevity", "reigns", "endurance", "championship"}:
        return "sustained"
    if (
        family == "discovery"
        or "return" in candidate.record_key
        or "comeback" in candidate.record_key
    ):
        return "discovery_return"
    if family in {"behavior", "time_patterns", "market", "movement"}:
        return "behavior"
    return "other"


def record_candidate_to_featured(candidate: YearlyHighlightCandidate) -> YearlyFeaturedRecord:
    """Project an internal candidate into the stable public record contract."""
    featured = present_record_candidate(candidate)
    if featured is None:
        raise ValueError(f"unsupported public record: {candidate.record_key}")
    return featured


def qualified_yearly_candidates(
    year: int, candidates: Sequence[YearlyHighlightCandidate]
) -> list[YearlyHighlightCandidate]:
    eligible = [candidate for candidate in candidates if _eligible(candidate, year)]
    deduped: dict[str, YearlyHighlightCandidate] = {}
    for candidate in eligible:
        key = _semantic_key(candidate)
        existing = deduped.get(key)
        if existing is None or (
            candidate.evidence_grade,
            -len(candidate.source_refs),
            candidate.candidate_id,
        ) < (
            existing.evidence_grade,
            -len(existing.source_refs),
            existing.candidate_id,
        ):
            deduped[key] = candidate
    return list(deduped.values())


def _choose(
    ordered: Sequence[YearlyHighlightCandidate],
    *,
    category_cap: int,
    seed: Sequence[YearlyHighlightCandidate] = (),
) -> list[YearlyHighlightCandidate]:
    selected = list(seed)
    selected_ids = {item.candidate_id for item in selected}
    categories = Counter(item.source_family for item in selected)
    entities = Counter(_entity_key(item) for item in selected if item.entity_refs)
    metrics = {_metric_key(item) for item in selected}
    for candidate in ordered:
        if candidate.candidate_id in selected_ids:
            continue
        entity = _entity_key(candidate)
        metric = _metric_key(candidate)
        if categories[candidate.source_family] >= category_cap:
            continue
        if candidate.entity_refs and entities[entity] >= HIGHLIGHT_ENTITY_CAP:
            continue
        if metric in metrics:
            continue
        selected.append(candidate)
        selected_ids.add(candidate.candidate_id)
        categories[candidate.source_family] += 1
        if candidate.entity_refs:
            entities[entity] += 1
        metrics.add(metric)
        if len(selected) == HIGHLIGHT_MAX_COUNT:
            break
    return selected


def select_yearly_records(
    year: int,
    candidate_groups: Sequence[Sequence[YearlyHighlightCandidate]],
    *,
    catalog_counts: Mapping[str, int] | None = None,
) -> YearlyRecordsChapter:
    pool = [candidate for group in candidate_groups for candidate in group]
    eligible = [candidate for candidate in pool if _eligible(candidate, year)]
    candidates = qualified_yearly_candidates(year, pool)
    scores = _normalized_scores(candidates)
    ordered = sorted(
        candidates,
        key=lambda item: (
            -scores[item.candidate_id],
            item.source_family,
            item.record_key,
            item.candidate_id,
        ),
    )

    seed: list[YearlyHighlightCandidate] = []
    for family in ("peak", "sustained", "discovery_return", "behavior"):
        match = next((item for item in ordered if _narrative_family(item) == family), None)
        if match:
            seed = _choose([match], category_cap=HIGHLIGHT_CATEGORY_CAP, seed=seed)
    selected = _choose(ordered, category_cap=HIGHLIGHT_CATEGORY_CAP, seed=seed)
    if len(selected) < HIGHLIGHT_MIN_COUNT:
        selected = _choose(
            ordered,
            category_cap=HIGHLIGHT_RELAXED_CATEGORY_CAP,
            seed=selected,
        )
    selected = selected[:HIGHLIGHT_MAX_COUNT]
    counts = dict(catalog_counts or {})
    counts.update(
        {
            "input_total": len(pool),
            "eligible_total": len(eligible),
            "deduped_total": len(candidates),
            "featured_total": len(selected),
        }
    )
    return YearlyRecordsChapter(
        policy_version=HIGHLIGHT_POLICY_VERSION,
        featured=[record_candidate_to_featured(candidate) for candidate in selected],
        catalog_counts=counts,
    )
