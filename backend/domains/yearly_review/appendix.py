"""Complete, non-narrative annual indexes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.models.yearly_review import YearlyAppendix, YearlyMonthSummary


def build_appendix(
    play_rankings: Mapping[str, Any],
    billboard: Mapping[str, Any],
    months: Sequence[YearlyMonthSummary],
    *,
    playback_record_counts: Mapping[str, int] | None = None,
) -> YearlyAppendix:
    play_charts: dict[str, list[dict[str, Any]]] = {}
    for entity, chart in dict(play_rankings.get("charts", {})).items():
        play_charts[f"{entity}_by_plays"] = [dict(row) for row in chart.get("by_plays", [])]
        play_charts[f"{entity}_by_hours"] = [dict(row) for row in chart.get("by_hours", [])]
    billboard_charts = {
        entity: [dict(row) for row in rows]
        for entity, rows in dict(billboard.get("charts", {})).items()
    }
    monthly_champions = [
        {
            "month": month.month,
            "plays": month.plays,
            "hours": month.hours,
            "active_days": month.active_days,
            "leaders": {key: value.model_dump() for key, value in month.leaders.items()},
            "stage_id": month.stage_id,
            "event_ids": list(month.event_ids),
        }
        for month in months
    ]
    record_counts = dict(playback_record_counts or {})
    for key, value in dict(billboard.get("record_catalog_counts", {})).items():
        record_counts[f"billboard_{key}"] = int(value)
    return YearlyAppendix(
        play_charts=play_charts,
        billboard_charts=billboard_charts,
        monthly_champions=monthly_champions,
        record_catalog_counts=record_counts,
    )
