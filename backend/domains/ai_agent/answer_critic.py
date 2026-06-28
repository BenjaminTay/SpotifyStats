"""Deterministic final-answer critique for AI Agent responses."""

from __future__ import annotations

from typing import Any

EXTERNAL_BILLBOARD_TOKENS = (
    "Billboard 市场",
    "市场影响力",
    "商业成绩",
    "权威榜单",
    "外部官方 Billboard",
    "官方 Billboard",
)

PERSONAL_BILLBOARD_QUALIFIERS = (
    "个人 Billboard",
    "个人Billboard",
    "本地个人榜单",
    "个人榜单",
    "本地播放数据",
    "个人播放数据",
)

MISSING_DATA_TOKENS = (
    "数据不足",
    "证据不足",
    "缺少",
    "缺乏",
    "未查询",
    "没有查询",
    "无法比较",
)

NEGATION_TOKENS = ("不是", "不能", "不代表", "不等于", "无法说明", "不能说明")


def _sentences(answer: str) -> list[str]:
    normalized = answer
    for punctuation in ("。", "；", ";", "，", ",", "\n"):
        normalized = normalized.replace(punctuation, "\n")
    return [part.strip() for part in normalized.splitlines() if part.strip()]


def _coverage_found_entities(coverage: Any) -> list[str]:
    if not isinstance(coverage, dict):
        return []
    entities = coverage.get("entities")
    if not isinstance(entities, dict):
        return []
    found_entities: list[str] = []
    for entity_name, tool_statuses in entities.items():
        if not isinstance(entity_name, str) or not isinstance(tool_statuses, dict):
            continue
        if any(status == "found" for status in tool_statuses.values()):
            found_entities.append(entity_name)
    return found_entities


def _missing_claim_targets_entity(sentence: str, entity_name: str) -> bool:
    entity_index = sentence.find(entity_name)
    if entity_index < 0:
        return False
    after_entity = sentence[entity_index : entity_index + len(entity_name) + 24]
    before_entity = sentence[max(0, entity_index - 12) : entity_index + len(entity_name)]
    direct_missing_tokens = tuple(
        token for token in MISSING_DATA_TOKENS if token not in {"无法比较"}
    )
    if any(token in after_entity for token in direct_missing_tokens):
        return True
    return any(token in before_entity for token in ("缺少", "缺乏", "未查询", "没有查询"))


def _compare_entities_globally_found(coverage: Any) -> bool:
    if not isinstance(coverage, dict):
        return False
    comparison = coverage.get("comparison")
    return isinstance(comparison, dict) and comparison.get("compare_entities") == "found"


def _is_negated_external_billboard_sentence(sentence: str) -> bool:
    return any(token in sentence for token in NEGATION_TOKENS)


def critique_answer(answer: str, final_payload: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic answer issues without calling external services."""
    issues: list[str] = []
    for sentence in _sentences(answer):
        if not any(token in sentence for token in EXTERNAL_BILLBOARD_TOKENS):
            continue
        if _is_negated_external_billboard_sentence(sentence):
            continue
        if not any(qualifier in sentence for qualifier in PERSONAL_BILLBOARD_QUALIFIERS):
            issues.append(
                "回答把 SpotifyStats 个人 Billboard 表述成外部官方 Billboard 或市场成绩。"
            )
            break

    coverage = final_payload.get("coverage") if isinstance(final_payload, dict) else {}
    found_entities = _coverage_found_entities(coverage)
    compare_found = _compare_entities_globally_found(coverage)
    for sentence in _sentences(answer):
        if not any(token in sentence for token in MISSING_DATA_TOKENS):
            continue
        contradicted_entities = [
            entity for entity in found_entities if _missing_claim_targets_entity(sentence, entity)
        ]
        if contradicted_entities:
            issues.append(
                f"{'、'.join(contradicted_entities)} 已查到 found 证据，但回答声称数据不足或未查询。"
            )
            break
        if compare_found:
            issues.append("compare_entities 已 found，但回答声称数据不足、未查询或无法比较。")
            break

    return {"ok": len(issues) == 0, "issues": issues}
