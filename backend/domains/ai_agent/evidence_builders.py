"""Build compact evidence cards from read-only Agent tool results."""

from __future__ import annotations

from typing import Any

from backend.domains.ai_agent.evidence import EvidenceCard, EvidenceMetric, EvidenceSource


def _source(item: dict[str, Any]) -> EvidenceSource:
    return EvidenceSource(
        tool_name=str(item.get("tool_name") or ""),
        source_range=str(item.get("source_range") or ""),
        params_summary=str(item.get("params_summary") or ""),
        result_summary=str(item.get("result_summary") or ""),
    )


def _metric(
    name: str,
    label: str,
    value: Any,
    unit: str | None = None,
) -> EvidenceMetric | None:
    if value is None:
        return None
    return EvidenceMetric(name=name, label=label, value=value, unit=unit)


def _append_metric(metrics: list[EvidenceMetric], metric: EvidenceMetric | None) -> None:
    if metric is not None:
        metrics.append(metric)


def _entity_name(item: dict[str, Any], data: dict[str, Any]) -> str | None:
    for key in ("album_name", "artist_name", "track_name"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    params_summary = str(item.get("params_summary") or "")
    for part in params_summary.split(", "):
        if part.startswith(("album_name=", "artist_name=", "track_name=")):
            return part.split("=", 1)[1]
    return None


def _entity_type(item: dict[str, Any], data: dict[str, Any]) -> str | None:
    entity = data.get("entity")
    if isinstance(entity, str):
        return entity
    params_summary = str(item.get("params_summary") or "")
    for part in params_summary.split(", "):
        if part.startswith("entity="):
            return part.split("=", 1)[1]
    return None


def _entity_stats_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return None
    name = _entity_name(item, data)
    entity_type = _entity_type(item, data)
    metrics: list[EvidenceMetric] = []
    _append_metric(metrics, _metric("total_plays", "播放次数", summary.get("total_plays"), "plays"))
    _append_metric(metrics, _metric("total_hours", "播放时长", summary.get("total_hours"), "hours"))
    _append_metric(
        metrics, _metric("unique_tracks", "不同歌曲数", summary.get("unique_tracks"), "tracks")
    )
    return EvidenceCard(
        card_id=f"{entity_type or 'entity'}:{name or 'unknown'}:entity_stats",
        title=f"{name or '实体'} 播放统计",
        entity_name=name,
        entity_type=entity_type,
        question_axis="personal_playback",
        source=_source(item),
        metrics=metrics,
        limitations=["本地 Spotify 播放记录口径"],
    )


def _billboard_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    summary = data.get("chart_summary")
    if not isinstance(summary, dict):
        return None
    name = _entity_name(item, data)
    entity_type = _entity_type(item, data)
    metrics: list[EvidenceMetric] = []
    _append_metric(
        metrics, _metric("power_score", "个人榜单 Power Score", summary.get("power_score"))
    )
    _append_metric(metrics, _metric("power_rank", "个人榜单总排名", summary.get("power_rank")))
    _append_metric(metrics, _metric("peak_position", "最高排名", summary.get("peak_position")))
    _append_metric(
        metrics, _metric("weeks_on_chart", "在榜周数", summary.get("weeks_on_chart"), "weeks")
    )
    _append_metric(metrics, _metric("no1_weeks", "冠军周数", summary.get("no1_weeks"), "weeks"))
    return EvidenceCard(
        card_id=f"{entity_type or 'entity'}:{name or 'unknown'}:billboard",
        title=f"{name or '实体'} 个人榜单表现",
        entity_name=name,
        entity_type=entity_type,
        question_axis="personal_billboard",
        source=_source(item),
        metrics=metrics,
        limitations=["SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"],
    )


def build_evidence_cards(tool_results: list[dict[str, Any]]) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    for item in tool_results:
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        tool_name = item.get("tool_name")
        if tool_name == "entity_stats":
            card = _entity_stats_card(item, data)
        elif tool_name == "billboard_entity_detail":
            card = _billboard_card(item, data)
        else:
            card = None
        if card is not None:
            cards.append(card)
    return cards
