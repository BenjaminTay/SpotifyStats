from __future__ import annotations

import threading
import time
from collections import Counter

import pytest

from backend.domains.ai_reports.section_writer import (
    SectionAuditResult,
    SectionCompletion,
    SectionWritePlan,
    SectionWriterError,
    write_report_sections,
)

pytestmark = pytest.mark.unit


def _plans() -> tuple[SectionWritePlan, ...]:
    return tuple(
        SectionWritePlan(
            section_id=f"section-{index}",
            heading=f"第 {index} 节",
            payload={"order": index},
        )
        for index in range(6)
    )


def _parse(plan: SectionWritePlan, content: str) -> dict[str, object]:
    return {"id": plan.section_id, "heading": plan.heading, "prose": content}


def _accept(_plan: SectionWritePlan, _section: dict[str, object]) -> SectionAuditResult:
    return SectionAuditResult(accepted=True)


def _fallback(plan: SectionWritePlan, _attempts: tuple[object, ...]) -> dict[str, object]:
    return {"id": plan.section_id, "heading": plan.heading, "prose": "deterministic"}


def test_writer_limits_concurrency_and_preserves_plan_order() -> None:
    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def complete(plan: SectionWritePlan, _attempt: int) -> SectionCompletion:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            time.sleep(0.005 * (7 - int(plan.payload["order"])))
            return SectionCompletion(
                content=f"model-{plan.section_id}",
                finish_reason="stop",
                usage={"input_tokens": 10, "output_tokens": 4},
            )
        finally:
            with lock:
                active -= 1

    run = write_report_sections(
        _plans(), complete=complete, parse=_parse, audit=_accept, fallback=_fallback
    )

    assert maximum_active == 2
    assert [result.plan.section_id for result in run.results] == [
        f"section-{index}" for index in range(6)
    ]
    assert [section["prose"] for section in run.sections] == [
        f"model-section-{index}" for index in range(6)
    ]
    assert run.metadata.model_accepted_count == 6
    assert run.metadata.fallback_count == 0
    assert run.metadata.attempt_count == 6
    assert all(item["accepted"] is True for item in run.metadata.sections)


def test_empty_completion_retries_only_affected_section() -> None:
    calls: Counter[str] = Counter()

    def complete(plan: SectionWritePlan, _attempt: int) -> SectionCompletion:
        calls[plan.section_id] += 1
        if plan.section_id == "section-2" and calls[plan.section_id] == 1:
            return SectionCompletion(
                finish_reason="length",
                usage={"input_tokens": 8},
                empty_reason="provider_empty_choice",
            )
        return SectionCompletion(content="valid", finish_reason="stop")

    run = write_report_sections(
        _plans(), complete=complete, parse=_parse, audit=_accept, fallback=_fallback
    )

    assert calls == Counter({"section-2": 2, **{f"section-{i}": 1 for i in (0, 1, 3, 4, 5)}})
    assert run.metadata.attempt_count == 7
    assert run.metadata.empty_reasons == {"section-2": ("provider_empty_choice",)}
    section = run.results[2]
    assert [attempt.status for attempt in section.attempts] == ["empty", "accepted"]
    assert section.accepted is True


def test_structural_parse_error_retries_only_current_section() -> None:
    completion_calls: Counter[str] = Counter()

    def complete(plan: SectionWritePlan, _attempt: int) -> SectionCompletion:
        completion_calls[plan.section_id] += 1
        return SectionCompletion(content=f"payload-{completion_calls[plan.section_id]}")

    def parse(plan: SectionWritePlan, content: str) -> dict[str, object]:
        if plan.section_id == "section-4" and content == "payload-1":
            return {}
        return _parse(plan, content)

    run = write_report_sections(
        _plans(), complete=complete, parse=parse, audit=_accept, fallback=_fallback
    )

    assert completion_calls["section-4"] == 2
    assert all(completion_calls[f"section-{index}"] == 1 for index in range(6) if index != 4)
    assert [attempt.status for attempt in run.results[4].attempts] == [
        "parse_error",
        "accepted",
    ]


def test_audit_rejection_is_retried_and_usage_is_aggregated() -> None:
    def complete(plan: SectionWritePlan, attempt: int) -> SectionCompletion:
        return SectionCompletion(
            content=f"attempt-{attempt}",
            finish_reason=f"stop-{attempt}",
            usage={"input_tokens": 10, "output_tokens": attempt},
        )

    def audit(plan: SectionWritePlan, section: dict[str, object]) -> SectionAuditResult:
        if plan.section_id == "section-1" and section["prose"] == "attempt-1":
            return SectionAuditResult(accepted=False, issues=("missing_evidence",))
        return SectionAuditResult(accepted=True)

    run = write_report_sections(
        _plans(), complete=complete, parse=_parse, audit=audit, fallback=_fallback
    )

    section_metadata = run.metadata.sections[1]
    assert section_metadata["attempt_count"] == 2
    assert section_metadata["finish_reason"] == "stop-2"
    assert section_metadata["usage"] == {"input_tokens": 20, "output_tokens": 3}
    assert run.results[1].attempts[0].issues == ("missing_evidence",)


def test_exhausted_section_uses_fallback_without_marking_it_accepted() -> None:
    fallback_calls: list[str] = []

    def complete(plan: SectionWritePlan, _attempt: int) -> SectionCompletion:
        if plan.section_id == "section-3":
            return SectionCompletion(empty_reason="upstream_empty")
        return SectionCompletion(content="valid")

    def fallback(plan: SectionWritePlan, attempts: tuple[object, ...]) -> dict[str, object]:
        fallback_calls.append(plan.section_id)
        assert len(attempts) == 2
        return _fallback(plan, attempts)

    run = write_report_sections(
        _plans(), complete=complete, parse=_parse, audit=_accept, fallback=fallback
    )

    assert fallback_calls == ["section-3"]
    result = run.results[3]
    assert result.status == "fallback"
    assert result.accepted is False
    assert result.fallback_reason == "empty"
    assert result.to_dict()["accepted"] is False
    assert run.metadata.model_accepted_count == 5
    assert run.metadata.fallback_count == 1
    assert run.metadata.sections[3]["accepted"] is False


@pytest.mark.parametrize(
    ("plans", "options", "message"),
    [
        (_plans()[:5], {}, "exactly 6"),
        (_plans(), {"max_workers": 3}, "max_workers"),
        (_plans(), {"max_attempts": 3}, "max_attempts"),
        (
            (*_plans()[:5], SectionWritePlan(section_id="section-0", heading="duplicate")),
            {},
            "unique",
        ),
    ],
)
def test_writer_rejects_invalid_bounded_configuration(
    plans: tuple[SectionWritePlan, ...], options: dict[str, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        write_report_sections(
            plans,
            complete=lambda _plan, _attempt: SectionCompletion(content="valid"),
            parse=_parse,
            audit=_accept,
            fallback=_fallback,
            **options,
        )


def test_invalid_fallback_fails_closed() -> None:
    with pytest.raises(SectionWriterError, match="invalid section"):
        write_report_sections(
            _plans(),
            complete=lambda _plan, _attempt: SectionCompletion(),
            parse=_parse,
            audit=_accept,
            fallback=lambda _plan, _attempts: {},
        )
