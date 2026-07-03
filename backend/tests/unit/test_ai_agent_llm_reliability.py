from __future__ import annotations

import pytest

from backend.services import ai_agent_service

pytestmark = pytest.mark.unit


def test_final_llm_error_classification_distinguishes_unconfigured_provider() -> None:
    assert (
        ai_agent_service._classify_final_llm_error(RuntimeError("LLM provider is not configured"))
        == ai_agent_service.FINAL_LLM_UNCONFIGURED_MESSAGE
    )
    assert (
        ai_agent_service._classify_final_llm_error(TimeoutError("request timed out"))
        == ai_agent_service.FINAL_LLM_PROVIDER_FAILURE_MESSAGE
    )


def test_final_llm_call_retries_transient_failure_once() -> None:
    calls: list[int] = []

    def flaky_call() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("request timed out")
        return "最终回答"

    assert ai_agent_service._call_final_llm_with_retry(flaky_call) == "最终回答"
    assert len(calls) == 2


def test_final_llm_call_does_not_retry_unconfigured_provider() -> None:
    calls: list[int] = []

    def unconfigured_call() -> str:
        calls.append(1)
        raise RuntimeError("LLM provider is not configured")

    with pytest.raises(ai_agent_service.ChatAgentError) as exc_info:
        ai_agent_service._call_final_llm_with_retry(unconfigured_call)

    assert str(exc_info.value) == ai_agent_service.FINAL_LLM_UNCONFIGURED_MESSAGE
    assert len(calls) == 1
