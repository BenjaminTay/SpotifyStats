"""Storyline planning for yearly editorial-agent reports."""

from __future__ import annotations

from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn, call_json_step
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleSection,
    ResearchBrief,
    StoryCandidate,
    StorylinePlan,
)
from backend.domains.ai_reports.editorial_agent.prompts import PLANNER_SYSTEM_PROMPT

_FALLBACK_BACKBONE = (
    (
        "year_shape",
        "先看这一年的听歌方式",
        "把活跃日、播放量和曲目广度写成年度底色，而不是罗列概览。",
        ("playback_rank", "monthly_shift"),
    ),
    (
        "chart_relationship",
        "个人 Billboard 让喜欢多了一层时间感",
        "解释本地个人榜单和播放量分别回答什么问题。",
        ("playback_billboard_relation", "playback_rank"),
    ),
    (
        "turning_points",
        "密集播放日和新声音是阶段变化的入口",
        "说明年度里曾经变亮的日子、月份或新发现。",
        ("monthly_shift", "day_density", "discovery"),
    ),
    (
        "taste_reading",
        "这些数字合在一起，更像一种使用音乐的方式",
        "把艺人、专辑、曲风和高光日收束为偏好解释。",
        ("playback_rank", "playback_billboard_relation", "day_density", "discovery"),
    ),
)


def plan_storyline(brief: ResearchBrief, *, chat_fn: ChatFn | None = None) -> StorylinePlan:
    parsed = call_json_step(
        PLANNER_SYSTEM_PROMPT,
        {"research_brief": brief.to_dict()},
        temperature=0.1,
        chat_fn=chat_fn,
    )
    plan = StorylinePlan.from_dict(parsed)
    return plan if plan.section_plan and plan.thesis else _fallback_plan(brief)


def _fallback_plan(brief: ResearchBrief) -> StorylinePlan:
    year = brief.period.get("year") or "这一年"
    end_date = brief.period.get("end_date")
    subtitle = (
        f"截至 {end_date}，这是一份仍在展开的音乐年记。" if end_date else "一份个人音乐年记。"
    )
    sections = [
        ArticleSection(
            id="opening",
            heading="今年还没有结束，但音乐重心已经出现",
            purpose="建立阶段性年报边界和主论点",
            prose="",
            evidence_refs=_opening_evidence_refs(brief),
            chart_refs=(),
        )
    ]
    for candidate in brief.story_candidates[:5]:
        _append_candidate_section(sections, candidate)
    for section_id, heading, purpose, kinds in _FALLBACK_BACKBONE:
        if len(sections) >= 5:
            break
        _append_section(
            sections,
            ArticleSection(
                id=section_id,
                heading=heading,
                purpose=purpose,
                prose="",
                evidence_refs=_evidence_refs(brief, kinds),
                chart_refs=(),
            ),
        )
    return StorylinePlan(
        thesis=f"{year} 的音乐记录需要同时看稳定回访、阶段变化和长期留下。",
        title=f"{year} 音乐年记",
        subtitle=subtitle,
        section_plan=tuple(sections),
        must_not_write=(
            "不要写成榜单摘要。",
            "不要编造具体生活事件。",
            "不要把个人 Billboard 写成外部官方 Billboard。",
        ),
    )


def _append_candidate_section(sections: list[ArticleSection], candidate: StoryCandidate) -> None:
    _append_section(
        sections,
        ArticleSection(
            id=candidate.id,
            heading=candidate.title,
            purpose=candidate.why_it_matters,
            prose="",
            evidence_refs=candidate.evidence_refs,
            chart_refs=(),
        ),
    )


def _append_section(sections: list[ArticleSection], section: ArticleSection) -> None:
    if any(existing.id == section.id for existing in sections):
        return
    sections.append(section)


def _evidence_refs(brief: ResearchBrief, kinds: tuple[str, ...]) -> tuple[str, ...]:
    refs = [item.id for item in brief.evidence_ledger if item.kind in kinds]
    if not refs:
        refs = [item.id for item in brief.evidence_ledger[:3]]
    return tuple(refs[:4])


def _opening_evidence_refs(brief: ResearchBrief) -> tuple[str, ...]:
    playback_refs = [item.id for item in brief.evidence_ledger if item.kind == "playback_rank"]
    return tuple((playback_refs or [item.id for item in brief.evidence_ledger[:2]])[:3])
