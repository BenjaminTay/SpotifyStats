"""Stable lineage and dependency proofs for incremental search snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_credits import get_track_credit_revision


def active_playback_lineage(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    """Return the published playback generation and dataset digest in O(1)."""
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='playback_import_state'"
    ).fetchone()
    if table is None:
        return None, None
    columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(playback_import_state)").fetchall()
    }
    if "active_generation_id" not in columns or "dataset_digest" not in columns:
        return None, None
    row = conn.execute(
        """SELECT active_generation_id, dataset_digest
           FROM playback_import_state WHERE state_id=1"""
    ).fetchone()
    if row is None:
        return None, None
    generation_id = str(row[0]) if row[0] else None
    dataset_digest = str(row[1]) if row[1] else None
    return generation_id, dataset_digest


def music_search_snapshot_dependency_manifest(conn: sqlite3.Connection) -> dict[str, Any]:
    """Describe non-playback facts that must remain compatible for delta reuse."""
    from backend.domains.yearly_review.context import (
        _TRACK_GROUP_TABLES,
        _album_project_semantic_revision,
        _table_set_revision,
    )

    identity_revision = get_identity_revision(conn)
    credit_revision = get_track_credit_revision(conn)
    aggregation_keys = (
        "builder_version",
        "playback_policy_version",
        "duration_revision",
        "credit_membership_revision",
        "identity_revision",
        "track_credit_revision",
        "album_project_revision",
    )
    try:
        aggregation_config = {
            str(row[0]): str(row[1])
            for row in conn.execute("SELECT key, value FROM agg_config").fetchall()
        }
        aggregation = {key: aggregation_config.get(key, "unavailable") for key in aggregation_keys}
    except sqlite3.OperationalError:
        aggregation = {"status": "unavailable"}
    try:
        index_row = conn.execute(
            """SELECT normalization_version, content_digest
               FROM music_search_index_state WHERE state_id=1"""
        ).fetchone()
    except sqlite3.OperationalError:
        index_row = None
    return {
        "version": "music_search_snapshot_dependency_v1",
        "identity_revision": identity_revision,
        "track_credit_revision": credit_revision,
        "aggregation": aggregation,
        "track_group_revision": _table_set_revision(conn, _TRACK_GROUP_TABLES),
        "album_project_revision": _album_project_semantic_revision(conn),
        "candidate_normalization_version": str(index_row[0] or "unavailable")
        if index_row
        else "unavailable",
        # Random generations and revision-driven candidate versions are
        # publication details.  Exact document content is the compatibility
        # proof needed by a cloned statistics snapshot.
        "candidate_content_digest": str(index_row[1] or "unavailable")
        if index_row
        else "unavailable",
    }


def music_search_snapshot_dependency_digest(conn: sqlite3.Connection) -> str:
    payload = music_search_snapshot_dependency_manifest(conn)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if "unavailable" in encoded:
        raise RuntimeError("music-search snapshot dependencies are incomplete")
    return hashlib.sha256(encoded.encode()).hexdigest()
