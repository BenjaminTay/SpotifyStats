"""Deterministic closing synthesis that does not copy opening headlines."""

from __future__ import annotations

from collections.abc import Sequence

from backend.models.yearly_review import YearlyEntityRef, YearlyEpilogue, YearlyHeadline


def _clone_as_conclusion(headline: YearlyHeadline, index: int) -> YearlyHeadline:
    metric = headline.primary_metric
    entity = headline.entity_refs[0] if headline.entity_refs else None
    if headline.headline_id == "listening_time_change" and metric:
        direction = "扩张" if float(metric.value) >= 0 else "收紧"
        title = "全年节奏"
        statement = f"与同期相比，全年有效收听规模呈现{direction}，变化幅度为 {abs(float(metric.value)):.1f}%。"
    elif headline.headline_id in {"most_played_artist", "artist_concentration"} and entity:
        title = "陪伴主线"
        statement = f"{entity.name} 不只是一次高峰，而是这一年最清晰、最持续的艺人主线。"
    elif headline.headline_id.startswith("taste_migration_"):
        title = "品味落点"
        statement = f"年内前后阶段的结构变化最终落在：{headline.statement}"
    elif headline.headline_id == "peak_listening_month" and metric:
        title = "年度峰值"
        statement = f"最密集的收听集中在一个明确月份，峰值达到 {metric.value}{metric.unit or ''}。"
    elif headline.headline_id == "replay_pattern" and metric:
        title = "熟悉感"
        statement = f"复听构成了这一年的重要底色，占比达到 {metric.value}{metric.unit or ''}。"
    else:
        title = f"年度结论 {index}"
        statement = f"综合全年证据，可以确认：{headline.statement}"
    return headline.model_copy(
        update={
            "headline_id": f"epilogue_{index}_{headline.headline_id}",
            "title": title,
            "statement": statement,
        }
    )


def build_epilogue(
    headline_candidates: Sequence[YearlyHeadline],
    *,
    new_history_tops: Sequence[YearlyEntityRef] = (),
    next_year_carryovers: Sequence[YearlyEntityRef] = (),
) -> YearlyEpilogue:
    priority = {
        "listening_time_change": 0,
        "most_played_artist": 1,
        "artist_concentration": 2,
        "replay_pattern": 3,
        "peak_listening_month": 4,
    }
    ordered = sorted(
        headline_candidates,
        key=lambda item: (
            2
            if item.headline_id.startswith("taste_migration_")
            else priority.get(item.headline_id, 9),
            item.headline_id,
        ),
    )
    conclusions: list[YearlyHeadline] = []
    seen_themes: set[str] = set()
    source_statements = {headline.statement for headline in headline_candidates}
    for headline in ordered:
        theme = (
            "taste"
            if headline.headline_id.startswith("taste_migration_")
            else "artist"
            if headline.headline_id in {"most_played_artist", "artist_concentration"}
            else "volume"
            if headline.headline_id == "listening_time_change"
            else headline.headline_id
        )
        if theme in seen_themes:
            continue
        conclusion = _clone_as_conclusion(headline, len(conclusions) + 1)
        if conclusion.statement in source_statements:
            continue
        conclusions.append(conclusion)
        seen_themes.add(theme)
        if len(conclusions) == 3:
            break
    return YearlyEpilogue(
        conclusions=conclusions,
        new_history_tops=list(new_history_tops)[:6],
        next_year_carryovers=list(next_year_carryovers)[:6],
    )
