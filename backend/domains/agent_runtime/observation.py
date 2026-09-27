"""Compact, valid-JSON observations for the model-facing transcript."""

from __future__ import annotations

from typing import Any

from backend.domains.agent_runtime.serialization import compact_value


def compact_observation(data: dict[str, Any]) -> dict[str, Any]:
    """Keep evidence useful while bounding repeated rows and verbose text."""

    compacted = compact_value(
        data,
        # Tool envelopes add two levels before domain payloads.  Seven keeps
        # scalar fields inside common ``...buckets[].label/hours`` rows while
        # still bounding unexpectedly deep provider payloads.
        max_depth=7,
        max_list_items=12,
        max_string_chars=1200,
    )
    return compacted if isinstance(compacted, dict) else {}
