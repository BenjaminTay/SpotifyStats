"""Provider-neutral primitives shared by chat and report observation loops."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.domains.agent_runtime.provider_reliability import (
    BudgetCaps,
    DynamicAgentBudget,
    ModelStepExecutor,
    ProviderCandidate,
    dynamic_agent_budget,
)
from backend.domains.agent_runtime.serialization import compact_json
from backend.providers.llm.client import LLMCompletion, LLMToolCall


class NativeToolModel(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        thinking: bool,
    ) -> LLMCompletion: ...


class NativeLoopCancelledError(RuntimeError):
    """Raised at a safe boundary after the owning durable task is cancelled."""


@dataclass(frozen=True)
class ModelObservationStep:
    completion: LLMCompletion
    assistant_message: dict[str, Any]
    elapsed_ms: int


@dataclass(frozen=True)
class NativeToolObservation:
    model_payload: dict[str, Any]
    result_payload: dict[str, Any]
    counted: bool = True


@dataclass
class NativeLoopResult:
    content: str
    messages: list[dict[str, Any]]
    observations: list[dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    tool_call_count: int = 0
    stop_reason: str = "max_steps"


def assistant_message(completion: LLMCompletion) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": completion.content or ""}
    if completion.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in completion.tool_calls
        ]
    return message


def tool_message(call: LLMToolCall, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": call.call_id,
        "name": call.name,
        # Tool payloads have their own domain-level bounds.  The envelope adds
        # several structural levels, so the generic context depth would erase
        # leaf scalars such as ``taste_profile.*.buckets[].label``.
        "content": compact_json(
            payload,
            max_depth=10,
            max_list_items=12,
            max_string_chars=1200,
        ),
    }


class NativeObservationLoop:
    """Shared native model/tool protocol; domain-specific policy stays in adapters."""

    def __init__(
        self,
        *,
        model: NativeToolModel,
        schemas: list[dict[str, Any]],
        thinking: bool,
        clock: Callable[[], float] = time.monotonic,
        model_executor: ModelStepExecutor | None = None,
        budget: DynamicAgentBudget | None = None,
    ) -> None:
        self.model = model
        self.schemas = schemas
        self.thinking = thinking
        self.clock = clock
        provider_id = str(getattr(model, "provider_id", f"native:{model.__class__.__name__}"))
        self.model_executor = model_executor or ModelStepExecutor(
            primary=ProviderCandidate(provider_id, model),
            clock=clock,
        )
        self.budget = budget or dynamic_agent_budget(
            {},
            caps=BudgetCaps(max_steps=7, max_tool_calls=12),
        )

    def complete_step(self, messages: list[dict[str, Any]]) -> ModelObservationStep:
        started_at = self.clock()
        completion = self.model_executor.execute(
            messages=messages,
            tools=self.schemas,
            thinking=self.thinking,
            budget=self.budget,
        ).completion
        return ModelObservationStep(
            completion=completion,
            assistant_message=assistant_message(completion),
            elapsed_ms=round((self.clock() - started_at) * 1000),
        )

    def run(
        self,
        *,
        messages: list[dict[str, Any]],
        execute_tool: Callable[[LLMToolCall, int], NativeToolObservation],
        max_steps: int,
        max_tool_calls: int,
        on_step: Callable[[int, int], None] | None = None,
        should_continue: Callable[[], bool] | None = None,
    ) -> NativeLoopResult:
        observations: list[dict[str, Any]] = []
        tool_call_count = 0
        for step in range(1, max_steps + 1):
            if should_continue is not None and not should_continue():
                raise NativeLoopCancelledError("年度报告任务已取消")
            model_step = self.complete_step(messages)
            if should_continue is not None and not should_continue():
                raise NativeLoopCancelledError("年度报告任务已取消")
            completion = model_step.completion
            messages.append(model_step.assistant_message)
            if not completion.tool_calls:
                return NativeLoopResult(
                    content=completion.content.strip(),
                    messages=messages,
                    observations=observations,
                    steps=step,
                    tool_call_count=tool_call_count,
                    stop_reason="final_answer",
                )
            for call in completion.tool_calls:
                if should_continue is not None and not should_continue():
                    raise NativeLoopCancelledError("年度报告任务已取消")
                if tool_call_count >= max_tool_calls:
                    return NativeLoopResult(
                        content="",
                        messages=messages,
                        observations=observations,
                        steps=step,
                        tool_call_count=tool_call_count,
                        stop_reason="max_tool_calls",
                    )
                observation = execute_tool(call, step)
                observations.append(observation.result_payload)
                if observation.counted:
                    tool_call_count += 1
                messages.append(tool_message(call, observation.model_payload))
            if on_step:
                on_step(step, tool_call_count)
        return NativeLoopResult(
            content="",
            messages=messages,
            observations=observations,
            steps=max_steps,
            tool_call_count=tool_call_count,
            stop_reason="max_steps",
        )
