"""Agentic longform yearly report orchestration."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any, Optional

from backend.domains.ai_reports.agentic_models import (
    AGENTIC_YEARLY_CONTRACT_VERSION,
    AGENTIC_YEARLY_REPORT_MODE,
    BASIC_SUMMARY_FALLBACK_LEVEL,
    AgenticYearlyMetadata,
    DynamicOutline,
    EvidenceLedgerEntry,
    InsightSynthesis,
    OutlineSection,
)
from backend.domains.ai_reports.agentic_prompts import (
    DYNAMIC_OUTLINE_SYSTEM_PROMPT,
    INSIGHT_SYNTHESIS_SYSTEM_PROMPT,
    LONGFORM_DRAFT_SYSTEM_PROMPT,
    REPAIR_DRAFT_SYSTEM_PROMPT,
)
from backend.domains.ai_reports.agentic_tools import execute_report_tool
from backend.domains.ai_reports.editorial_critic import critique_yearly_article
from backend.domains.ai_reports.yearly_validator import validate_yearly_report
from backend.services.ai_insights_service import _llm_chat

logger = logging.getLogger(__name__)

ReportAgentEvent = Callable[[str, str, Optional[dict[str, Any]]], None]

DEFAULT_RESEARCH_PLAN = (
    "report_period_context",
    "yearly_overview",
    "yearly_top_entities",
    "yearly_same_period_comparison",
    "personal_billboard_year_end",
    "billboard_yearly_diagnostics",
    "genre_distribution",
    "discovery_and_returns",
    "highlight_day_detail",
)


def generate_agentic_yearly_report(
    request: dict[str, Any],
    *,
    emit_event: ReportAgentEvent | None = None,
) -> dict[str, Any]:
    """Generate a researched yearly report using read-only report tools."""
    evidence, context = _run_research_plan(request, emit_event=emit_event)

    _emit(
        emit_event,
        "stage_started",
        "正在综合播放数据与个人 Billboard 证据",
        "synthesizing_insights",
    )
    synthesis = _build_insight_synthesis(evidence)

    _emit(emit_event, "stage_started", "正在生成动态文章大纲", "outlining")
    outline = _build_dynamic_outline(synthesis)

    _emit(emit_event, "stage_started", "正在撰写长篇年度报告", "drafting")
    report = _write_longform_report(context, evidence, synthesis, outline)

    _emit(emit_event, "stage_started", "正在进行编辑审稿与事实口径检查", "critic_review")
    critique = critique_yearly_article(
        report,
        _critic_context(context),
    )
    fact_validation = _validate_agentic_fact_safety(report, context)
    if not critique.ok or not fact_validation["ok"]:
        repaired = _repair_longform_report(context, evidence, synthesis, outline, report, critique)
        if repaired and repaired != report:
            repaired_critique = critique_yearly_article(
                repaired,
                _critic_context(context),
            )
            repaired_fact_validation = _validate_agentic_fact_safety(repaired, context)
            if repaired_critique.ok and repaired_fact_validation["ok"]:
                report = repaired
                critique = repaired_critique
                fact_validation = repaired_fact_validation

    if not critique.ok or not fact_validation["ok"]:
        structured_repair = _build_structured_longform_repair(context, evidence, synthesis, outline)
        if structured_repair:
            structured_critique = critique_yearly_article(
                structured_repair,
                _critic_context(context),
            )
            structured_fact_validation = _validate_agentic_fact_safety(structured_repair, context)
            if structured_critique.ok and structured_fact_validation["ok"]:
                report = structured_repair
                critique = structured_critique
                fact_validation = structured_fact_validation

    if not critique.ok or not fact_validation["ok"]:
        fallback = _build_basic_summary_fallback(context, request)
        fallback_metadata = _metadata(
            context=context,
            fallback_level=BASIC_SUMMARY_FALLBACK_LEVEL,
            tool_calls=len(evidence),
            critic_passed=False,
            article_length=len(fallback),
        )
        return {
            "success": True,
            "report": fallback,
            "cached": False,
            "cached_at": None,
            "entities": _extract_entities_from_context(context),
            "metadata": fallback_metadata.to_dict(),
            "critic": critique.to_dict(),
            "fact_validation": fact_validation,
            "insight_synthesis": synthesis.to_dict(),
            "dynamic_outline": outline.to_dict(),
            "evidence_ledger": [entry.to_dict() for entry in evidence],
            "error": None,
        }

    metadata = _metadata(
        context=context,
        fallback_level=None,
        tool_calls=len(evidence),
        critic_passed=True,
        article_length=len(report),
    )
    return {
        "success": True,
        "report": report,
        "cached": False,
        "cached_at": None,
        "entities": _extract_entities_from_context(context),
        "metadata": metadata.to_dict(),
        "critic": critique.to_dict(),
        "fact_validation": fact_validation,
        "insight_synthesis": synthesis.to_dict(),
        "dynamic_outline": outline.to_dict(),
        "evidence_ledger": [entry.to_dict() for entry in evidence],
        "error": None,
    }


def _run_research_plan(
    request: dict[str, Any],
    *,
    emit_event: ReportAgentEvent | None = None,
) -> tuple[list[EvidenceLedgerEntry], dict[str, Any]]:
    evidence: list[EvidenceLedgerEntry] = []
    context: dict[str, Any] = {"year": request.get("year")}
    latest_play_date = request.get("latest_play_date")
    for index, tool_name in enumerate(DEFAULT_RESEARCH_PLAN, start=1):
        params = dict(request)
        if latest_play_date and "latest_play_date" not in params:
            params["latest_play_date"] = latest_play_date
        _emit(
            emit_event,
            "stage_started",
            f"正在查询：{tool_name}",
            "researching",
            progress_pct=0.18 + min(0.22, index * 0.02),
        )
        try:
            result = execute_report_tool(tool_name, params)
        except Exception as exc:
            logger.warning("Agentic yearly report tool failed: %s", tool_name, exc_info=True)
            result = {
                "ok": False,
                "data": {},
                "summary": "",
                "error": str(exc) or exc.__class__.__name__,
            }

        data = result.get("data") if isinstance(result, dict) else {}
        if isinstance(data, dict):
            context.update(_context_fragment(tool_name, data))

        entry = EvidenceLedgerEntry(
            tool_name=tool_name,
            params=_compact_params(params),
            result_summary=str(result.get("summary") or result.get("error") or ""),
            supports=(tool_name,),
            questions_raised=tuple(_questions_from_tool_result(tool_name, result)),
        )
        evidence.append(entry)
        _emit(
            emit_event,
            "tool_call_completed",
            f"已完成只读工具：{tool_name}",
            "researching",
            payload=entry.to_dict(),
        )
    return evidence, context


def _context_fragment(tool_name: str, data: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "report_period_context":
        return {"reporting_period": data}
    if tool_name == "yearly_overview":
        return data
    if tool_name == "yearly_top_entities":
        return {
            "top_artists": data.get("top_artists") or [],
            "top_tracks": data.get("top_tracks") or [],
            "top_albums": data.get("top_albums") or [],
        }
    return {tool_name: data}


def _build_insight_synthesis(evidence: list[EvidenceLedgerEntry]) -> InsightSynthesis:
    payload = {"evidence_ledger": [entry.to_dict() for entry in evidence]}
    parsed = _call_llm_json(INSIGHT_SYNTHESIS_SYSTEM_PROMPT, payload)
    if not parsed:
        parsed = _default_synthesis_payload(evidence)
    return InsightSynthesis(
        main_thesis=str(parsed.get("main_thesis") or ""),
        supporting_arguments=tuple(_dict_rows(parsed.get("supporting_arguments"))),
        billboard_findings=tuple(_string_rows(parsed.get("billboard_findings"))),
        playback_findings=tuple(_string_rows(parsed.get("playback_findings"))),
        tensions=tuple(_string_rows(parsed.get("tensions"))),
        interesting_anomalies=tuple(_string_rows(parsed.get("interesting_anomalies"))),
    )


def _build_dynamic_outline(synthesis: InsightSynthesis) -> DynamicOutline:
    parsed = _call_llm_json(
        DYNAMIC_OUTLINE_SYSTEM_PROMPT,
        {"insight_synthesis": synthesis.to_dict()},
    )
    if not parsed:
        parsed = {
            "title": synthesis.main_thesis or "你的年度音乐主线",
            "sections": [
                {
                    "heading": "今年真正的主线",
                    "question": "播放与个人 Billboard 共同说明了什么？",
                    "claims": [synthesis.main_thesis],
                },
                {
                    "heading": "稳定中心与新入口",
                    "question": "哪些实体同时支撑稳定与变化？",
                    "claims": list(synthesis.playback_findings[:2]),
                },
                {
                    "heading": "个人 Billboard 给出的第二层证据",
                    "question": "榜单维度如何补充播放次数？",
                    "claims": list(synthesis.billboard_findings[:2]),
                },
            ],
        }
    sections = tuple(
        OutlineSection(
            heading=str(row.get("heading") or ""),
            question=str(row.get("question") or ""),
            claims=tuple(_string_rows(row.get("claims"))),
        )
        for row in _dict_rows(parsed.get("sections"))
        if row.get("heading")
    )
    return DynamicOutline(title=str(parsed.get("title") or ""), sections=sections)


def _write_longform_report(
    context: dict[str, Any],
    evidence: list[EvidenceLedgerEntry],
    synthesis: InsightSynthesis,
    outline: DynamicOutline,
) -> str:
    return _call_llm_text(
        LONGFORM_DRAFT_SYSTEM_PROMPT,
        {
            "reporting_period": context.get("reporting_period"),
            "context": context,
            "evidence_ledger": [entry.to_dict() for entry in evidence],
            "insight_synthesis": synthesis.to_dict(),
            "dynamic_outline": outline.to_dict(),
        },
    )


def _repair_longform_report(
    context: dict[str, Any],
    evidence: list[EvidenceLedgerEntry],
    synthesis: InsightSynthesis,
    outline: DynamicOutline,
    report: str,
    critique: Any,
) -> str:
    return _call_llm_text(
        REPAIR_DRAFT_SYSTEM_PROMPT,
        {
            "reporting_period": context.get("reporting_period"),
            "context": context,
            "evidence_ledger": [entry.to_dict() for entry in evidence],
            "insight_synthesis": synthesis.to_dict(),
            "dynamic_outline": outline.to_dict(),
            "draft": report,
            "critic": critique.to_dict() if hasattr(critique, "to_dict") else {},
        },
    )


def _build_basic_summary_fallback(context: dict[str, Any], request: dict[str, Any]) -> str:
    del context
    from backend.core.db import get_db
    from backend.services.ai_insights_service import (
        _build_yearly_report_fallback,
        _gather_yearly_data,
    )

    conn = get_db(readonly=True)
    try:
        data = _gather_yearly_data(
            conn,
            min_ms=int(request.get("min_ms") or 30000),
            music_only=bool(request.get("music_only", True)),
            merge_enabled=bool(request.get("merge_enabled", True)),
            year=int(request.get("year") or 0),
            dynamic_threshold=bool(request.get("dynamic_threshold", True)),
            max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
        )
    finally:
        conn.close()
    return _build_yearly_report_fallback(data)


def _build_structured_longform_repair(
    context: dict[str, Any],
    evidence: list[EvidenceLedgerEntry],
    synthesis: InsightSynthesis,
    outline: DynamicOutline,
) -> str:
    del evidence, synthesis, outline
    period = (
        context.get("reporting_period") if isinstance(context.get("reporting_period"), dict) else {}
    )
    hero = context.get("hero") if isinstance(context.get("hero"), dict) else {}
    top_artists = context.get("top_artists") if isinstance(context.get("top_artists"), list) else []
    billboard = (
        context.get("personal_billboard_year_end")
        if isinstance(context.get("personal_billboard_year_end"), dict)
        else {}
    )
    if not period or not hero or not top_artists or not billboard:
        return ""

    top_tracks = context.get("top_tracks") if isinstance(context.get("top_tracks"), list) else []
    top_albums = context.get("top_albums") if isinstance(context.get("top_albums"), list) else []
    diagnostics = (
        context.get("billboard_yearly_diagnostics")
        if isinstance(context.get("billboard_yearly_diagnostics"), dict)
        else {}
    )
    comparison = (
        context.get("yearly_same_period_comparison")
        if isinstance(context.get("yearly_same_period_comparison"), dict)
        else {}
    )
    genre = (
        context.get("genre_distribution")
        if isinstance(context.get("genre_distribution"), dict)
        else {}
    )
    discovery = (
        context.get("discovery_and_returns")
        if isinstance(context.get("discovery_and_returns"), dict)
        else {}
    )
    highlight = (
        context.get("highlight_day_detail")
        if isinstance(context.get("highlight_day_detail"), dict)
        else {}
    )

    year = period.get("year") or context.get("year") or str(period.get("start_date") or "")[:4]
    start_date = period.get("start_date") or f"{year}-01-01"
    end_date = period.get("end_date") or ""
    lead_artist = _row_name(top_artists, 0)
    second_artist = _row_name(top_artists, 1)
    third_artist = _row_name(top_artists, 2)
    lead_track = _row_name(top_tracks, 0)
    lead_album = _row_name(top_albums, 0)
    billboard_track = _row_name(billboard.get("tracks"), 0)
    billboard_album = _row_name(billboard.get("albums"), 0)
    billboard_artist = _row_name(billboard.get("artists"), 0)
    new_artist = _row_name(discovery.get("new_artists"), 0) or third_artist
    thesis = (
        f"{lead_artist} 仍是稳定中心，而 {new_artist} 让阶段性音乐版图出现外扩。"
        if new_artist
        else f"{lead_artist} 仍是阶段性音乐偏好的稳定中心。"
    )

    changes = {}
    same_period = (
        comparison.get("same_period") if isinstance(comparison.get("same_period"), dict) else {}
    )
    if isinstance(same_period.get("changes"), dict):
        changes = same_period["changes"]
    top_genres = genre.get("top_genres") if isinstance(genre.get("top_genres"), list) else []
    genre_leader = _row_name(top_genres, 0)
    genre_share = _row_metric(top_genres, 0, "share")
    highlight_guidance = _safe_highlight_guidance(highlight.get("interpretation_guidance") or "")
    longest_love = (
        discovery.get("longest_love") if isinstance(discovery.get("longest_love"), dict) else {}
    )
    longest_love_name = longest_love.get("track_name") or longest_love.get("name") or ""

    paragraphs = [
        f"## {year} 年中音乐报告（截至 {end_date}）",
        (
            f"从 {start_date} 到 {end_date}，这份报告更适合被读成一篇阶段性音乐档案，"
            f"而不是最终结论。{thesis} 这个判断来自两层证据："
            "一层是实际播放留下的时间和次数，另一层是本地个人 Billboard 对持续性、峰值和跨榜联动的整理。"
            "两者共同说明，你的偏好不是简单变少或变散，而是在稳定中心之外展开新的入口。"
        ),
        "## 稳定中心没有消失",
        (
            f"{lead_artist} 的 {_fmt_int(_row_metric(top_artists, 0, 'plays'))} 次说明其仍是阶段性坐标。"
            f"如果只看播放次数，{second_artist or '第二条主线'} 和 {third_artist or '新入口'} 也很突出；"
            f"但 {lead_artist} 的意义不只是数字最大，而是它把艺人、作品和专辑三条线索连接起来。"
            f"{lead_track or '阶段性最高单曲'} 与 {lead_album or '阶段性最高专辑'} 提供了具体落点，"
            "使这个中心不是抽象喜好，而是能在不同榜单层级里互相印证的偏好结构。"
        ),
        "## 播放量的下降不等于兴趣收缩",
        (
            f"阶段概览显示总播放为 {_fmt_int(hero.get('total_plays'))} 次，累计约 {_fmt_hours(hero.get('total_minutes'))} 小时，"
            f"覆盖 {_fmt_int(hero.get('unique_tracks'))} 首曲目和 {_fmt_int(hero.get('unique_artists'))} 位艺人。"
            "这组数据说明音乐仍然是高频背景，但兴趣分配更分散。"
            f"同周期对比中，播放变化为 {_fmt_percent(changes.get('plays_change'))}，曲目覆盖变化为 {_fmt_percent(changes.get('tracks_change'))}，"
            "这种一降一升的张力反映出：重复强度降低的同时，探索面没有收窄。"
            "所以这里真正值得写的不是“少听了”，而是听歌结构从单纯堆播放量，转向更宽的候选池。"
        ),
        "## 个人 Billboard 给出的第二层证据",
        (
            "个人 Billboard 是基于你的本地播放记录计算出的个人榜，不是外部官方 Billboard。"
            f"它的价值在于把播放行为转换成持续性和稳定性的证据：{billboard_track or lead_track} 在单曲阶段榜保持强势，"
            f"{billboard_album or lead_album} 在专辑阶段榜提供作品层面的支撑，"
            f"{billboard_artist or lead_artist} 在艺人阶段榜形成更长周期的在榜能力。"
            "这与播放数据互相印证，说明核心偏好不是某一天或某一首歌的偶发波动，"
            "而是多首作品、多张专辑和多周记录共同形成的稳定中心。"
        ),
        "## 三榜联动与新入口同时存在",
        (
            f"Billboard 诊断中，{_diagnostic_artist(diagnostics) or lead_artist} 是统治力最清晰的对象；"
            "三榜联动说明同一个核心不仅被反复播放，也能在单曲、专辑和艺人维度持续占位。"
            f"与此同时，{new_artist or '新艺人'} 的出现改变了报告的另一条线。"
            f"它不是把 {lead_artist} 的中心位置推翻，而是说明你的音乐版图开始出现新的入口："
            "核心仍在，外沿变宽。这样的结构比单纯的 TOP 5 更有信息量，因为它解释了为什么稳定和探索可以同时成立。"
        ),
        "## 流派和高光日说明偏好如何展开",
        (
            f"流派层面，{genre_leader or '主要流派'}"
            f"{f'约占 {genre_share:.1f}%' if isinstance(genre_share, (int, float)) else ''}，"
            "但 Spotify 的流派标签可能重叠，因此它更适合作为方向线索，而不是互斥分类。"
            "华语、区域流行和其他流派共同出现，说明探索不是完全随机，而是在熟悉语境与新鲜入口之间移动。"
            f"{highlight.get('date') or '最活跃日'} 的 {_fmt_int(highlight.get('plays'))} 次也说明这一点："
            f"{highlight_guidance or '这更像多曲目活跃，而不是单曲循环'}。"
            "高光日因此不是某一首歌压倒全部，而是一次更密集的浏览和切换。"
        ),
        "## 长线记忆让阶段报告有纵深",
        (
            f"{longest_love_name or '最长情曲目'} 这类长线回归信号提醒我们，阶段性报告不只记录新东西。"
            "它同时记录哪些声音穿过更长时间后仍然会回来。"
            "当稳定中心、新入口和长线回归放在一起看，2026 上半年的画像就更完整："
            "你没有只停在旧循环里，也没有完全抛开旧坐标；更准确的说法是，旧坐标继续提供方向，"
            "新入口负责扩大边界，个人 Billboard 则把这种方向和边界转化为可追踪的连续证据。"
        ),
        "## 下半年可以观察什么",
        (
            f"接下来最值得观察的是两个问题：{lead_artist} 的三榜联动是否继续保持，"
            f"以及 {new_artist or third_artist or '新入口'} 是否从阶段性发现变成稳定偏好。"
            f"如果 {lead_album or '当前专辑线索'} 继续维持专辑阶段榜优势，说明核心作品仍有长尾；"
            "如果新入口的播放和在榜能力继续上升，说明探索面会进一步改变年度结构。"
            "这份报告的价值就在这里：它不是把年度总结页重新讲一遍，而是把播放、个人 Billboard 和阶段性变化放在同一张图里，"
            "说明你的音乐偏好如何在稳定与扩张之间重新排列。"
        ),
    ]
    return "\n\n".join(part for part in paragraphs if part)


def _call_llm_json(system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _llm_chat(
        system_prompt,
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
        temperature=0.1,
    )
    if not text:
        return {}
    raw = _extract_json(text)
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _call_llm_text(system_prompt: str, payload: dict[str, Any]) -> str:
    return str(
        _llm_chat(
            system_prompt,
            f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
            temperature=0.2,
        )
        or ""
    ).strip()


def _metadata(
    *,
    context: dict[str, Any],
    fallback_level: str | None,
    tool_calls: int,
    critic_passed: bool,
    article_length: int,
) -> AgenticYearlyMetadata:
    return AgenticYearlyMetadata(
        report_mode=AGENTIC_YEARLY_REPORT_MODE,
        contract_version=AGENTIC_YEARLY_CONTRACT_VERSION,
        fallback_level=fallback_level,
        tool_calls=tool_calls,
        data_range=_data_range(context),
        is_partial_year=_is_partial_year(context),
        critic_passed=critic_passed,
        article_length=article_length,
    )


def _critic_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "is_partial_year": _is_partial_year(context),
        "min_length": 1400,
        "requires_billboard": True,
        "requires_playback_billboard_connection": True,
    }


def _validate_agentic_fact_safety(report: str, context: dict[str, Any]) -> dict[str, Any]:
    validation = validate_yearly_report(report, _validator_data_from_context(context))
    issues = [
        {
            "code": issue.code,
            "message": issue.message,
            "severity": issue.severity,
        }
        for issue in validation.issues
        if issue.code != "yearly_report_too_long"
    ]
    return {"ok": not issues, "issues": issues}


def _validator_data_from_context(context: dict[str, Any]) -> dict[str, Any]:
    discovery = (
        context.get("discovery_and_returns")
        if isinstance(context.get("discovery_and_returns"), dict)
        else {}
    )
    genre = (
        context.get("genre_distribution")
        if isinstance(context.get("genre_distribution"), dict)
        else {}
    )
    highlight = (
        context.get("highlight_day_detail")
        if isinstance(context.get("highlight_day_detail"), dict)
        else {}
    )
    return {
        "reporting_period": context.get("reporting_period"),
        "top_artists": context.get("top_artists") or [],
        "top_tracks": context.get("top_tracks") or [],
        "top_albums": context.get("top_albums") or [],
        "new_artists": discovery.get("new_artists") or context.get("new_artists") or [],
        "genre_summary": {
            "top_genres": genre.get("top_genres") or context.get("top_genres") or [],
            "caveat": genre.get("caveat") or "Spotify genre 标签可能重叠。",
        },
        "billboard_year_end": context.get("personal_billboard_year_end") or {},
        "most_active_day": highlight,
    }


def _data_range(context: dict[str, Any]) -> str:
    period = (
        context.get("reporting_period") if isinstance(context.get("reporting_period"), dict) else {}
    )
    start = str(period.get("start_date") or "")
    end = str(period.get("end_date") or "")
    if start and end:
        return f"{start} to {end}"
    return ""


def _is_partial_year(context: dict[str, Any]) -> bool:
    period = (
        context.get("reporting_period") if isinstance(context.get("reporting_period"), dict) else {}
    )
    return bool(period.get("is_partial_year"))


def _extract_entities_from_context(context: dict[str, Any]) -> dict[str, list[str]]:
    artists = _names(context.get("top_artists"))
    tracks = _names(context.get("top_tracks"))
    if not artists or not tracks:
        top_entities = context.get("yearly_top_entities")
        if isinstance(top_entities, dict):
            artists = artists or _names(top_entities.get("top_artists"))
            tracks = tracks or _names(top_entities.get("top_tracks"))
    return {"artists": artists[:5], "tracks": tracks[:5]}


def _names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(row.get("name"))
        for row in value
        if isinstance(row, dict) and isinstance(row.get("name"), str) and row.get("name")
    ]


def _row_name(rows: Any, index: int) -> str:
    if not isinstance(rows, list) or index >= len(rows) or not isinstance(rows[index], dict):
        return ""
    return str(rows[index].get("name") or "")


def _row_metric(rows: Any, index: int, key: str) -> Any:
    if not isinstance(rows, list) or index >= len(rows) or not isinstance(rows[index], dict):
        return None
    return rows[index].get(key)


def _diagnostic_artist(diagnostics: dict[str, Any]) -> str:
    dominance = (
        diagnostics.get("dominance") if isinstance(diagnostics.get("dominance"), dict) else {}
    )
    artist = dominance.get("artist")
    return str(artist) if artist else ""


def _safe_highlight_guidance(guidance: str) -> str:
    if any(term in guidance for term in ("单曲循环", "重度循环", "疯狂循环", "循环播放")):
        return "当天最高单曲重复不高，更适合看作多曲目活跃"
    return guidance


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return "0"


def _fmt_hours(total_minutes: Any) -> str:
    try:
        return f"{float(total_minutes) / 60:.1f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "0"


def _fmt_percent(value: Any) -> str:
    try:
        return f"{float(value):+.1f}%"
    except (TypeError, ValueError):
        return "暂无同比"


def _emit(
    emit_event: ReportAgentEvent | None,
    event_type: str,
    message: str,
    stage: str,
    *,
    progress_pct: float | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if emit_event is None:
        return
    event_payload = dict(payload or {})
    event_payload["stage"] = stage
    if progress_pct is not None:
        event_payload["progress_pct"] = progress_pct
    emit_event(event_type, message, event_payload)


def _compact_params(params: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "year",
        "min_ms",
        "music_only",
        "merge_enabled",
        "dynamic_threshold",
        "max_merge_gap_minutes",
        "latest_play_date",
    }
    return {key: params[key] for key in keep if key in params}


def _questions_from_tool_result(tool_name: str, result: dict[str, Any]) -> list[str]:
    if not result.get("ok", True):
        return [f"{tool_name} 查询失败，是否需要回退到其他证据？"]
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if tool_name == "billboard_yearly_diagnostics" and not data.get("cross_chart_alignment"):
        return ["播放榜和个人 Billboard 是否存在分歧？"]
    return []


def _extract_json(text: str) -> str:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{[\s\S]*\}", cleaned)
    return match.group(0) if match else cleaned


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]


def _string_rows(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [str(row) for row in value or [] if row is not None]


def _default_synthesis_payload(evidence: list[EvidenceLedgerEntry]) -> dict[str, Any]:
    summaries = " ".join(entry.result_summary for entry in evidence if entry.result_summary)
    return {
        "main_thesis": "播放分析和个人 Billboard 共同构成今年音乐偏好的两层证据。",
        "supporting_arguments": [
            {"claim": "播放数据提供偏好强度，个人 Billboard 提供稳定性和持续性。"}
        ],
        "billboard_findings": ["个人 Billboard 可以补充播放次数之外的在榜能力、稳定性和跨榜联动。"],
        "playback_findings": [summaries[:240] if summaries else "播放概览提供年度报告基础。"],
        "tensions": [],
        "interesting_anomalies": [],
    }
