"""Merge level normalization.

L1 = no merge, L2 = recording scope (default), L3 = composition scope.
"""

from __future__ import annotations


def normalize_merge_level(value: int | str | None) -> int:
    """Coerce any merge_level input to a valid 1-3 integer, defaulting to 2."""
    try:
        level = int(value) if value is not None else 2
    except (TypeError, ValueError):
        return 2
    return level if level in {1, 2, 3} else 2
