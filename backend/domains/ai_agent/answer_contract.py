"""Deterministic, multi-dimensional quality contract for Agent answers.

The legacy critic exposes a single ``ok`` flag.  This module keeps that public
surface compatible while making the reason for acceptance explicit: an answer
must be grounded, complete, informative, constraint-compliant, and readable.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

QualityDimension = Literal[
    "grounded",
    "complete",
    "informative",
    "constraint_compliant",
    "readable",
]

_PLACEHOLDER_ANSWERS = (
    "已有可用结果",
    "已完成查询",
    "查询成功",
    "已获取结果",
    "请查看结果",
)
_RANKING_TOKENS = ("排名", "排行", "第", "Top", "TOP", "最常", "最高", "榜首")
_METRIC_TOKENS = (
    "播放次数",
    "播放时长",
    "次",
    "小时",
    "占比",
    "Power Score",
    "在榜周",
)
_COMPARISON_TOKENS = (
    "更高",
    "更低",
    "更多",
    "更少",
    "领先",
    "胜出",
    "占优",
    "相近",
    "持平",
    "不同口径",
    "分别",
    "更喜欢",
)
_TREND_TOKENS = (
    "上升",
    "下降",
    "增加",
    "减少",
    "回升",
    "回落",
    "稳定",
    "持平",
    "波动",
    "变化",
)
_LIMITATION_TOKENS = (
    "数据不足",
    "证据不足",
    "缺少",
    "缺乏",
    "未覆盖",
    "无法确定",
    "无法判断",
    "限制",
)
_SAFE_REFUSAL_TOKENS = ("不能", "无法", "不会", "不支持", "没有权限", "只读")
_SAFE_ALTERNATIVE_TOKENS = ("可以", "允许", "只读", "改为", "你可以")
_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


class AnswerDimensionResult(BaseModel):
    passed: bool = True
    applicable: bool = True
    issues: list[str] = Field(default_factory=list)


class AnswerContractResult(BaseModel):
    ok: bool
    classification: Literal["pass", "partial", "fail"]
    dimensions: dict[QualityDimension, AnswerDimensionResult]
    issues: list[str] = Field(default_factory=list)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _dimension_result(issues: list[str], *, applicable: bool = True) -> AnswerDimensionResult:
    return AnswerDimensionResult(passed=not issues, applicable=applicable, issues=issues)


def _ledger_issues(claim_ledger: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    unsupported_literals = _as_list(claim_ledger.get("unsupported_literals"))
    if unsupported_literals:
        rendered = "、".join(str(item) for item in unsupported_literals[:8])
        issues.append(f"grounded: 存在无法追溯到事实目录的数字：{rendered}")
    unsupported_semantic = _as_list(claim_ledger.get("unsupported_semantic_claims"))
    if unsupported_semantic:
        rendered_claims: list[str] = []
        for item in unsupported_semantic[:4]:
            if isinstance(item, dict):
                rendered_claims.append(str(item.get("text") or item.get("predicate") or "语义结论"))
            else:
                rendered_claims.append(str(item))
        issues.append(f"grounded: 存在无法追溯到事实目录的语义结论：{'；'.join(rendered_claims)}")
    return issues


def _obligation_satisfied(answer: str, obligation: dict[str, Any]) -> bool:
    tokens = tuple(
        item
        for item in _as_list(obligation.get("required_tokens_any"))
        if isinstance(item, str) and item
    )
    values = [str(item) for item in _as_list(obligation.get("required_values")) if item]
    tokens_ok = not tokens or _contains_any(answer, tokens)
    values_ok = not values or (
        all(value in answer for value in values) if len(values) > 1 else values[0] in answer
    )
    return tokens_ok and values_ok


def _obligation_issues(
    answer: str,
    obligations: list[dict[str, Any]],
    dimension: QualityDimension,
) -> list[str]:
    issues: list[str] = []
    for obligation in obligations:
        obligation_dimension = str(obligation.get("quality_dimension") or "constraint_compliant")
        if obligation_dimension != dimension or _obligation_satisfied(answer, obligation):
            continue
        issues.append(
            f"{dimension}: answer_obligations.{obligation.get('kind') or 'unknown'} 未满足"
        )
    return issues


def _expected_entities(payload: dict[str, Any]) -> list[str]:
    frame = _as_dict(payload.get("question_frame"))
    entities = [str(item) for item in _as_list(frame.get("entities")) if isinstance(item, str)]
    if entities:
        return entities
    winners = _as_dict(_as_dict(payload.get("analytical_brief")).get("dimension_winners"))
    return list(dict.fromkeys(str(item) for item in winners.values() if item))


def _informative_issues(answer: str, payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    stripped = answer.strip()
    if not stripped or any(stripped == placeholder for placeholder in _PLACEHOLDER_ANSWERS):
        return ["informative: 回答为空或仅报告查询状态，没有消费事实"]

    frame = _as_dict(payload.get("question_frame"))
    family = str(frame.get("family") or "")
    sufficiency = _as_dict(payload.get("evidence_sufficiency"))
    obligations = [
        item for item in _as_list(payload.get("answer_obligations")) if isinstance(item, dict)
    ]
    issues.extend(_obligation_issues(answer, obligations, "informative"))

    if family == "safety_boundary":
        if not _contains_any(answer, _SAFE_REFUSAL_TOKENS):
            issues.append("informative: 安全拒绝没有明确拒绝越界操作")
        if not _contains_any(answer, _SAFE_ALTERNATIVE_TOKENS):
            issues.append("informative: 安全拒绝没有提供边界内替代方案")
        return issues

    if sufficiency.get("sufficient") is False:
        if not _contains_any(answer, _LIMITATION_TOKENS):
            issues.append("informative: 无数据或证据不足回答没有解释缺失边界")
        return issues

    if family in {"simple_ranking", "scoped_ranking", "time_of_day_ranking"}:
        has_rank = _contains_any(answer, _RANKING_TOKENS)
        has_metric = _contains_any(answer, _METRIC_TOKENS) or bool(re.search(r"\d", answer))
        if not has_rank or not has_metric:
            issues.append("informative: 排行回答必须给出实际排名实体及排序指标")
    elif family in {"preference_comparison", "period_comparison", "identity_preference"}:
        expected_entities = _expected_entities(payload)
        if expected_entities and not all(entity in answer for entity in expected_entities):
            issues.append("informative: 比较回答没有覆盖全部比较对象")
        if not _contains_any(answer, _COMPARISON_TOKENS):
            issues.append("informative: 比较回答没有给出直接或分口径结论")
    elif family == "community_lookup":
        catalog = [item for item in _as_list(payload.get("fact_catalog")) if isinstance(item, dict)]
        subjects = [
            str(item.get("value") or "")
            for item in catalog
            if ".top_" in str(item.get("metric_name") or "")
            and str(item.get("metric_name") or "").endswith("_subject")
        ]
        if subjects and not any(subject and subject in answer for subject in subjects):
            issues.append("informative: 社区查询没有列出任何实际匹配帖子或实体")
    elif family in {"trend_preference", "change_explanation"} and not _contains_any(
        answer, _TREND_TOKENS
    ):
        issues.append("informative: 趋势回答没有说明变化方向")
    return issues


def _complete_issues(answer: str, payload: dict[str, Any]) -> list[str]:
    obligations = [
        item for item in _as_list(payload.get("answer_obligations")) if isinstance(item, dict)
    ]
    issues = _obligation_issues(answer, obligations, "complete")
    frame = _as_dict(payload.get("question_frame"))
    family = str(frame.get("family") or "")
    if family in {"preference_comparison", "period_comparison", "identity_preference"}:
        missing = [entity for entity in _expected_entities(payload) if entity not in answer]
        if missing:
            issues.append(f"complete: 比较回答缺少对象：{'、'.join(missing)}")
    return issues


def _constraint_issues(answer: str, payload: dict[str, Any]) -> list[str]:
    obligations = [
        item for item in _as_list(payload.get("answer_obligations")) if isinstance(item, dict)
    ]
    issues = _obligation_issues(answer, obligations, "constraint_compliant")
    frame = _as_dict(payload.get("question_frame"))
    excluded = [str(item) for item in _as_list(frame.get("excluded_dimensions")) if item]
    for dimension in excluded:
        if dimension.casefold() in answer.casefold():
            issues.append(f"constraint_compliant: 回答包含已排除维度 {dimension}")
    return issues


def _readability_issues(answer: str, claim_ledger: dict[str, Any]) -> list[str]:
    stripped = answer.strip()
    issues: list[str] = []
    if not stripped:
        return ["readable: 回答为空"]
    if "```" in stripped and stripped.count("```") % 2:
        issues.append("readable: Markdown 代码块未闭合")
    if "|" in stripped:
        table_lines = [line for line in stripped.splitlines() if "|" in line]
        if len(table_lines) == 1:
            issues.append("readable: Markdown 表格缺少表头或数据行")
    numeric_count = claim_ledger.get("numeric_claim_count")
    if isinstance(numeric_count, int) and numeric_count > 0:
        facts_without_units = [
            item
            for item in _as_list(claim_ledger.get("claims"))
            if isinstance(item, dict) and item.get("numeric_literals") and not item.get("fact_refs")
        ]
        if facts_without_units:
            issues.append("readable: 数字缺少可识别的事实或单位上下文")
    return issues


def evaluate_answer_contract(
    answer: str,
    final_payload: dict[str, Any],
    *,
    claim_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the five independent answer-quality dimensions.

    ``claim_ledger`` is explicit so callers can build it once and use the same
    evidence snapshot for both validation and the published result.  For a
    staged migration, a ledger embedded in ``final_payload`` is also accepted.
    """

    payload = final_payload if isinstance(final_payload, dict) else {}
    ledger = claim_ledger or _as_dict(payload.get("claim_ledger"))
    grounded_issues = _ledger_issues(ledger)
    complete_issues = _complete_issues(answer, payload)
    informative_issues = _informative_issues(answer, payload)
    constraint_issues = _constraint_issues(answer, payload)
    readable_issues = _readability_issues(answer, ledger)
    dimensions: dict[QualityDimension, AnswerDimensionResult] = {
        "grounded": _dimension_result(grounded_issues, applicable=bool(ledger)),
        "complete": _dimension_result(complete_issues),
        "informative": _dimension_result(informative_issues),
        "constraint_compliant": _dimension_result(constraint_issues),
        "readable": _dimension_result(readable_issues),
    }
    issues = [issue for result in dimensions.values() for issue in result.issues]
    failed_dimensions = sum(not result.passed for result in dimensions.values())
    classification: Literal["pass", "partial", "fail"]
    if not failed_dimensions:
        classification = "pass"
    elif dimensions["grounded"].passed and dimensions["readable"].passed:
        classification = "partial"
    else:
        classification = "fail"
    return AnswerContractResult(
        ok=not issues,
        classification=classification,
        dimensions=dimensions,
        issues=issues,
    ).model_dump()
