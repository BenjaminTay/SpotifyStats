"""Exact semantic filter context and lightweight source revisions for search."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_credits import get_track_credit_revision
from backend.domains.metadata.track_identity import (
    TRACK_IDENTITY_POLICY_VERSION,
    get_track_identity_revision,
)
from backend.domains.metadata.track_presentation import TRACK_PRESENTATION_POLICY_VERSION
from backend.domains.music_search.revisions import get_music_search_revision_state
from backend.domains.playback.album_projects import get_album_project_revision

MUSIC_SEARCH_STATISTICS_FINGERPRINT_VERSION = "music_search_statistics_v8_canonical_track"
# Compatibility name used by existing reports and API terminology.
MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION = MUSIC_SEARCH_STATISTICS_FINGERPRINT_VERSION
MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION = "music_search_snapshot_v8_canonical_track"
MUSIC_SEARCH_CHART_BUILDER_VERSION = "music_search_chart_v8_canonical_track"
MUSIC_SEARCH_SNAPSHOT_POLICY_VERSION = "music_search_snapshot_policy_v1"
LEGACY_MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION = "music_search_filter_v2"


@dataclass(frozen=True)
class MusicSearchFilterContext:
    min_ms: int
    music_only: bool
    merge_enabled: bool
    dynamic_threshold: bool
    max_merge_gap_minutes: int
    merge_level: int
    include_compilations: bool
    bb_top_n: int
    bb_album_top_n: int
    bb_artist_top_n: int
    bb_week_start_dow: int
    bb_week_start_hour: int
    year_start: int | None
    year_end: int | None
    playback_revision: int
    billboard_aggregation_revision: int
    metadata_revision: int
    settings_revision: int
    artist_identity_revision: int
    track_credit_revision: int
    track_identity_revision: int
    track_identity_policy: str
    semantic_base_key: str
    filter_fingerprint: str
    source_revision: str
    album_project_revision: int = 0
    track_presentation_policy: str = TRACK_PRESENTATION_POLICY_VERSION

    def filter_values(self) -> dict[str, Any]:
        return asdict(self)


def _value(source: Mapping[str, Any] | object, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _digest_payload(payload: Mapping[str, Any], length: int | None = None) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    return digest[:length] if length else digest


def music_search_variant_fingerprint(
    semantic_base_key: str,
    *,
    merge_level: int,
    dynamic_threshold: bool,
) -> str:
    return _digest_payload(
        {
            "semantic_base_key": semantic_base_key,
            "merge_level": int(merge_level),
            "dynamic_threshold": bool(dynamic_threshold),
        }
    )


def music_search_snapshot_policy_key(context: MusicSearchFilterContext) -> str:
    """Return the variant semantics that remain stable across data appends.

    Playback, Billboard, metadata and settings revisions identify one exact
    snapshot and therefore intentionally remain in ``filter_fingerprint``.
    They are excluded here so maintenance can look up a prior compatible
    generation.  The actual filter values and governance revisions stay in
    the policy key; changing any of them makes a previous snapshot ineligible
    as an incremental base.
    """
    values = context.filter_values()
    excluded = {
        "playback_revision",
        "billboard_aggregation_revision",
        "metadata_revision",
        "settings_revision",
        "semantic_base_key",
        "filter_fingerprint",
        "source_revision",
    }
    return _digest_payload(
        {
            "version": MUSIC_SEARCH_SNAPSHOT_POLICY_VERSION,
            "snapshot_builder": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            "chart_builder": MUSIC_SEARCH_CHART_BUILDER_VERSION,
            **{key: value for key, value in values.items() if key not in excluded},
        }
    )


def playback_source_revision(conn: sqlite3.Connection) -> str:
    """Offline audit digest; request-time context construction must not call it."""
    row = conn.execute(
        """SELECT COUNT(*) AS play_count,
                  COALESCE(MAX(play_id), 0) AS max_play_id,
                  COALESCE(MAX(ts), '') AS latest_play_ts,
                  COALESCE(SUM(ms_played), 0) AS total_ms,
                  COUNT(DISTINCT track_id) AS played_tracks
           FROM plays"""
    ).fetchone()
    return _digest_payload(
        {
            "play_count": int(row[0]),
            "max_play_id": int(row[1]),
            "latest_play_ts": str(row[2]),
            "total_ms": int(row[3]),
            "played_tracks": int(row[4]),
        },
        20,
    )


def billboard_aggregation_revision(conn: sqlite3.Connection) -> str:
    """Offline audit digest; request-time context construction must not call it."""
    payload: dict[str, Any] = {}
    for table in ("agg_track_wks", "agg_album_wks", "agg_artist_wks", "agg_weekly_track_sources"):
        if not _table_exists(conn, table):
            payload[table] = "missing"
            continue
        columns = {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}
        week_column = "billboard_week" if "billboard_week" in columns else None
        play_column = "play_count" if "play_count" in columns else None
        select = ["COUNT(*)"]
        if week_column:
            select.append(f"COALESCE(MAX({week_column}), '')")
        if play_column:
            select.append(f"COALESCE(SUM({play_column}), 0)")
        payload[table] = list(conn.execute(f'SELECT {", ".join(select)} FROM "{table}"').fetchone())
    return _digest_payload(payload, 20)


def build_music_search_filter_context(
    conn: sqlite3.Connection,
    filters: Mapping[str, Any] | object,
) -> MusicSearchFilterContext:
    from backend.domains.playback.merge_levels import normalize_merge_level

    revisions = get_music_search_revision_state(conn)
    values: dict[str, Any] = {
        "min_ms": int(_value(filters, "min_ms", 30000)),
        "music_only": bool(_value(filters, "music_only", True)),
        "merge_enabled": bool(_value(filters, "merge_enabled", True)),
        "dynamic_threshold": bool(_value(filters, "dynamic_threshold", True)),
        "max_merge_gap_minutes": int(_value(filters, "max_merge_gap_minutes", 5) or 5),
        "merge_level": normalize_merge_level(_value(filters, "merge_level", 2)),
        "include_compilations": bool(_value(filters, "include_compilations", False)),
        "bb_top_n": int(_value(filters, "bb_top_n", 30)),
        "bb_album_top_n": int(_value(filters, "bb_album_top_n", 20)),
        "bb_artist_top_n": int(_value(filters, "bb_artist_top_n", 20)),
        "bb_week_start_dow": int(_value(filters, "bb_week_start_dow", 4)),
        "bb_week_start_hour": int(_value(filters, "bb_week_start_hour", 0)),
        "year_start": _value(filters, "year_start"),
        "year_end": _value(filters, "year_end"),
        "playback_revision": revisions.playback_revision,
        "billboard_aggregation_revision": revisions.billboard_revision,
        "metadata_revision": revisions.metadata_revision,
        "settings_revision": revisions.settings_revision,
        "artist_identity_revision": get_identity_revision(conn),
        "track_credit_revision": get_track_credit_revision(conn),
        "track_identity_revision": get_track_identity_revision(conn),
        "track_identity_policy": TRACK_IDENTITY_POLICY_VERSION,
        "album_project_revision": get_album_project_revision(conn),
        "track_presentation_policy": TRACK_PRESENTATION_POLICY_VERSION,
    }
    semantic_values = {
        key: value
        for key, value in values.items()
        if key not in {"merge_level", "dynamic_threshold"}
    }
    semantic_base_key = _digest_payload(
        {
            "version": MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION,
            "snapshot_builder": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            "chart_builder": MUSIC_SEARCH_CHART_BUILDER_VERSION,
            **semantic_values,
        }
    )
    fingerprint = music_search_variant_fingerprint(
        semantic_base_key,
        merge_level=values["merge_level"],
        dynamic_threshold=values["dynamic_threshold"],
    )
    source_revision = _digest_payload(
        {
            "playback": revisions.playback_revision,
            "billboard": revisions.billboard_revision,
            "metadata": revisions.metadata_revision,
            "settings": revisions.settings_revision,
            "identity": values["artist_identity_revision"],
            "credits": values["track_credit_revision"],
            "track_identity": values["track_identity_revision"],
            "track_identity_policy": values["track_identity_policy"],
            "album_project_revision": values["album_project_revision"],
            "track_presentation_policy": values["track_presentation_policy"],
        },
        20,
    )
    return MusicSearchFilterContext(
        **values,
        semantic_base_key=semantic_base_key,
        filter_fingerprint=fingerprint,
        source_revision=source_revision,
    )


def legacy_v2_statistics_identity(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> tuple[str, str]:
    """Reconstruct the exact pre-split identity for one-time safe adoption.

    This is intentionally not used by request readers.  Maintenance may use
    it to prove that a current v2 row was built from the still-active index
    generation before re-keying its stable entity-key payload to v3.
    """
    from backend.domains.music_search.index import get_music_search_index_state

    index_state = get_music_search_index_state(conn)
    generation_id = str(index_state.get("active_generation_id") or "unavailable")
    index_revision = str(index_state.get("source_revision") or "unavailable")
    normalization_version = str(index_state.get("normalization_version") or "unavailable")
    values = {
        key: value
        for key, value in context.filter_values().items()
        if key not in {"semantic_base_key", "filter_fingerprint", "source_revision"}
    }
    values["search_index_revision"] = index_revision
    semantic_values = {
        key: value
        for key, value in values.items()
        if key not in {"merge_level", "dynamic_threshold"}
    }
    base = _digest_payload(
        {
            "version": LEGACY_MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION,
            "snapshot_builder": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            "chart_builder": MUSIC_SEARCH_CHART_BUILDER_VERSION,
            "index_generation": generation_id,
            "index_normalization": normalization_version,
            **semantic_values,
        }
    )
    fingerprint = music_search_variant_fingerprint(
        base,
        merge_level=context.merge_level,
        dynamic_threshold=context.dynamic_threshold,
    )
    return base, fingerprint


def legacy_v2_statistics_source_revision(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> str:
    """Reconstruct the v2 source digest without its random generation id."""
    from backend.domains.music_search.index import get_music_search_index_state

    index_revision = str(get_music_search_index_state(conn).get("source_revision") or "unavailable")
    return _digest_payload(
        {
            "playback": context.playback_revision,
            "billboard": context.billboard_aggregation_revision,
            "metadata": context.metadata_revision,
            "settings": context.settings_revision,
            "index": index_revision,
            "identity": context.artist_identity_revision,
            "credits": context.track_credit_revision,
        },
        20,
    )
