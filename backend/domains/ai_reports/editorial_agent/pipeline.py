"""Orchestration for the yearly editorial-agent writing pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.domains.ai_reports.editorial_agent import (
    RESEARCH_BRIEF_VERSION,
    WRITER_PIPELINE_VERSION,
)
from backend.domains.ai_reports.editorial_agent.claim_checker import check_article_claims
from backend.domains.ai_reports.editorial_agent.editor import edit_article
from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn
from backend.domains.ai_reports.editorial_agent.models import ArticleDraft, StorylinePlan
from backend.domains.ai_reports.editorial_agent.research_brief import build_research_brief
from backend.domains.ai_reports.editorial_agent.storyline_planner import plan_storyline
from backend.domains.ai_reports.editorial_agent.taste_rubric import score_article_taste
from backend.domains.ai_reports.editorial_agent.writer import fallback_article, write_article


def run_editorial_agent_pipeline(
    context: dict[str, Any],
    *,
    chart_data: dict[str, Any],
    chat_fn: ChatFn | None = None,
    emit_stage: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    _emit(emit_stage, "building_research_brief", "正在整理年度研究简报")
    brief = build_research_brief({**context, "chart_data": chart_data})
    _emit(emit_stage, "planning_storyline", "正在规划文章主线")
    plan = plan_storyline(brief, chat_fn=chat_fn)
    _emit(emit_stage, "writing_article", "正在撰写年报文章")
    draft = write_article(brief, plan, chart_data=chart_data, chat_fn=chat_fn)
    draft = _restore_article_contract(draft, plan)
    _emit(emit_stage, "editing_article", "正在编辑年报文风")
    edited = edit_article(brief, plan, draft, chat_fn=chat_fn)
    _emit(emit_stage, "checking_claims", "正在核对文章事实")
    article = _restore_article_contract(edited.article, plan)
    claim_check = check_article_claims(article, brief)
    if not claim_check.ok:
        article = _remove_failed_sentences(
            article,
            claim_check.unsupported_claims + claim_check.scope_leaks + claim_check.ambiguous_claims,
        )
        article = _restore_article_contract(article, plan)
        claim_check = check_article_claims(article, brief)
    _emit(emit_stage, "scoring_taste", "正在评估文章可读性")
    taste = score_article_taste(article)
    edit_notes = edited.edit_notes
    risk_flags = edited.risk_flags
    if not claim_check.ok or not taste.ok or not _article_has_minimum_shape(article, brief):
        draft_claim_check = check_article_claims(draft, brief)
        draft_taste = score_article_taste(draft)
        if draft_claim_check.ok and draft_taste.ok and _article_has_minimum_shape(draft, brief):
            article = draft
            claim_check = draft_claim_check
            taste = draft_taste
            edit_notes = (*edit_notes, "编辑输出未通过质量门槛，已回退到 writer 草稿。")
            risk_flags = (*risk_flags, "editor_output_rejected")
        else:
            fallback = _restore_article_contract(fallback_article(brief, plan), plan)
            fallback_claim_check = check_article_claims(fallback, brief)
            fallback_taste = score_article_taste(fallback)
            if (
                fallback_claim_check.ok
                and fallback_taste.ok
                and _article_has_minimum_shape(fallback, brief)
            ):
                article = fallback
                claim_check = fallback_claim_check
                taste = fallback_taste
                edit_notes = (*edit_notes, "LLM 草稿未通过质量门槛，已使用确定性长文兜底。")
                risk_flags = ()
            else:
                risk_flags = (*risk_flags, "fallback_article_failed")
    return {
        "article": article,
        "research_brief": brief,
        "storyline_plan": plan,
        "edit_notes": edit_notes,
        "risk_flags": risk_flags,
        "claim_check": claim_check,
        "taste_score": taste,
        "metadata": {
            "writer_pipeline_version": WRITER_PIPELINE_VERSION,
            "research_brief_version": RESEARCH_BRIEF_VERSION,
            "claim_check_passed": claim_check.ok,
            "editorial_review_passed": len(risk_flags) == 0,
            "taste_score": taste.to_dict(),
        },
    }


def _emit(emit_stage: Callable[[str, str], None] | None, stage: str, message: str) -> None:
    if emit_stage is not None:
        emit_stage(stage, message)


def _remove_failed_sentences(
    article: ArticleDraft, failed_sentences: tuple[str, ...]
) -> ArticleDraft:
    if not failed_sentences:
        return article
    failed = set(failed_sentences)
    return ArticleDraft(
        title=_strip_sentences(article.title, failed) or article.title,
        subtitle=_strip_sentences(article.subtitle, failed),
        thesis=_strip_sentences(article.thesis, failed),
        sections=tuple(
            section.__class__(
                id=section.id,
                heading=section.heading,
                purpose=section.purpose,
                prose=_strip_sentences(section.prose, failed),
                evidence_refs=section.evidence_refs,
                chart_refs=section.chart_refs,
            )
            for section in article.sections
        ),
        closing=_strip_sentences(article.closing, failed),
    )


def _strip_sentences(text: str, failed: set[str]) -> str:
    parts = [part.strip() for part in text.split("。") if part.strip()]
    kept = [part for part in parts if part not in failed]
    return "。".join(kept) + ("。" if kept else "")


def _article_has_minimum_shape(article: ArticleDraft, brief) -> bool:
    if len(article.sections) < 5:
        return False
    text = "\n".join(section.prose for section in article.sections) + "\n" + (article.closing or "")
    minimum = 1800 if brief.period.get("is_partial_year") else 2800
    return len(text) >= minimum


def _restore_article_contract(article: ArticleDraft, plan: StorylinePlan) -> ArticleDraft:
    thesis = article.thesis
    if not _has_clear_theme(thesis):
        thesis = plan.thesis if _has_clear_theme(plan.thesis) else thesis
    if not _has_clear_theme(thesis):
        thesis = "这份音乐年记由稳定回访、阶段变化和个人 Billboard 长留共同构成。"
    chart_refs_by_id = {section.id: section.chart_refs for section in plan.section_plan}
    fallback_chart_refs = tuple(
        ref for section in plan.section_plan for ref in section.chart_refs if ref
    )
    has_chart_refs = any(section.chart_refs for section in article.sections)
    sections = []
    for index, section in enumerate(article.sections):
        chart_refs = section.chart_refs
        if not has_chart_refs:
            chart_refs = chart_refs_by_id.get(section.id) or (
                fallback_chart_refs[:1] if index == 0 else ()
            )
        sections.append(
            section.__class__(
                id=section.id,
                heading=_soften_language(section.heading),
                purpose=section.purpose,
                prose=_soften_language(section.prose),
                evidence_refs=section.evidence_refs,
                chart_refs=chart_refs,
            )
        )
    return ArticleDraft(
        title=_soften_language(article.title),
        subtitle=_soften_language(article.subtitle),
        thesis=_soften_language(thesis),
        sections=tuple(sections),
        closing=_soften_language(article.closing),
    )


def _has_clear_theme(thesis: str) -> bool:
    thesis = thesis.strip()
    return len(thesis) >= 24 and any(
        marker in thesis for marker in ("共同", "构成", "不是", "而是", "同时")
    )


def _soften_language(text: str) -> str:
    replacements = {
        "综合来看": "",
        "三榜联动": "多条线索",
        "第二层证据": "另一条线索",
        "证据": "线索",
        "画像": "样子",
        "结构": "关系",
        "尺度": "层次",
        "重心": "位置",
        "声音线": "声音",
        "官方 Billboard": "个人 Billboard",
        "外部 Billboard": "个人 Billboard",
        "美国 Billboard": "个人 Billboard",
        "她的": "其",
        "他的": "其",
        "她以": "其以",
        "他以": "其以",
        "用户的": "你的",
        "用户": "你",
        "通勤路上": "日常里",
        "通勤": "日常",
        "下雨": "某一天",
        "分手": "情绪变化",
        "旅行": "日常变化",
        "加班": "忙碌时段",
    }
    cleaned = str(text or "")
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned
