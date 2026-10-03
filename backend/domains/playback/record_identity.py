"""Canonical song IDs for new record rows and existing publications."""

from __future__ import annotations

import re

_INTEGER_ID = re.compile(r"([0-9]+)(?:\.0+)?")


def record_track_id(value: object) -> str | None:
    """Accept positive integer IDs, including legacy zero-fraction strings.

    Work with decimal text so large integer IDs are not rounded through float.
    Invalid IDs lose their link rather than pointing at a different song.
    """
    if value is None or isinstance(value, bool):
        return None
    match = _INTEGER_ID.fullmatch(str(value))
    if match is None:
        return None
    return match.group(1).lstrip("0") or None


def normalize_record_identity(row: dict) -> dict:
    """Copy a row, preserving names, metrics and non-song identities."""
    normalized = dict(row)
    if row.get("entity_type") == "track":
        normalized["entity_id"] = record_track_id(row.get("entity_id"))
    if "top_track_entity_id" in row:
        normalized["top_track_entity_id"] = record_track_id(row["top_track_entity_id"])
    return normalized
