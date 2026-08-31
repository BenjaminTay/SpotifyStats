from backend.domains.agent_runtime.projections import (
    project_turn,
    projection_hash,
    select_context_messages,
)


def _event(sequence: int, event_type: str, payload=None, step_index=None):
    return {
        "sequence": sequence,
        "event_type": event_type,
        "payload": payload or {},
        "step_index": step_index,
    }


def test_project_turn_reconstructs_messages_state_usage_and_completed_tools() -> None:
    events = [
        _event(1, "turn_started"),
        _event(
            2,
            "model_message",
            {"message": {"role": "system", "content": "rules"}},
        ),
        _event(
            3,
            "model_message",
            {"message": {"role": "user", "content": "top artist"}},
        ),
        _event(4, "step_started", step_index=1),
        _event(5, "model_request", step_index=1),
        _event(
            6,
            "assistant_message",
            {
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 30,
                    "total_tokens": 150,
                }
            },
            1,
        ),
        _event(7, "tool_call", {"call_id": "call-1"}, 1),
        _event(8, "tool_result", {"call_id": "call-1"}, 1),
        _event(
            9,
            "model_message",
            {
                "message": {
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "name": "statistics",
                    "content": "{}",
                }
            },
            1,
        ),
        _event(10, "turn_ended", {"stop_reason": "final_answer"}, 2),
    ]

    projection = project_turn(list(reversed(events)))

    assert [item["role"] for item in projection.messages] == ["system", "user", "tool"]
    assert [item["role"] for item in projection.transcript] == ["user", "tool"]
    assert projection.status == "done"
    assert projection.stop_reason == "final_answer"
    assert projection.current_step == 2
    assert projection.model_call_count == 1
    assert projection.tool_call_count == 1
    assert projection.completed_call_ids == {"call-1"}
    assert projection.usage == {
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
    }


def test_select_context_messages_can_shadow_compare_before_cutover() -> None:
    messages = [{"role": "user", "content": "hello"}]
    events = [
        _event(1, "model_message", {"message": messages[0]}),
    ]

    selected, verdict = select_context_messages(
        memory_messages=messages,
        events=events,
        source="memory",
    )

    assert selected == messages
    assert verdict["matches"] is True
    assert verdict["memory_hash"] == verdict["event_log_hash"]
    assert projection_hash({"b": 2, "a": 1}) == projection_hash({"a": 1, "b": 2})


def test_select_context_messages_uses_replayed_context_after_cutover() -> None:
    memory_messages = [{"role": "user", "content": "stale"}]
    replayed = {"role": "user", "content": "durable"}

    selected, verdict = select_context_messages(
        memory_messages=memory_messages,
        events=[_event(1, "model_message", {"message": replayed})],
        source="event_log",
    )

    assert selected == [replayed]
    assert verdict["matches"] is False
    assert verdict["source"] == "event_log"
