from backend.domains.agent_runtime.native_loop import (
    NativeObservationLoop,
    NativeToolObservation,
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
