from backend.domains.agent_runtime.constraint_patch import (
    CONSTRAINT_PATCH_SCHEMA_VERSION,
    ConstraintPatch,
    build_constraint_patch,
    constraint_fingerprint,
    merge_constraint_patch,
    validate_constraint_patch,
)

TEMPORAL = {
    "today": "2026-08-31",
    "data_start_date": "2020-01-01",
    "data_end_date": "2026-08-21",
    "latest_play_date": "2026-08-21",
}


def _state() -> dict:
    return {
        "version": 1,
        "active_question": "比较 Album A 和 Album B 的播放次数与个人 Billboard",
        "entities": ["Album A", "Album B"],
        "time_range": {"period": "lifetime"},
        "metrics": ["plays", "personal_billboard"],
        "dimensions": ["ranking", "personal_billboard"],
        "excluded_dimensions": [],
        "filters": {"include_billboard": True},
        "pending_requirements": [],
    }


def test_mixed_steering_replaces_time_excludes_billboard_and_keeps_hours() -> None:
    patch = build_constraint_patch(
        input_type="steer",
        content="只看今年，不要看 Billboard，再比较播放时长",
        temporal_context=TEMPORAL,
        current_state=_state(),
    )
    result = merge_constraint_patch(_state(), patch)

    assert patch.schema_version == CONSTRAINT_PATCH_SCHEMA_VERSION
    assert patch.operation == "replace"
    assert "hours" in patch.metrics
    assert "personal_billboard" in patch.excluded_dimensions
    assert result.validation.decision == "apply"
    assert result.state["time_range"]["start_date"] == "2026-01-01"
    assert result.state["time_range"]["end_date"] == "2026-08-21"
    assert result.state["filters"]["include_billboard"] is False
    assert result.evidence_invalidated is True


def test_correction_uses_second_year_and_clips_to_observed_data() -> None:
    patch = build_constraint_patch(
        input_type="steer",
        content="不是 2025 年，是 2024 年",
        temporal_context=TEMPORAL,
        current_state=_state(),
    )

    assert patch.requested_time_range is not None
    assert patch.requested_time_range.start_date == "2024-01-01"
    assert patch.requested_time_range.end_date == "2024-12-31"
    assert patch.unresolved_references == []


def test_ambiguous_reference_requires_clarification_and_preserves_state() -> None:
    state = _state()
    patch = build_constraint_patch(
        input_type="steer",
        content="把它换成 Album C",
        temporal_context=TEMPORAL,
        current_state=state,
    )
    validation = validate_constraint_patch(patch, current_state=state)
    result = merge_constraint_patch(state, patch)

    assert validation.decision == "clarify"
    assert validation.high_risk_ambiguity is True
    assert result.constraints_changed is False
    assert result.state["entities"] == state["entities"]


def test_reset_restores_explicit_baseline_and_changes_fingerprint() -> None:
    state = _state()
    baseline = {
        **state,
        "metrics": ["plays"],
        "excluded_dimensions": [],
        "filters": {"include_billboard": False},
    }
    result = merge_constraint_patch(
        state,
        ConstraintPatch(operation="reset"),
        reset_state=baseline,
    )

    assert result.validation.decision == "apply"
    assert result.state["metrics"] == ["plays"]
    assert result.state["filters"]["include_billboard"] is False
    assert result.previous_fingerprint != result.constraint_fingerprint


def test_constraint_fingerprint_is_order_independent() -> None:
    left = _state()
    right = {**_state(), "entities": ["Album B", "Album A"]}

    assert constraint_fingerprint(left) == constraint_fingerprint(right)
