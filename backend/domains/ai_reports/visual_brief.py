"""Visual chart planning for visual yearly report artifacts."""

from __future__ import annotations

from typing import Any

from backend.domains.ai_reports.dynamic_outline import plan_visual_yearly_outline


def build_visual_brief(
    narrative_brief: dict[str, Any],
    coverage: dict[str, bool],
    *,
    chart_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    is_partial_year = bool(narrative_brief.get("is_partial_year"))
    lead = _thread_entity(narrative_brief, "companionship_thread")
    second = _thread_entity(narrative_brief, "second_thread")
    discovery = _thread_entity(narrative_brief, "discovery_thread")
    entities = tuple(entity for entity in (lead, second) if entity)
    specs: list[dict[str, Any]] = []

    def add(
        chart_id: str,
        chart_type: str,
        title: str,
        question: str,
        chart_entities: tuple[str, ...],
        insight: str,
        fallback: str,
    ) -> None:
        if coverage.get(chart_id):
            specs.append(
                {
                    "id": chart_id,
                    "chart_type": chart_type,
                    "title": title,
                    "narrative_question": question,
                    "entities": list(chart_entities),
                    "data_key": chart_id,
                    "insight": insight,
                    "fallback": fallback,
                }
            )

    add(
        "listening_calendar",
        "listening_calendar_heatmap",
        "音乐铺满当前统计期" if is_partial_year else "音乐铺满这一年",
        "音乐是否几乎每天都在场？",
        (),
        "用每日播放强度展示当前统计期的陪伴密度。"
        if is_partial_year
        else "用每日播放强度展示全年陪伴密度。",
        "数据不足时展示活跃日数字卡。",
    )
    add(
        "artist_monthly_trend",
        "artist_monthly_trend",
        f"{lead} 与 {second} 的阶段声音线索"
        if is_partial_year and second
        else f"{lead} 的阶段声音线索"
        if is_partial_year
        else f"{lead} 与 {second} 的年度声音线索"
        if second
        else f"{lead} 的年度声音线索",
        "核心声音是否贯穿当前统计期？" if is_partial_year else "核心声音是否贯穿全年？",
        entities,
        "展示稳定陪伴与第二情绪线的月度变化。",
        "月度数据不足时展示艺人阶段对照卡。"
        if is_partial_year
        else "月度数据不足时展示艺人年度对照卡。",
    )
    add(
        "album_duality_compare",
        "album_duality_compare",
        "专辑热度与长留关系",
        "播放量和个人榜单讲的是同一种喜欢吗？",
        (),
        "解释播放领先专辑和个人榜单领先专辑的关系。",
        "缺少个人榜单时隐藏该图表。",
    )
    add(
        "highlight_day_timeline",
        "highlight_day_timeline",
        "阶段高光日拆解" if is_partial_year else "年度高光日拆解",
        "最密集的一天是循环还是漫游？",
        (),
        "把最高播放日拆成小时节奏和曲目集中度。",
        "缺少小时数据时展示高光日摘要。",
    )
    add(
        "genre_language_mix",
        "genre_language_mix",
        "你的音乐地理",
        "今年的声音来自哪些语境？",
        (),
        "把流派标签翻译成音乐地理。",
        "缺少流派时隐藏该图表。",
    )
    add(
        "discovery_timeline",
        "discovery_timeline",
        f"{discovery} 出现以后" if discovery else "新发现时间线",
        "新声音是路过还是留下？",
        (discovery,) if discovery else (),
        "展示新艺人的首次出现和后续播放。",
        "缺少新艺人时隐藏该图表。",
    )
    add(
        "playback_billboard_matrix",
        "playback_billboard_matrix",
        "常听与长留",
        "哪些作品既常听又稳定？",
        (),
        "展示播放量强度和个人榜单稳定性的关系。",
        "缺少个人榜单时隐藏该图表。",
    )

    outline_chart_data = (
        chart_data if isinstance(chart_data, dict) else _dict(narrative_brief.get("chart_data"))
    )

    return {
        "visual_thesis": "这份年报用陪伴密度、核心声音、专辑差异、高光日和新发现来呈现。",
        "chart_specs": specs,
        "required_chart_ids": [chart["id"] for chart in specs[:4]],
        "optional_chart_ids": [chart["id"] for chart in specs[4:]],
        "fallback_level": None if len(specs) >= 4 else "reduced_visuals",
        "outline_sections": plan_visual_yearly_outline({"chart_data": outline_chart_data}),
        "chart_order_reasoning": [
            "先展示音乐如何铺满一年。",
            "再展示核心声音的时间变化。",
            "再解释专辑播放量和持续在榜的关系。",
            "最后用高光日、流派和新发现增加记忆点。",
        ],
    }


def _thread_entity(narrative_brief: dict[str, Any], key: str) -> str:
    thread = narrative_brief.get(key)
    return str(thread.get("entity") or "") if isinstance(thread, dict) else ""


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
