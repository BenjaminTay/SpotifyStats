"""Provider reliability primitives scoped to one model step.

This module deliberately knows nothing about tool execution.  Retrying a
failed model step therefore reuses the exact observed tool-result context and
cannot re-run already completed tools.
"""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from backend.providers.base import (
    ProviderNetworkError,
    ProviderParseError,
    ProviderRateLimitError,
    ProviderServerError,
)
from backend.providers.llm.client import LLMCompletion

ComplexityLevel = Literal["simple", "standard", "complex"]


class ModelProvider(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        thinking: bool,
    ) -> LLMCompletion: ...


@dataclass(frozen=True)
class BudgetCaps:
    max_steps: int = 7
    max_tool_calls: int = 12
    turn_timeout_seconds: int = 150
    model_timeout_seconds: int = 60
    max_model_retries: int = 2
    max_output_tokens: int = 6144

    def __post_init__(self) -> None:
        positive = (
            self.max_steps,
            self.max_tool_calls,
            self.turn_timeout_seconds,
            self.model_timeout_seconds,
            self.max_output_tokens,
        )
        if any(value <= 0 for value in positive) or self.max_model_retries < 0:
            raise ValueError("budget caps must be positive and retries must be non-negative")


@dataclass(frozen=True)
class DynamicAgentBudget:
    complexity: ComplexityLevel
    complexity_score: int
    reasons: tuple[str, ...]
    max_steps: int
    max_tool_calls: int
    turn_timeout_seconds: int
    model_timeout_seconds: int
    model_retries: int
    max_model_calls: int
    max_output_tokens: int


_DESIRED_BUDGETS: dict[ComplexityLevel, dict[str, int]] = {
    "simple": {
        "max_steps": 3,
        "max_tool_calls": 4,
        "turn_timeout_seconds": 45,
        "model_timeout_seconds": 30,
        "model_retries": 1,
        "max_model_calls": 3,
        "max_output_tokens": 2048,
    },
    "standard": {
        "max_steps": 5,
        "max_tool_calls": 8,
        "turn_timeout_seconds": 90,
        "model_timeout_seconds": 45,
        "model_retries": 1,
        "max_model_calls": 5,
        "max_output_tokens": 4096,
    },
    "complex": {
        "max_steps": 7,
        "max_tool_calls": 12,
        "turn_timeout_seconds": 150,
        "model_timeout_seconds": 60,
        "model_retries": 2,
        "max_model_calls": 7,
        "max_output_tokens": 6144,
    },
}


def assess_question_complexity(question_context: Mapping[str, Any]) -> tuple[int, tuple[str, ...]]:
    """Score a normalized question context without another model call."""

    intent_value = question_context.get("question_intent")
    intent = intent_value if isinstance(intent_value, Mapping) else question_context
    task_type = str(intent.get("task_type") or question_context.get("family") or "")
    entities_value = intent.get("entities")
    entities = (
        entities_value
        if isinstance(entities_value, Sequence) and not isinstance(entities_value, (str, bytes))
        else ()
    )
    metrics_value = intent.get("requested_metrics")
    metrics = (
        metrics_value
        if isinstance(metrics_value, Sequence) and not isinstance(metrics_value, (str, bytes))
        else ()
    )

    score = 0
    reasons: list[str] = []
    if task_type in {"comparison", "trend", "period_comparison"}:
        score += 2
        reasons.append(f"task:{task_type}")
    elif task_type in {"ranking", "summary", "entity_lookup"}:
        score += 1
        reasons.append(f"task:{task_type}")
    if len(entities) >= 3:
        score += 2
        reasons.append("entities:3+")
    elif len(entities) == 2:
        score += 1
        reasons.append("entities:2")
    if len(metrics) >= 3:
        score += 2
        reasons.append("metrics:3+")
    elif len(metrics) == 2:
        score += 1
        reasons.append("metrics:2")
    if "personal_billboard" in metrics:
        score += 1
        reasons.append("metric:personal_billboard")
    if any(metric in metrics for metric in ("recent_window", "time_of_day", "trend")):
        score += 1
        reasons.append("metric:temporal_analysis")
    return score, tuple(reasons)


def dynamic_agent_budget(
    question_context: Mapping[str, Any],
    *,
    caps: BudgetCaps = BudgetCaps(),
) -> DynamicAgentBudget:
    score, reasons = assess_question_complexity(question_context)
    level: ComplexityLevel = "simple" if score <= 1 else "standard" if score <= 4 else "complex"
    desired = _DESIRED_BUDGETS[level]
    return DynamicAgentBudget(
        complexity=level,
        complexity_score=score,
        reasons=reasons,
        max_steps=max(1, min(desired["max_steps"], caps.max_steps)),
        max_tool_calls=max(1, min(desired["max_tool_calls"], caps.max_tool_calls)),
        turn_timeout_seconds=max(
            1, min(desired["turn_timeout_seconds"], caps.turn_timeout_seconds)
        ),
        model_timeout_seconds=max(
            1, min(desired["model_timeout_seconds"], caps.model_timeout_seconds)
        ),
        model_retries=max(0, min(desired["model_retries"], caps.max_model_retries)),
        max_model_calls=max(1, min(desired["max_model_calls"], caps.max_steps)),
        max_output_tokens=max(256, min(desired["max_output_tokens"], caps.max_output_tokens)),
    )


@dataclass(frozen=True)
class ProviderCandidate:
    provider_id: str
    model: ModelProvider


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    open_until: float = 0.0
    half_open_in_flight: bool = False


class ProviderCircuitBreaker:
    """Thread-safe consecutive-failure circuit breaker per provider."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self.clock = clock
        self._states: dict[str, _CircuitState] = {}
        self._lock = threading.Lock()

    def allow_request(self, provider_id: str) -> bool:
        with self._lock:
            state = self._states.setdefault(provider_id, _CircuitState())
            now = self.clock()
            if state.open_until <= 0:
                return True
            if now < state.open_until:
                return False
            if state.half_open_in_flight:
                return False
            state.half_open_in_flight = True
            return True

    def record_success(self, provider_id: str) -> None:
        with self._lock:
            self._states[provider_id] = _CircuitState()

    def record_failure(self, provider_id: str) -> None:
        with self._lock:
            state = self._states.setdefault(provider_id, _CircuitState())
            state.half_open_in_flight = False
            state.consecutive_failures += 1
            if state.consecutive_failures >= self.failure_threshold:
                state.open_until = self.clock() + self.cooldown_seconds

    def snapshot(self, provider_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._states.get(provider_id, _CircuitState())
            now = self.clock()
            status = "closed"
            if state.open_until > now:
                status = "open"
            elif state.open_until > 0:
                status = "half_open"
            return {
                "provider_id": provider_id,
                "status": status,
                "consecutive_failures": state.consecutive_failures,
                "retry_after_seconds": max(0.0, state.open_until - now),
            }


def retryable_model_error(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (
            ProviderNetworkError,
            ProviderRateLimitError,
            ProviderServerError,
            ProviderParseError,
            TimeoutError,
            ConnectionError,
        ),
    )


@dataclass(frozen=True)
class ModelStepAttempt:
    provider_id: str
    attempt: int
    outcome: Literal["success", "failed", "circuit_open"]
    retryable: bool = False
    error_type: str = ""
    elapsed_ms: int = 0


@dataclass(frozen=True)
class ModelStepResult:
    completion: LLMCompletion
    provider_id: str
    attempts: tuple[ModelStepAttempt, ...]


class ModelStepExhaustedError(RuntimeError):
    def __init__(self, attempts: Sequence[ModelStepAttempt]):
        super().__init__("All configured model providers failed for the current step")
        self.attempts = tuple(attempts)


@dataclass
class ModelStepExecutor:
    """Retry only a failed model completion using preserved observations."""

    primary: ProviderCandidate
    fallbacks: tuple[ProviderCandidate, ...] = ()
    circuit_breaker: ProviderCircuitBreaker = field(default_factory=ProviderCircuitBreaker)
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        ids = [candidate.provider_id for candidate in (self.primary, *self.fallbacks)]
        if any(not provider_id for provider_id in ids) or len(ids) != len(set(ids)):
            raise ValueError("provider IDs must be non-empty and unique")

    def execute(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        thinking: bool,
        budget: DynamicAgentBudget,
    ) -> ModelStepResult:
        # Freeze the observed state once. Each provider receives an isolated
        # copy, while completed tool observations/evidence remain unchanged.
        preserved_messages = copy.deepcopy(messages)
        preserved_tools = copy.deepcopy(tools)
        attempts: list[ModelStepAttempt] = []
        total_calls = 0

        for candidate in (self.primary, *self.fallbacks):
            for provider_attempt in range(1, budget.model_retries + 2):
                if total_calls >= budget.max_model_calls:
                    raise ModelStepExhaustedError(attempts)
                if not self.circuit_breaker.allow_request(candidate.provider_id):
                    attempts.append(
                        ModelStepAttempt(
                            provider_id=candidate.provider_id,
                            attempt=provider_attempt,
                            outcome="circuit_open",
                        )
                    )
                    break
                total_calls += 1
                started_at = self.clock()
                try:
                    completion = candidate.model.complete(
                        copy.deepcopy(preserved_messages),
                        copy.deepcopy(preserved_tools),
                        thinking=thinking,
                    )
                except Exception as exc:
                    retryable = retryable_model_error(exc)
                    self.circuit_breaker.record_failure(candidate.provider_id)
                    attempts.append(
                        ModelStepAttempt(
                            provider_id=candidate.provider_id,
                            attempt=provider_attempt,
                            outcome="failed",
                            retryable=retryable,
                            error_type=exc.__class__.__name__,
                            elapsed_ms=max(0, round((self.clock() - started_at) * 1000)),
                        )
                    )
                    if not retryable:
                        break
                    continue
                self.circuit_breaker.record_success(candidate.provider_id)
                attempts.append(
                    ModelStepAttempt(
                        provider_id=candidate.provider_id,
                        attempt=provider_attempt,
                        outcome="success",
                        elapsed_ms=max(0, round((self.clock() - started_at) * 1000)),
                    )
                )
                return ModelStepResult(
                    completion=completion,
                    provider_id=candidate.provider_id,
                    attempts=tuple(attempts),
                )
        raise ModelStepExhaustedError(attempts)
