from backend.domains.agent_runtime.recovery import build_resume_checkpoint


def _event(sequence: int, event_type: str, payload=None, step_index=None):
    return {
        "sequence": sequence,
        "event_type": event_type,
        "payload": payload or {},
        "step_index": step_index,
    }


def test_resume_checkpoint_only_replays_unfinished_tool_calls() -> None:
    assistant = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "done-call",
                "type": "function",
                "function": {"name": "statistics", "arguments": '{"period":"this_year"}'},
            },
            {
                "id": "pending-call",
                "type": "function",
                "function": {"name": "top_items", "arguments": {"limit": 5}},
            },
        ],
    }
    events = [
        _event(1, "turn_started"),
        _event(2, "model_message", {"message": {"role": "system", "content": "rules"}}),
        _event(3, "model_message", {"message": {"role": "user", "content": "今年"}}),
        _event(4, "step_started", step_index=1),
        _event(5, "model_message", {"message": assistant}, 1),
        _event(
            6,
            "tool_result",
            {
                "call_id": "done-call",
                "outcome": {
                    "tool_name": "statistics",
                    "status": "ok",
                    "result_summary": "100 次",
                    "source_range": "2026",
                    "data": {"play_count": 100},
                },
            },
            1,
        ),
        _event(
            7,
            "model_message",
            {
                "message": {
                    "role": "tool",
                    "tool_call_id": "done-call",
                    "name": "statistics",
                    "content": "{}",
                }
            },
            1,
        ),
    ]

    checkpoint = build_resume_checkpoint(events)

    assert checkpoint.resumable is True
    assert checkpoint.completed_call_ids == {"done-call"}
    assert [item.call_id for item in checkpoint.pending_tool_calls] == ["pending-call"]
    assert checkpoint.pending_tool_calls[0].params == {"limit": 5}
    assert checkpoint.recovered_tool_results[0]["data"] == {"play_count": 100}
    assert checkpoint.next_step == 2


def test_completed_turn_is_never_resumed() -> None:
    checkpoint = build_resume_checkpoint(
        [
            _event(1, "turn_started"),
            _event(2, "model_message", {"message": {"role": "user", "content": "hi"}}),
            _event(3, "turn_ended", {"stop_reason": "final_answer"}, 1),
        ]
    )

    assert checkpoint.resumable is False
    assert checkpoint.reason == "turn_done"


def test_recovery_restores_executed_params_and_missing_tool_message() -> None:
    checkpoint = build_resume_checkpoint(
        [
            _event(1, "turn_started"),
            _event(
                2,
                "model_message",
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "statistics",
                                    "arguments": '{"period":"2026"}',
                                },
                            }
                        ],
                    }
                },
                1,
            ),
            _event(
                3,
                "tool_call",
                {
                    "call_id": "call-1",
                    "tool_name": "statistics",
                    "params": {"period": "2026", "min_ms": 30000},
                },
                1,
            ),
            _event(
                4,
                "tool_result",
                {
                    "call_id": "call-1",
                    "tool_name": "statistics",
                    "outcome": {
                        "tool_name": "statistics",
                        "status": "ok",
                        "result_summary": "100 次",
                        "source_range": "2026",
                        "data": {"plays": 100},
                    },
                },
                1,
            ),
        ]
    )

    assert checkpoint.recovered_tool_results[0]["params"] == {
        "period": "2026",
        "min_ms": 30000,
    }
    assert checkpoint.messages[-1]["role"] == "tool"
    assert checkpoint.messages[-1]["tool_call_id"] == "call-1"
