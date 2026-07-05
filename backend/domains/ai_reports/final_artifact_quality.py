"""Final user-visible quality checks for visual yearly artifacts."""

from __future__ import annotations

import re
from typing import Any

INTERNAL_BRIEF_PATTERNS = (
    re.compile(r"(?:^|\n)展示.{0,80}(播放量|个人榜单|偏好|关系|证据|趋势)", re.MULTILINE),
    re.compile(r"(?:^|\n)解释播放领先", re.MULTILINE),
    re.compile(r"(?:^|\n)揭示偏好深度", re.MULTILINE),
    re.compile(r"(?:^|\n)说明偏好会在特定月份", re.MULTILINE),
    re.compile(r"(chart_refs|evidence_refs|interpretation_guidance|safe_speculation_rules)"),
)

PLACEHOLDER_PATTERN = re.compile(r"\b(undefined|null|nan|unknown)\b", re.IGNORECASE)


def final_visible_artifact_text(artifact: dict[str, Any]) -> str:
    """Return the text a user can see in the visual yearly artifact."""
    chart_specs = _chart_specs_by_id(artifact)
    chart_data = _dict(artifact.get("chart_data"))
    parts: list[str] = [
        str(artifact.get("title") or ""),
        str(artifact.get("subtitle") or ""),
    ]
    for card in _list(artifact.get("insight_cards")):
        parts.extend(
            [
                str(card.get("label") or ""),
                str(card.get("value") or ""),
                str(card.get("caption") or ""),
            ]
        )
    rendered_charts: set[str] = set()
    for section in _list(artifact.get("sections")):
        parts.extend(
            [
                str(section.get("heading") or ""),
                str(section.get("deck") or ""),
                str(section.get("prose") or ""),
                str(section.get("pull_quote") or ""),
            ]
        )
        for chart_id in _chart_refs(section):
            if chart_id in rendered_charts:
                continue
            rendered_charts.add(chart_id)
            spec = chart_specs.get(chart_id)
            if spec:
                parts.append(str(spec.get("title") or ""))
            data_key = str(_dict(spec).get("data_key") or chart_id)
            parts.extend(
                _chart_observations(_dict(chart_data.get(chart_id) or chart_data.get(data_key)))
            )
    return "\n".join(part for part in parts if part).strip()


def evaluate_final_artifact_quality(
    artifact: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    visible_text = final_visible_artifact_text(artifact)
    sections = _list(artifact.get("sections"))
    context = context or {}

    issues.extend(_internal_brief_issues(artifact, sections))
    issues.extend(_duplicate_section_issues(sections))
    issues.extend(_repeated_paragraph_issues(sections))
    issues.extend(_duplicate_chart_ref_issues(sections))
    issues.extend(_conflicting_play_count_issues(visible_text))
    issues.extend(_unsupported_entity_alias_issues(visible_text, context))
    issues.extend(_partial_year_language_issues(artifact, visible_text, context))

    placeholders = sorted(
        set(match.group(0) for match in PLACEHOLDER_PATTERN.finditer(visible_text))
    )
    if placeholders:
        issues.append(
            _issue(
                "placeholder_token",
                "最终可见文本包含占位符：" + ", ".join(placeholders),
            )
        )

    metadata = _dict(artifact.get("metadata"))
    if issues and (
        metadata.get("writer_pipeline_status") == "accepted"
        or _dict(metadata.get("taste_score")).get("ok") is True
        or metadata.get("critic_passed") is True
    ):
        issues.append(
            _issue(
                "misleading_quality_metadata",
                "最终可见文本未通过质量门禁，但 metadata 仍显示 accepted/critic/taste 通过。",
            )
        )

    return {
        "ok": not issues,
        "issues": issues,
        "visible_text_length": len(visible_text),
    }


def _internal_brief_issues(
    artifact: dict[str, Any], sections: list[dict[str, Any]]
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for section in sections:
        text = "\n".join(
            str(section.get(key) or "") for key in ("heading", "deck", "prose", "pull_quote")
        )
        for pattern in INTERNAL_BRIEF_PATTERNS:
            if pattern.search(text.strip()):
                issues.append(
                    _issue(
                        "internal_brief_leakage",
                        f"章节 {section.get('id') or section.get('heading') or 'unknown'} 泄漏内部 brief 语言。",
                    )
                )
                break
    for card in _list(artifact.get("insight_cards")):
        text = "\n".join(str(card.get(key) or "") for key in ("label", "value", "caption"))
        for pattern in INTERNAL_BRIEF_PATTERNS:
            if pattern.search(text.strip()):
                issues.append(
                    _issue(
                        "internal_brief_leakage",
                        f"洞察卡片 {card.get('id') or card.get('label') or 'unknown'} 泄漏内部 brief 语言。",
                    )
                )
                break
    return issues


def _duplicate_section_issues(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        prose = str(section.get("prose") or "")
        signature = _section_signature(prose)
        if not signature:
            continue
        previous = seen.get(signature)
        if previous:
            issues.append(
                _issue(
                    "duplicate_section_text",
                    f"章节 {previous} 与 {section_id} 的正文高度重复。",
                )
            )
        else:
            seen[signature] = section_id
    return issues


def _repeated_paragraph_issues(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        chunks = _paragraph_signatures(str(section.get("prose") or ""))
        seen: set[str] = set()
        for chunk in chunks:
            if chunk in seen:
                issues.append(
                    _issue(
                        "repeated_section_paragraph",
                        f"章节 {section_id} 内部重复了同一段或同一句正文。",
                    )
                )
                break
            seen.add(chunk)
    return issues


def _duplicate_chart_ref_issues(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    owner: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        for chart_id in _chart_refs(section):
            previous = owner.get(chart_id)
            if previous:
                issues.append(
                    _issue(
                        "duplicate_chart_ref",
                        f"图表 {chart_id} 同时被章节 {previous} 与 {section_id} 引用。",
                    )
                )
            else:
                owner[chart_id] = section_id
    return issues


def _conflicting_play_count_issues(text: str) -> list[dict[str, str]]:
    counts: dict[str, set[int]] = {}
    for name, count in _entity_play_count_mentions(text):
        if not name or count <= 0:
            continue
        counts.setdefault(name.casefold(), set()).add(count)
    return [
        _issue(
            "conflicting_entity_play_count",
            f"同一实体 {name_key} 在最终文本中出现多个播放次数："
            + ", ".join(str(value) for value in sorted(values)),
        )
        for name_key, values in counts.items()
        if len(values) > 1
    ]


def _unsupported_entity_alias_issues(
    text: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    del context
    unsupported_aliases = {
        "Zhang Zhen Yue": ("张真源",),
    }
    issues: list[dict[str, str]] = []
    for canonical, aliases in unsupported_aliases.items():
        for alias in aliases:
            if alias in text:
                issues.append(
                    _issue(
                        "unsupported_entity_alias",
                        f"最终文本把 {canonical} 写成了未受支持的别名 {alias}。",
                    )
                )
    return issues


def _partial_year_language_issues(
    artifact: dict[str, Any],
    visible_text: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    period = _dict(context.get("reporting_period"))
    artifact_period = _dict(artifact.get("period"))
    is_partial_year = bool(period.get("is_partial_year") or artifact_period.get("is_partial_year"))
    if not is_partial_year:
        return []
    chart_text = "\n".join(
        "\n".join(
            str(spec.get(key) or "")
            for key in ("title", "narrative_question", "insight", "fallback")
        )
        for spec in _list(artifact.get("chart_specs"))
    )
    full_text = "\n".join([visible_text, chart_text])
    forbidden = [
        term
        for term in ("全年陪伴密度", "年度高光日", "年度声音线索", "这一年")
        if term in full_text
    ]
    if not forbidden:
        return []
    return [
        _issue(
            "partial_year_full_year_language",
            "部分年份报告包含完整年份措辞：" + ", ".join(forbidden),
        )
    ]


def _section_signature(prose: str) -> str:
    text = re.sub(r"\s+", "", prose)
    if len(text) < 40:
        return ""
    return text[:120]


def _paragraph_signatures(prose: str) -> list[str]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", prose) if chunk.strip()]
    if len(chunks) <= 1:
        chunks = [
            chunk.strip()
            for chunk in re.split(r"(?<=[。！？!?])", prose)
            if len(chunk.strip()) >= 18
        ]
    signatures: list[str] = []
    for chunk in chunks:
        compact = re.sub(r"\s+", "", chunk)
        if len(compact) >= 24:
            signatures.append(compact[:160])
    return signatures


def _entity_play_count_mentions(text: str) -> list[tuple[str, int]]:
    mentions: list[tuple[str, int]] = []
    for match in re.finditer(
        r"([^。！？!?；;\n]{1,80}?)(?:以|是|为|达到|播放)?\s*(\d{1,5})\s*次播放", text
    ):
        name = _clean_count_entity_name(match.group(1))
        if name:
            mentions.append((name, int(match.group(2))))
    return mentions


def _clean_count_entity_name(value: str) -> str:
    value = re.sub(r"^[，,。；;：:\s]*(?:后文又写|其中|而|但|此外|单曲层面)?", "", value).strip()
    latin_matches = re.findall(r"[A-Za-z][A-Za-z0-9'’.,:!?&() -]{1,80}", value)
    if latin_matches:
        return latin_matches[-1].strip(" ，,。；;：:")
    value = re.sub(r".*[：:，,]\s*", "", value).strip()
    value = re.sub(r"^(?:后文又写|其中|而|但|此外|单曲层面)", "", value).strip()
    return value[:40].strip(" ，,。；;：:")


def _chart_refs(section: dict[str, Any]) -> list[str]:
    return [str(ref) for ref in section.get("chart_refs") or [] if str(ref).strip()]


def _chart_specs_by_id(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(spec.get("id")): spec for spec in _list(artifact.get("chart_specs")) if spec.get("id")
    }


def _chart_observations(data: dict[str, Any]) -> list[str]:
    observations = data.get("observations")
    if not isinstance(observations, list):
        return []
    return [str(item).strip() for item in observations if str(item).strip()]


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": "error"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]
