"""Evidence recipes for AI Agent analytical question families."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.domains.ai_agent.question_frame import QuestionFrame


class EvidenceRecipe(BaseModel):
    family: str
    required_axes: list[str] = Field(default_factory=list)
    conditional_axes: list[str] = Field(default_factory=list)
    required_tool_patterns: list[dict[str, object]] = Field(default_factory=list)
    recommended_tool_patterns: list[dict[str, object]] = Field(default_factory=list)
    required_context: dict[str, object] = Field(default_factory=dict)
    max_followup_calls: int = 4


def _ranking_metric(frame: QuestionFrame) -> str:
    if "hours" in frame.requested_metrics and "plays" not in frame.requested_metrics:
        return "hours"
    return "plays"


def recipe_for_frame(frame: QuestionFrame | dict[str, object]) -> EvidenceRecipe:
    parsed_frame = (
        frame if isinstance(frame, QuestionFrame) else QuestionFrame.model_validate(frame)
    )
    family = parsed_frame.family

    if family == "preference_comparison":
        required_axes = ["cumulative", "recency", "intensity"]
        if "personal_billboard" in parsed_frame.analysis_axes:
            required_axes.append("personal_billboard")
        return EvidenceRecipe(
            family=family,
            required_axes=required_axes,
            conditional_axes=["fairness"],
            required_tool_patterns=[
                {"tool_name": "compare_entities"},
                {"tool_name": "entity_stats", "period": "last_6_months"},
                {"tool_name": "entity_stats", "period": "last_4_weeks"},
            ],
            max_followup_calls=5,
        )

    if family == "identity_preference":
        return EvidenceRecipe(
            family=family,
            required_axes=["cumulative", "recency", "consistency", "peak"],
            conditional_axes=["personal_billboard", "fairness"],
            required_tool_patterns=[
                {"tool_name": "compare_entities"},
                {"tool_name": "entity_stats", "period": "last_6_months"},
                {"tool_name": "billboard_entity_detail"},
            ],
            recommended_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_4_weeks"},
            ],
            max_followup_calls=4,
        )

    if family == "trend_preference":
        return EvidenceRecipe(
            family=family,
            required_axes=["recency", "trend"],
            required_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_6_months"},
                {"tool_name": "analysis_charts", "period": "last_6_months"},
            ],
            max_followup_calls=3,
        )

    if family == "period_comparison":
        return EvidenceRecipe(
            family=family,
            required_axes=["period", "ranking"],
            required_tool_patterns=[
                {"tool_name": "analysis_charts"},
                {"tool_name": "wrapped_yearly"},
            ],
            max_followup_calls=3,
        )

    if family == "change_explanation":
        return EvidenceRecipe(
            family=family,
            required_axes=["trend", "recency", "ranking"],
            required_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_6_months"},
                {"tool_name": "entity_stats", "period": "last_4_weeks"},
                {"tool_name": "analysis_charts", "period": "last_6_months"},
            ],
            max_followup_calls=4,
        )

    if family == "time_of_day_ranking":
        return EvidenceRecipe(
            family=family,
            required_axes=["time_of_day", "ranking"],
            required_tool_patterns=[{"tool_name": "listening_hours", "view": "late_night_tracks"}],
            max_followup_calls=1,
        )

    if family == "scoped_ranking":
        scope_entity_name = parsed_frame.scope_entity_name or (
            parsed_frame.entities[0] if parsed_frame.entities else ""
        )
        return EvidenceRecipe(
            family=family,
            required_axes=["scope", "cumulative", "ranking"],
            conditional_axes=["recency"],
            required_tool_patterns=[
                {"tool_name": "entity_stats", "entity": "artist", "period": "lifetime"}
            ],
            recommended_tool_patterns=[
                {"tool_name": "entity_stats", "entity": "artist", "period": "last_6_months"},
                {"tool_name": "billboard_entity_detail", "entity": "artist"},
            ],
            required_context={
                "scope_entity_type": parsed_frame.scope_entity_type or "artist",
                "scope_entity_name": scope_entity_name,
                "target_entity_types": parsed_frame.target_entity_types,
                "metric": _ranking_metric(parsed_frame),
            },
            max_followup_calls=3,
        )

    if family == "simple_ranking":
        return EvidenceRecipe(
            family=family,
            required_axes=["ranking"],
            required_tool_patterns=[{"tool_name": "analysis_charts"}],
            recommended_tool_patterns=[{"tool_name": "wrapped_yearly"}],
            required_context={
                "entity_type": parsed_frame.entity_type,
                "time_scope": parsed_frame.time_scope,
                "metric": _ranking_metric(parsed_frame),
            },
            max_followup_calls=2,
        )

    if family == "entity_detail":
        required_axes = ["detail", "cumulative"]
        required_tool_patterns: list[dict[str, object]] = [{"tool_name": "entity_stats"}]
        if "personal_billboard" in parsed_frame.analysis_axes:
            required_axes.append("personal_billboard")
            required_tool_patterns.append({"tool_name": "billboard_entity_detail"})
        return EvidenceRecipe(
            family=family,
            required_axes=required_axes,
            required_tool_patterns=required_tool_patterns,
            max_followup_calls=3,
        )

    return EvidenceRecipe(
        family=family,
        required_axes=["behavior", "cumulative"],
        required_tool_patterns=[
            {"tool_name": "analysis_stats"},
            {"tool_name": "listening_hours"},
        ],
        max_followup_calls=3,
    )
