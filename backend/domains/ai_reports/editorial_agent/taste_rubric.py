"""Taste rubric for yearly editorial-agent reports."""

from __future__ import annotations

from backend.domains.ai_reports.editorial_agent.models import ArticleDraft, TasteScore

JARGON = ("证据", "画像", "结构", "尺度", "重心", "综合来看", "三榜联动", "第二层证据")
SPECIFIC_MARKERS = (
    "Taylor Swift",
    "Olivia Rodrigo",
    "The Life of a Showgirl",
    "个人 Billboard",
    "2026-05",
)


def score_article_taste(article: ArticleDraft) -> TasteScore:
    text = _text(article)
    notes: list[str] = []
    dimensions = {
        "文章感": _article_feel(text),
        "年度主题": _theme_score(article),
        "洞见密度": _insight_score(text),
        "个人化": _specificity_score(text),
        "事实安全": _fact_safety_score(text),
        "可读性": _readability_score(text),
        "图文融合": _visual_score(article),
    }
    if dimensions["可读性"] < 4:
        notes.append("抽象术语或模板词偏多。")
    if dimensions["年度主题"] < 4:
        notes.append("缺少清楚年度主题。")
    if "后续观察走势" in text:
        notes.append("结尾仍像模板展望。")
    return TasteScore(dimensions=dimensions, notes=tuple(notes))


def _text(article: ArticleDraft) -> str:
    return "\n".join(
        [
            article.title,
            article.subtitle,
            article.thesis,
            *(s.prose for s in article.sections),
            article.closing,
        ]
    )


def _article_feel(text: str) -> int:
    if any(term in text for term in ("我查了什么", "依据", "自检与限制")):
        return 2
    if sum(text.count(term) for term in JARGON) >= 6:
        return 2
    return 5 if len(text) >= 80 else 4


def _theme_score(article: ArticleDraft) -> int:
    thesis = article.thesis.strip()
    if len(thesis) >= 24 and any(
        marker in thesis for marker in ("共同", "构成", "不是", "而是", "同时")
    ):
        return 5
    return 3 if thesis else 1


def _insight_score(text: str) -> int:
    markers = sum(
        text.count(marker) for marker in ("不是", "而是", "同时", "反复", "留下", "变亮", "长留")
    )
    return 5 if markers >= 5 else 4 if markers >= 3 else 2


def _specificity_score(text: str) -> int:
    hits = sum(1 for marker in SPECIFIC_MARKERS if marker in text)
    return 5 if hits >= 4 else 4 if hits >= 3 else 2


def _fact_safety_score(text: str) -> int:
    unsafe = ("通勤", "考试", "下雨", "分手", "旅行", "加班", "官方 Billboard")
    return 3 if any(term in text for term in unsafe) else 5


def _readability_score(text: str) -> int:
    jargon_hits = sum(text.count(term) for term in JARGON)
    if jargon_hits >= 6:
        return 2
    if jargon_hits >= 3:
        return 3
    return 5


def _visual_score(article: ArticleDraft) -> int:
    refs = {ref for section in article.sections for ref in section.chart_refs}
    return 5 if refs else 3
