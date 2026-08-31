"""Provider-neutral orchestration for section-by-section yearly report writing.

This module deliberately owns no prompt construction, provider client, API key,
or report-specific audit policy.  Callers inject those concerns and receive a
deterministically ordered result with bounded concurrency and per-section
observability.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Literal

SECTION_WRITER_VERSION = "yearly_section_writer_v1"
SECTION_COUNT = 6
MAX_SECTION_WORKERS = 2
MAX_SECTION_ATTEMPTS = 2

SectionAttemptStatus = Literal[
    "accepted",
    "empty",
    "completion_error",
    "parse_error",
    "audit_rejected",
]
SectionWriteStatus = Literal["accepted", "fallback"]


@dataclass(frozen=True)
class SectionWritePlan:
    """One immutable unit of work in the caller-defined report outline."""

    section_id: str
    heading: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class SectionCompletion:
    """Small provider-neutral completion envelope returned by the caller."""

    content: str = ""
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    empty_reason: str | None = None


@dataclass(frozen=True)
class SectionAuditResult:
    """Caller-owned audit decision for one parsed section."""

    accepted: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class SectionAttempt:
    attempt: int
    status: SectionAttemptStatus
    elapsed_ms: int
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    empty_reason: str | None = None
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "empty_reason": self.empty_reason,
            "issues": list(self.issues),
        }


@dataclass(frozen=True)
class SectionWriteResult:
    plan: SectionWritePlan
    status: SectionWriteStatus
    section: dict[str, Any]
    attempts: tuple[SectionAttempt, ...]
    elapsed_ms: int
    fallback_reason: str | None = None

    @property
    def accepted(self) -> bool:
        """Only model output that passed audit is accepted; fallback never is."""

        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.plan.section_id,
            "heading": self.plan.heading,
            "status": self.status,
            "accepted": self.accepted,
            "section": dict(self.section),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "elapsed_ms": self.elapsed_ms,
            "fallback_reason": self.fallback_reason,
        }


@dataclass(frozen=True)
class SectionWriterMetadata:
    version: str
    model_accepted_count: int
    fallback_count: int
    attempt_count: int
    empty_reasons: dict[str, tuple[str, ...]]
    sections: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "model_accepted_count": self.model_accepted_count,
            "fallback_count": self.fallback_count,
            "attempt_count": self.attempt_count,
            "empty_reasons": {
                section_id: list(reasons) for section_id, reasons in self.empty_reasons.items()
            },
            "sections": [dict(section) for section in self.sections],
        }


@dataclass(frozen=True)
class SectionWriterRun:
    results: tuple[SectionWriteResult, ...]
    metadata: SectionWriterMetadata

    @property
    def sections(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(result.section) for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": [dict(section) for section in self.sections],
            "results": [result.to_dict() for result in self.results],
            "metadata": self.metadata.to_dict(),
        }


CompletionCallback = Callable[[SectionWritePlan, int], SectionCompletion]
ParseCallback = Callable[[SectionWritePlan, str], dict[str, Any]]
AuditCallback = Callable[[SectionWritePlan, dict[str, Any]], SectionAuditResult]
FallbackCallback = Callable[
    [SectionWritePlan, tuple[SectionAttempt, ...]],
    dict[str, Any],
]


class SectionWriterError(RuntimeError):
    """Raised when the deterministic orchestration contract cannot be fulfilled."""


def write_report_sections(
    plans: Sequence[SectionWritePlan],
    *,
    complete: CompletionCallback,
    parse: ParseCallback,
    audit: AuditCallback,
    fallback: FallbackCallback,
    max_workers: int = MAX_SECTION_WORKERS,
    max_attempts: int = MAX_SECTION_ATTEMPTS,
) -> SectionWriterRun:
    """Write exactly six report sections with isolated retries and fallback.

    Work may finish out of order, but both ``results`` and ``sections`` retain
    the input plan order.  Each callback invocation is scoped to one section;
    a bad or empty completion therefore never restarts another section.
    """

    normalized_plans = tuple(plans)
    _validate_options(normalized_plans, max_workers=max_workers, max_attempts=max_attempts)

    indexed_results: dict[int, SectionWriteResult] = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="section-writer") as pool:
        futures = {
            pool.submit(
                _write_section,
                plan,
                complete=complete,
                parse=parse,
                audit=audit,
                fallback=fallback,
                max_attempts=max_attempts,
            ): index
            for index, plan in enumerate(normalized_plans)
        }
        for future in as_completed(futures):
            indexed_results[futures[future]] = future.result()

    results = tuple(indexed_results[index] for index in range(len(normalized_plans)))
    return SectionWriterRun(results=results, metadata=_build_metadata(results))


def _write_section(
    plan: SectionWritePlan,
    *,
    complete: CompletionCallback,
    parse: ParseCallback,
    audit: AuditCallback,
    fallback: FallbackCallback,
    max_attempts: int,
) -> SectionWriteResult:
    section_started = time.perf_counter()
    attempts: list[SectionAttempt] = []

    for attempt_number in range(1, max_attempts + 1):
        attempt_started = time.perf_counter()
        try:
            completion = complete(plan, attempt_number)
        except Exception as exc:
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="completion_error",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    issues=(f"completion_exception:{type(exc).__name__}",),
                )
            )
            continue

        if not isinstance(completion, SectionCompletion):
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="completion_error",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    issues=("invalid_completion_envelope",),
                )
            )
            continue

        content = completion.content.strip()
        if not content:
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="empty",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    finish_reason=completion.finish_reason,
                    usage=dict(completion.usage),
                    empty_reason=completion.empty_reason or "empty_content",
                )
            )
            continue

        try:
            parsed = parse(plan, content)
        except Exception as exc:
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="parse_error",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    finish_reason=completion.finish_reason,
                    usage=dict(completion.usage),
                    issues=(f"parse_exception:{type(exc).__name__}",),
                )
            )
            continue
        if not isinstance(parsed, dict) or not parsed:
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="parse_error",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    finish_reason=completion.finish_reason,
                    usage=dict(completion.usage),
                    issues=("invalid_parsed_section",),
                )
            )
            continue

        try:
            audit_result = audit(plan, parsed)
        except Exception as exc:
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="audit_rejected",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    finish_reason=completion.finish_reason,
                    usage=dict(completion.usage),
                    issues=(f"audit_exception:{type(exc).__name__}",),
                )
            )
            continue
        if not isinstance(audit_result, SectionAuditResult):
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="audit_rejected",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    finish_reason=completion.finish_reason,
                    usage=dict(completion.usage),
                    issues=("invalid_audit_result",),
                )
            )
            continue
        if not audit_result.accepted:
            attempts.append(
                SectionAttempt(
                    attempt=attempt_number,
                    status="audit_rejected",
                    elapsed_ms=_elapsed_ms(attempt_started),
                    finish_reason=completion.finish_reason,
                    usage=dict(completion.usage),
                    issues=audit_result.issues,
                )
            )
            continue

        attempts.append(
            SectionAttempt(
                attempt=attempt_number,
                status="accepted",
                elapsed_ms=_elapsed_ms(attempt_started),
                finish_reason=completion.finish_reason,
                usage=dict(completion.usage),
                issues=audit_result.issues,
            )
        )
        return SectionWriteResult(
            plan=plan,
            status="accepted",
            section=dict(parsed),
            attempts=tuple(attempts),
            elapsed_ms=_elapsed_ms(section_started),
        )

    fallback_reason = attempts[-1].status if attempts else "attempts_exhausted"
    try:
        fallback_section = fallback(plan, tuple(attempts))
    except Exception as exc:
        raise SectionWriterError(
            f"deterministic fallback failed for section {plan.section_id}: {type(exc).__name__}"
        ) from exc
    if not isinstance(fallback_section, dict) or not fallback_section:
        raise SectionWriterError(
            f"deterministic fallback returned an invalid section for {plan.section_id}"
        )
    return SectionWriteResult(
        plan=plan,
        status="fallback",
        section=dict(fallback_section),
        attempts=tuple(attempts),
        elapsed_ms=_elapsed_ms(section_started),
        fallback_reason=fallback_reason,
    )


def _validate_options(
    plans: tuple[SectionWritePlan, ...],
    *,
    max_workers: int,
    max_attempts: int,
) -> None:
    if len(plans) != SECTION_COUNT:
        raise ValueError(f"section writer requires exactly {SECTION_COUNT} plans")
    if any(not isinstance(plan, SectionWritePlan) for plan in plans):
        raise TypeError("all section plans must be SectionWritePlan instances")
    section_ids = [plan.section_id.strip() for plan in plans]
    if any(not section_id for section_id in section_ids):
        raise ValueError("section_id must not be empty")
    if len(set(section_ids)) != len(section_ids):
        raise ValueError("section_id must be unique")
    if not 1 <= max_workers <= MAX_SECTION_WORKERS:
        raise ValueError(f"max_workers must be between 1 and {MAX_SECTION_WORKERS}")
    if not 1 <= max_attempts <= MAX_SECTION_ATTEMPTS:
        raise ValueError(f"max_attempts must be between 1 and {MAX_SECTION_ATTEMPTS}")


def _build_metadata(results: tuple[SectionWriteResult, ...]) -> SectionWriterMetadata:
    section_metadata: list[dict[str, Any]] = []
    empty_reasons: dict[str, tuple[str, ...]] = {}
    for result in results:
        reasons = tuple(
            attempt.empty_reason for attempt in result.attempts if attempt.empty_reason is not None
        )
        if reasons:
            empty_reasons[result.plan.section_id] = reasons
        finish_reason = result.attempts[-1].finish_reason if result.attempts else ""
        section_metadata.append(
            {
                "section_id": result.plan.section_id,
                "status": result.status,
                "accepted": result.accepted,
                "attempt_count": len(result.attempts),
                "elapsed_ms": result.elapsed_ms,
                "finish_reason": finish_reason,
                "usage": _aggregate_usage(result.attempts),
                "empty_reasons": list(reasons),
                "fallback_reason": result.fallback_reason,
            }
        )
    return SectionWriterMetadata(
        version=SECTION_WRITER_VERSION,
        model_accepted_count=sum(result.accepted for result in results),
        fallback_count=sum(not result.accepted for result in results),
        attempt_count=sum(len(result.attempts) for result in results),
        empty_reasons=empty_reasons,
        sections=tuple(section_metadata),
    )


def _aggregate_usage(attempts: tuple[SectionAttempt, ...]) -> dict[str, Any]:
    totals: dict[str, float | int] = {}
    for attempt in attempts:
        for key, value in attempt.usage.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            totals[key] = totals.get(key, 0) + value
    return totals


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
