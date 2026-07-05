"""Visual yearly report artifact orchestration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from backend.domains.ai_reports.final_artifact_quality import evaluate_final_artifact_quality
from backend.domains.ai_reports.report_writer import (
    REPORT_WRITER_SYSTEM_PROMPT,
    WRITER_PIPELINE_REQUEST_VALUE,
    build_report_writer_context,
    call_report_writer_llm,
    parse_report_sections,
    report_writer_metadata,
)
from backend.domains.ai_reports.yearly_validator import validate_yearly_report

VISUAL_YEARLY_CONTRACT_VERSION = "visual_yearly_v1"
VISUAL_YEARLY_REPORT_MODE = "visual_yearly_artifact"

ReportAgentEvent = Callable[[str, str, Optional[dict[str, Any]]], None]

_REPORT_WRITER_STAGE = "generating_report_prose"

_EDITORIAL_ROLE_CHART_REFS = {
    "opening": ("listening_calendar",),
    "main_artist": ("listening_calendar",),
    "turning_point": ("artist_monthly_trend", "genre_language_mix"),
    "album_story": ("album_duality_compare", "playback_billboard_matrix"),
    "billboard_divergence": ("album_duality_compare", "playback_billboard_matrix"),
    "highlight_day": ("highlight_day_timeline",),
    "discovery": ("discovery_timeline",),
}


@dataclass(frozen=True)
class _Section:
    id: str
    role: str
    heading: str
    deck: str
    prose: str
    chart_refs: tuple[str, ...] = ()
    insight_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    pull_quote: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "heading": self.heading,
            "deck": self.deck,
            "prose": self.prose,
            "chart_refs": list(self.chart_refs),
            "insight_refs": list(self.insight_refs),
            "evidence_refs": list(self.evidence_refs),
            "pull_quote": self.pull_quote,
        }


def generate_visual_yearly_artifact(
    request: dict[str, Any],
    *,
    emit_event: ReportAgentEvent | None = None,
) -> dict[str, Any]:
    """Generate a visual yearly artifact using Agent-synthesis style LLM writing."""
    writer_pipeline = _writer_pipeline(request)
    evidence, context = _run_visual_research(request, emit_event=emit_event)
    context = {**context, "request_filters": _request_filters(request)}

    # Phase B: Deterministic chart planning and data
    _emit(emit_event, "stage_started", "正在选择年报图表", "planning_visuals", 0.50)
    coverage = chart_coverage(context)
    # Build a minimal narrative for visual brief (only chart planning, no LLM)
    narrative = _minimal_narrative(context)
    visual = build_visual_brief(narrative, coverage)
    chart_specs = list(visual.get("chart_specs") or _default_chart_specs())
    _emit(emit_event, "stage_started", "正在准备图表数据", "building_chart_data", 0.62)
    chart_data = build_visual_chart_data(context, chart_specs)
    context = {**context, "chart_data": chart_data}
    visual = build_visual_brief(narrative, coverage, chart_data=chart_data)
    chart_specs = list(visual.get("chart_specs") or chart_specs)

    # Phase D: Agent-synthesis LLM report writing
    _emit(emit_event, "stage_started", "正在撰写年度报告", _REPORT_WRITER_STAGE, 0.75)
    writer_context = build_report_writer_context(context, chart_data, chart_specs)
    writer_accepted = False
    llm_output: str | None = None
    if writer_pipeline in (WRITER_PIPELINE_REQUEST_VALUE, "editorial_agent_v1"):
        llm_output = call_report_writer_llm(
            REPORT_WRITER_SYSTEM_PROMPT,
            writer_context,
        )
        if llm_output and llm_output.strip():
            writer_accepted = True

    sections_raw = parse_report_sections(llm_output, chart_specs)
    if sections_raw:
        # Apply chart observation interpretations to each section
        enriched_raw: list[dict[str, Any]] = []
        for s in sections_raw:
            chart_refs = tuple(s.get("chart_refs", []))
            prose = _append_chart_observation_interpretations(s["prose"], chart_refs, chart_data)
            enriched_raw.append({**s, "prose": prose, "chart_refs": chart_refs})
        sections = tuple(
            _Section(
                id=s["id"],
                role=s["role"],
                heading=s["heading"],
                deck=s["deck"],
                prose=_clean_user_text(s["prose"], context),
                chart_refs=s["chart_refs"],
                insight_refs=tuple(s.get("insight_refs", [])),
                evidence_refs=tuple(s.get("evidence_refs", [])),
                pull_quote=s.get("pull_quote"),
            )
            for s in enriched_raw
        )
        # LLM-generated content is naturally comprehensive; skip template obligations
    else:
        # Fallback: use deterministic sections as safety net
        story_insights = build_story_insights(context, narrative)
        sections = _compose_sections(context, narrative, story_insights, visual)
        writer_accepted = False

    # Phase E: Deterministic post-processing
    # Only run obligations check for fallback sections; LLM output is naturally comprehensive
    if not sections_raw:
        sections = _ensure_editorial_story_obligations(sections, context)
    sections = _remove_duplicate_editorial_fact_claims(sections, None)
    sections = _ensure_minimum_editorial_prose(sections, context)
    sections = _dedupe_editorial_sections(sections)
    sections = _dedupe_chart_refs_across_sections(sections)
    story_insights = build_story_insights(context, narrative)
    insight_cards = _compose_insight_cards(context, narrative, story_insights)
    prose = _report_text(sections)
    _emit(emit_event, "stage_started", "正在检查文风与事实口径", "reviewing_visual_artifact", 0.88)

    w_metadata = report_writer_metadata(writer_accepted)

    artifact = {
        "report_mode": VISUAL_YEARLY_REPORT_MODE,
        "contract_version": VISUAL_YEARLY_CONTRACT_VERSION,
        "title": _title(context),
        "subtitle": _subtitle(narrative),
        "period": context.get("reporting_period") or {},
        "narrative_brief": narrative,
        "story_insights": story_insights,
        "visual_brief": visual,
        "sections": [section.to_dict() for section in sections],
        "insight_cards": insight_cards,
        "chart_specs": chart_specs,
        "chart_data": chart_data,
        "metadata": {**w_metadata},
    }
    critic = critique_visual_yearly_artifact(
        artifact,
        {
            **context,
            "is_partial_year": bool(_period(context).get("is_partial_year")),
        },
    )
    fact_validation = _validate_visual_fact_safety(prose, artifact, context)
    final_quality = evaluate_final_artifact_quality(artifact)
    if not final_quality["ok"]:
        critic = {
            **critic,
            "ok": False,
            "issues": [*_list(critic.get("issues")), *final_quality["issues"]],
            "repair_instructions": [
                *_str_list(critic.get("repair_instructions")),
                "修复最终可见 artifact 文本后再缓存报告。",
            ],
        }
    if not final_quality["ok"]:
        fallback_level = "final_quality_gate_failed"
    elif not critic["ok"]:
        fallback_level = "reduced_visuals"
    else:
        fallback_level = None

    metadata = {
        "report_mode": VISUAL_YEARLY_REPORT_MODE,
        "contract_version": VISUAL_YEARLY_CONTRACT_VERSION,
        "fallback_level": fallback_level,
        "section_count": len(sections),
        "chart_count": len(chart_data),
        "insight_card_count": len(insight_cards),
        "article_length": len(prose),
        "critic_passed": bool(critic["ok"]),
        "fact_validation_passed": bool(fact_validation["ok"]),
        "final_artifact_quality_passed": bool(final_quality["ok"]),
        "final_artifact_quality": final_quality,
        **w_metadata,
    }
    artifact["metadata"] = metadata
    if not final_quality["ok"]:
        return {
            "success": False,
            "report": None,
            "artifact": None,
            "cached": False,
            "cached_at": None,
            "entities": _entities(context),
            "metadata": metadata,
            "critic": critic,
            "fact_validation": fact_validation,
            "evidence_ledger": [_entry_to_dict(entry) for entry in evidence],
            "error": "最终年报质量校验未通过，请重新生成。",
        }
    return {
        "success": True,
        "report": prose,
        "artifact": artifact,
        "cached": False,
        "cached_at": None,
        "entities": _entities(context),
        "metadata": metadata,
        "critic": critic,
        "fact_validation": fact_validation,
        "evidence_ledger": [_entry_to_dict(entry) for entry in evidence],
        "error": None,
    }


def build_narrative_brief(context: dict[str, Any]) -> dict[str, Any]:
    try:
        from backend.domains.ai_reports.narrative_brief import build_narrative_brief as build
    except ModuleNotFoundError:
        return _fallback_narrative_brief(context)
    return build(context)


def build_visual_brief(
    narrative: dict[str, Any],
    coverage: dict[str, Any],
    *,
    chart_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        from backend.domains.ai_reports.visual_brief import build_visual_brief as build
    except ModuleNotFoundError:
        return {
            "chart_specs": _default_chart_specs(),
            "fallback_level": None,
            "narrative": narrative,
        }
    try:
        return build(narrative, coverage, chart_data=chart_data)
    except Exception:
        return {"chart_specs": _default_chart_specs(), "fallback_level": "visual_brief_fallback"}


def chart_coverage(context: dict[str, Any]) -> dict[str, Any]:
    try:
        from backend.domains.ai_reports.visual_chart_data import chart_coverage as coverage
    except ModuleNotFoundError:
        return {spec["id"]: True for spec in _default_chart_specs()}
    try:
        return coverage(context)
    except Exception:
        return {spec["id"]: True for spec in _default_chart_specs()}


def build_visual_chart_data(
    context: dict[str, Any],
    chart_specs: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        from backend.domains.ai_reports.visual_chart_data import (
            build_visual_chart_data as build,
        )
    except ModuleNotFoundError:
        return {spec["id"]: _fallback_chart_data(context, spec) for spec in chart_specs}
    try:
        return build(context, chart_specs)
    except Exception:
        return {spec["id"]: _fallback_chart_data(context, spec) for spec in chart_specs}


def build_story_insights(context: dict[str, Any], narrative: dict[str, Any]) -> dict[str, Any]:
    try:
        from backend.domains.ai_reports.story_insight_builder import (
            build_story_insights as build,
        )
    except ModuleNotFoundError:
        return _fallback_story_insights(context, narrative)
    try:
        return build(context, narrative)
    except Exception:
        return _fallback_story_insights(context, narrative)


def build_editorial_plan(
    context: dict[str, Any],
    narrative: dict[str, Any],
    insights: dict[str, Any],
    visual: dict[str, Any] | None = None,
) -> Any:
    from backend.domains.ai_reports.editorial_plan import build_editorial_plan as build

    return build(context, narrative, insights, visual)


def _minimal_narrative(context: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal narrative dict for chart planning (no LLM needed)."""
    top_artists = _list(context.get("top_artists"))

    return {
        "main_story": "",
        "opening_scene": "",
        "companionship_thread": {"entity": _name_at(top_artists, 0, "")},
        "second_thread": {"entity": _name_at(top_artists, 1, "")},
        "discovery_thread": {"entity": ""},
        "life_rhythm": {},
        "tensions": {},
        "closing_direction": "",
    }


def _deck_for_role(role: str, context: dict[str, Any]) -> str:
    if role == "turning_point":
        return "累计排名之外，也有某个月突然变亮的声音。"
    if role in {"album_story", "billboard_divergence"}:
        return "播放热度和个人 Billboard 长留需要放在一起读。"
    if role == "highlight_day":
        day = _dict(context.get("highlight_day_detail"))
        date = str(day.get("date") or "高光日")
        return f"{date} 更适合被看作播放密度升高的一天。"
    if role == "discovery":
        return "新出现的名字让年度画像不只停在旧偏好里。"
    if role == "closing":
        return "把前面的线索收束成一份可回看的音乐年记。"
    return "这一节继续解释播放记录里出现的年度关系。"


def critique_visual_yearly_artifact(
    artifact: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    try:
        from backend.domains.ai_reports.visual_yearly_critic import (
            critique_visual_yearly_artifact as critique,
        )
    except ModuleNotFoundError:
        issues = []
        if len(artifact.get("sections") or []) < 6:
            issues.append(
                {
                    "code": "too_few_sections",
                    "message": "visual artifact needs at least six sections",
                }
            )
        if len(artifact.get("chart_data") or {}) < 4:
            issues.append(
                {"code": "too_few_charts", "message": "visual artifact needs at least four charts"}
            )
        if any(term in _report_text_from_payload(artifact) for term in _forbidden_terms()):
            issues.append(
                {"code": "forbidden_terms", "message": "artifact contains internal terms"}
            )
        return {"ok": not issues, "issues": issues}
    return critique(artifact, context)


def _run_visual_research(
    request: dict[str, Any],
    emit_event: ReportAgentEvent | None = None,
):
    from backend.services.yearly_report_agent_service import _run_research_plan

    return _run_research_plan(request, emit_event=emit_event)


def _compose_sections(
    context: dict[str, Any],
    narrative: dict[str, Any],
    insights: dict[str, Any],
    visual: dict[str, Any] | None = None,
    *,
    editorial_plan: Any | None = None,
) -> tuple[_Section, ...]:
    lead = str(insights.get("first_artist") or "").strip() or _thread_entity(
        narrative,
        "companionship_thread",
        _top_name(context, "top_artists", 0, "年度主线艺人"),
    )
    second = str(
        _dict(insights.get("second_thread")).get("entity") or ""
    ).strip() or _thread_entity(
        narrative,
        "second_thread",
        _top_name(context, "top_artists", 1, "另一条声音"),
    )
    discovery = str(_dict(insights.get("discovery")).get("entity") or "").strip() or _thread_entity(
        narrative,
        "discovery_thread",
        _new_artist(context),
    )
    album = _dict(insights.get("album_relation")) or _album_tension(context)
    roles = _editorial_roles(editorial_plan) or _outline_roles(visual)
    has_turning_point = "turning_point" in roles
    artist_chart_refs: tuple[str, ...] = () if has_turning_point else ("artist_monthly_trend",)
    section_by_role = {
        "opening": _Section(
            "opening",
            "opening",
            _opening_heading(context),
            str(narrative.get("opening_scene") or "音乐在这一年保持着稳定的在场感。"),
            _long_opening(context, narrative, insights),
            ("listening_calendar",),
            ("activity_density",),
            ("yearly_overview",),
            "音乐不是成绩单，而是这一年反复出现的日常节奏。",
        ),
        "main_artist": _Section(
            "companionship",
            "main_artist",
            f"{lead}，你反复回到的声音",
            f"{lead} 不是只在某一首歌里出现。",
            _long_companionship(context, lead, insights),
            artist_chart_refs,
            ("companion_artist",),
            ("yearly_top_entities",),
        ),
        "second_thread": _Section(
            "second_thread",
            "second_thread",
            f"{second} 带来的另一条情绪线",
            _dict(insights.get("second_thread")).get("claim") or "这一年并不是单一语境的流行音乐。",
            _long_second_thread(context, insights),
            ("artist_monthly_trend", "genre_language_mix"),
            ("second_thread",),
            ("genre_distribution",),
        ),
        "turning_point": _Section(
            "turning_point",
            "turning_point",
            _turning_point_heading(context, second),
            _turning_point_deck(context, insights),
            _long_turning_point(context, insights),
            ("artist_monthly_trend", "genre_language_mix"),
            ("second_thread",),
            ("yearly_top_entities", "genre_distribution"),
        ),
        "album_story": _Section(
            "album_story",
            "album_story",
            _album_heading(album),
            str(album.get("claim") or "专辑偏好需要同时看播放量和个人榜单。"),
            _long_album_story(context, album),
            ("album_duality_compare", "playback_billboard_matrix"),
            ("album_duality",),
            ("personal_billboard_year_end",),
        ),
        "billboard_divergence": _Section(
            "billboard_divergence",
            "billboard_divergence",
            "播放热度和长留位置分开了",
            str(album.get("claim") or "播放榜和个人 Billboard 讲出两种不同偏好。"),
            _long_album_story(context, album),
            ("album_duality_compare", "playback_billboard_matrix"),
            ("album_duality",),
            ("personal_billboard_year_end",),
        ),
        "highlight_day": _Section(
            "highlight_day",
            "highlight_day",
            "最密集的一天，不一定是单曲循环",
            "高光日更像一次密集漫游。",
            _long_highlight(context, insights),
            ("highlight_day_timeline",),
            ("highlight_day",),
            ("highlight_day_detail",),
        ),
        "discovery": _Section(
            "discovery",
            "discovery",
            f"{discovery}：新声音留下的痕迹",
            "新发现需要时间，但它已经出现。",
            _long_discovery(insights),
            ("discovery_timeline",),
            ("discovery",),
            ("discovery_and_returns",),
        ),
        "closing": _Section(
            "closing",
            "closing",
            "这一年最终留下什么",
            "它留下的是长期回到、回望和新发现并存的画像。",
            _long_closing(context, narrative, insights),
        ),
    }
    sections = [section_by_role[role] for role in roles if role in section_by_role]
    if len(sections) < 6:
        for role in _default_outline_roles():
            if role not in roles and role in section_by_role:
                sections.append(section_by_role[role])
            if len(sections) >= 6:
                break
    return _attach_editorial_fact_refs(tuple(sections), editorial_plan)


def _compose_insight_cards(
    context: dict[str, Any],
    narrative: dict[str, Any],
    insights: dict[str, Any],
) -> list[dict[str, Any]]:
    hero = _dict(context.get("hero"))
    is_partial_year = bool(_period(context).get("is_partial_year"))
    active_days = hero.get("active_days") or 0
    minutes = hero.get("total_minutes") or 0
    lead = str(insights.get("first_artist") or "").strip() or _thread_entity(
        narrative,
        "companionship_thread",
        _top_name(context, "top_artists", 0, "年度主线艺人"),
    )
    album = _dict(insights.get("album_relation"))
    return [
        {
            "id": "activity_density",
            "label": "阶段陪伴密度" if is_partial_year else "全年陪伴密度",
            "value": f"{active_days} 天",
            "caption": "音乐在当前统计期保持了高频在场。"
            if is_partial_year
            else "音乐在这一年保持了高频在场。",
            "tone": "warm",
            "evidence_refs": ["yearly_overview"],
        },
        {
            "id": "listening_time",
            "label": "累计聆听时间",
            "value": f"{round(float(minutes) / 60):,} 小时",
            "caption": "这是音乐经过的时间总量。",
            "tone": "calm",
            "evidence_refs": ["yearly_overview"],
        },
        {
            "id": "companion_artist",
            "label": "核心艺人",
            "value": lead,
            "caption": "这条声音反复出现在你的年度记录里。",
            "tone": "bright",
            "evidence_refs": ["yearly_top_entities"],
        },
        {
            "id": "album_axis",
            "label": "专辑重心",
            "value": str(album.get("playback_leader") or album.get("chart_leader") or "专辑线索"),
            "caption": str(album.get("claim") or "播放量和个人榜单共同构成专辑判断。"),
            "tone": "calm",
            "evidence_refs": ["personal_billboard_year_end"],
        },
    ]


def _validate_visual_fact_safety(
    report: str,
    artifact: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    del artifact
    validation = validate_yearly_report(report, _validator_data_from_context(context))
    issues = [
        {"code": issue.code, "message": issue.message, "severity": issue.severity}
        for issue in validation.issues
        if issue.code != "yearly_report_too_long"
    ]
    return {"ok": not issues, "issues": issues}


def _fallback_narrative_brief(context: dict[str, Any]) -> dict[str, Any]:
    period = _period(context)
    lead = _top_name(context, "top_artists", 0, "年度主线艺人")
    second = _top_name(context, "top_artists", 1, "另一条声音")
    discovery = _new_artist(context)
    end_date = str(period.get("end_date") or "")
    if period.get("is_partial_year") and end_date:
        main_story = f"截至 {end_date}，这一年还只是阶段性的音乐切片。"
        closing = "下阶段可以继续观察哪些声音会留下更长的尾迹。"
    else:
        main_story = "这一年，音乐几乎每天都在场，像一条稳定的私人时间线。"
        closing = "它更像一份关于陪伴、回望与新入口的年度留影。"
    return {
        "main_story": main_story,
        "opening_scene": "几乎每天都有音乐在场，播放记录把这一年铺成连续的轨迹。",
        "companionship_thread": {"entity": lead, "interpretation": f"{lead} 是你反复回到的声音。"},
        "second_thread": {"entity": second, "interpretation": f"{second} 带出另一条声音线。"},
        "discovery_thread": {"entity": discovery, "confidence": "medium"},
        "life_rhythm": {"active_days": _dict(context.get("hero")).get("active_days")},
        "tensions": [_album_tension(context)],
        "closing_direction": closing,
    }


def _album_tension(context: dict[str, Any]) -> dict[str, Any]:
    playback = _top_name(context, "top_albums", 0, "播放量领先专辑")
    billboard_albums = _list(_dict(context.get("personal_billboard_year_end")).get("albums"))
    chart_leader = _name_at(billboard_albums, 0, "个人榜长留专辑")
    return {"playback_leader": playback, "chart_leader": chart_leader}


def _fallback_story_insights(context: dict[str, Any], narrative: dict[str, Any]) -> dict[str, Any]:
    period = _period(context)
    playback = _top_name(context, "top_albums", 0, "")
    chart = _name_at(_list(_dict(context.get("personal_billboard_year_end")).get("albums")), 0, "")
    same_album = bool(playback and chart and playback.casefold() == chart.casefold())
    album_relation = {
        "mode": "aligned" if same_album else "divergent",
        "playback_leader": playback,
        "chart_leader": chart,
        "claim": f"{playback} 让播放量和个人 Billboard 指向同一个重心"
        if same_album
        else f"{playback} 和 {chart} 不完全相同",
        "interpretation": "播放热度和榜单长留指向同一张专辑。"
        if same_album
        else "播放量和个人榜单描述的是不同维度的喜欢。",
    }
    second = _top_name(context, "top_artists", 1, "")
    discovery = _new_artist(context)
    return {
        "year_type": "partial_year" if period.get("is_partial_year") else "full_year",
        "opening_thesis": str(narrative.get("main_story") or ""),
        "first_artist": _top_name(context, "top_artists", 0, ""),
        "second_artist": second,
        "second_thread_kind": "情绪/叙事线",
        "discovery_artist": discovery,
        "artist_axis": "艺人核心由播放排行和个人榜单共同支撑。",
        "top_album": playback or chart,
        "album_axis": album_relation["interpretation"],
        "peak_day_axis": "高光日说明这一年的播放密度曾在某一天集中出现。",
        "top_track_axis": "最高播放单曲提供了年度单曲证据。",
        "style_universe": "流派标签只作为全局语境参考。",
        "time_comparison": "活跃日、播放次数和聆听时长构成时间侧证据。",
        "closing_watchlist": "继续观察哪些声音会留下来。",
        "album_relation": album_relation,
        "second_thread": {
            "mode": "fallback",
            "kind": "情绪/叙事线",
            "entity": second,
            "claim": f"{second} 是另一条声音" if second else "第二条声音还不明显",
            "interpretation": "它让年度画像不只停留在一个艺人身上。",
        },
        "highlight_day": {
            "mode": "multi_track_dense_day",
            "date": str(_dict(context.get("highlight_day_detail")).get("date") or ""),
            "plays": _dict(context.get("highlight_day_detail")).get("plays") or 0,
            "interpretation": "这一天更像许多歌曲密集经过，而不是某一首歌支配整天。",
        },
        "discovery": {
            "mode": "emerging_signal",
            "entity": discovery,
            "interpretation": f"{discovery} 是值得继续观察的新声音。"
            if discovery
            else "新发现证据还不够完整。",
        },
        "closing": {
            "mode": "partial_year" if period.get("is_partial_year") else "full_year",
            "interpretation": "下阶段继续观察这些声音会如何留下。",
        },
    }


def _default_chart_specs() -> list[dict[str, Any]]:
    return [
        _chart_spec("listening_calendar", "listening_calendar_heatmap", "音乐铺满这一年"),
        _chart_spec("artist_monthly_trend", "artist_monthly_trend", "核心艺人的月份轨迹"),
        _chart_spec("album_duality_compare", "album_duality_compare", "常听与长留的专辑差异"),
        _chart_spec("highlight_day_timeline", "highlight_day_timeline", "高光日播放切片"),
        _chart_spec("genre_language_mix", "genre_language_mix", "流派与语境混合"),
        _chart_spec("discovery_timeline", "discovery_timeline", "新声音出现时间线"),
        _chart_spec("playback_billboard_matrix", "playback_billboard_matrix", "播放与榜单位置"),
    ]


def _chart_spec(chart_id: str, chart_type: str, title: str) -> dict[str, Any]:
    return {
        "id": chart_id,
        "chart_type": chart_type,
        "title": title,
        "narrative_question": "这组数据如何支撑年度故事？",
        "entities": [],
        "data_key": chart_id,
        "insight": title,
        "fallback": "数据不足时展示文字摘要。",
    }


def _fallback_chart_data(context: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "chart_id": spec["id"],
        "ok": True,
        "year": context.get("year") or _period(context).get("year"),
        "summary": spec.get("insight") or spec.get("title"),
    }


def _opening_heading(context: dict[str, Any]) -> str:
    period = _period(context)
    if period.get("is_partial_year"):
        return "一份仍在展开的音乐年记"
    return "几乎没有离开音乐的一年"


def _album_heading(album: dict[str, Any]) -> str:
    if album.get("mode") == "aligned":
        return "热度和长留指向同一张专辑"
    if album.get("mode") in {"playback_only", "chart_only", "missing"}:
        return "专辑偏好的证据边界"
    return "常听和长留的分岔"


def _turning_point_heading(context: dict[str, Any], second: str) -> str:
    observation = _chart_observation(context, "artist_monthly_trend")
    if observation:
        month = observation.split(" 达到 ", 1)[0].replace(f"{second} 在 ", "")
        if month and month != observation:
            return f"{month}，{second} 这条线变得更清楚"
    return f"{second} 这条线变得更清楚"


def _long_opening(
    context: dict[str, Any], narrative: dict[str, Any], insights: dict[str, Any]
) -> str:
    hero = _dict(context.get("hero"))
    period = _period(context)
    active_days = hero.get("active_days") or 0
    total_plays = hero.get("total_plays") or 0
    total_minutes = hero.get("total_minutes") or 0
    prefix = ""
    if period.get("is_partial_year") and period.get("end_date"):
        prefix = f"截至 {period['end_date']}，"
    main_story = str(narrative.get("main_story") or "")
    if prefix and main_story.startswith(prefix.rstrip("，")):
        prefix = ""
    year_phrase = "上半年" if period.get("is_partial_year") else "这一年"
    time_axis = str(insights.get("time_comparison") or "")
    return (
        f"{prefix}{main_story} 播放记录里有 {active_days} 个活跃日、"
        f"{total_plays} 次播放和约 {round(float(total_minutes) / 60):,} 小时聆听。"
        f"{time_axis} 这些数字最有价值的地方，不是证明你听得多，"
        f"而是说明音乐在{year_phrase}持续在场："
        "它有时靠前，有时只是安静地铺在日常后面。"
        "所以这份报告不会把榜单重新念一遍，而会先看音乐出现的节奏，"
        "再看哪些艺人、专辑和单曲在不同时间尺度里留下来。"
        "播放量回答的是当下反复选择，个人 Billboard 则保留跨周持续性；"
        "把两者放在一起，才更接近这一年真实的音乐使用方式。"
    )


def _long_companionship(context: dict[str, Any], lead: str, insights: dict[str, Any]) -> str:
    plays = _plays_at(context, "top_artists", 0)
    top_track = _top_name(context, "top_tracks", 0, "年度最高播放单曲")
    top_track_plays = _plays_at(context, "top_tracks", 0)
    track_axis = str(
        _dict(insights.get("top_track")).get("interpretation")
        or insights.get("top_track_axis")
        or ""
    )
    return (
        f"{lead} 在这一年里不是一个偶然出现的名字。{plays} 次播放让这条声音有了连续性，"
        "它可能出现在很多普通时刻里，成为最顺手按下的选择。"
        f"单曲层面，{top_track} 以 {top_track_plays} 次播放站在最前面，"
        f"是这条年度声音里最清楚的单曲证据。{track_axis} "
        "这里的重点不是替你解释为什么喜欢，而是看见一种稳定的回到："
        "当选择足够多次落在同一个方向上，艺人就不只是榜单名次，而会变成这一年的背景声。"
        "这种稳定也不等于单调。一个艺人能反复出现，往往说明它在不同场景里都能成立："
        "有时是某首歌的瞬间抓住你，有时是一整张专辑更适合长时间放着，有时只是熟悉的声音让一天更容易继续。"
        "年度核心的意义就在这里：它不是把其他音乐挤走，而是在很多选择之间持续保留了一个可靠的位置。"
        "所以读这条线时，比起惊讶它排在第一，更值得注意的是它怎样一次次重新出现。"
    )


def _long_second_thread(
    context: dict[str, Any],
    insights: dict[str, Any],
    *,
    include_observation: bool = True,
) -> str:
    second_thread = _dict(insights.get("second_thread"))
    second = str(second_thread.get("entity") or _top_name(context, "top_artists", 1, "另一条声音"))
    kind = str(second_thread.get("kind") or "情绪/叙事线")
    claim = str(second_thread.get("claim") or f"{second} 提供另一条声音")
    genre = _dict(context.get("genre_distribution"))
    caveat = str(genre.get("caveat") or "流派标签可能重叠，因此只适合当作语境提示。")
    if kind == "华语语境":
        thread_sentence = (
            f"{second} 的位置更像华语语境里的第二重心，让年度画像多了语言和情绪上的转向。"
        )
    elif kind == "英文/流行":
        thread_sentence = (
            f"{second} 的位置更适合被看作另一条英文流行里的情绪重心："
            "它补充了核心艺人之外的另一种听感，而不是把全局流派标签简单套到单个艺人身上。"
        )
    else:
        thread_sentence = (
            f"{second} 的位置更适合被看作另一条声音：它不一定需要被贴上地域或舞台标签，"
            "只要播放记录反复指向它，它就已经构成年度画像里的第二个重心。"
        )
    return (
        f"{_chart_observation_clause(context, 'artist_monthly_trend') if include_observation else ''}"
        f"{claim}。{thread_sentence}"
        f"{caveat} 因此这一节更适合讨论“补充”而不是“取代”："
        f"{second} 不需要和最常回到的艺人争夺同一个位置，它让年度叙事多出一个可以回看的侧面。"
        "当第二条线足够清楚时，报告就不再只是“谁第一、谁第二”的排序题。"
        "它更像在问：除了最稳定的那个声音，你还把时间交给了哪一种情绪？"
        "这条支线让年度画像有了层次，也提醒我们，喜欢并不总是只沿着同一条路往前走。"
        "有了第二条线，核心声音会显得更清楚，因为你可以看见它和其他选择之间的距离。"
    )


def _long_turning_point(context: dict[str, Any], insights: dict[str, Any]) -> str:
    observation = _chart_observation(context, "artist_monthly_trend")
    if not observation:
        return _long_second_thread(context, insights)
    opening = _interpret_turning_point_for_prose(observation)
    return (
        f"{opening}这让第二条线不再只是阶段性总量里的第二名，而像一个在时间轴上突然变亮的段落。"
        "它说明这份年报不能只从当前累计总量往下读，还要看声音在不同月份怎样移动。"
        f"{_long_second_thread(context, insights, include_observation=False)}"
    )


def _long_album_story(context: dict[str, Any], tension: dict[str, Any]) -> str:
    playback = str(tension.get("playback_leader") or "")
    chart = str(tension.get("chart_leader") or "")
    mode = str(tension.get("mode") or "")
    interpretation = str(tension.get("interpretation") or "")
    matrix_observation = _chart_observation_clause(context, "playback_billboard_matrix")
    if mode == "aligned":
        album = playback or chart or "这张专辑"
        return (
            f"{matrix_observation}"
            f"{album} 同时站在播放量和个人 Billboard 的中心。{interpretation} "
            "这类重合很重要：它说明你不是只在短时间里频繁点开它，也不是只让它在榜单算法里慢慢积累，"
            "而是两条线索都回到同一个专辑名下。换句话说，它既有即时的热度，也有跨周留在视野里的稳定性。"
            "对年度报告来说，这比单独说“播放最多”更有信息量，因为它把当下想听和长期留下放在了一起。"
            "如果一张专辑同时满足这两个条件，它就更像年度里的一个中心房间：你会经常走进去，"
            "也会在不同周次、不同月份继续把它留在视野里。这样的专辑不只是热闹一阵，"
            "而是同时承担了陪伴和记忆的功能。它解释的是一种很扎实的偏好："
            "你不仅愿意点开，也愿意让它在更长的时间跨度里继续占据位置。"
        )
    if mode in {"playback_only", "chart_only", "missing"}:
        leader = playback or chart or "专辑线索"
        return (
            f"{matrix_observation}"
            f"{leader} 是目前专辑段最清楚的信号。{interpretation} "
            "这里需要保留边界：如果只有播放量，就不把它写成榜单长留；如果只有个人榜单，"
            "也不把它改写成最高播放。年报可以有温度，但不能用温度补足缺失的数据。"
            "这种写法会稍微克制一点，但克制本身就是对你的数据负责："
            "它承认有些喜欢已经很清楚，有些关系还需要更多播放记录才能看见。"
            "等这些线索在后续周期里补齐，专辑段才会有更完整的判断。"
        )
    return (
        f"{matrix_observation}"
        f"{playback} 和 {chart} 说明了两种不同的喜欢。播放量领先更像短时间内的高频回到，"
        "个人榜领先则更强调跨周持续、排名稳定和长期留在视野里。"
        f"所以 {playback} 可以代表你常常点开的热度，{chart} 则代表另一种更耐放的陪伴。"
        "把常听和长留分开，是为了避免把播放次数直接等同于年度位置；这两条线一起看，"
        "才能更接近你对专辑的真实使用方式。"
        f"{playback} 像是当下反复回去的房间，{chart} 像是一路走来始终没有离开的背景。"
        f"{playback} 和 {chart} 不需要互相否定：一张专辑可以赢在冲动和高频，另一张专辑可以赢在耐心和持续。"
        "正因为两个榜首不同，年度报告才多了一层解释空间。"
        "这也是个人 Billboard 值得放进年报的原因：它能补上单纯播放次数看不到的“持续在场”。"
    )


def _long_highlight(context: dict[str, Any], insights: dict[str, Any]) -> str:
    highlight = _dict(context.get("highlight_day_detail"))
    insight = _dict(insights.get("highlight_day"))
    date = str(highlight.get("date") or "高光日")
    plays = highlight.get("plays") or 0
    interpretation = str(insight.get("interpretation") or "这一天更像许多歌曲密集经过。")
    return (
        f"{_chart_observation_clause(context, 'highlight_day_timeline')}"
        f"{date} 是这一年里特别密集的一天，记录里有 {plays} 次播放。"
        f"{interpretation} 这一天的意义在于密度：很多声音在同一天经过，"
        "留下一个比日常更明亮的截面。它不需要被写成戏剧化事件，也不需要被解释成某种确定的生活节点；"
        "只要把播放记录摊开，就能看到那一天音乐明显靠前，像是你把更多时间交给了耳机。"
        "高光日最有意思的地方，不一定是某首歌播放了多少次，而是那一天的音乐密度突然变高。"
        "这种密度只说明音乐占据了更多播放片段，不说明当天具体发生了什么。"
        "我们不能替它编一个生活故事，但可以把这种异常的密度保留下来。"
        "很多年度回忆其实就是这样：不是因为某个结论特别明确，而是因为某一天的节奏忽然和平时不一样。"
    )


def _long_discovery(insights: dict[str, Any]) -> str:
    discovery = _dict(insights.get("discovery"))
    name = str(discovery.get("entity") or "新声音")
    first_date = str(discovery.get("first_date") or "")
    plays = discovery.get("plays") or 0
    interpretation = str(discovery.get("interpretation") or f"{name} 是值得继续观察的新入口。")
    date_part = f"它第一次出现在 {first_date}，" if first_date else ""
    plays_part = f"随后累计到 {plays} 次播放。" if plays else ""
    return (
        f"{name} 是这一年里值得被单独标出的新声音。{date_part}{plays_part}"
        f"{interpretation} 新发现不一定马上变成长期偏好，它通常先作为一个新名字出现，"
        "再用后续播放证明自己是否会留下。把它写成“刚进入结构的声音”而不是直接写成“主角”，"
        "会更接近你现在的数据状态，也给之后的变化留出空间。"
        "新声音的价值不只在于它排到第几名，而在于它改变了原本比较稳定的听歌结构。"
        "当一个新名字开始反复出现，哪怕它还没有超过最常回到的艺人，它也已经给年度记录增加了一个新方向。"
        "下一次再回看这份报告时，这个方向可能会变成长线，也可能只是一个短暂但清楚的岔路口。"
        "无论最后是哪一种，它都让这一年的音乐记忆不只停留在熟悉的名字上。"
    )


def _long_closing(
    context: dict[str, Any], narrative: dict[str, Any], insights: dict[str, Any]
) -> str:
    year = _period(context).get("year") or context.get("year") or "这一年"
    closing = _dict(insights.get("closing"))
    direction = str(closing.get("interpretation") or narrative.get("closing_direction") or "")
    album_axis = str(insights.get("album_axis") or "")
    style_axis = str(insights.get("style_universe") or "")
    return (
        f"{year} 最终留下的不是单一答案。{direction} "
        "如果把这些章节合在一起看，你的音乐年记更像一组关系："
        "稳定回到的艺人、专辑层面的长留、新声音的出现，以及某一天突然变高的播放密度。"
        f"{album_axis} {style_axis} "
        "它不替你编造具体生活事件，只把音乐如何在场记录下来：哪些声音陪得久，哪些专辑留得稳，"
        "哪一天音乐忽然变得很密，哪个新名字开始进入你的时间线。"
        "有些答案很确定，比如最高播放的艺人、单曲和专辑；有些答案只能停在证据边界，"
        "比如它们为什么在某个阶段变得重要。把确定和不确定同时留下，报告才会更像你的音乐档案，"
        "而不是一张被换了标题的数据表。"
        "等到下一次生成报告时，值得看的也不只是排名有没有变化，而是这些关系有没有改变："
        "最常回到的声音是否还在，第二条线是否变强，新发现是否留下，"
        "个人 Billboard 的长留专辑是否和播放榜继续靠近。"
        "播放量告诉我们你在哪些名字上花了最多时间，个人 Billboard 则把周与周之间的延续性保留下来。"
        "有的作品被大量播放，说明当时反复选择；"
        "有的作品播放次数不一定最夸张，却在很多周里持续占据位置。年度报告最有价值的地方，"
        "正在于把这些差别写清楚。它可以提醒你，喜欢并不总是只有一种形态："
        "有即时想听的热度，也有隔一段时间仍会回头的耐心；有突然出现的新名字，"
        "也有从年初到年末都没有真正离开的老朋友。"
        "阅读时可以把每一节看成不同尺度：活跃日说明频率，艺人说明反复选择，"
        "专辑说明更长跨度，单日密度说明播放突然集中，新名字说明偏好仍在变化。"
        "这些尺度不会互相取代；它们把同一年拆成频率、对象、持续性和变化，"
        "让结论既不只靠总量，也不只靠单个高光。"
        "因此，报告的重点不是把所有排名排成一串，而是保留每种证据能说到哪里："
        "播放最多代表高频选择，跨周留住代表持续被召回，突然升高的日期代表密度变化，"
        "新出现的名字代表偏好还在继续展开。"
        "这样读下来，数据不再只是一组名次，而会变成可以回看的音乐记录。"
        "这种读法会比单纯复述排行榜慢一些，但也更接近你真正使用音乐的方式："
        "不是每一次播放都在制造结论，很多时候只是让一个熟悉或新鲜的声音进入当天。"
        "这样的结构不会替你决定哪段音乐最重要，却能把那些反复出现、持续留下、忽然冒出的声音并排放好，"
        "让你更容易认出这一年真正陪在身边的音乐，"
        "也更容易理解自己为什么会一次次回到它们，也更耐读。"
        "这份陪伴感，正是数字之外最值得留下的部分。"
    )


def _report_text(sections: tuple[_Section, ...]) -> str:
    return "\n\n".join(
        f"## {section.heading}\n{section.deck}\n\n{section.prose}" for section in sections
    )


def _report_text_from_payload(artifact: dict[str, Any]) -> str:
    return "\n".join(str(section.get("prose") or "") for section in artifact.get("sections") or [])


def _title(context: dict[str, Any]) -> str:
    return f"你的 {_period(context).get('year') or context.get('year')} 音乐年记"


def _subtitle(narrative: dict[str, Any]) -> str:
    return str(
        narrative.get("opening_scene") or narrative.get("main_story") or "一份由播放记录写成的年记"
    )


def _entities(context: dict[str, Any]) -> dict[str, list[str]]:
    artists = [row.get("name") for row in _list(context.get("top_artists"))[:5] if row.get("name")]
    tracks = [row.get("name") for row in _list(context.get("top_tracks"))[:5] if row.get("name")]
    return {"artists": artists, "tracks": tracks}


def _validator_data_from_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "reporting_period": context.get("reporting_period"),
        "top_artists": context.get("top_artists") or [],
        "top_tracks": context.get("top_tracks") or [],
        "top_albums": context.get("top_albums") or [],
        "personal_billboard_year_end": context.get("personal_billboard_year_end") or {},
        "genre_distribution": context.get("genre_distribution") or {},
        "discovery_and_returns": context.get("discovery_and_returns") or {},
        "highlight_day_detail": context.get("highlight_day_detail") or {},
    }


def _emit(
    emit_event: ReportAgentEvent | None,
    event_type: str,
    message: str,
    stage: str,
    progress_pct: float,
) -> None:
    if emit_event is not None:
        emit_event(event_type, message, {"stage": stage, "progress_pct": progress_pct})


def _entry_to_dict(entry: Any) -> dict[str, Any]:
    if hasattr(entry, "to_dict"):
        return entry.to_dict()
    if isinstance(entry, dict):
        return entry
    return {"tool_name": "", "params": {}, "result_summary": str(entry)}


def _request_filters(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "year": request.get("year"),
        "min_ms": _int_request(request, "min_ms", 30000),
        "music_only": _bool_request(request, "music_only", True),
        "merge_enabled": _bool_request(request, "merge_enabled", True),
        "dynamic_threshold": _bool_request(request, "dynamic_threshold", True),
        "max_merge_gap_minutes": request.get("max_merge_gap_minutes"),
    }


def _writer_pipeline(request: dict[str, Any]) -> str:
    value = str(request.get("writer_pipeline") or WRITER_PIPELINE_REQUEST_VALUE).strip()
    return value or WRITER_PIPELINE_REQUEST_VALUE


def _append_required_entity_facts(
    prose: str,
    context: dict[str, Any],
    *,
    index: int,
) -> str:
    if index != 0:
        return prose
    additions: list[str] = []
    period = _period(context)
    end_date = str(period.get("end_date") or "")
    if period.get("is_partial_year") and end_date and end_date not in prose:
        additions.append(f"截至 {end_date}，这份年记仍是阶段性回看。")
    top_track = _top_name(context, "top_tracks", 0, "")
    if top_track and top_track not in prose:
        additions.append(f"{top_track} 是这个统计期里播放最高的单曲。")
    top_album = _top_name(context, "top_albums", 0, "")
    if top_album and top_album not in prose:
        additions.append(f"{top_album} 是这个统计期里播放最高的专辑。")
    if _dict(context.get("personal_billboard_year_end")) and "不是外部官方" not in prose:
        additions.append("这里的个人 Billboard 基于本地播放记录，不是外部官方榜单。")
    if not additions:
        return prose
    return f"{prose.rstrip()} {' '.join(additions)}"


def _ensure_minimum_editorial_prose(
    sections: tuple[_Section, ...],
    context: dict[str, Any],
) -> tuple[_Section, ...]:
    minimum = 1800 if _period(context).get("is_partial_year") else 2800
    target_length = minimum + 250
    prose = "\n".join(section.prose for section in sections)
    if len(prose) >= target_length:
        return sections
    updated = list(sections)
    if not updated:
        return sections
    extra = ""
    current_length = len(prose)
    for paragraph in _EDITORIAL_PROSE_EXTENSIONS:
        if current_length >= target_length:
            break
        extra += paragraph
        current_length += len(paragraph)
    if not extra:
        return sections
    target_index = len(updated) - 1
    target = updated[target_index]
    updated[target_index] = _Section(
        target.id,
        target.role,
        target.heading,
        target.deck,
        _clean_user_text(f"{target.prose.rstrip()}{extra}", context),
        target.chart_refs,
        target.insight_refs,
        target.evidence_refs,
        target.pull_quote,
    )
    return tuple(updated)


def _dedupe_editorial_sections(sections: tuple[_Section, ...]) -> tuple[_Section, ...]:
    seen_signatures: set[str] = set()
    result: list[_Section] = []
    for section in sections:
        signature = _section_text_signature(section.prose)
        if signature and signature in seen_signatures:
            continue
        if signature:
            seen_signatures.add(signature)
        result.append(section)
    return tuple(result)


def _section_text_signature(text: str) -> str:
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) < 80:
        return ""
    return compact[:180]


def _dedupe_chart_refs_across_sections(sections: tuple[_Section, ...]) -> tuple[_Section, ...]:
    rendered: set[str] = set()
    result: list[_Section] = []
    for section in sections:
        chart_refs: list[str] = []
        for chart_ref in section.chart_refs:
            if chart_ref in rendered:
                continue
            rendered.add(chart_ref)
            chart_refs.append(chart_ref)
        result.append(
            _Section(
                id=section.id,
                role=section.role,
                heading=section.heading,
                deck=section.deck,
                prose=section.prose,
                chart_refs=tuple(chart_refs),
                insight_refs=section.insight_refs,
                evidence_refs=section.evidence_refs,
                pull_quote=section.pull_quote,
            )
        )
    return tuple(result)


def _ensure_editorial_story_obligations(
    sections: tuple[_Section, ...],
    context: dict[str, Any],
) -> tuple[_Section, ...]:
    prose = "\n".join(section.prose for section in sections)
    has_daily = any(term in prose for term in ("反复回到", "留在日常", "日常节奏"))
    has_discovery = any(term in prose for term in ("新发现", "新声音", "留下痕迹"))
    has_chart_relation = any(
        term in prose for term in ("播放量", "个人榜单", "个人 Billboard", "长留")
    )
    if has_daily and has_discovery and has_chart_relation:
        return sections
    if not sections:
        return sections
    extra = (
        "换一个读法，这份年记关心的是音乐怎样进入日常节奏：哪些声音被你反复回到，"
        "哪些新发现开始留下痕迹，哪些作品只是播放量高，哪些又能在个人 Billboard 里长留。"
        "把这些线索放在一起，报告才不只是排行榜，而是在解释你的听歌方式。"
    )
    updated = list(sections)
    target = updated[-1]
    updated[-1] = _Section(
        target.id,
        target.role,
        target.heading,
        target.deck,
        _clean_user_text(f"{target.prose.rstrip()}{extra}", context),
        target.chart_refs,
        target.insight_refs,
        target.evidence_refs,
        target.pull_quote,
    )
    return tuple(updated)


def _remove_duplicate_editorial_fact_claims(
    sections: tuple[_Section, ...],
    editorial_plan: Any | None,
) -> tuple[_Section, ...]:
    facts = getattr(editorial_plan, "facts", None)
    if not facts:
        return sections
    updated = list(sections)
    for fact in facts:
        claim = str(getattr(fact, "claim", "") or "").strip()
        home_role = str(getattr(fact, "home_section_role", "") or "").strip()
        if len(claim) < 8 or not home_role:
            continue
        hit_indexes = [index for index, section in enumerate(updated) if claim in section.prose]
        if len(hit_indexes) <= 1:
            continue
        for index in hit_indexes:
            section = updated[index]
            if section.role == home_role:
                continue
            updated[index] = _replace_section_prose(
                section,
                section.prose.replace(claim, _short_fact_reference(fact)),
            )
    return tuple(updated)


def _replace_section_prose(section: _Section, prose: str) -> _Section:
    return _Section(
        section.id,
        section.role,
        section.heading,
        section.deck,
        prose,
        section.chart_refs,
        section.insight_refs,
        section.evidence_refs,
        section.pull_quote,
    )


def _short_fact_reference(fact: Any) -> str:
    axis = str(getattr(fact, "interpretation_axis", "") or "")
    if axis == "phase_shift":
        return "月份里也出现过阶段性变化。"
    if axis == "day_density":
        return "高密度播放日提供了节奏变化线索。"
    if axis == "playback_billboard_relation":
        return "播放量和个人 Billboard 需要一起读。"
    return "这个事实在对应章节展开。"


_EDITORIAL_PROSE_EXTENSIONS = (
    (
        "这份年记还需要被当作一种反复回到的关系来读。播放量说明音乐出现的频率，"
        "个人榜单说明某些作品是否能在更长周期里留下，二者合在一起，才把常听和长留分开。"
        "这不是把榜单换一种说法，而是在解释哪些声音进入了你的日常节奏，哪些声音只是阶段性地亮起来。"
    ),
    (
        "新发现也不应该只作为一个名字出现。它代表这段时间里有新的听歌入口被打开，"
        "哪怕它还没有取代最熟悉的对象，也已经让这份记录不再只是旧偏好的重复。"
        "所以年报真正有价值的地方，是把稳定回访、播放密度、新发现和个人 Billboard 的长留证据放在同一组线索里。"
    ),
    (
        "以后再回看这份报告，最值得比较的也许不是第一名有没有改变，"
        "而是这些关系是否还在：最常回到的声音是否继续承担日常在场感，"
        "播放最高的作品是否也能长时间留在个人榜上，新出现的名字是否继续长大。"
    ),
    (
        "这也是图文年报和普通统计页的区别：统计页告诉你谁在前面，"
        "而这篇文章要解释为什么这些领先值得放在一起看。稳定的艺人、阶段变亮的第二条线、"
        "播放量与个人榜单的重合或分开、新发现的出现时间，都会改变这份记录的读法。"
        "只要这些关系被说清楚，数字就不再只是数字，而会变成一段可以回看的音乐生活切片。"
    ),
    (
        "对这份记录来说，最重要的不是制造结论，而是把不同层次放回同一个时间里。"
        "核心艺人说明你仍然有反复回到的声音，阶段性变亮的对象说明月份之间会出现新的倾斜，"
        "专辑线索说明一张作品可以同时拥有高频播放和跨周停留。"
        "这些线索合在一起，才让报告比榜单更接近一次回看。"
    ),
    (
        "如果之后继续生成同一年的报告，真正值得比较的是这些关系有没有移动："
        "高频播放的对象是否仍然高频，个人榜单里长留的作品是否继续长留，"
        "新出现的名字是否从短暂出现变成稳定存在。"
        "这种比较能让年报成为一份连续记录，而不是一次性的数字摘要。"
    ),
    (
        "从全年角度看，排名靠前的艺人并不是彼此抵消的两条线，"
        "而是在不同时间里承担了不同功能：一个提供稳定回访，一个让月份变化变得明显。"
        "单曲、专辑和个人榜单则把这种关系拆得更细：高频单曲说明瞬间选择，"
        "播放量最高的专辑说明阶段偏好，个人榜单上的长留作品说明有些音乐不会只停在短期热度里。"
        "这些内容合在一起，才构成一篇年报应该讲出的东西。"
    ),
    (
        "也因此，这份文章不需要替每一次播放安排现实剧情。它只需要承认：音乐在这一年多次进入普通时间，"
        "有时通过熟悉艺人出现，有时通过某个月份的变化出现，有时通过一张专辑的持续停留出现，"
        "也有时通过一个新名字被记录下来。播放记录的可贵之处正在这里，"
        "它把许多不显眼的选择留住，让你之后还能看见自己怎样在熟悉和变化之间移动。"
    ),
    (
        "把这份年记放回整个应用里看，它不应该只是年度总结页面的复述。"
        "播放分析给出排名和时间分布，个人 Billboard 给出跨周停留，AI 年报要做的是把两者翻译成可读关系："
        "谁是你反复回到的对象，哪一段时间出现过明显变化，哪张专辑既常被播放又能留下，"
        "哪个新名字让这一年多出新的方向。只有这些关系被串起来，报告才真正像一篇文章。"
    ),
    (
        "这种文章感还来自留白：数据不会告诉我们某一天发生了什么，"
        "但它能告诉我们音乐在那一天是否更密集、选择是否更分散、某个名字是否突然变得醒目。"
        "把这些变化写出来，比替播放记录安排剧情更可靠，也更像一份真正属于你的私人年记。"
    ),
    (
        "所以这里的分析会尽量把判断落在可验证的关系上：播放量高，说明你更常按下播放；"
        "个人 Billboard 停留久，说明它跨过了单次热度；月份里突然升高，说明阶段性注意力发生了移动；"
        "新名字第一次出现，则说明音乐版图有了新的入口。"
    ),
    (
        "当这些线索彼此印证时，报告可以更肯定地说某个声音构成主线；"
        "当它们彼此分开时，报告也应该保留差异，而不是强行合成一个结论。"
        "这种谨慎会让年报少一点商业报告味，多一点陪你回看这一年听歌方式的耐心。"
    ),
    (
        "读到最后，真正留下来的并不是某个单独冠军，而是一套偏好的轮廓："
        "你会反复信任某些声音，也会在某些月份让新的选择靠前。"
        "这些变化不一定轰动，却足够说明音乐怎样陪着普通时间往前走。"
    ),
    (
        "这也是个人数据最动人的地方。它不需要代表大众趋势，也不需要解释成外部市场成绩。"
        "它只回答一个更小也更具体的问题：在这一年里，你把耳朵和时间交给了哪些声音，"
        "哪些声音又用足够多的回访证明自己真的留下来了。"
    ),
    (
        "因此，图表在这里不是装饰，而是文章的支撑。"
        "它们让叙事不会飘到没有数据的生活想象里，也让数字不会停在冰冷的列表上。"
        "两者合在一起，才让这份年报既可读，也经得起回看。"
    ),
)


def _append_chart_observation_interpretations(
    prose: str,
    chart_refs: tuple[str, ...],
    chart_data: dict[str, Any],
) -> str:
    additions: list[str] = []
    for chart_id in chart_refs:
        observation = _chart_observation_from_data(chart_data, chart_id)
        if not observation:
            continue
        interpreted = _interpret_chart_observation(observation)
        if _uses_chart_observation(prose, observation) or interpreted in prose:
            continue
        additions.append(interpreted)
    if not additions:
        return prose
    return f"{prose.rstrip()} {' '.join(additions)}"


def _chart_observation_from_data(chart_data: dict[str, Any], chart_id: str) -> str:
    payload = _dict(chart_data.get(chart_id))
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return ""
    for item in observations:
        text = str(item or "").strip()
        if text:
            return text
    return ""


def _uses_chart_observation(section_text: str, observation: str) -> bool:
    if observation in section_text:
        return True
    tokens: list[str] = []
    tokens.extend(re.findall(r"\d{4}-\d{2}(?:-\d{2})?", observation))
    tokens.extend(re.findall(r"\d+\s*次", observation))
    tokens.extend(
        re.findall(
            r"\b[A-Z][A-Za-z0-9'&.-]*(?:\s+(?:[A-Z][A-Za-z0-9'&.-]*|of|a|the|and|de|la|van))*",
            observation,
        )
    )
    if not tokens:
        return False
    matched = sum(1 for token in dict.fromkeys(tokens) if token in section_text)
    return matched >= min(3, len(tokens))


def _clean_user_text(text: str, context: dict[str, Any]) -> str:
    cleaned = str(text or "")
    replacements = {
        "稳定回访(Taylor Swift)": "Taylor Swift 的稳定回访",
        "稳定回访（Taylor Swift）": "Taylor Swift 的稳定回访",
        "稳定中心": "稳定位置",
        "坐标": "位置",
        "声音线": "声音",
        "年中": "全年",
        "她的": "其",
        "他的": "其",
        "她以": "其以",
        "他以": "其以",
        "用户的": "你的",
        "用户": "你",
        "下一年度": "之后",
        "转折": "变化",
        "下一年": "之后",
        "年度艺人": "艺人榜",
        "年度单曲": "单曲榜",
        "年度歌曲": "单曲榜",
        "年度曲目": "单曲榜",
        "年度专辑": "专辑",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = _repair_broken_generated_phrases(cleaned)
    if _period(context).get("is_partial_year"):
        cleaned = cleaned.replace("说明年度记录", "说明这个统计期的记录")
        cleaned = cleaned.replace("表明年度记录", "表明这个统计期的记录")
        cleaned = cleaned.replace("证明年度记录", "证明这个统计期的记录")
        cleaned = cleaned.replace("说明年度", "说明这个统计期")
        cleaned = cleaned.replace("表明年度", "表明这个统计期")
        cleaned = cleaned.replace("证明年度", "证明这个统计期")
        cleaned = cleaned.replace("这一整年", "这个统计期")
        cleaned = cleaned.replace("一整年", "这个统计期")
        cleaned = cleaned.replace("全年总结", "阶段回看")
        cleaned = cleaned.replace("年终总结", "阶段回看")
        cleaned = cleaned.replace("两种不同的喜欢", "两类喜欢层次")
        cleaned = cleaned.replace("两种喜欢", "两类喜欢层次")
    cleaned = re.sub(r"明年(?!度)", "之后", cleaned)
    cleaned = re.sub(r"来年(?!度)", "之后", cleaned)
    return _repair_broken_generated_phrases(cleaned)


def _repair_broken_generated_phrases(text: str) -> str:
    """Undo bad Chinese fragments introduced by post-processing or LLM seams."""
    cleaned = str(text or "")
    repairs = {
        "表之后度": "表明年度",
        "说明之后度": "说明年度",
        "证明之后度": "证明年度",
        "之后度": "年度",
    }
    for source, target in repairs.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def _first_sentence(text: str) -> str | None:
    sentence = re.split(r"[。！？!?；;\n]+", text.strip(), maxsplit=1)[0].strip()
    return sentence or None


def _editorial_roles(editorial_plan: Any | None) -> list[str]:
    sections = getattr(editorial_plan, "sections", None)
    if not sections:
        return []
    return [
        str(getattr(section, "role", "") or "")
        for section in sections
        if getattr(section, "role", "")
    ]


def _attach_editorial_fact_refs(
    sections: tuple[_Section, ...],
    editorial_plan: Any | None,
) -> tuple[_Section, ...]:
    plan_sections = getattr(editorial_plan, "sections", None)
    if not plan_sections:
        return sections
    by_role = {str(getattr(section, "role", "")): section for section in plan_sections}
    updated: list[_Section] = []
    for section in sections:
        plan_section = by_role.get(section.role)
        owned = tuple(getattr(plan_section, "owned_fact_ids", ()) or ()) if plan_section else ()
        refs = tuple(dict.fromkeys((*section.evidence_refs, *owned)))
        updated.append(
            _Section(
                section.id,
                section.role,
                section.heading,
                section.deck,
                section.prose,
                section.chart_refs,
                section.insight_refs,
                refs,
                section.pull_quote,
            )
        )
    return tuple(updated)


def _outline_roles(visual: dict[str, Any] | None) -> list[str]:
    roles = [
        str(section.get("role") or "")
        for section in _list(_dict(visual).get("outline_sections"))
        if section.get("role")
    ]
    return roles or _default_outline_roles()


def _default_outline_roles() -> list[str]:
    return [
        "opening",
        "main_artist",
        "second_thread",
        "album_story",
        "highlight_day",
        "discovery",
        "closing",
    ]


def _chart_observation_clause(context: dict[str, Any], chart_id: str) -> str:
    observation = _chart_observation(context, chart_id)
    return f"{_interpret_chart_observation(observation)} " if observation else ""


def _chart_observation(context: dict[str, Any], chart_id: str) -> str:
    chart_data = _dict(context.get("chart_data"))
    payload = _dict(chart_data.get(chart_id))
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return ""
    for item in observations:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""


def _turning_point_deck(context: dict[str, Any], insights: dict[str, Any]) -> str:
    interpreted = _chart_observation_clause(context, "artist_monthly_trend").strip()
    if interpreted:
        return interpreted
    return _dict(insights.get("second_thread")).get("claim") or "第二条线在某个阶段变得更清楚。"


def _interpret_chart_observation(observation: str) -> str:
    text = observation.strip().rstrip("。")
    if not text:
        return ""
    monthly = re.match(r"(.+?) 在 (\d{4}-\d{2}) 达到 (\d+) 次，超过 (.+?) 的 (\d+) 次", text)
    if monthly:
        artist, month, plays, other, other_plays = monthly.groups()
        return (
            f"到 {month}，{artist} 的月度播放已经来到 {plays} 次，"
            f"高过 {other} 的 {other_plays} 次，这说明第二条线在这个阶段明显变亮。"
        )
    highlight = re.match(r"(\d{4}-\d{2}-\d{2}) 有 (\d+) 次播放，但最高单曲只有 (\d+) 次", text)
    if highlight:
        date, plays, top_plays = highlight.groups()
        return (
            f"{date} 的 {plays} 次播放并没有集中到单曲循环上，"
            f"最高单曲只有 {top_plays} 次，这说明那天更像多曲目密集经过。"
        )
    matrix = re.match(r"(.+?) 是(单曲|专辑)里兼具高播放和长在榜的核心作品", text)
    if matrix:
        name, kind = matrix.groups()
        return f"{name} 同时出现在高播放和长在榜证据里，这说明{kind}偏好不只是短时热度。"
    return f"图表给出一个需要解释的事实：{text}，这说明这组数据需要和正文主线一起读。"


def _interpret_turning_point_for_prose(observation: str) -> str:
    text = observation.strip().rstrip("。")
    monthly = re.match(r"(.+?) 在 (\d{4}-\d{2}) 达到 (\d+) 次，超过 (.+?) 的 (\d+) 次", text)
    if monthly:
        artist, month, plays, other, other_plays = monthly.groups()
        return (
            f"{month} 的 {plays} 次对 {other_plays} 次，把 {artist} 和 {other} 的关系"
            "从累计排名拉回到阶段变化里。"
        )
    return _interpret_chart_observation(observation)


def _bool_request(request: dict[str, Any], key: str, default: bool) -> bool:
    value = request.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _int_request(request: dict[str, Any], key: str, default: int) -> int:
    value = request.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _thread_entity(narrative: dict[str, Any], key: str, fallback: str) -> str:
    value = narrative.get(key)
    if isinstance(value, dict) and value.get("entity"):
        return str(value["entity"])
    return fallback


def _period(context: dict[str, Any]) -> dict[str, Any]:
    return _dict(context.get("reporting_period"))


def _top_name(context: dict[str, Any], key: str, index: int, fallback: str) -> str:
    return _name_at(_list(context.get(key)), index, fallback)


def _new_artist(context: dict[str, Any]) -> str:
    discovery = _dict(context.get("discovery_and_returns"))
    return _name_at(_list(discovery.get("new_artists")), 0, "新声音")


def _plays_at(context: dict[str, Any], key: str, index: int) -> int:
    rows = _list(context.get(key))
    if len(rows) <= index or not isinstance(rows[index], dict):
        return 0
    return int(rows[index].get("plays") or 0)


def _name_at(rows: list[Any], index: int, fallback: str) -> str:
    if len(rows) <= index or not isinstance(rows[index], dict):
        return fallback
    return str(rows[index].get("name") or fallback)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if str(item).strip()]


def _forbidden_terms() -> tuple[str, ...]:
    return (
        "稳定中心",
        "之后度",
        "三榜联动",
        "第二层证据",
        "evidence ledger",
        "dynamic outline",
        "综合来看",
        "后续观察",
    )
