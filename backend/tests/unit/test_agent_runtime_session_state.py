from backend.domains.agent_runtime.session_state import (
    apply_session_input,
    filters_for_session_state,
    initial_session_state,
    restore_session_state,
)

TEMPORAL_CONTEXT = {
    "today": "2026-08-31",
    "data_start_date": "2020-01-01",
    "data_end_date": "2026-08-21",
    "latest_play_date": "2026-08-21",
}


def _initial_state():
    return initial_session_state(
        {"question": "比较 Taylor Swift 和 Olivia Rodrigo 的播放次数"},
        default_filters={
            "period": "lifetime",
            "music_only": True,
            "merge_enabled": True,
            "include_billboard": False,
        },
        temporal_context=TEMPORAL_CONTEXT,
    )


def test_session_state_applies_replace_add_and_remove_semantics() -> None:
    state = _initial_state()

    replaced = apply_session_input(
        state,
        input_type="steer",
        content="只看今年",
        temporal_context=TEMPORAL_CONTEXT,
    )
    assert replaced.action == "replace_constraints"
    assert replaced.state.time_range["period"] == "custom"
    assert replaced.state.time_range["label"] == "今年"
    assert replaced.state.time_range["start_date"] == "2026-01-01"
    assert replaced.state.time_range["end_date"] == "2026-08-21"
    assert replaced.state.time_range["requested_end_date"] == "2026-12-31"
    assert replaced.state.time_range["coverage_clipped"] is True

    added = apply_session_input(
        replaced.state,
        input_type="followup",
        content="再比较播放时长",
        temporal_context=TEMPORAL_CONTEXT,
    )
    assert added.action == "add_requirements"
    assert "hours" in added.state.metrics
    assert added.state.pending_requirements == ["只看今年", "再比较播放时长"]

    removed = apply_session_input(
        added.state,
        input_type="steer",
        content="不要看 Billboard",
        temporal_context=TEMPORAL_CONTEXT,
    )
    assert removed.action == "remove_requirements"
    assert "personal_billboard" in removed.state.excluded_dimensions
    assert removed.state.filters["include_billboard"] is False


def test_session_state_replace_task_resets_old_constraints() -> None:
    state = apply_session_input(
        _initial_state(),
        input_type="followup",
        content="再比较播放时长",
        temporal_context=TEMPORAL_CONTEXT,
    ).state

    update = apply_session_input(
        state,
        input_type="steer",
        content="停止这个问题，改问我今年听得最多的艺人",
        temporal_context=TEMPORAL_CONTEXT,
    )

    assert update.action == "replace_task"
    assert update.state.active_question == "我今年听得最多的艺人"
    assert update.state.pending_requirements == []
    assert "hours" not in update.state.metrics
    assert update.state.time_range["start_date"] == "2026-01-01"
    assert update.state.time_range["end_date"] == "2026-08-21"
    assert update.state.time_range["coverage_clipped"] is True


def test_session_state_cancel_is_structured_without_mutating_state() -> None:
    state = _initial_state()

    update = apply_session_input(
        state,
        input_type="cancel",
        content="",
        temporal_context=TEMPORAL_CONTEXT,
    )

    assert update.action == "cancel"
    assert update.state.to_dict() == state.to_dict()


def test_session_state_restores_latest_event_and_updates_tool_filters() -> None:
    fallback = _initial_state()
    updated = apply_session_input(
        fallback,
        input_type="steer",
        content="只看今年，不合并播放",
        temporal_context=TEMPORAL_CONTEXT,
    ).state
    events = [
        {
            "sequence": 1,
            "event_type": "session_state_initialized",
            "payload": {"state": fallback.to_dict()},
        },
        {
            "sequence": 2,
            "event_type": "session_state_updated",
            "payload": {"state": updated.to_dict()},
        },
    ]

    restored = restore_session_state(events, fallback)
    filters = filters_for_session_state(
        restored,
        {"period": "lifetime", "start_date": "stale", "end_date": "stale"},
    )

    assert restored.to_dict() == updated.to_dict()
    assert filters["period"] == "custom"
    assert filters["start_date"] == "2026-01-01"
    assert filters["end_date"] == "2026-08-21"
    assert filters["merge_enabled"] is False
