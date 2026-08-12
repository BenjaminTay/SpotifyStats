"""Deterministic closing chapter without repeating the full report."""

from __future__ import annotations

from collections.abc import Sequence

from backend.models.yearly_review import YearlyEntityRef, YearlyEpilogue, YearlyHeadline


def _headline_identity(headline: YearlyHeadline) -> str:
    if headline.entity_refs:
        entity = headline.entity_refs[0]
        return f"{entity.entity_type}:{entity.entity_id or entity.name}".casefold()
    return headline.headline_id


def build_epilogue(
    headline_candidates: Sequence[YearlyHeadline],
    *,
    new_history_tops: Sequence[YearlyEntityRef] = (),
    next_year_carryovers: Sequence[YearlyEntityRef] = (),
) -> YearlyEpilogue:
    conclusions: list[YearlyHeadline] = []
    seen: set[str] = set()
    for headline in headline_candidates:
        identity = _headline_identity(headline)
        if identity in seen:
            continue
        conclusions.append(headline)
        seen.add(identity)
        if len(conclusions) == 3:
            break
    return YearlyEpilogue(
        conclusions=conclusions,
        new_history_tops=list(new_history_tops)[:6],
        next_year_carryovers=list(next_year_carryovers)[:6],
    )
