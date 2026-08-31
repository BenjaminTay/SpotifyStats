from __future__ import annotations

import json
from typing import Any, cast

import pytest

from backend.infrastructure.http.client import HttpResponse
from backend.providers.base import ProviderConfig, ProviderHTTPError
from backend.providers.llm.client import LLMProvider


class FakeHttpClient:
    def __init__(self, response: HttpResponse):
        self.response = response
        self.requests: list[tuple[str, Any, Any]] = []

    def post(self, url, data=None, headers=None):
        self.requests.append((url, data, headers))
        return self.response


def _provider(
    provider: str, payload: dict, status: int = 200
) -> tuple[LLMProvider, FakeHttpClient]:
    llm = LLMProvider(
        provider=provider,
        api_key="test-key",  # pragma: allowlist secret
        model="test-model",
        config=ProviderConfig(name="test", base_url="https://llm.test/v1"),
    )
    fake = FakeHttpClient(
        HttpResponse(
            status=status,
            body=json.dumps(payload).encode(),
            headers={},
        )
    )
    llm._http = cast(Any, fake)
    return llm, fake


def test_openai_native_tool_call_is_normalized():
    llm, fake = _provider(
        "openai",
        {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "analysis_stats",
                                    "arguments": '{"period":"year"}',
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {"total_tokens": 42},
        },
    )

    result = llm.complete_with_tools(
        [{"role": "user", "content": "今年听歌怎么样"}],
        [
            {
                "name": "analysis_stats",
                "description": "统计",
                "parameters": {"type": "object"},
            }
        ],
    )

    assert result.tool_calls[0].call_id == "call-1"
    assert result.tool_calls[0].name == "analysis_stats"
    assert result.tool_calls[0].arguments == {"period": "year"}
    assert result.usage == {"total_tokens": 42}
    assert fake.requests[0][1]["tool_choice"] == "auto"


def test_anthropic_tool_use_and_tool_result_are_native_blocks():
    llm, fake = _provider(
        "anthropic",
        {
            "stop_reason": "end_turn",
            "content": [
                {"type": "text", "text": "完成"},
                {
                    "type": "tool_use",
                    "id": "toolu-1",
                    "name": "entity_stats",
                    "input": {"entity_name": "A"},
                },
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )
    messages = [
        {"role": "system", "content": "system"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "old-call",
                    "function": {
                        "name": "entity_stats",
                        "arguments": '{"entity_name":"A"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "old-call",
            "name": "entity_stats",
            "content": '{"status":"ok"}',
        },
    ]

    result = llm.complete_with_tools(
        messages,
        [
            {
                "name": "entity_stats",
                "description": "实体统计",
                "parameters": {"type": "object"},
            }
        ],
    )

    assert result.content == "完成"
    assert result.tool_calls[0].arguments == {"entity_name": "A"}
    request_body = fake.requests[0][1]
    assert request_body["system"] == "system"
    assert request_body["messages"][0]["content"][0]["type"] == "tool_use"
    assert request_body["messages"][1]["content"][0]["type"] == "tool_result"


def test_native_tool_http_failure_is_not_silently_swallowed():
    llm, _fake = _provider("openai", {"error": "unsupported tools"}, status=400)

    with pytest.raises(ProviderHTTPError) as caught:
        llm.complete_with_tools([], [])

    assert caught.value.status == 400
