"""Editorial quality critic for agentic yearly reports."""

from __future__ import annotations

import re
from typing import Any

from backend.domains.ai_reports.agentic_models import EditorialCritique, EditorialIssue

INTERPRETATION_TERMS = (
    "说明",
    "意味着",
    "反映",
    "不是",
    "而是",
    "共同指向",
    "形成",
    "支撑",
    "改变",
    "转向",
    "稳定",
    "扩张",
    "收束",
    "分化",
    "矛盾",
)

LISTING_PATTERNS = (
    r"以\s*[\d,]+",
    r"位列",
    r"排在",
    r"榜首",
    r"播放\s*[\d,]+",
    r"[\d,]+\s*次播放",
)

PARTIAL_YEAR_ANNUAL_LABELS = (
    "年度专辑",
    "年度单曲",
    "年度艺人",
    "年度冠军",
    "全年冠军",
    "全年榜首",
    "来年寄语",
)


def critique_yearly_article(
    report: str,
    context: dict[str, Any] | None = None,
) -> EditorialCritique:
    context = context or {}
    issues: list[EditorialIssue] = []
    min_length = int(context.get("min_length") or 1400)
    text = str(report or "").strip()

    if len(text) < min_length:
        issues.append(
            EditorialIssue(
                code="too_short_for_longform",
                message=f"正式长文报告至少需要 {min_length} 中文字符，当前为 {len(text)}。",
            )
        )

    if _listing_ratio(text) > 0.4 or _has_listing_run(text):
        issues.append(
            EditorialIssue(
                code="data_listing_too_heavy",
                message="报告过度罗列排名和播放次数，缺少解释段落。",
            )
        )

    if context.get("requires_billboard") and _billboard_underused(text):
        issues.append(
            EditorialIssue(
                code="billboard_underused",
                message="个人 Billboard 只被列为排名或在榜周数，缺少统治力、稳定性或三榜联动解释。",
            )
        )

    if context.get(
        "requires_playback_billboard_connection"
    ) and not _connects_playback_and_billboard(text):
        issues.append(
            EditorialIssue(
                code="playback_billboard_not_connected",
                message="报告没有解释播放数据和个人 Billboard 数据之间的关系。",
            )
        )

    if context.get("is_partial_year") and any(
        label in text for label in PARTIAL_YEAR_ANNUAL_LABELS
    ):
        issues.append(
            EditorialIssue(
                code="partial_year_annual_label",
                message="阶段性报告不应使用完整年度实体标签。",
            )
        )

    repair = tuple(_repair_instruction(issue.code) for issue in issues)
    return EditorialCritique(ok=not issues, issues=tuple(issues), repair_instructions=repair)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]


def _listing_ratio(text: str) -> float:
    sentences = _sentences(text)
    if not sentences:
        return 1.0

    listing_sentences = 0
    for sentence in sentences:
        has_number = bool(re.search(r"\d", sentence))
        has_listing = any(re.search(pattern, sentence) for pattern in LISTING_PATTERNS)
        has_interpretation = any(term in sentence for term in INTERPRETATION_TERMS)
        if has_number and has_listing and not has_interpretation:
            listing_sentences += 1
    return listing_sentences / len(sentences)


def _has_listing_run(text: str) -> bool:
    run = 0
    for sentence in _sentences(text):
        if any(re.search(pattern, sentence) for pattern in LISTING_PATTERNS):
            run += 1
        else:
            run = 0
        if run >= 3:
            return True
    return False


def _billboard_underused(text: str) -> bool:
    if "Billboard" not in text and "个人榜" not in text:
        return True
    return not any(
        term in text for term in ("统治", "稳定", "持续", "峰值", "三榜", "联动", "在榜能力")
    )


def _connects_playback_and_billboard(text: str) -> bool:
    if "播放" not in text or ("Billboard" not in text and "个人榜" not in text):
        return False
    return any(term in text for term in ("共同", "同时", "印证", "说明", "不是单点", "互相"))


def _repair_instruction(code: str) -> str:
    return {
        "too_short_for_longform": "扩写为文章级长文，增加解释段落而不是填充榜单。",
        "data_listing_too_heavy": "把连续榜单句合并成论点段落，每段写出判断、证据和解释。",
        "billboard_underused": "补充个人 Billboard 的统治力、稳定性、三榜联动或播放/Billboard 分歧分析。",
        "playback_billboard_not_connected": "解释播放次数、播放时长和个人 Billboard 指标如何互相印证或冲突。",
        "partial_year_annual_label": "把完整年度措辞改为年中、阶段性或截至日期表达。",
    }.get(code, "根据 critic 问题重写对应段落。")
