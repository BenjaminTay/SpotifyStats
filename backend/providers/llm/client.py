"""LLM provider — unified interface for multiple LLM backends.

Supports DeepSeek, OpenAI, Anthropic, and custom OpenAI-compatible backends.
Uses the shared HttpClient for HTTP transport.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from backend.core.config import HTTP_PROXY, HTTPS_PROXY
from backend.infrastructure.http.client import HttpClient
from backend.providers.base import (
    BaseProvider,
    ProviderConfig,
    ProviderParseError,
    provider_error_from_status,
)


@dataclass(frozen=True)
class LLMToolCall:
    """Provider-neutral native tool call."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMCompletion:
    """Provider-neutral model turn used by the Agent V2 runtime."""

    content: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider(BaseProvider):
    """Provider for LLM APIs (translation, structured extraction).

    Supports multiple backends through a unified interface:
    - DeepSeek (api.deepseek.com)
    - OpenAI (api.openai.com)
    - Anthropic (api.anthropic.com)
    - Custom (user-specified OpenAI-compatible endpoint)
    """

    PROVIDER_URLS = {
        "deepseek": "https://api.deepseek.com/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
    }

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str | None = None,
        config: ProviderConfig | None = None,
    ):
        if config is None:
            config = ProviderConfig(
                name=f"llm-{provider}",
                base_url=base_url or self.PROVIDER_URLS.get(provider, ""),
                timeout=60,
                retries=3,
                rate_limit_rps=3.0,
                https_proxy=HTTPS_PROXY or "",
                http_proxy=HTTP_PROXY or "",
            )
        super().__init__(config)
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self._http = HttpClient(timeout=config.timeout, retries=config.retries)

    @property
    def base_url(self) -> str:
        return self.config.base_url

    def health_check(self) -> bool:
        try:
            headers = self._auth_headers()
            resp = self._http.get(
                f"{self.base_url}/models",
                headers=headers,
            )
            return resp.status in (200, 401)  # 401 = key invalid but endpoint reachable
        except Exception:
            return False

    def redact(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key[:8] + "***" if self.api_key else "unset",
        }

    def _auth_headers(self) -> dict:
        if self.provider == "anthropic":
            return {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> dict | None:
        """Send a chat completion request. Returns the API response dict or None on failure."""
        headers = self._auth_headers()

        if self.provider == "anthropic":
            system_msg = ""
            user_messages = []
            for m in messages:
                if m["role"] == "system":
                    system_msg = m["content"]
                else:
                    user_messages.append(m)
            body = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": user_messages,
            }
            if system_msg:
                body["system"] = system_msg
            url = f"{self.base_url}/messages"
        else:
            body = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if thinking:
                body["thinking"] = {"type": "enabled"}
            url = f"{self.base_url}/chat/completions"

        resp = self._http.post(url, data=body, headers=headers)
        if resp.status == 200:
            return resp.json()
        return None

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> LLMCompletion:
        """Run one native tool-calling turn and fail with structured errors.

        V2 deliberately does not parse tool calls from prose/JSON. A provider
        must implement the OpenAI-compatible ``tools`` protocol or Anthropic's
        native ``tool_use`` content blocks.
        """

        headers = self._auth_headers()
        if self.provider == "anthropic":
            system, anthropic_messages = self._anthropic_messages(messages)
            body: dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": anthropic_messages,
                "tools": [
                    {
                        "name": item["name"],
                        "description": item.get("description", ""),
                        "input_schema": item.get("parameters", {"type": "object"}),
                    }
                    for item in tools
                ],
            }
            if system:
                body["system"] = system
            url = f"{self.base_url}/messages"
        else:
            body = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": item["name"],
                            "description": item.get("description", ""),
                            "parameters": item.get("parameters", {"type": "object"}),
                        },
                    }
                    for item in tools
                ],
                "tool_choice": "auto",
            }
            if thinking:
                body["thinking"] = {"type": "enabled"}
            url = f"{self.base_url}/chat/completions"

        resp = self._http.post(url, data=body, headers=headers)
        if resp.status != 200:
            detail = resp.text()[:500]
            raise provider_error_from_status(self.provider, resp.status, detail)
        try:
            payload = resp.json()
            if self.provider == "anthropic":
                return self._parse_anthropic_completion(payload)
            return self._parse_openai_completion(payload)
        except ProviderParseError:
            raise
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderParseError(self.provider, f"Invalid native tool response: {exc}") from exc

    @staticmethod
    def _decode_tool_arguments(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if raw in (None, ""):
            return {}
        parsed = json.loads(str(raw))
        if not isinstance(parsed, dict):
            raise ValueError("tool arguments must be a JSON object")
        return parsed

    def _parse_openai_completion(self, payload: dict[str, Any]) -> LLMCompletion:
        choice = payload["choices"][0]
        message = choice["message"]
        calls = []
        for index, item in enumerate(message.get("tool_calls") or []):
            function = item.get("function") or {}
            calls.append(
                LLMToolCall(
                    call_id=str(item.get("id") or f"call_{index}"),
                    name=str(function["name"]),
                    arguments=self._decode_tool_arguments(function.get("arguments")),
                )
            )
        return LLMCompletion(
            content=str(message.get("content") or ""),
            tool_calls=calls,
            finish_reason=str(choice.get("finish_reason") or ""),
            usage=payload.get("usage") or {},
        )

    def _parse_anthropic_completion(self, payload: dict[str, Any]) -> LLMCompletion:
        text_parts = []
        calls = []
        for index, block in enumerate(payload.get("content") or []):
            if block.get("type") == "text":
                text_parts.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                calls.append(
                    LLMToolCall(
                        call_id=str(block.get("id") or f"toolu_{index}"),
                        name=str(block["name"]),
                        arguments=self._decode_tool_arguments(block.get("input")),
                    )
                )
        return LLMCompletion(
            content="\n".join(part for part in text_parts if part),
            tool_calls=calls,
            finish_reason=str(payload.get("stop_reason") or ""),
            usage=payload.get("usage") or {},
        )

    @staticmethod
    def _anthropic_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        converted: list[dict[str, Any]] = []
        pending_tool_results: list[dict[str, Any]] = []

        def flush_tool_results() -> None:
            if pending_tool_results:
                converted.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for message in messages:
            role = message.get("role")
            if role == "system":
                system_parts.append(str(message.get("content") or ""))
                continue
            if role == "tool":
                pending_tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": str(message.get("tool_call_id") or ""),
                        "content": str(message.get("content") or ""),
                    }
                )
                continue
            flush_tool_results()
            if role == "assistant" and message.get("tool_calls"):
                content: list[dict[str, Any]] = []
                if message.get("content"):
                    content.append({"type": "text", "text": str(message["content"])})
                for item in message["tool_calls"]:
                    function = item.get("function") or {}
                    content.append(
                        {
                            "type": "tool_use",
                            "id": str(item.get("id") or ""),
                            "name": str(function.get("name") or ""),
                            "input": LLMProvider._decode_tool_arguments(function.get("arguments")),
                        }
                    )
                converted.append({"role": "assistant", "content": content})
            else:
                converted.append({"role": str(role), "content": str(message.get("content") or "")})
        flush_tool_results()
        return "\n\n".join(system_parts), converted

    def translate(
        self, text: str, target_lang: str = "zh-CN", source_lang: str = "en"
    ) -> str | None:
        """Translate text using the configured LLM. Returns translated text or None."""
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. Translate the following text "
                    f"from {source_lang} to {target_lang}. Preserve formatting, "
                    f"paragraph structure, and markdown (bold, italic). Output ONLY the translation."
                ),
            },
            {"role": "user", "content": text},
        ]
        result = self.chat(messages, temperature=0.3)
        if result is None:
            return None
        if self.provider == "anthropic":
            return result.get("content", [{}])[0].get("text", "")
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")

    def extract_structured(self, text: str, schema_description: str) -> dict | None:
        """Extract structured JSON data from text using the configured LLM."""
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a data extraction engine. Extract structured information "
                    f"from the given text according to this schema: {schema_description}. "
                    f"Output ONLY valid JSON, no explanatory text."
                ),
            },
            {"role": "user", "content": text},
        ]
        result = self.chat(messages, temperature=0.1, max_tokens=2048)
        if result is None:
            return None
        raw = ""
        if self.provider == "anthropic":
            raw = result.get("content", [{}])[0].get("text", "")
        else:
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
