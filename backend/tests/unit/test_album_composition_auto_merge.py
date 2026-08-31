"""Unit coverage for conservative L3 Album composition governance."""

from __future__ import annotations

import json
import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.playback.album_composition_auto_merge import (
    apply_album_composition_plan,
    normalize_album_composition_title,
    plan_album_composition_merges,
)
from backend.domains.playback.album_projects import (
    get_album_project_revision,
    load_album_project_membership,
    rebuild_album_projects,
)

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _add_album(
    conn: sqlite3.Connection,
    *,
    album_id: int,
    name: str,
    artist_id: int = 1,
    artist_name: str = "Taylor Swift",
    track_count: int = 8,
) -> list[int]:
    conn.execute(
        "INSERT OR IGNORE INTO artists(artist_id, artist_name) VALUES (?, ?)",
        (artist_id, artist_name),
    )
    conn.execute(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
        (album_id, name, artist_id),
    )
    track_ids: list[int] = []
    for offset in range(track_count):
        track_id = album_id * 100 + offset
        track_ids.append(track_id)
        conn.execute(
            """INSERT INTO tracks(track_id, track_name, artist_id, album_id)
               VALUES (?, ?, ?, ?)""",
            (track_id, f"Song {offset + 1}", artist_id, album_id),
        )
        conn.execute(
            """INSERT INTO plays(
                   ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                   platform, ms_played, track_id, source_album_id
               ) VALUES (?, 2026, 1, 1, 1, 0, '2026-01-01',
                         'fixture', 180000, ?, ?)""",
            (f"2026-01-01T00:{album_id % 60:02d}:{offset:02d}Z", track_id, album_id),
        )
        conn.execute(
            """INSERT INTO track_l1_identities(
                   l1_id, fallback_track_id, representative_track_id
               ) VALUES (?, ?, ?)""",
            (track_id, track_id, track_id),
        )
        conn.execute(
            """INSERT INTO track_l1_source_links(
                   l1_id, track_id, evidence_type, observed_plays
               ) VALUES (?, ?, 'track_projection', 1)""",
            (track_id, track_id),
        )
    return track_ids


def _link_compositions(
    conn: sqlite3.Connection,
    left_tracks: list[int],
    right_tracks: list[int],
    *,
    limit: int | None = None,
) -> None:
    assert len(left_tracks) == len(right_tracks)
    pairs = list(zip(left_tracks, right_tracks))
    if limit is not None:
        pairs = pairs[:limit]
    for index, (left, right) in enumerate(pairs, start=1):
        cursor = conn.execute(
            """INSERT INTO track_groups(
                   canonical_name, primary_track_id, primary_l1_id,
                   scope, is_manual, group_status
               ) VALUES (?, ?, ?, 'composition', 1, 'active')""",
            (f"Song {index}", left, left),
        )
        group_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (?, ?)",
            ((group_id, left), (group_id, right)),
        )


def _prepare_original_and_rerecord(
    conn: sqlite3.Connection,
    *,
    overlap: int = 8,
) -> tuple[list[int], list[int]]:
    original = _add_album(conn, album_id=10, name="1989")
    rerecord = _add_album(conn, album_id=20, name="1989 (Taylor's Version)")
    _link_compositions(conn, original, rerecord, limit=overlap)
    conn.commit()
    rebuild_album_projects(conn)
    return original, rerecord


def _attach_to_existing_compositions(
    conn: sqlite3.Connection,
    anchor_tracks: list[int],
    new_tracks: list[int],
) -> None:
    assert len(anchor_tracks) == len(new_tracks)
    for anchor, new_track in zip(anchor_tracks, new_tracks):
        group_id = int(
            conn.execute(
                """SELECT members.group_id
                     FROM track_group_l1_members members
                     JOIN track_groups groups ON groups.group_id=members.group_id
                    WHERE members.l1_id=? AND groups.scope='composition'
                      AND groups.group_status='active'""",
                (anchor,),
            ).fetchone()[0]
        )
        conn.execute(
            "INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (?, ?)",
            (group_id, new_track),
        )


def test_title_parser_only_strips_controlled_trailing_relations() -> None:
    rerecord = normalize_album_composition_title("1989 (Taylor's Version) [Deluxe]")
    assert rerecord.base_name == "1989"
    assert rerecord.base_key == "1989"
    assert rerecord.relation_tag == "rerecord"
    assert rerecord.removed_suffixes == ("Deluxe", "Taylor's Version")

    live = normalize_album_composition_title("Album - Live at Wembley")
    assert (live.base_name, live.relation_tag) == ("Album", "live")

    ordinary = normalize_album_composition_title("We Are Born to Live")
    assert ordinary.base_name == "We Are Born to Live"
    assert ordinary.relation_tag is None

    generic = normalize_album_composition_title("Album (International Version)")
    assert generic.base_name == "Album (International Version)"
    assert generic.relation_tag is None


def test_plan_is_json_serializable_and_requires_strong_overlap() -> None:
    conn = _connection()
    try:
        _prepare_original_and_rerecord(conn, overlap=3)

        plan = plan_album_composition_merges(conn)

        assert plan.candidates == ()
        assert dict(plan.skipped_reason_counts)["insufficient_composition_track_overlap"] == 1
        json.dumps(plan.to_dict(), ensure_ascii=False)
    finally:
        conn.close()


def test_canonical_album_artist_aliases_can_share_one_composition_parent() -> None:
    conn = _connection()
    try:
        original = _add_album(conn, album_id=10, name="1989", artist_id=1)
        rerecord = _add_album(
            conn,
            album_id=20,
            name="1989 (Taylor's Version)",
            artist_id=2,
            artist_name="Taylor Swift Catalog Alias",
        )
        conn.execute(
            """INSERT INTO artist_identity_groups(
                   identity_id, canonical_artist_id, display_artist_id,
                   display_name, status
               ) VALUES (1, 1, 1, 'Taylor Swift', 'active')"""
        )
        conn.executemany(
            """INSERT INTO artist_identity_members(
                   identity_id, artist_id, role, evidence_type, active
               ) VALUES (1, ?, ?, 'manual', 1)""",
            ((1, "canonical"), (2, "alias")),
        )
        _link_compositions(conn, original, rerecord)
        conn.commit()
        rebuild_album_projects(conn)

        plan = plan_album_composition_merges(conn)

        assert len(plan.candidates) == 1
        assert plan.candidates[0].artist_id == 1
        units = plan.candidates[0].project_units
        assert {unit.artist_id for unit in units} == {1}
        assert {unit.source_artist_id for unit in units} == {1, 2}
        apply_album_composition_plan(conn, plan)
        assert (
            conn.execute(
                "SELECT artist_id FROM release_groups WHERE scope='composition'"
            ).fetchone()[0]
            == 1
        )
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT artist_id FROM release_groups WHERE scope='release'"
            ).fetchall()
        } == {1, 2}
    finally:
        conn.close()


def test_rerecord_is_created_as_l3_parent_without_collapsing_l2_projects() -> None:
    conn = _connection()
    try:
        _prepare_original_and_rerecord(conn)
        before_revision = get_album_project_revision(conn)

        plan = plan_album_composition_merges(conn)

        assert len(plan.candidates) == 1
        candidate = plan.candidates[0]
        assert candidate.action == "create"
        assert candidate.relation_tags == ("rerecord",)
        assert candidate.album_ids == (10, 20)
        assert candidate.matched_track_keys == 8
        assert candidate.minimum_pair_coverage == 1.0

        report = apply_album_composition_plan(conn, plan)

        assert report.groups_created == 1
        assert report.release_children_created == 2
        assert report.groups_updated == 0
        assert report.groups_archived == 0
        assert report.album_project_revision == before_revision + 1
        groups = conn.execute(
            """SELECT group_id, canonical_name, scope, parent_group_id
                 FROM release_groups ORDER BY scope, group_id"""
        ).fetchall()
        composition = next(row for row in groups if row["scope"] == "composition")
        release_children = [row for row in groups if row["scope"] == "release"]
        assert composition["canonical_name"] == "1989"
        assert len(release_children) == 2
        assert {row["parent_group_id"] for row in release_children} == {composition["group_id"]}

        # L2 projects remain independently addressable; L3 gets one additional
        # composition project instead of replacing either child.
        projects = conn.execute(
            """SELECT canonical_name, scope FROM album_projects
                WHERE project_type='album' ORDER BY scope, canonical_name"""
        ).fetchall()
        assert [(row["canonical_name"], row["scope"]) for row in projects] == [
            ("1989", "composition"),
            ("1989", "release"),
            ("1989 (Taylor's Version)", "release"),
        ]
        composition_identity = conn.execute(
            """SELECT normalized_name, album_artist_key, identity_policy_version
                 FROM album_projects WHERE scope='composition'"""
        ).fetchone()
        assert tuple(composition_identity) == (
            "1989",
            "taylor swift",
            "canonical_album_composition_v1",
        )
        l2 = load_album_project_membership(conn, merge_level=2)
        l3 = load_album_project_membership(conn, merge_level=3)
        assert set(l2["album_project_name"]) == {"1989", "1989 (Taylor's Version)"}
        assert set(l3["album_project_name"]) == {"1989"}

        converged = plan_album_composition_merges(conn)
        assert len(converged.candidates) == 1
        assert converged.candidates[0].action == "unchanged"
        revision = get_album_project_revision(conn)
        second = apply_album_composition_plan(conn, converged)
        assert second.requires_downstream_refresh is False
        assert get_album_project_revision(conn) == revision
    finally:
        conn.close()


def test_stale_owned_auto_group_is_archived_and_l2_children_survive() -> None:
    conn = _connection()
    try:
        _prepare_original_and_rerecord(conn)
        apply_album_composition_plan(conn, plan_album_composition_merges(conn))
        composition_id = int(
            conn.execute(
                "SELECT group_id FROM release_groups WHERE scope='composition'"
            ).fetchone()[0]
        )
        conn.execute("DELETE FROM track_group_l1_members")
        conn.execute("DELETE FROM track_groups")
        conn.commit()

        stale = plan_album_composition_merges(conn)

        assert stale.candidates == ()
        assert stale.archive_group_ids == (composition_id,)
        report = apply_album_composition_plan(conn, stale)
        assert report.groups_archived == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM release_groups WHERE scope='composition'"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                """SELECT COUNT(*) FROM release_groups
                WHERE scope='release' AND parent_group_id IS NULL"""
            ).fetchone()[0]
            == 2
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM album_projects WHERE scope='release'").fetchone()[0]
            == 2
        )
    finally:
        conn.close()


def test_manual_release_child_prevents_auto_parent_rewrite_or_archive() -> None:
    conn = _connection()
    try:
        _prepare_original_and_rerecord(conn)
        apply_album_composition_plan(conn, plan_album_composition_merges(conn))
        composition_id = int(
            conn.execute(
                "SELECT group_id FROM release_groups WHERE scope='composition'"
            ).fetchone()[0]
        )
        manual_child_id = int(
            conn.execute(
                """SELECT group_id FROM release_groups
                    WHERE scope='release' AND parent_group_id=? ORDER BY group_id LIMIT 1""",
                (composition_id,),
            ).fetchone()[0]
        )
        conn.execute("UPDATE release_groups SET is_manual=1 WHERE group_id=?", (manual_child_id,))
        conn.execute("DELETE FROM track_group_l1_members")
        conn.execute("DELETE FROM track_groups")
        conn.commit()

        plan = plan_album_composition_merges(conn)

        assert plan.candidates == ()
        assert plan.archive_group_ids == ()
        assert dict(plan.skipped_reason_counts)["manual_composition_topology_frozen"] >= 1
        assert (
            conn.execute(
                "SELECT parent_group_id FROM release_groups WHERE group_id=?", (manual_child_id,)
            ).fetchone()[0]
            == composition_id
        )
    finally:
        conn.close()


def test_existing_auto_component_updates_when_a_new_live_project_appears() -> None:
    conn = _connection()
    try:
        original, _rerecord = _prepare_original_and_rerecord(conn)
        apply_album_composition_plan(conn, plan_album_composition_merges(conn))
        live = _add_album(conn, album_id=30, name="1989 (Live)")
        _attach_to_existing_compositions(conn, original, live)
        conn.commit()
        rebuild_album_projects(conn)

        plan = plan_album_composition_merges(conn)

        assert len(plan.candidates) == 1
        candidate = plan.candidates[0]
        assert candidate.action == "update"
        assert candidate.relation_tags == ("live", "rerecord")
        assert candidate.album_ids == (10, 20, 30)
        report = apply_album_composition_plan(conn, plan)
        assert report.groups_created == 0
        assert report.groups_updated == 1
        assert report.release_children_created == 1
        group_id = candidate.existing_group_id
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT album_id FROM release_group_members WHERE group_id=?", (group_id,)
            ).fetchall()
        } == {10, 20, 30}
        assert (
            conn.execute(
                """SELECT COUNT(*) FROM release_groups
                WHERE scope='release' AND parent_group_id=?""",
                (group_id,),
            ).fetchone()[0]
            == 3
        )
    finally:
        conn.close()


def test_manual_groups_are_hard_overrides_and_standard_deluxe_stays_l2() -> None:
    conn = _connection()
    try:
        original, rerecord = _prepare_original_and_rerecord(conn)
        conn.execute(
            """INSERT INTO release_groups(
                   canonical_name, artist_id, primary_album_id, scope, is_manual
               ) VALUES ('Manual 1989 Work', 1, 10, 'composition', 1)"""
        )
        manual_group = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            "INSERT INTO release_group_members(group_id, album_id) VALUES (?, 10)",
            (manual_group,),
        )

        plan = plan_album_composition_merges(conn)

        assert plan.candidates == ()
        assert dict(plan.skipped_reason_counts)["manual_composition_group_frozen"] == 1

        # A standard/deluxe L2 bundle is one project node and cannot become a
        # separate L3 component merely because one source album says Deluxe.
        conn.execute("DELETE FROM release_group_members WHERE group_id=?", (manual_group,))
        conn.execute("DELETE FROM release_groups WHERE group_id=?", (manual_group,))
        conn.execute(
            """INSERT INTO release_groups(
                   canonical_name, artist_id, primary_album_id, scope, is_manual
               ) VALUES ('1989', 1, 10, 'release', 0)"""
        )
        release_group = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.executemany(
            "INSERT INTO release_group_members(group_id, album_id) VALUES (?, ?)",
            ((release_group, 10), (release_group, 20)),
        )
        conn.execute("UPDATE albums SET album_name='1989 (Deluxe)' WHERE album_id=20")
        conn.commit()
        rebuild_album_projects(conn)

        assert plan_album_composition_merges(conn).candidates == ()
        assert original and rerecord
    finally:
        conn.close()


def test_compilation_named_projects_are_frozen_even_with_track_overlap() -> None:
    conn = _connection()
    try:
        original = _add_album(conn, album_id=10, name="Artist Best Of")
        live = _add_album(conn, album_id=20, name="Artist Best Of (Live)")
        _link_compositions(conn, original, live)
        conn.commit()
        rebuild_album_projects(conn)

        plan = plan_album_composition_merges(conn)

        assert plan.candidates == ()
        assert dict(plan.skipped_reason_counts)["compilation_policy_frozen"] == 2
    finally:
        conn.close()
