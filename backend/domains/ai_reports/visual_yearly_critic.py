"""Narrative and visual quality critic for visual yearly artifacts."""

from __future__ import annotations

import re
from typing import Any

from backend.domains.ai_reports.narrative_quality import evaluate_visual_yearly_quality

BUSINESS_REPORT_TERMS = (
    "稳定中心",
    "之后度",
    "三榜联动",
    "第二层证据",
    "evidence ledger",
    "dynamic outline",
    "综合来看",
    "后续观察",
)

INTERNAL_GUIDANCE_TERMS = (
    "证据强度",
    "不要写成",
    "interpretation_guidance",
    "safe_speculation_rules",
    "展示Olivia",
    "展示播放",
    "解释播放领先",
    "揭示偏好深度",
    "说明偏好会在特定月份",
)

CONFIDENCE_LABEL_PATTERN = re.compile(
    r"\bconfidence(?:_level)?\s*(?:[:：=]\s*)?(?:is\s*)?(?:high|medium|low)\b|置信度\s*[:：=]?\s*(?:high|medium|low)",
    re.IGNORECASE,
)

REPEATED_META_TERMS = (
    "图表负责回答",
    "正文负责回答",
    "为什么值得被记住",
)

SAME_ENTITY_FALSE_CONTRAST_TERMS = (
    "两种不同",
    "两种喜欢",
    "不同喜欢",
    "不完全相同",
    "一边",
    "另一边",
    "一方面",
    "另一方面",
    "分歧",
)

UNSUPPORTED_OLIVIA_CLAIM_TERMS = (
    "华语",
    "中文",
    "现场感",
    "回望",
)

UNSUPPORTED_CLAIM_NEGATIONS = (
    "不是华语",
    "不属于华语",
    "不应强行绑定",
    "不能强行绑定",
    "不适合写成",
    "没有证据",
    "避免把",
    "不要把",
    "不得把",
)


def critique_visual_yearly_artifact(
    artifact: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    issues: list[dict[str, str]] = []
    prose = _all_prose(artifact)
    sections = _list(artifact.get("sections"))
    chart_specs = _list(artifact.get("chart_specs"))
    insight_cards = _list(artifact.get("insight_cards"))
    chart_data = artifact.get("chart_data") if isinstance(artifact.get("chart_data"), dict) else {}

    min_length = 1800 if context.get("is_partial_year") else 2800
    if len(prose) < min_length:
        issues.append(
            _issue("too_short", f"正文至少需要 {min_length} 个中文字符，当前为 {len(prose)}。")
        )
    if len(sections) < 6:
        issues.append(_issue("not_enough_sections", "图文年报至少需要 6 个章节。"))
    if len(chart_specs) < 4:
        issues.append(_issue("not_enough_charts", "图文年报至少需要 4 个图表。"))
    if len(insight_cards) < 3:
        issues.append(_issue("not_enough_insight_cards", "图文年报至少需要 3 个重点卡片。"))

    missing_refs = _missing_chart_refs(sections, chart_specs, chart_data)
    if missing_refs:
        issues.append(
            _issue(
                "missing_chart_refs", "章节引用了不存在或无数据的图表：" + ", ".join(missing_refs)
            )
        )

    forbidden = [term for term in BUSINESS_REPORT_TERMS if term in prose]
    if forbidden:
        issues.append(
            _issue(
                "business_report_tone", "用户正文泄漏商业报告腔或内部术语：" + ", ".join(forbidden)
            )
        )

    internal = _internal_guidance_leaks(prose)
    if internal:
        issues.append(
            _issue(
                "internal_guidance_leakage",
                "用户正文泄漏内部写作指令或证据标签：" + ", ".join(internal),
            )
        )

    if _has_repeated_template_prose(prose):
        issues.append(
            _issue("repeated_template_prose", "多个章节重复同一段模板解释，读起来不像文章。")
        )

    if _has_same_entity_false_contrast(prose, context):
        issues.append(_issue("same_entity_false_contrast", "同一实体被写成了两种不同偏好的对比。"))

    if _has_unsupported_entity_claim(prose, context):
        issues.append(
            _issue(
                "unsupported_entity_claim", "艺人或专辑被写入缺少证据支撑的地域、现场或回望归因。"
            )
        )

    if not _has_story_obligations(prose):
        issues.append(
            _issue(
                "missing_story_obligations",
                "正文缺少陪伴、生活节奏、新发现或播放/个人榜单关系分析。",
            )
        )

    quality = evaluate_visual_yearly_quality(artifact, _dict(context.get("editorial_plan")))
    if not quality["ok"]:
        issues.extend(issue for issue in quality["issues"] if isinstance(issue, dict))

    return {
        "ok": not issues,
        "issues": issues,
        "repair_instructions": [_repair_instruction(issue["code"]) for issue in issues],
    }


def _all_prose(artifact: dict[str, Any]) -> str:
    parts: list[str] = []
    for section in _list(artifact.get("sections")):
        parts.extend(
            [
                str(section.get("heading") or ""),
                str(section.get("deck") or ""),
                str(section.get("prose") or ""),
                str(section.get("pull_quote") or ""),
            ]
        )
    chart_data = _dict(artifact.get("chart_data"))
    for payload in chart_data.values():
        observations = _dict(payload).get("observations")
        if isinstance(observations, list):
            parts.extend(str(item) for item in observations if str(item).strip())
    return "\n".join(part for part in parts if part)


def _missing_chart_refs(
    sections: list[dict[str, Any]],
    chart_specs: list[dict[str, Any]],
    chart_data: dict[str, Any],
) -> list[str]:
    available = {str(spec.get("id")) for spec in chart_specs if spec.get("id")} & set(chart_data)
    refs = {str(ref) for section in sections for ref in section.get("chart_refs") or [] if ref}
    return sorted(ref for ref in refs if ref not in available)


def _has_story_obligations(prose: str) -> bool:
    companionship = any(term in prose for term in ("陪伴", "反复回到", "留在日常", "日常节奏"))
    discovery = any(term in prose for term in ("新入口", "新声音", "新发现", "留下痕迹"))
    chart_relation = any(term in prose for term in ("播放量", "个人榜单", "长留", "持续在榜"))
    return companionship and discovery and chart_relation


def _internal_guidance_leaks(prose: str) -> list[str]:
    terms = [term for term in INTERNAL_GUIDANCE_TERMS if term in prose]
    terms.extend(match.group(0) for match in CONFIDENCE_LABEL_PATTERN.finditer(prose))
    return sorted(set(terms), key=terms.index)


def _has_repeated_template_prose(prose: str) -> bool:
    repeated = any(prose.count(term) >= 2 for term in REPEATED_META_TERMS)
    product_explainer = "图表负责回答" in prose and "正文负责回答" in prose
    return repeated or product_explainer


def _has_same_entity_false_contrast(prose: str, context: dict[str, Any]) -> bool:
    playback = _name(_first(_list(context.get("top_albums"))))
    chart = _name(_first(_list(_dict(context.get("personal_billboard_year_end")).get("albums"))))
    if not playback or not chart or playback.strip().casefold() != chart.strip().casefold():
        return False
    if prose.casefold().count(playback.casefold()) < 2:
        return False
    return any(term in prose for term in SAME_ENTITY_FALSE_CONTRAST_TERMS)


def _has_unsupported_entity_claim(prose: str, context: dict[str, Any]) -> bool:
    if "Olivia Rodrigo" not in prose:
        return False
    artist_names = {_name(row) for row in _list(context.get("top_artists"))}
    if artist_names and "Olivia Rodrigo" not in artist_names:
        return False
    sentences = _sentences(prose)
    for index, sentence in enumerate(sentences):
        has_entity = "Olivia Rodrigo" in sentence
        previous_has_entity = index > 0 and "Olivia Rodrigo" in sentences[index - 1]
        if not has_entity and not previous_has_entity:
            continue
        window = sentence if has_entity else f"{sentences[index - 1]}。{sentence}"
        if not any(term in window for term in UNSUPPORTED_OLIVIA_CLAIM_TERMS):
            continue
        if any(negation in window for negation in UNSUPPORTED_CLAIM_NEGATIONS):
            continue
        return True
    return False


def _sentences(prose: str) -> list[str]:
    return [part for part in re.split(r"[。！？!?；;\n]+", prose) if part]


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": "error"}


def _repair_instruction(code: str) -> str:
    return {
        "too_short": "扩写章节正文，增加故事解释而不是追加榜单。",
        "not_enough_sections": "补足 opening、year_rhythm、companionship、album_story、discovery、closing 等章节。",
        "not_enough_charts": "至少加入 4 个有真实 chart_data 的图表。",
        "not_enough_insight_cards": "至少加入 3 个重点卡片。",
        "missing_chart_refs": "移除无数据图表引用或补齐对应 chart_data。",
        "business_report_tone": "把商业报告词替换成用户可读的陪伴和音乐年记表达。",
        "internal_guidance_leakage": "删除内部写作指令、confidence 标签和 prompt 约束，只保留用户可读解释。",
        "repeated_template_prose": "删除跨章节复用的元叙述，每个章节只写该章节自己的判断、证据和解释。",
        "same_entity_false_contrast": "当播放榜和个人榜实体相同时，写成热度与长留重合，不要写成两种不同偏爱。",
        "unsupported_entity_claim": "删除无证据的地域、现场感或回望归因；只能写播放数据能支撑的艺人/专辑关系。",
        "missing_story_obligations": "补充陪伴感、生活节奏、新发现和播放/个人榜单关系分析。",
        "repeated_core_fact": "删掉相邻句中重复出现的活跃日、播放次数或小时数，只保留一次并接续新的解释。",
        "missing_chart_observation": "引用图表的章节必须解释图表中的具体转折或对比。",
        "chart_prose_echo": "正文不要只复述图表观察；保留关键实体/月份/数字，并补充解释增量。",
        "generic_phrase_density": "减少陪伴、入口、声音线等泛化词，换成可核验的艺人、月份、播放量或榜单关系。",
        "duplicate_fact_home": "同一事实只能在主场章节完整展开，其他章节必须改成短引用或解释。",
        "section_role_violation": "把事实移回对应章节，或调整 editorial plan 的 fact ownership。",
        "generic_language_overuse": "减少入口、坐标、地图、声音线、陪伴等抽象词，改成具体实体和证据。",
        "data_listing_without_interpretation": "连续数字后必须补解释句，说明它代表稳定、转折、集中或长留。",
        "unsupported_life_claim": "删除无证据生活事件，只保留从播放密度、时段和持续性可推导的生活节奏分析。",
    }[code]


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "")
