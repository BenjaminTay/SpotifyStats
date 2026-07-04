"""LLM helpers for editorial-agent steps."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, Optional

from backend.services.ai_insights_service import _llm_chat

ChatFn = Callable[[str, str, float], Optional[str]]


def extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        raw = raw[start : end + 1] if start >= 0 and end > start else raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def call_json_step(
    system_prompt: str,
    payload: dict[str, Any],
    *,
    temperature: float,
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    chat = chat_fn or _llm_chat
    text = chat(
        system_prompt,
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
        temperature,
    )
    if not text:
        return {}
    return extract_json_object(text)
