"""Low-cardinality runtime metrics for Agent turns."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0, int(value))
    return 0


def json_size_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


@dataclass
class RuntimeMetrics:
    """Accumulate timings and provider usage without retaining prompt content."""

    clock: Callable[[], float] = time.monotonic
    model_elapsed_ms: int = 0
    model_cache_hit_elapsed_ms: int = 0
    tool_elapsed_ms: int = 0
    tool_cumulative_elapsed_ms: int = 0
    tool_cache_hit_elapsed_ms: int = 0
    validation_elapsed_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_call_count: int = 0
    tool_call_count: int = 0
    cache_hit_count: int = 0
    model_cache_hit_count: int = 0
    tool_cache_hit_count: int = 0
    tool_dedup_hit_count: int = 0
    tool_result_bytes: int = 0
    model_input_chars: int = 0

    def __post_init__(self) -> None:
        self._started_at = self.clock()

    def record_model(
        self,
        *,
        elapsed_ms: int,
        usage: dict[str, Any] | None,
        input_chars: int,
    ) -> None:
        normalized = usage if isinstance(usage, dict) else {}
        self.model_call_count += 1
        self.model_elapsed_ms += max(0, elapsed_ms)
        self.model_input_chars += max(0, input_chars)
        self.input_tokens += _usage_int(normalized, "input_tokens", "prompt_tokens")
        self.output_tokens += _usage_int(normalized, "output_tokens", "completion_tokens")
        details = normalized.get("prompt_tokens_details")
        cache_hit = isinstance(details, dict) and _usage_int(details, "cached_tokens") > 0
        cache_hit = cache_hit or _usage_int(normalized, "cache_read_input_tokens") > 0
        if cache_hit:
            self.cache_hit_count += 1
            self.model_cache_hit_count += 1
            self.model_cache_hit_elapsed_ms += max(0, elapsed_ms)

    def record_tool(
        self,
        *,
        elapsed_ms: int,
        result_bytes: int,
        cache_hit: bool = False,
        deduplicated: bool = False,
        executed: bool = True,
        include_wall_time: bool = True,
    ) -> None:
        elapsed_ms = max(0, elapsed_ms)
        if executed:
            self.tool_call_count += 1
            self.tool_cumulative_elapsed_ms += elapsed_ms
            if include_wall_time:
                self.tool_elapsed_ms += elapsed_ms
            self.tool_result_bytes += max(0, result_bytes)
        if cache_hit:
            self.cache_hit_count += 1
            self.tool_cache_hit_count += 1
            self.tool_cache_hit_elapsed_ms += elapsed_ms
        if deduplicated:
            self.cache_hit_count += 1
            self.tool_dedup_hit_count += 1

    def record_tool_batch_wall(self, elapsed_ms: int) -> None:
        """Record actual user-visible wait for a parallel batch.

        Individual executions are still accumulated in
        ``tool_cumulative_elapsed_ms`` for compute/cost analysis.  The legacy
        ``tool_elapsed_ms`` field intentionally follows wall-clock semantics so
        parallel work is not double-counted.
        """

        self.tool_elapsed_ms += max(0, elapsed_ms)

    def record_validation(self, elapsed_ms: int) -> None:
        self.validation_elapsed_ms += max(0, elapsed_ms)

    @contextmanager
    def measure_validation(self) -> Iterator[None]:
        """Measure one complete validation stage exactly once, including failures."""

        started_at = self.clock()
        try:
            yield
        finally:
            self.record_validation(round((self.clock() - started_at) * 1000))

    def snapshot(self) -> dict[str, int]:
        return {
            "total_elapsed_ms": max(0, round((self.clock() - self._started_at) * 1000)),
            "model_elapsed_ms": self.model_elapsed_ms,
            "model_wait_elapsed_ms": self.model_elapsed_ms,
            "model_cache_hit_elapsed_ms": self.model_cache_hit_elapsed_ms,
            "tool_elapsed_ms": self.tool_elapsed_ms,
            "tool_wall_elapsed_ms": self.tool_elapsed_ms,
            "tool_cumulative_elapsed_ms": self.tool_cumulative_elapsed_ms,
            "tool_cache_hit_elapsed_ms": self.tool_cache_hit_elapsed_ms,
            "validation_elapsed_ms": self.validation_elapsed_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model_call_count": self.model_call_count,
            "tool_call_count": self.tool_call_count,
            "cache_hit_count": self.cache_hit_count,
            "model_cache_hit_count": self.model_cache_hit_count,
            "tool_cache_hit_count": self.tool_cache_hit_count,
            "tool_dedup_hit_count": self.tool_dedup_hit_count,
            "tool_result_bytes": self.tool_result_bytes,
            "model_input_chars": self.model_input_chars,
        }
