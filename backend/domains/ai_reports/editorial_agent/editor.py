"""Editorial rewrite pass for yearly reports."""

from __future__ import annotations

from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn, call_json_step
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    EditedArticle,
    ResearchBrief,
    StorylinePlan,
)
from backend.domains.ai_reports.editorial_agent.prompts import EDITOR_SYSTEM_PROMPT


def edit_article(
    brief: ResearchBrief,
    plan: StorylinePlan,
    draft: ArticleDraft,
    *,
    chat_fn: ChatFn | None = None,
) -> EditedArticle:
    parsed = call_json_step(
        EDITOR_SYSTEM_PROMPT,
        {
            "research_brief": brief.to_dict(),
            "storyline_plan": plan.to_dict(),
            "draft": draft.to_dict(),
        },
        temperature=0.2,
        chat_fn=chat_fn,
    )
    revised = (
        parsed.get("revised_article") if isinstance(parsed.get("revised_article"), dict) else {}
    )
    article = ArticleDraft.from_dict(revised)
    if not article.sections:
        article = _deterministic_cleanup(draft)
    return EditedArticle(
        article=article,
        edit_notes=tuple(str(item) for item in parsed.get("edit_notes") or [] if str(item).strip()),
        risk_flags=tuple(str(item) for item in parsed.get("risk_flags") or [] if str(item).strip()),
    )


def _deterministic_cleanup(draft: ArticleDraft) -> ArticleDraft:
    return ArticleDraft(
        title=draft.title,
        subtitle=draft.subtitle,
        thesis=draft.thesis,
        sections=tuple(
            section.__class__(
                id=section.id,
                heading=section.heading,
                purpose=section.purpose,
                prose=_dedupe_sentences(section.prose),
                evidence_refs=section.evidence_refs,
                chart_refs=section.chart_refs,
            )
            for section in draft.sections
        ),
        closing=_dedupe_sentences(draft.closing),
    )


def _dedupe_sentences(text: str) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for sentence in [part.strip() for part in text.split("。") if part.strip()]:
        if sentence in seen:
            continue
        seen.add(sentence)
        output.append(sentence)
    return "。".join(output) + ("。" if output else "")
