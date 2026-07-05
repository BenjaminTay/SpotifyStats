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


def evaluate_final_artifact_quality(artifact: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    visible_text = final_visible_artifact_text(artifact)
    sections = _list(artifact.get("sections"))

    issues.extend(_internal_brief_issues(artifact, sections))
    issues.extend(_duplicate_section_issues(sections))
    issues.extend(_duplicate_chart_ref_issues(sections))

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


def _section_signature(prose: str) -> str:
    text = re.sub(r"\s+", "", prose)
    if len(text) < 40:
        return ""
    return text[:120]


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
