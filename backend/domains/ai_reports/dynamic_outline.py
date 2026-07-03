"""Dynamic outline planning for visual yearly report artifacts."""

from __future__ import annotations

from typing import Any


def plan_visual_yearly_outline(context: dict[str, Any]) -> list[dict[str, str]]:
    """Select report section roles from deterministic chart signals."""
    chart_data = _dict(context.get("chart_data"))
    sections: list[dict[str, str]] = [
        {"role": "opening", "reason": "年度报告需要先建立时间范围和总氛围。"},
        {"role": "main_artist", "reason": "最高播放艺人构成年度稳定中心。"},
    ]

    if _has_observations(chart_data, "artist_monthly_trend"):
        sections.append({"role": "turning_point", "reason": "月度趋势出现明确转折。"})
    else:
        sections.append({"role": "second_thread", "reason": "第二艺人构成补充线索。"})

    if _album_relation(chart_data) == "divergent":
        sections.append(
            {
                "role": "billboard_divergence",
                "reason": "播放榜和个人 Billboard 讲出不同偏好。",
            }
        )
    else:
        sections.append(
            {
                "role": "album_story",
                "reason": "播放和个人 Billboard 可共同解释专辑偏好。",
            }
        )

    sections.append({"role": "highlight_day", "reason": "最高播放日提供年度节奏截面。"})

    if _has_new_artists(chart_data):
        sections.append({"role": "discovery", "reason": "新艺人形成年度新入口。"})

    sections.append({"role": "closing", "reason": "收束陪伴、长留和新发现。"})
    return sections[:8]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_observations(chart_data: dict[str, Any], key: str) -> bool:
    payload = _dict(chart_data.get(key))
    observations = payload.get("observations")
    return isinstance(observations, list) and any(
        isinstance(item, str) and item.strip() for item in observations
    )


def _album_relation(chart_data: dict[str, Any]) -> str:
    payload = _dict(chart_data.get("album_duality_compare"))
    return str(payload.get("relation") or "")


def _has_new_artists(chart_data: dict[str, Any]) -> bool:
    payload = _dict(chart_data.get("discovery_timeline"))
    new_artists = payload.get("new_artists")
    return isinstance(new_artists, list) and bool(new_artists)
