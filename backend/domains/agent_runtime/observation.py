"""Compact, valid-JSON observations for the model-facing transcript."""

from __future__ import annotations

from typing import Any

from backend.domains.agent_runtime.serialization import compact_value


def compact_observation(data: dict[str, Any]) -> dict[str, Any]:
    """Keep evidence useful while bounding repeated rows and verbose text."""

    compacted = compact_value(
        data,
        max_depth=5,
        max_list_items=12,
        max_string_chars=1200,
    )
    return compacted if isinstance(compacted, dict) else {}
