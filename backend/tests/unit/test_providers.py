"""Unit tests for provider error mapping and redaction."""

from __future__ import annotations

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
