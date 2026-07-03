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

HARD_MISSING_DATA_TOKENS = (
    "数据不足",
    "缺少",
    "缺乏",
    "未查询",
    "没有查询",
    "无法比较",
)

NEGATION_TOKENS = (
    "不是",
    "不能",
    "不代表",
    "不等于",
    "无法",
    "不要",
    "不应",
    "不宜",
    "并非",
    "不完全",
)

LOCAL_BILLBOARD_BOUNDARY_TOKENS = (
    "个人 Billboard",
    "个人Billboard",
    "本地个人榜单",
    "SpotifyStats Billboard",
    "个人榜单",
)

LIMITATION_TOKENS = (
    "限制",
    "证据不足",
    "数据不足",
    "缺失证据",
    "缺少证据",
    "缺乏证据",
    "无法确定",
    "无法判断",
    "不能确定",
    "不能断定",
    "只能说",
    "目前只能",
)

SINGLE_WINNER_TOKENS = (
    "明显胜出",
    "明显更胜",
    "均指向",
    "都指向",
    "毫无疑问",
    "完全",
    "单方胜出",
    "单方明显胜出",
)

INSUFFICIENT_CONFIDENCE_TOKENS = (
    "明显",
    "确定",
    "更甚",
    "毫无疑问",
    "均指向",
    "都指向",
)

METRIC_LAYERING_TOKENS = (
    "分口径",
    "不同口径",
    "长期",
    "近期",
    "强度",
    "累计",
    "最近",
    "播放次数",
    "Power Score",
)

SAFE_REFUSAL_TOKENS = (
    "只读",
    "不能",
    "无法",
    "不会",
    "不支持",
    "没有权限",
)

WRITE_OPERATION_TOKENS = (
    "删除",
    "修改",
    "写入",
    "更新",
    "导入",
    "设置",
    "执行",
    "写操作",
)


def _sentences(answer: str) -> list[str]:
    normalized = answer
    for punctuation in ("。", "；", ";", "，", ",", "\n"):
        normalized = normalized.replace(punctuation, "\n")
    return [part.strip() for part in normalized.splitlines() if part.strip()]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _sentence_has_unnegated_token(sentence: str, token: str) -> bool:
    start = 0
    while True:
        index = sentence.find(token, start)
        if index < 0:
            return False
        before_token = sentence[max(0, index - 8) : index]
        token_context = sentence[max(0, index - 8) : index + len(token)]
        if not any(
            negation in token_context or negation in before_token for negation in NEGATION_TOKENS
        ):
            return True
        start = index + len(token)


def _has_unnegated_any(sentence: str, tokens: tuple[str, ...]) -> bool:
    return any(_sentence_has_unnegated_token(sentence, token) for token in tokens)


def _brief(final_payload: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(final_payload.get("analytical_brief"))


def _evidence_sufficiency(final_payload: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(final_payload.get("evidence_sufficiency"))


def _question_frame(final_payload: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(final_payload.get("question_frame"))


def _must_explain_requires(must_explain: list[str], token: str) -> bool:
    return any(token in item for item in must_explain)


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


def _global_missing_claim_conflicts_with_found(
    sentence: str,
    evidence_sufficiency: dict[str, Any],
) -> bool:
    if any(token in sentence for token in HARD_MISSING_DATA_TOKENS):
        return True
    if "证据不足" in sentence and evidence_sufficiency.get("sufficient") is not False:
        return True
    return False


def _check_forbidden_claims(answer: str, analytical_brief: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    forbidden_claims = _as_str_list(analytical_brief.get("forbidden_claims"))
    for claim in forbidden_claims:
        if any(_sentence_has_unnegated_token(sentence, claim) for sentence in _sentences(answer)):
            issues.append(f"回答出现 analytical_brief.forbidden_claims 禁止表述：{claim}")
            break
    return issues


def _conflict_answer_mentions_layered_evidence(
    answer: str,
    analytical_brief: dict[str, Any],
) -> bool:
    dimension_winners = analytical_brief.get("dimension_winners")
    winners: set[str] = set()
    if isinstance(dimension_winners, dict):
        winners = {str(value) for value in dimension_winners.values() if value}
    mentioned_winners = {winner for winner in winners if winner in answer}
    has_layering_language = _contains_any(answer, METRIC_LAYERING_TOKENS)
    has_limitation_language = _contains_any(answer, LIMITATION_TOKENS)
    if len(winners) >= 2:
        return len(mentioned_winners) >= 2 and has_layering_language
    return has_layering_language and has_limitation_language


def _check_conflict_contract(answer: str, analytical_brief: dict[str, Any]) -> list[str]:
    if analytical_brief.get("conflict") is not True:
        return []
    for sentence in _sentences(answer):
        if _has_unnegated_any(sentence, SINGLE_WINNER_TOKENS):
            return ["analytical_brief.conflict=true，但回答给出过度单一结论。"]
    if not _conflict_answer_mentions_layered_evidence(answer, analytical_brief):
        return ["analytical_brief.conflict=true，但回答没有呈现多口径冲突证据。"]
    return []


def _check_must_explain_contract(answer: str, analytical_brief: dict[str, Any]) -> list[str]:
    must_explain = _as_str_list(analytical_brief.get("must_explain"))
    issues: list[str] = []
    if _must_explain_requires(must_explain, "本地个人榜单") and not _contains_any(
        answer,
        LOCAL_BILLBOARD_BOUNDARY_TOKENS,
    ):
        issues.append("analytical_brief.must_explain 要求说明本地个人榜单边界。")
    if _must_explain_requires(must_explain, "不同口径胜者不一致") and not _contains_any(
        answer,
        METRIC_LAYERING_TOKENS,
    ):
        issues.append("analytical_brief.must_explain 要求解释不同口径胜者不一致。")
    return issues


def _check_insufficient_evidence_contract(
    answer: str,
    evidence_sufficiency: dict[str, Any],
    question_frame: dict[str, Any],
) -> list[str]:
    if evidence_sufficiency.get("sufficient") is not False:
        return []
    if question_frame.get("family") == "safety_boundary" and _is_clear_safe_refusal(answer):
        return []
    issues: list[str] = []
    if not _contains_any(answer, LIMITATION_TOKENS):
        issues.append("evidence_sufficiency.sufficient=false，但回答没有说明限制或证据不足。")
    for sentence in _sentences(answer):
        if _has_unnegated_any(sentence, INSUFFICIENT_CONFIDENCE_TOKENS):
            issues.append("证据不足时回答使用了强确定单一结论。")
            break
    return issues


def _is_clear_safe_refusal(answer: str) -> bool:
    return _contains_any(answer, SAFE_REFUSAL_TOKENS) and (
        _contains_any(answer, WRITE_OPERATION_TOKENS) or "只读" in answer
    )


def _answer_obligations(final_payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = final_payload.get("answer_obligations")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _obligation_values_satisfied(answer: str, values: list[Any]) -> bool:
    required_values = [str(value) for value in values if value]
    if not required_values:
        return True
    if len(required_values) >= 2:
        return all(value in answer for value in required_values)
    return any(value in answer for value in required_values)


def _check_answer_obligations(answer: str, final_payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for obligation in _answer_obligations(final_payload):
        kind = str(obligation.get("kind") or "unknown")
        tokens = tuple(
            token
            for token in obligation.get("required_tokens_any", [])
            if isinstance(token, str) and token
        )
        values = obligation.get("required_values")
        if not isinstance(values, list):
            values = []
        tokens_ok = True if not tokens else _contains_any(answer, tokens)
        values_ok = _obligation_values_satisfied(answer, values)
        if kind == "readonly_refusal" and _is_clear_safe_refusal(answer):
            continue
        if not tokens_ok or not values_ok:
            issues.append(f"answer_obligations.{kind} 未满足。")
    return issues


def critique_answer(answer: str, final_payload: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic answer issues without calling external services."""
    issues: list[str] = []
    if not isinstance(final_payload, dict):
        final_payload = {}
    analytical_brief = _brief(final_payload)
    question_frame = _question_frame(final_payload)
    issues.extend(_check_forbidden_claims(answer, analytical_brief))
    issues.extend(_check_conflict_contract(answer, analytical_brief))
    issues.extend(_check_must_explain_contract(answer, analytical_brief))
    issues.extend(
        _check_insufficient_evidence_contract(
            answer,
            _evidence_sufficiency(final_payload),
            question_frame,
        )
    )
    issues.extend(_check_answer_obligations(answer, final_payload))

    for sentence in _sentences(answer):
        if not _has_unnegated_any(sentence, EXTERNAL_BILLBOARD_TOKENS):
            continue
        if not any(qualifier in sentence for qualifier in PERSONAL_BILLBOARD_QUALIFIERS):
            issues.append(
                "回答把 SpotifyStats 个人 Billboard 表述成外部官方 Billboard 或市场成绩。"
            )
            break

    coverage = final_payload.get("coverage") if isinstance(final_payload, dict) else {}
    evidence_sufficiency = _evidence_sufficiency(final_payload)
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
        if compare_found and _global_missing_claim_conflicts_with_found(
            sentence,
            evidence_sufficiency,
        ):
            issues.append("compare_entities 已 found，但回答声称数据不足、未查询或无法比较。")
            break

    return {"ok": len(issues) == 0, "issues": issues}
