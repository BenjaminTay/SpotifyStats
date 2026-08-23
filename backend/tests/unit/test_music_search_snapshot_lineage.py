from __future__ import annotations

import sqlite3

import pytest

from backend.domains.music_search.snapshot_lineage import (
    active_playback_lineage,
    music_search_snapshot_dependency_digest,
)
from backend.domains.yearly_review import context as yearly_context

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE playback_import_state(
            state_id INTEGER PRIMARY KEY,
            active_generation_id TEXT,
            dataset_digest TEXT
        );
        INSERT INTO playback_import_state VALUES (1, 'generation-2', 'dataset-2');
        CREATE TABLE music_search_index_state(
            state_id INTEGER PRIMARY KEY,
            normalization_version TEXT,
            candidate_index_version TEXT,
            content_digest TEXT
        );
        INSERT INTO music_search_index_state
        VALUES (1, 'normalization-v1', 'candidate-random-v1', 'documents-v1');
        CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO agg_config VALUES
            ('builder_version', 'builder-v1'),
            ('playback_policy_version', 'playback-v1'),
            ('duration_revision', 'duration-v1'),
            ('credit_membership_revision', 'credits-v1'),
            ('identity_revision', '0'),
            ('track_credit_revision', '0'),
            ('album_project_revision', 'albums-v1');
        """
    )
    return conn


def test_active_playback_lineage_requires_persisted_generation_and_digest() -> None:
    conn = _conn()
    assert active_playback_lineage(conn) == ("generation-2", "dataset-2")

    conn.execute("UPDATE playback_import_state SET dataset_digest=NULL WHERE state_id=1")
    assert active_playback_lineage(conn) == ("generation-2", None)


def test_dependency_digest_uses_candidate_content_not_random_version(monkeypatch) -> None:
    conn = _conn()
    monkeypatch.setattr(
        yearly_context,
        "_table_set_revision",
        lambda *_args, **_kwargs: "track-groups-stable",
    )
    monkeypatch.setattr(
        yearly_context,
        "_album_project_semantic_revision",
        lambda *_args, **_kwargs: "album-projects-stable",
    )

    baseline = music_search_snapshot_dependency_digest(conn)
    conn.execute(
        "UPDATE music_search_index_state SET candidate_index_version='candidate-random-v2'"
    )
    assert music_search_snapshot_dependency_digest(conn) == baseline

    conn.execute("UPDATE music_search_index_state SET content_digest='documents-v2'")
    assert music_search_snapshot_dependency_digest(conn) != baseline


def test_dependency_digest_uses_published_aggregation_semantics(monkeypatch) -> None:
    conn = _conn()
    monkeypatch.setattr(
        yearly_context,
        "_table_set_revision",
        lambda *_args, **_kwargs: "track-groups-stable",
    )
    monkeypatch.setattr(
        yearly_context,
        "_album_project_semantic_revision",
        lambda *_args, **_kwargs: "album-projects-stable",
    )
    baseline = music_search_snapshot_dependency_digest(conn)

    conn.execute("UPDATE agg_config SET value='duration-v2' WHERE key='duration_revision'")

    assert music_search_snapshot_dependency_digest(conn) != baseline
