import pytest

from backend.domains.agent_runtime.native_loop import (
    NativeLoopCancelledError,
    NativeObservationLoop,
    NativeToolObservation,
    tool_message,
)
from backend.providers.llm.client import LLMCompletion, LLMToolCall


def test_native_observation_loop_is_shared_provider_neutral_protocol() -> None:
    class Model:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            self.calls += 1
            assert tools[0]["name"] == "statistics"
            assert thinking is True
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="call-1",
                            name="statistics",
                            arguments={"period": "2026"},
                        )
                    ]
                )
            return LLMCompletion(content="研究完成。")

    executed = []

    def execute_tool(call, step):
        executed.append((call.name, call.arguments, step))
        return NativeToolObservation(
            model_payload={"status": "ok", "data": {"plays": 100}},
            result_payload={"tool_name": call.name, "status": "ok"},
        )

    result = NativeObservationLoop(
        model=Model(),
        schemas=[{"name": "statistics", "parameters": {"type": "object"}}],
        thinking=True,
    ).run(
        messages=[{"role": "user", "content": "今年"}],
        execute_tool=execute_tool,
        max_steps=4,
        max_tool_calls=2,
    )

    assert result.content == "研究完成。"
    assert result.stop_reason == "final_answer"
    assert result.steps == 2
    assert result.tool_call_count == 1
    assert executed == [("statistics", {"period": "2026"}, 1)]
    assert [message["role"] for message in result.messages] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]


def test_tool_message_preserves_bounded_nested_bucket_scalars() -> None:
    call = LLMToolCall(call_id="taste", name="taste_profile", arguments={})
    message = tool_message(
        call,
        {
            "status": "ok",
            "data": {
                "taste_profile": {"primary_styles": {"buckets": [{"label": "Pop", "hours": 88.5}]}}
            },
        },
    )

    import json

    bucket = json.loads(message["content"])["data"]["taste_profile"]["primary_styles"]["buckets"][0]
    assert bucket == {"label": "Pop", "hours": 88.5}


def test_native_observation_loop_stops_after_model_returns_to_cancelled_task() -> None:
    class Model:
        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            return LLMCompletion(
                tool_calls=[LLMToolCall(call_id="late", name="statistics", arguments={})]
            )

    checks = iter([True, False])
    with pytest.raises(NativeLoopCancelledError):
        NativeObservationLoop(
            model=Model(),
            schemas=[],
            thinking=False,
        ).run(
            messages=[],
            execute_tool=lambda *_args: pytest.fail("取消后不得执行工具"),
            max_steps=2,
            max_tool_calls=2,
            should_continue=lambda: next(checks),
        )
