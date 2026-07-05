"""LLM provider — unified interface for multiple LLM backends.

Supports DeepSeek, OpenAI, Anthropic, and custom OpenAI-compatible backends.
Uses the shared HttpClient for HTTP transport.
"""

from __future__ import annotations

import json

from backend.core.config import HTTP_PROXY, HTTPS_PROXY
from backend.infrastructure.http.client import HttpClient
from backend.providers.base import BaseProvider, ProviderConfig


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
