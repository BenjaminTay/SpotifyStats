"""Valid-JSON context compaction for model-visible tool results."""

from __future__ import annotations

import json
from typing import Any


def compact_value(
    value: Any,
    *,
    max_depth: int = 6,
    max_list_items: int = 30,
    max_string_chars: int = 4000,
    _depth: int = 0,
) -> Any:
    """Bound nested values without ever slicing serialized JSON mid-token."""

    if _depth >= max_depth:
        return {"_truncated": True, "reason": "max_depth"}
    if isinstance(value, dict):
        return {
            str(key): compact_value(
                item,
                max_depth=max_depth,
                max_list_items=max_list_items,
                max_string_chars=max_string_chars,
                _depth=_depth + 1,
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        compacted = [
            compact_value(
                item,
                max_depth=max_depth,
                max_list_items=max_list_items,
                max_string_chars=max_string_chars,
                _depth=_depth + 1,
            )
            for item in value[:max_list_items]
        ]
        if len(value) > max_list_items:
            compacted.append(
                {
                    "_truncated": True,
                    "omitted_items": len(value) - max_list_items,
                }
            )
        return compacted
    if isinstance(value, str) and len(value) > max_string_chars:
        return {
            "_truncated_text": value[:max_string_chars],
            "original_chars": len(value),
        }
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def compact_json(value: Any) -> str:
    return json.dumps(compact_value(value), ensure_ascii=False, separators=(",", ":"))
