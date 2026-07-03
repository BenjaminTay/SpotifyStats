"""Deterministic narrative quality gates for visual yearly report artifacts."""

from __future__ import annotations

import re
from typing import Any

GENERIC_PHRASES = (
    "年度路径",
    "声音线",
    "情绪线",
    "陪伴",
    "入口",
    "纹理",
)

CORE_FACT_PATTERNS = (
    re.compile(r"\d+\s*个活跃日"),
    re.compile(r"\d+\s*次播放"),
    re.compile(r"(?:约\s*)?\d+\s*小时"),
)

INTERPRETATION_MARKERS = (
    "说明",
    "意味着",
    "更像",
    "不是",
    "而是",
    "因此",
    "这让",
    "这使",
    "可以看见",
)

UNSUPPORTED_LIFE_EVENT_TERMS = (
    "考试",
    "分手",
    "旅行",
    "加班",
    "通勤路上",
    "下雨",
    "失眠",
)


def evaluate_visual_yearly_quality(
    artifact: dict[str, Any],
    editorial_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    chart_data = artifact.get("chart_data") if isinstance(artifact.get("chart_data"), dict) else {}

    for text in _section_texts(artifact):
        if _has_repeated_core_fact(text):
            issues.append(_issue("repeated_core_fact", "相邻句重复核心事实。"))

    for section in artifact.get("sections") or []:
        if not isinstance(section, dict):
            continue
        prose = section.get("prose")
        if not isinstance(prose, str):
            continue
        for chart_id in section.get("chart_refs") or []:
            if not isinstance(chart_id, str):
                continue
            observations = _chart_observations(chart_data, chart_id)
            has_chart_echo = any(_is_chart_echo(prose, observation) for observation in observations)
            if (
                observations
                and not has_chart_echo
                and not any(
                    _uses_chart_observation(prose, observation) for observation in observations
                )
            ):
                issues.append(
                    _issue(
                        "missing_chart_observation",
                        f"章节引用 {chart_id}，但正文没有解释该图表的具体观察。",
                    )
                )
            if has_chart_echo:
                issues.append(
                    _issue(
                        "chart_prose_echo",
                        f"章节引用 {chart_id}，但正文只复述图表观察，没有解释增量。",
                    )
                )

    full_text = "\n".join(_section_texts(artifact))
    generic_hits = sum(full_text.count(phrase) for phrase in GENERIC_PHRASES)
    if generic_hits >= 18:
        issues.append(_issue("generic_phrase_density", "抽象陪伴类词语密度过高。"))

    if editorial_plan:
        issues.extend(_editorial_plan_issues(artifact, editorial_plan))

    issue_codes = [item["code"] for item in issues]
    return {"ok": not issues, "issues": issues, "issue_codes": issue_codes}


def _section_texts(artifact: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for section in artifact.get("sections") or []:
        if not isinstance(section, dict):
            continue
        prose = section.get("prose")
        if isinstance(prose, str):
            texts.append(prose)
    return texts


def _has_repeated_core_fact(text: str) -> bool:
    sentences = [part.strip() for part in re.split(r"[。！？!?]", text) if part.strip()]
    for left, right in zip(sentences, sentences[1:]):
        shared_patterns = sum(
            1 for pattern in CORE_FACT_PATTERNS if pattern.search(left) and pattern.search(right)
        )
        if shared_patterns >= 2:
            return True
    return False


def _chart_observations(chart_data: dict[str, Any], chart_id: str) -> list[str]:
    payload = chart_data.get(chart_id)
    if not isinstance(payload, dict):
        return []
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return []
    return [item.strip() for item in observations if isinstance(item, str) and item.strip()]


def _uses_chart_observation(section_text: str, observation: str) -> bool:
    if observation in section_text:
        return _has_interpretation_marker(section_text.replace(observation, "", 1))
    tokens = _observation_tokens(observation)
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in section_text)
    return matched >= min(3, len(tokens)) and _has_interpretation_marker(section_text)


def _is_chart_echo(section_text: str, observation: str) -> bool:
    if observation not in section_text:
        return False
    return not _has_interpretation_marker(section_text.replace(observation, "", 1))


def _has_interpretation_marker(text: str) -> bool:
    return any(marker in text for marker in INTERPRETATION_MARKERS)


def _observation_tokens(observation: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(re.findall(r"\d{4}-\d{2}", observation))
    tokens.extend(re.findall(r"\d+\s*次", observation))
    tokens.extend(
        re.findall(
            r"\b[A-Z][A-Za-z0-9'&.-]*(?:\s+(?:[A-Z][A-Za-z0-9'&.-]*|of|a|the|and|de|la|van))*",
            observation,
        )
    )
    return list(dict.fromkeys(tokens))


def _editorial_plan_issues(
    artifact: dict[str, Any],
    editorial_plan: dict[str, Any],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    prose_by_role = {
        _section_role(section): str(section.get("prose") or "")
        for section in artifact.get("sections") or []
        if isinstance(section, dict)
    }
    facts = [fact for fact in editorial_plan.get("facts") or [] if isinstance(fact, dict)]
    for fact in facts:
        claim = str(fact.get("claim") or "").strip()
        home = str(fact.get("home_section_role") or "").strip()
        if len(claim) < 8 or not home:
            continue
        full_hits = [role for role, prose in prose_by_role.items() if role and claim in prose]
        if len(full_hits) > 1:
            issues.append(
                _issue(
                    "duplicate_fact_home",
                    f"事实 {fact.get('id')} 在多个章节完整复述：{', '.join(full_hits)}。",
                )
            )
        if full_hits and home not in full_hits:
            issues.append(
                _issue(
                    "section_role_violation",
                    f"事实 {fact.get('id')} 出现在 {full_hits[0]}，但主场是 {home}。",
                )
            )

    budget = (
        editorial_plan.get("language_budget")
        if isinstance(editorial_plan.get("language_budget"), dict)
        else {}
    )
    full_text = "\n".join(prose_by_role.values())
    for phrase, limit in budget.items():
        try:
            max_count = int(limit)
        except (TypeError, ValueError):
            continue
        if full_text.count(str(phrase)) > max_count:
            issues.append(
                _issue("generic_language_overuse", f"“{phrase}”超过语言预算 {max_count} 次。")
            )
    if _has_unsupported_life_claim(full_text):
        issues.append(_issue("unsupported_life_claim", "正文出现无证据生活事件推测。"))
    if _has_data_listing_without_interpretation(full_text):
        issues.append(_issue("data_listing_without_interpretation", "连续数字罗列缺少解释句。"))
    return issues


def _section_role(section: dict[str, Any]) -> str:
    return str(section.get("role") or section.get("id") or "")


def _has_unsupported_life_claim(text: str) -> bool:
    return any(term in text for term in UNSUPPORTED_LIFE_EVENT_TERMS)


def _has_data_listing_without_interpretation(text: str) -> bool:
    sentences = [part for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]
    numeric_run = 0
    for sentence in sentences:
        numberish = len(re.findall(r"\d+", sentence)) >= 2
        interpretive = _has_interpretation_marker(sentence)
        if numberish and not interpretive:
            numeric_run += 1
        else:
            numeric_run = 0
        if numeric_run >= 3:
            return True
    return False


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": "error"}
