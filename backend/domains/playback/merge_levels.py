"""Public merge-level normalization for the L2/L3 product modes."""

from __future__ import annotations


def normalize_merge_level(value: int | str | None) -> int:
    """Coerce legacy/invalid values to L2; only L2 and L3 are selectable."""
    try:
        level = int(value) if value is not None else 2
    except (TypeError, ValueError):
        return 2
    return level if level in {2, 3} else 2
