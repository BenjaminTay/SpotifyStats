"""Supported music-search snapshot variants and deterministic priority."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from backend.domains.music_search.context import (
    MusicSearchFilterContext,
    build_music_search_filter_context,
)


@dataclass(frozen=True)
class MusicSearchSnapshotVariant:
    merge_level: int
    dynamic_threshold: bool
    priority: int

    @property
    def key(self) -> str:
        dynamic = "dynamic" if self.dynamic_threshold else "fixed"
        return f"l{self.merge_level}:{dynamic}"


# Default private behavior is built first.  The remaining order is stable so
# reports, tests and job diagnostics can be compared across runs.
MUSIC_SEARCH_SNAPSHOT_VARIANTS: tuple[MusicSearchSnapshotVariant, ...] = (
    MusicSearchSnapshotVariant(merge_level=2, dynamic_threshold=True, priority=0),
    MusicSearchSnapshotVariant(merge_level=1, dynamic_threshold=True, priority=1),
    MusicSearchSnapshotVariant(merge_level=3, dynamic_threshold=True, priority=2),
    MusicSearchSnapshotVariant(merge_level=2, dynamic_threshold=False, priority=3),
    MusicSearchSnapshotVariant(merge_level=1, dynamic_threshold=False, priority=4),
    MusicSearchSnapshotVariant(merge_level=3, dynamic_threshold=False, priority=5),
)


def build_music_search_variant_contexts(
    conn: sqlite3.Connection,
    base_filters: Mapping[str, Any],
) -> tuple[MusicSearchFilterContext, ...]:
    return tuple(
        build_music_search_filter_context(
            conn,
            {
                **base_filters,
                "merge_level": variant.merge_level,
                "dynamic_threshold": variant.dynamic_threshold,
            },
        )
        for variant in MUSIC_SEARCH_SNAPSHOT_VARIANTS
    )
