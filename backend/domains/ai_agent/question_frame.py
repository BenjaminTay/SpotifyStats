"""Deterministic analytical framing for AI Agent questions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

from backend.domains.ai_agent.question_intent import QuestionIntent

QuestionFamily = Literal[
    "simple_ranking",
    "entity_detail",
    "preference_comparison",
    "trend_preference",
    "period_comparison",
    "change_explanation",
    "time_of_day_ranking",
    "identity_preference",
    "habit_summary",
]

AnalysisAxis = Literal[
    "cumulative",
    "recency",
    "intensity",
    "personal_billboard",
    "fairness",
    "trend",
    "period",
    "time_of_day",
    "ranking",
    "detail",
    "consistency",
    "peak",
    "behavior",
]

AnswerContract = Literal[
    "simple_rank_answer",
    "entity_detail_answer",
    "layered_preference_comparison",
    "trend_answer",
    "period_comparison_answer",
    "change_explanation_answer",
    "time_of_day_answer",
    "identity_preference_answer",
    "habit_summary_answer",
]


class QuestionFrame(BaseModel):
    family: QuestionFamily
    task_type: str = "general"
    entity_type: str = "unknown"
    entities: list[str] = Field(default_factory=list)
    time_scope: str = "lifetime"
    requested_metrics: list[str] = Field(default_factory=list)
    analysis_axes: list[AnalysisAxis] = Field(default_factory=list)
    answer_contract: AnswerContract
    requires_layered_conclusion: bool = False


def _contains_any(question: str, tokens: Sequence[str]) -> bool:
    lower_question = question.casefold()
    return any(token.casefold() in lower_question for token in tokens)


def _dedupe_axes(axes: list[AnalysisAxis]) -> list[AnalysisAxis]:
    deduped: list[AnalysisAxis] = []
    for axis in axes:
        if axis not in deduped:
            deduped.append(axis)
    return deduped


def _family(question: str, intent: QuestionIntent) -> QuestionFamily:
    if _contains_any(question, ("是否就代表", "是不是就代表", "等于最喜欢", "代表最喜欢")):
        return "habit_summary"
    if _contains_any(question, ("本命", "真爱", "核心偏好")):
        return "identity_preference"
    if _contains_any(question, ("为什么", "原因")) and _contains_any(
        question,
        ("下降", "掉", "回落", "变少", "减少"),
    ):
        return "change_explanation"
    if _contains_any(question, ("今年和去年", "去年和今年", "相比去年", "对比去年")):
        return "period_comparison"
    if "time_of_day" in intent.requested_metrics:
        return "time_of_day_ranking"
    if intent.task_type == "comparison" and (
        _contains_any(question, ("更喜欢", "喜爱", "更甚", "最爱", "喜欢程度"))
        or "plays" in intent.requested_metrics
    ):
        return "preference_comparison"
    if intent.task_type == "trend":
        return "trend_preference"
    if intent.task_type == "ranking":
        return "simple_ranking"
    if intent.task_type == "entity_detail":
        return "entity_detail"
    return "habit_summary"


def _axes_for_family(family: QuestionFamily, intent: QuestionIntent) -> list[AnalysisAxis]:
    if family == "preference_comparison":
        axes: list[AnalysisAxis] = ["cumulative", "recency", "intensity"]
        if "personal_billboard" in intent.requested_metrics:
            axes.append("personal_billboard")
        if intent.needs_fairness_note or len(intent.entities) >= 2:
            axes.append("fairness")
        return _dedupe_axes(axes)
    if family == "identity_preference":
        return ["cumulative", "recency", "consistency", "peak", "personal_billboard", "fairness"]
    if family == "trend_preference":
        return ["recency", "trend"]
    if family == "period_comparison":
        return ["period", "ranking"]
    if family == "change_explanation":
        return ["trend", "recency", "ranking"]
    if family == "time_of_day_ranking":
        return ["time_of_day", "ranking"]
    if family == "simple_ranking":
        return ["ranking"]
    if family == "entity_detail":
        detail_axes: list[AnalysisAxis] = ["detail", "cumulative"]
        if "personal_billboard" in intent.requested_metrics:
            detail_axes.append("personal_billboard")
        return detail_axes
    return ["behavior", "cumulative"]


def _contract_for_family(family: QuestionFamily) -> AnswerContract:
    contracts: dict[QuestionFamily, AnswerContract] = {
        "simple_ranking": "simple_rank_answer",
        "entity_detail": "entity_detail_answer",
        "preference_comparison": "layered_preference_comparison",
        "trend_preference": "trend_answer",
        "period_comparison": "period_comparison_answer",
        "change_explanation": "change_explanation_answer",
        "time_of_day_ranking": "time_of_day_answer",
        "identity_preference": "identity_preference_answer",
        "habit_summary": "habit_summary_answer",
    }
    return contracts[family]


def _entity_type_for_family(family: QuestionFamily, intent: QuestionIntent) -> str:
    if family == "identity_preference" and intent.entity_type == "unknown":
        return "artist"
    return intent.entity_type


def build_question_frame(
    question: str, intent: QuestionIntent | dict[str, object]
) -> QuestionFrame:
    parsed_intent = (
        intent if isinstance(intent, QuestionIntent) else QuestionIntent.model_validate(intent)
    )
    family = _family(question, parsed_intent)
    return QuestionFrame(
        family=family,
        task_type=parsed_intent.task_type,
        entity_type=_entity_type_for_family(family, parsed_intent),
        entities=parsed_intent.entities,
        time_scope=parsed_intent.time_scope,
        requested_metrics=parsed_intent.requested_metrics,
        analysis_axes=_axes_for_family(family, parsed_intent),
        answer_contract=_contract_for_family(family),
        requires_layered_conclusion=family in {"preference_comparison", "identity_preference"},
    )
