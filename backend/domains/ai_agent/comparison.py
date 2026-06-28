"""Comparison evidence helpers for AI Agent answers."""

from __future__ import annotations

from typing import Any

_BILLBOARD_METRICS = (
    "power_score",
    "power_rank",
    "no1_weeks",
    "weeks_on_chart",
    "peak_position",
)


def _as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _winner(
    entities: list[dict[str, Any]],
    metric: str,
    *,
    lower_is_better: bool = False,
) -> str | None:
    ranked = [
        (value, entity)
        for entity in entities
        if (value := _as_number(entity.get(metric))) is not None
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=not lower_is_better)
    name = ranked[0][1].get("name")
    return str(name) if name else None


def _first_play_marker(entity: dict[str, Any]) -> str | None:
    value = entity.get("first_play_date") or entity.get("first_played")
    return str(value) if value else None


def _has_billboard_metrics(entity: dict[str, Any]) -> bool:
    return any(entity.get(metric) is not None for metric in _BILLBOARD_METRICS)


def _enrich_entity(entity: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(entity)
    if "found" not in enriched:
        enriched["found"] = not bool(enriched.get("error"))
    if enriched.get("no1_weeks") is None and enriched.get("weeks_at_no1") is not None:
        enriched["no1_weeks"] = enriched.get("weeks_at_no1")

    plays = _as_number(enriched.get("plays"))
    weeks = _as_number(enriched.get("weeks_on_chart"))
    enriched["plays_per_chart_week"] = (
        round(plays / weeks, 2) if plays is not None and weeks and weeks > 0 else None
    )
    return enriched


def summarize_entity_comparison(
    entity_type: str,
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize cumulative, Billboard, and normalized-intensity comparison axes."""
    normalized_entities = [_enrich_entity(entity) for entity in entities]

    fairness_notes: list[str] = []
    first_markers = [
        marker for entity in normalized_entities if (marker := _first_play_marker(entity))
    ]
    if len(set(first_markers)) > 1:
        fairness_notes.append("对象进入你的播放历史时间不同，累计值和强度值需要分开看。")
    if any(_has_billboard_metrics(entity) for entity in normalized_entities):
        fairness_notes.append(
            "SpotifyStats Billboard 是本地个人 Billboard，不是外部官方 Billboard。"
        )

    return {
        "entity_type": entity_type,
        "entities": normalized_entities,
        "winner_by_cumulative_plays": _winner(normalized_entities, "plays"),
        "winner_by_total_hours": _winner(normalized_entities, "hours"),
        "winner_by_power_score": _winner(normalized_entities, "power_score"),
        "winner_by_power_rank": _winner(
            normalized_entities,
            "power_rank",
            lower_is_better=True,
        ),
        "winner_by_intensity": _winner(normalized_entities, "plays_per_chart_week"),
        "fairness_notes": fairness_notes,
    }
