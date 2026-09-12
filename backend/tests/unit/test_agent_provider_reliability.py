from __future__ import annotations

import copy
from typing import Any

import pytest

from backend.domains.agent_runtime.provider_reliability import (
    BudgetCaps,
    ModelStepExecutor,
    ModelStepExhaustedError,
    ProviderCandidate,
    ProviderCircuitBreaker,
    dynamic_agent_budget,
)
from backend.providers.base import ProviderHTTPError, ProviderNetworkError
from backend.providers.llm.client import LLMCompletion

pytestmark = pytest.mark.unit


class SequencedModel:
    def __init__(self, outcomes: list[LLMCompletion | BaseException]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages, tools, *, thinking):
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "tools": copy.deepcopy(tools),
                "thinking": thinking,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _budget(context: dict[str, Any] | None = None):
    return dynamic_agent_budget(context or {"question_intent": {"task_type": "ranking"}})


def test_dynamic_budget_scales_with_question_complexity_and_respects_caps() -> None:
    simple = dynamic_agent_budget(
        {"question_intent": {"task_type": "entity_lookup", "entities": ["A"]}}
    )
    complex_budget = dynamic_agent_budget(
        {
            "question_intent": {
                "task_type": "comparison",
                "entities": ["A", "B", "C"],
                "requested_metrics": ["plays", "hours", "personal_billboard", "trend"],
            }
        }
    )
    capped = dynamic_agent_budget(
        {
            "question_intent": {
                "task_type": "comparison",
                "entities": ["A", "B", "C"],
                "requested_metrics": ["plays", "hours", "personal_billboard"],
            }
        },
        caps=BudgetCaps(
            max_steps=4,
            max_tool_calls=5,
            turn_timeout_seconds=70,
            model_timeout_seconds=35,
            max_model_retries=1,
            max_output_tokens=3000,
        ),
    )

    assert simple.complexity == "simple"
    assert complex_budget.complexity == "complex"
    assert complex_budget.max_steps > simple.max_steps
    assert complex_budget.max_tool_calls > simple.max_tool_calls
    assert complex_budget.max_output_tokens > simple.max_output_tokens
    assert capped.max_steps == 4
    assert capped.max_tool_calls == 5
    assert capped.turn_timeout_seconds == 70
    assert capped.model_timeout_seconds == 35
    assert capped.model_retries == 1
    assert capped.max_output_tokens == 3000


def test_budget_caps_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="budget caps"):
        BudgetCaps(max_steps=0)


def test_retry_replays_only_failed_model_step_with_identical_tool_evidence() -> None:
    model = SequencedModel(
        [
            ProviderNetworkError("primary", "temporary"),
            LLMCompletion(content="grounded answer"),
        ]
    )
    executor = ModelStepExecutor(primary=ProviderCandidate("primary", model))
    messages = [
        {"role": "user", "content": "question"},
        {
            "role": "tool",
            "tool_call_id": "tool-1",
            "content": '{"plays":12,"evidence_ref":"event-9"}',
        },
    ]
    original = copy.deepcopy(messages)

    result = executor.execute(
        messages=messages,
        tools=[{"name": "analysis_stats"}],
        thinking=True,
        budget=_budget(),
    )

    assert result.completion.content == "grounded answer"
    assert [attempt.outcome for attempt in result.attempts] == ["failed", "success"]
    assert len(model.calls) == 2
    assert model.calls[0]["messages"] == original
    assert model.calls[1]["messages"] == original
    assert messages == original
    assert all(attempt.elapsed_ms >= 0 for attempt in result.attempts)


def test_non_retryable_primary_failure_uses_first_fallback_deterministically() -> None:
    primary = SequencedModel([ProviderHTTPError("primary", "bad request", 400)])
    fallback_one = SequencedModel([LLMCompletion(content="fallback one")])
    fallback_two = SequencedModel([LLMCompletion(content="fallback two")])
    executor = ModelStepExecutor(
        primary=ProviderCandidate("primary", primary),
        fallbacks=(
            ProviderCandidate("fallback-1", fallback_one),
            ProviderCandidate("fallback-2", fallback_two),
        ),
    )

    result = executor.execute(messages=[], tools=[], thinking=False, budget=_budget())

    assert result.provider_id == "fallback-1"
    assert result.completion.content == "fallback one"
    assert len(primary.calls) == 1
    assert len(fallback_one.calls) == 1
    assert fallback_two.calls == []


def test_circuit_breaker_skips_failed_primary_then_allows_half_open_recovery() -> None:
    now = [100.0]
    breaker = ProviderCircuitBreaker(
        failure_threshold=2,
        cooldown_seconds=10,
        clock=lambda: now[0],
    )
    primary = SequencedModel(
        [
            ProviderNetworkError("primary", "one"),
            ProviderNetworkError("primary", "two"),
            LLMCompletion(content="primary recovered"),
        ]
    )
    fallback = SequencedModel(
        [LLMCompletion(content="fallback first"), LLMCompletion(content="fallback second")]
    )
    executor = ModelStepExecutor(
        primary=ProviderCandidate("primary", primary),
        fallbacks=(ProviderCandidate("fallback", fallback),),
        circuit_breaker=breaker,
    )

    first = executor.execute(messages=[], tools=[], thinking=False, budget=_budget())
    second = executor.execute(messages=[], tools=[], thinking=False, budget=_budget())

    assert first.provider_id == "fallback"
    assert second.provider_id == "fallback"
    assert len(primary.calls) == 2
    assert breaker.snapshot("primary")["status"] == "open"

    now[0] += 11
    recovered = executor.execute(messages=[], tools=[], thinking=False, budget=_budget())

    assert recovered.provider_id == "primary"
    assert recovered.completion.content == "primary recovered"
    assert breaker.snapshot("primary")["status"] == "closed"


def test_exhausted_step_reports_safe_attempt_metadata_without_provider_message() -> None:
    unsafe_provider_message = (
        "upstream failed with sk-secret-value-123456"  # pragma: allowlist secret
    )
    primary = SequencedModel([ProviderHTTPError("primary", unsafe_provider_message, 400)])
    executor = ModelStepExecutor(primary=ProviderCandidate("primary", primary))

    with pytest.raises(ModelStepExhaustedError) as caught:
        executor.execute(messages=[], tools=[], thinking=False, budget=_budget())

    assert caught.value.attempts[0].error_type == "ProviderHTTPError"
    assert unsafe_provider_message not in str(caught.value)


def test_provider_ids_must_be_unique() -> None:
    model = SequencedModel([LLMCompletion(content="unused")])

    with pytest.raises(ValueError, match="unique"):
        ModelStepExecutor(
            primary=ProviderCandidate("same", model),
            fallbacks=(ProviderCandidate("same", model),),
        )
