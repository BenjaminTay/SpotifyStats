"""Unit tests for merge level normalization."""

from __future__ import annotations

import sqlite3

import pytest

from backend.domains.playback.merge_levels import normalize_merge_level
from backend.domains.playback.track_groups import resolve_track_aggregation_scope

pytestmark = pytest.mark.unit


class TestNormalizeMergeLevel:
    def test_defaults_to_2_when_none(self):
        assert normalize_merge_level(None) == 2

    def test_defaults_to_2_when_invalid(self):
        assert normalize_merge_level(0) == 2
        assert normalize_merge_level(4) == 2
        assert normalize_merge_level(-1) == 2

    def test_defaults_to_2_on_unparseable_string(self):
        assert normalize_merge_level("abc") == 2

    def test_parses_valid_string(self):
        assert normalize_merge_level("1") == 2
        assert normalize_merge_level("3") == 3

    def test_passes_valid_integers(self):
        assert normalize_merge_level(1) == 2
        assert normalize_merge_level(2) == 2
        assert normalize_merge_level(3) == 3


def _group_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE track_l1_identities (
            l1_id INTEGER PRIMARY KEY,
            representative_track_id INTEGER
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            scope TEXT NOT NULL,
            parent_group_id INTEGER,
            primary_l1_id INTEGER,
            group_status TEXT NOT NULL
        );
        CREATE TABLE track_group_l1_members (
            group_id INTEGER NOT NULL,
            l1_id INTEGER NOT NULL
        );
        INSERT INTO track_l1_identities VALUES
            (10, 10), (11, 11), (12, 12), (13, 13), (14, 14), (15, 15);
        INSERT INTO track_groups VALUES
            (1, 'Recording', 'recording', 2, 10, 'active'),
            (2, 'Composition', 'composition', NULL, 12, 'active'),
            (3, 'Archived recording', 'recording', NULL, 14, 'archived');
        INSERT INTO track_group_l1_members VALUES
            (1, 10), (1, 11),
            (2, 12), (2, 13),
            (3, 14), (3, 15);
        """
    )
    return conn


class TestResolveTrackAggregationScope:
    def test_l2_resolves_active_recording_members(self):
        conn = _group_conn()
        try:
            scope = resolve_track_aggregation_scope(conn, 11, 2)
        finally:
            conn.close()

        assert scope.primary_track_id == 10
        assert scope.member_track_ids == (10, 11)
        assert scope.group_scope == "recording"

    def test_l3_expands_recording_group_to_parent_composition(self):
        conn = _group_conn()
        try:
            scope = resolve_track_aggregation_scope(conn, 11, 3)
        finally:
            conn.close()

        assert scope.primary_track_id == 12
        assert scope.member_track_ids == (10, 11, 12, 13)
        assert scope.group_scope == "composition"

    def test_l2_does_not_apply_composition_or_archived_groups(self):
        conn = _group_conn()
        try:
            composition = resolve_track_aggregation_scope(conn, 13, 2)
            archived = resolve_track_aggregation_scope(conn, 15, 3)
        finally:
            conn.close()

        assert composition.member_track_ids == (13,)
        assert archived.member_track_ids == (15,)
