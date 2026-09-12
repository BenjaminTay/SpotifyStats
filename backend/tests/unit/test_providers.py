"""Unit tests for provider error mapping and redaction."""

from __future__ import annotations

import logging
import urllib.error

import pytest

pytestmark = pytest.mark.unit


class _FailingOpener:
    def open(self, _req, timeout):  # noqa: ARG002
        raise urllib.error.URLError("network unavailable")


def test_http_client_maps_network_failure_to_provider_error(monkeypatch):
    from backend.infrastructure.http.client import HttpClient
    from backend.providers.base import ProviderNetworkError

    client = HttpClient(timeout=1, retries=0)
    monkeypatch.setattr(client, "_build_opener", lambda: _FailingOpener())

    with pytest.raises(ProviderNetworkError) as exc:
        client.get("https://example.invalid/test")

    assert "network unavailable" in str(exc.value)


def test_provider_http_error_classification():
    from backend.providers.base import (
        ProviderAuthError,
        ProviderRateLimitError,
        ProviderServerError,
        provider_error_from_status,
    )

    assert isinstance(provider_error_from_status("spotify", 401, "bad key"), ProviderAuthError)
    assert isinstance(
        provider_error_from_status("spotify", 429, "slow down"), ProviderRateLimitError
    )
    assert isinstance(provider_error_from_status("spotify", 503, "down"), ProviderServerError)


def test_llm_provider_redacts_api_key():
    from backend.providers.llm.client import LLMProvider

    provider = LLMProvider(
        provider="openai",
        api_key="sk-1234567890abcdef",  # pragma: allowlist secret
        model="gpt-test",  # pragma: allowlist secret
    )  # pragma: allowlist secret

    redacted = provider.redact()

    assert redacted["api_key"] != "sk-1234567890abcdef"  # pragma: allowlist secret
    assert redacted["api_key"].endswith("***")


def test_llm_text_completion_normalizes_openai_observability(monkeypatch):
    from backend.providers.llm.client import LLMProvider

    provider = LLMProvider(
        provider="openai",
        api_key="sk-test",  # pragma: allowlist secret
        model="gpt-test",
    )
    monkeypatch.setattr(
        provider,
        "chat",
        lambda *_args, **_kwargs: {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "完成"},
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 2},
        },
    )

    result = provider.complete_text([{"role": "user", "content": "问题"}])

    assert result.content == "完成"
    assert result.provider == "openai"
    assert result.model == "gpt-test"
    assert result.finish_reason == "stop"
    assert result.usage == {"prompt_tokens": 8, "completion_tokens": 2}
    assert result.elapsed_ms >= 0
    assert result.empty_reason == ""


def test_llm_text_completion_normalizes_anthropic_and_empty_reason(monkeypatch):
    from backend.providers.llm.client import LLMProvider

    provider = LLMProvider(
        provider="anthropic",
        api_key="anthropic-test",  # pragma: allowlist secret
        model="claude-test",
    )
    responses = iter(
        [
            {
                "stop_reason": "end_turn",
                "content": [
                    {"type": "text", "text": "第一段"},
                    {"type": "text", "text": "第二段"},
                ],
                "usage": {"input_tokens": 9, "output_tokens": 3},
            },
            {
                "stop_reason": "max_tokens",
                "content": [{"type": "text", "text": ""}],
                "usage": {"input_tokens": 9, "output_tokens": 0},
            },
        ]
    )
    monkeypatch.setattr(provider, "chat", lambda *_args, **_kwargs: next(responses))

    success = provider.complete_text([{"role": "user", "content": "问题"}])
    empty = provider.complete_text([{"role": "user", "content": "问题"}])

    assert success.content == "第一段\n第二段"
    assert success.finish_reason == "end_turn"
    assert success.usage == {"input_tokens": 9, "output_tokens": 3}
    assert success.empty_reason == ""
    assert empty.content == ""
    assert empty.finish_reason == "max_tokens"
    assert empty.empty_reason == "max_tokens_without_content"


def test_llm_text_completion_classifies_transport_failure(monkeypatch):
    from backend.providers.base import ProviderNetworkError
    from backend.providers.llm.client import LLMProvider

    provider = LLMProvider(
        provider="openai",
        api_key="sk-test",  # pragma: allowlist secret
        model="gpt-test",
    )

    def fail(*_args, **_kwargs):
        raise ProviderNetworkError("openai", "network unavailable")

    monkeypatch.setattr(provider, "chat", fail)

    result = provider.complete_text([{"role": "user", "content": "问题"}])

    assert result.content == ""
    assert result.provider == "openai"
    assert result.model == "gpt-test"
    assert result.empty_reason == "transport_error"


def test_deepseek_explicitly_switches_thinking_mode(monkeypatch):
    from backend.providers.llm.client import LLMProvider

    provider = LLMProvider(
        provider="deepseek",
        api_key="deepseek-test",  # pragma: allowlist secret
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    bodies: list[dict] = []

    class Response:
        status = 200

        @staticmethod
        def json():
            return {"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}]}

    def post(_url, *, data, headers):  # noqa: ARG001
        bodies.append(data)
        return Response()

    monkeypatch.setattr(provider._http, "post", post)

    provider.chat([{"role": "user", "content": "直接回答"}], thinking=False)
    provider.chat([{"role": "user", "content": "先分析"}], thinking=True)

    assert bodies[0]["thinking"] == {"type": "disabled"}
    assert bodies[1]["thinking"] == {"type": "enabled"}


def test_ai_insights_structured_helper_keeps_legacy_wrapper_compatible(monkeypatch):
    from backend.providers.llm.client import LLMTextCompletion
    from backend.services import ai_insights_service

    completions = iter(
        [
            LLMTextCompletion(
                content="结构化结果",
                provider="deepseek",
                model="deepseek-test",
                finish_reason="stop",
                usage={"total_tokens": 12},
                elapsed_ms=7,
            ),
            LLMTextCompletion(
                provider="deepseek",
                model="deepseek-test",
                empty_reason="transport_error",
            ),
        ]
    )

    class FakeProvider:
        provider = "deepseek"
        model = "deepseek-test"

        def complete_text(self, *_args, **_kwargs):
            return next(completions)

    monkeypatch.setattr(ai_insights_service, "_get_config", lambda: {})
    monkeypatch.setattr(ai_insights_service, "_get_llm", lambda _cfg: FakeProvider())

    structured = ai_insights_service._llm_text_completion("system", "data")
    failed_legacy = ai_insights_service._llm_chat("system", "data")

    assert structured is not None
    assert structured.content == "结构化结果"
    assert structured.finish_reason == "stop"
    assert structured.usage == {"total_tokens": 12}
    assert failed_legacy is None


def test_ai_insights_structured_helper_does_not_log_sensitive_inputs(monkeypatch, caplog):
    from backend.services import ai_insights_service

    class BrokenProvider:
        provider = "custom"
        model = "model-test"

        def complete_text(self, *_args, **_kwargs):
            raise RuntimeError("raw-provider-response")

    monkeypatch.setattr(ai_insights_service, "_get_config", lambda: {})
    monkeypatch.setattr(ai_insights_service, "_get_llm", lambda _cfg: BrokenProvider())

    with caplog.at_level(logging.WARNING):
        result = ai_insights_service._llm_text_completion(
            "system-secret-prompt",
            "user-private-data",
        )

    assert result is not None
    assert result.empty_reason == "provider_error"
    assert "system-secret-prompt" not in caplog.text
    assert "user-private-data" not in caplog.text
    assert "raw-provider-response" not in caplog.text


def test_llm_translator_uses_provider_for_openai_compatible(monkeypatch):
    from backend.services import llm_translator

    calls = []

    class FakeProvider:
        def __init__(self, provider, api_key, model, base_url):  # noqa: PLR0913
            calls.append((provider, api_key, model, base_url))

        def chat(self, messages, temperature=0.3, max_tokens=4096):  # noqa: ARG002
            assert messages[0]["role"] == "system"
            return {"choices": [{"message": {"content": "翻译结果"}}]}

    monkeypatch.setattr(llm_translator, "LLMProvider", FakeProvider)

    result = llm_translator._translate_openai_compat(
        "hello",
        "sk-test",  # pragma: allowlist secret
        "test-model",
        "https://example.test/v1",
        provider="custom",
    )

    assert result == "翻译结果"
    assert calls == [
        ("custom", "sk-test", "test-model", "https://example.test/v1")  # pragma: allowlist secret
    ]


def test_llm_translator_keeps_anthropic_v1_base_url(monkeypatch):
    from backend.services import llm_translator

    calls = []

    class FakeProvider:
        def __init__(self, provider, api_key, model, base_url):  # noqa: PLR0913
            calls.append((provider, api_key, model, base_url))

        def chat(self, messages, temperature=0.3, max_tokens=4096):  # noqa: ARG002
            assert messages[0]["role"] == "system"
            return {"content": [{"text": "结构化结果"}]}

    monkeypatch.setattr(llm_translator, "LLMProvider", FakeProvider)

    result = llm_translator._translate_anthropic(
        "hello",
        "anthropic-key",
        "claude-test",
        "https://api.anthropic.com",
    )

    assert result == "结构化结果"
    assert calls == [("anthropic", "anthropic-key", "claude-test", "https://api.anthropic.com/v1")]
