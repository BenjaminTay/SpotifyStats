"""Low-cardinality performance metrics for yearly Agent report generation."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportRuntimeMetrics:
    """Accumulate report timings without retaining prompts or raw provider payloads."""

    clock: Callable[[], float] = time.monotonic
    stages_ms: dict[str, int] = field(default_factory=dict)
    stage_counts: dict[str, int] = field(default_factory=dict)
    context_snapshot_hit: bool = False
    context_snapshot_key: str = ""
    context_build_count: int = 0
    provider_calls: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._started_at = self.clock()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = self.clock()
        try:
            yield
        finally:
            elapsed = max(0, round((self.clock() - started) * 1000))
            self.stages_ms[name] = self.stages_ms.get(name, 0) + elapsed
            self.stage_counts[name] = self.stage_counts.get(name, 0) + 1

    def record_context_snapshot(
        self,
        *,
        cache_hit: bool,
        snapshot_key: str,
        built: bool,
    ) -> None:
        self.context_snapshot_hit = cache_hit
        self.context_snapshot_key = snapshot_key[:16]
        if built:
            self.context_build_count += 1

    def record_provider_call(self, value: Any, *, stage: str) -> None:
        """Record an already-normalized completion object or mapping."""

        if hasattr(value, "to_metrics"):
            payload = value.to_metrics()
        elif isinstance(value, dict):
            payload = dict(value)
        else:
            payload = {}
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        self.provider_calls.append(
            {
                "stage": stage,
                "provider": str(payload.get("provider") or ""),
                "model": str(payload.get("model") or ""),
                "finish_reason": str(payload.get("finish_reason") or ""),
                "empty_reason": str(payload.get("empty_reason") or ""),
                "elapsed_ms": _non_negative_int(payload.get("elapsed_ms")),
                "input_tokens": _usage_int(usage, "input_tokens", "prompt_tokens"),
                "output_tokens": _usage_int(usage, "output_tokens", "completion_tokens"),
                "content_chars": _non_negative_int(payload.get("content_chars")),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "ai_report_runtime_metrics_v1",
            "total_elapsed_ms": max(0, round((self.clock() - self._started_at) * 1000)),
            "stages_ms": dict(sorted(self.stages_ms.items())),
            "stage_counts": dict(sorted(self.stage_counts.items())),
            "context_snapshot_hit": self.context_snapshot_hit,
            "context_snapshot_key": self.context_snapshot_key,
            "context_build_count": self.context_build_count,
            "provider_calls": list(self.provider_calls),
        }


def _non_negative_int(value: Any) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, int(value))
    return 0


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0, int(value))
    return 0
