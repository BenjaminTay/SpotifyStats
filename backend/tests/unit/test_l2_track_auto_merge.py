from __future__ import annotations

import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.metadata.l2_track_auto_merge import (
    apply_l2_track_merge_plan,
    build_l2_track_merge_plan,
)
from backend.domains.metadata.track_identity import validate_track_identity_invariants
from backend.domains.metadata.track_title_identity import normalize_l2_track_title

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Artist')")
    conn.execute("INSERT INTO albums(album_id, album_name, artist_id) VALUES (1, 'Album', 1)")
    return conn


def _track(
    conn: sqlite3.Connection,
    track_id: int,
    name: str,
    plays: int = 0,
    *,
    isrc: str | None = None,
    duration_ms: int = 180_000,
) -> None:
    spotify_id = f"spotify-{track_id}"
    conn.execute(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id)
           VALUES (?, ?, 1, 1, ?)""",
        (track_id, name, spotify_id),
    )
    conn.execute(
        "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, 1, 'primary')",
        (track_id,),
    )
    conn.execute(
        """INSERT INTO track_l1_identities(
               l1_id, fallback_track_id, identity_status, representative_track_id
           ) VALUES (?, ?, 'active', ?)""",
        (track_id, track_id, track_id),
    )
    conn.execute(
        """INSERT INTO track_l1_external_ids(
               provider, external_track_id, l1_id, evidence_type, is_primary
           ) VALUES ('spotify', ?, ?, 'provider_observed', 1)""",
        (spotify_id, track_id),
    )
    conn.execute(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, duration_ms, isrc)
           VALUES (?, ?, ?, ?)""",
        (spotify_id, name, duration_ms, isrc or f"ISRC-{track_id}"),
    )
    conn.execute(
        """INSERT INTO track_l1_source_links(
               l1_id, track_id, evidence_type, observed_plays
           ) VALUES (?, ?, 'play_at_time', ?)""",
        (track_id, track_id, plays),
    )
    for offset in range(plays):
        conn.execute(
            """INSERT INTO plays(
                   ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                   platform, ms_played, track_id, spotify_track_id_at_play
               ) VALUES (?, 2026, 1, 1, 4, 0, '2026-01-01',
                         'fixture', 180000, ?, ?)""",
            (f"2026-01-01T00:00:{track_id + offset:02d}Z", track_id, spotify_id),
        )


def test_title_normalizer_removes_packaging_but_preserves_recording_suffix() -> None:
    assert normalize_l2_track_title("純妹妹 - 2025版").key == ("纯妹妹", ())
    assert normalize_l2_track_title("Song - 2018 Remastered").key == ("song", ())
    assert normalize_l2_track_title("Song (Explicit)").key == ("song", ())
    assert normalize_l2_track_title("Song - Bonus Track").key == ("song", ())
    assert normalize_l2_track_title("Yoü And I").key != normalize_l2_track_title("You And I").key
    assert normalize_l2_track_title("Running Up That Hill (A Deal With God)").key == (
        "running up that hill a deal with god",
        (),
    )
    assert (
        normalize_l2_track_title("Song - Kungs Remix").key
        != normalize_l2_track_title("Song - ILLENIUM Remix").key
    )
    assert (
        normalize_l2_track_title("Song (feat. A)").key
        != normalize_l2_track_title("Song (feat. B)").key
    )


@pytest.mark.parametrize(
    ("title", "semantic_tag"),
    [
        ("the lakes - original version", "original_version"),
        ("Thriller - Single Version", "single_version"),
        ("Song - Album Version", "album_version"),
        ("Song - Extended Mix", "extended"),
        ("Song - Sped Up", "sped_up"),
        ("Song - Slowed Down", "slowed"),
        ("Song - Acoustic", "acoustic"),
        ("Song - Live", "live"),
        ("Song - Club Remix", "remix"),
        ("Song (Taylor's Version)", "rerecord"),
    ],
)
def test_title_normalizer_preserves_l2_semantic_versions(title: str, semantic_tag: str) -> None:
    identity = normalize_l2_track_title(title)
    assert identity.base_title in {"the lakes", "thriller", "song"}
    assert any(tag.startswith(f"{semantic_tag}:") for tag in identity.semantic_version_tags)


def test_title_normalizer_preserves_source_context_outside_identity_key() -> None:
    identity = normalize_l2_track_title('City Of Stars - From "La La Land" Soundtrack')
    assert identity.key == ("city of stars", ())
    assert identity.source_context_tags == ("from la la land soundtrack",)
    chinese = normalize_l2_track_title("任性（电视剧《难哄》主题曲）")
    assert chinese.key == ("任性", ())
    assert chinese.source_context_tags == ("电视剧 难哄 主题曲",)


def test_same_artist_and_normalized_title_merge_while_semantic_versions_stay_separate() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "純妹妹", plays=1)
        _track(conn, 2, "纯妹妹 - 2025版", plays=2)
        _track(conn, 3, "Song", plays=1)
        _track(conn, 4, "Song - Kungs Remix", plays=1)
        _track(conn, 5, "Song - ILLENIUM Remix", plays=1)

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert plan["groups"][0]["primary_l1_id"] == 2
        assert plan["groups"][0]["evidence_types"] == ["canonical_artist_normalized_title"]
    finally:
        conn.close()


def test_force_separate_outweighs_auto_merge_and_apply_is_idempotent() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Same", plays=1)
        _track(conn, 2, "same", plays=2)
        _track(conn, 3, "SAME", plays=3)
        conn.execute(
            """INSERT INTO track_merge_overrides(
                   scope, left_l1_id, right_l1_id, action, reason
               ) VALUES ('recording', 1, 2, 'force_separate', 'known exception')"""
        )
        conn.commit()
        before_plays = [tuple(row) for row in conn.execute("SELECT * FROM plays ORDER BY play_id")]
        before_revision = conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()[0]

        plan = build_l2_track_merge_plan(conn)
        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 3]]
        assert any(edge["reason"] == "force_separate" for edge in plan["blocked_edges"])

        report = apply_l2_track_merge_plan(conn, plan, commit=True)
        assert report["status"] == "applied"
        assert report["revision_bumped"] is True
        assert report["track_identity_revision"] == before_revision + 1
        group = conn.execute(
            """SELECT automatic_artist_id, automatic_title_key,
                      automatic_version_tag, identity_policy_version
                 FROM track_groups WHERE group_status='active'"""
        ).fetchone()
        assert tuple(group) == (1, "same", "", plan["policy_version"])
        assert [
            tuple(row) for row in conn.execute("SELECT * FROM plays ORDER BY play_id")
        ] == before_plays

        second = apply_l2_track_merge_plan(conn, commit=True)
        assert second["status"] == "unchanged"
        assert second["track_identity_revision"] == before_revision + 1
    finally:
        conn.close()


def test_known_semantic_versions_are_rejected_while_packaging_variants_merge() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "the lakes - bonus track", isrc="USUG12002851", duration_ms=211_813)
        _track(
            conn,
            2,
            "the lakes - original version",
            isrc="USUG12103510",
            duration_ms=227_203,
        )
        _track(conn, 3, "Thriller", isrc="USSM19902989", duration_ms=358_807)
        _track(
            conn,
            4,
            "Thriller - Single Version",
            isrc="USSM10501511",
            duration_ms=312_967,
        )
        _track(conn, 5, "Loverboy", isrc="USVI20100288", duration_ms=229_173)
        _track(
            conn,
            6,
            "Loverboy - Firecracker - Original Version, 2001",
            isrc="USQX92003593",
            duration_ms=194_588,
        )

        plan = build_l2_track_merge_plan(conn)

        assert plan["groups"] == []
        assert {
            (edge["left_l1_id"], edge["right_l1_id"], edge["reason"])
            for edge in plan["blocked_edges"]
        } == {
            (1, 2, "semantic_version_conflict"),
            (3, 4, "semantic_version_conflict"),
            (5, 6, "semantic_version_conflict"),
        }

        report = apply_l2_track_merge_plan(conn, plan, commit=True)
        assert report["status"] == "unchanged"
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM track_group_candidates WHERE status='rejected'"
            ).fetchone()[0]
            == 3
        )
    finally:
        conn.close()


def test_source_context_is_a_warning_and_same_base_title_still_merges() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "City Of Stars", isrc="USUG11600665", duration_ms=111_240)
        _track(
            conn,
            2,
            'City Of Stars - From "La La Land" Soundtrack',
            isrc="USUG11600656",
            duration_ms=149_706,
        )
        _track(conn, 3, "Another Song", isrc="SHARED", duration_ms=180_000)
        _track(
            conn,
            4,
            'Another Song - From "A Film" Soundtrack',
            isrc="SHARED",
            duration_ms=181_000,
        )

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2], [3, 4]]
        assert all(
            group["evidence_types"] == ["canonical_artist_normalized_title"]
            for group in plan["groups"]
        )
        assert plan["edge_status_counts"]["pending"] == 0
        assert plan["warning_reason_counts"] == {
            "disjoint_isrc": 1,
            "source_context_present": 2,
            "strong_duration_conflict": 1,
        }
    finally:
        conn.close()


def test_ordinary_same_title_merges_despite_isrc_and_duration_conflicts() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Ordinary Song", isrc="ISRC-A", duration_ms=120_000)
        _track(conn, 2, "ordinary song", isrc="ISRC-B", duration_ms=300_000)

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert plan["edge_status_counts"]["pending"] == 0
        assert plan["warning_reason_counts"] == {
            "disjoint_isrc": 1,
            "strong_duration_conflict": 1,
        }
    finally:
        conn.close()


def test_theme_inside_a_long_ordinary_song_title_is_not_structural() -> None:
    conn = _connection()
    try:
        title = "Can't Take That Away (Mariah's Theme)"
        _track(conn, 1, title)
        _track(conn, 2, title.lower())

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert not any(
            edge["reason"] == "structural_title_requires_explicit_merge"
            for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


def test_force_merge_overrides_semantic_version_rejection() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Song")
        _track(conn, 2, "Song - Original Version")
        conn.execute(
            """INSERT INTO track_merge_overrides(
                   scope, left_l1_id, right_l1_id, action, reason
               ) VALUES ('recording', 1, 2, 'force_merge', 'curated same recording')"""
        )

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert plan["groups"][0]["evidence_types"] == ["force_merge"]
        assert not any(
            {edge["left_l1_id"], edge["right_l1_id"]} == {1, 2} for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


def test_structural_intro_is_rejected_regardless_of_recording_evidence() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "INTRO", isrc="TWA450582101", duration_ms=48_077)
        _track(conn, 2, "Intro", isrc="TWA450170201", duration_ms=30_960)

        plan = build_l2_track_merge_plan(conn)

        assert plan["groups"] == []
        assert any(
            edge["reason"] == "structural_title_requires_explicit_merge"
            and edge["status"] == "rejected"
            for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


def test_structural_intro_with_internal_l1_conflict_is_still_deterministic() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "INTRO", isrc="TWA450582101", duration_ms=48_077)
        conn.execute(
            """INSERT INTO track_l1_external_ids(
                   provider, external_track_id, l1_id, evidence_type, is_primary
               ) VALUES ('spotify', 'spotify-1-alt', 1, 'provider_observed', 0)"""
        )
        conn.execute(
            """INSERT INTO spotify_track_meta(
                   spotify_track_id, track_name, duration_ms, isrc
               ) VALUES ('spotify-1-alt', 'INTRO', 13293, 'TWA450275401')"""
        )
        _track(conn, 2, "Intro", isrc="TWA450170201", duration_ms=48_000)

        plan = build_l2_track_merge_plan(conn)

        assert plan["groups"] == []
        assert plan["strong_internal_identity_conflict_node_count"] == 1
        assert any(
            edge["reason"] == "structural_title_requires_explicit_merge"
            and edge["status"] == "rejected"
            for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


@pytest.mark.parametrize(
    "title",
    [
        "Intro 1",
        "Outro - Closing",
        "Interlude: II",
        "Ouverture (Act I)",
        "Overture - Orchestra",
        "The Prelude II",
        "Prologue 2",
        "Epilogue - End",
        "Theme - Main",
        "Main Theme",
        "电影主题曲",
    ],
)
def test_structural_title_number_and_subtitle_forms_are_rejected(title: str) -> None:
    conn = _connection()
    try:
        _track(conn, 1, title, isrc="SHARED", duration_ms=180_000)
        _track(conn, 2, title.upper(), isrc="SHARED", duration_ms=180_000)

        plan = build_l2_track_merge_plan(conn)

        assert plan["groups"] == []
        assert any(
            edge["reason"] == "structural_title_requires_explicit_merge"
            for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


def test_force_merge_is_the_only_way_to_merge_structural_titles() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Intro")
        _track(conn, 2, "INTRO")
        conn.execute(
            """INSERT INTO track_merge_overrides(
                   scope, left_l1_id, right_l1_id, action, reason
               ) VALUES ('recording', 1, 2, 'force_merge', 'curated structural identity')"""
        )

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert "force_merge" in plan["groups"][0]["evidence_types"]
    finally:
        conn.close()


def test_shared_isrc_fallback_still_merges_different_title_spellings() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Colour Song", isrc="SHARED", duration_ms=180_000)
        _track(conn, 2, "Color Song", isrc="SHARED", duration_ms=181_000)

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert plan["groups"][0]["evidence_types"] == ["same_isrc_compatible_duration"]
    finally:
        conn.close()


def test_two_zero_evidence_local_nodes_merge_with_audit_warning() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Unsubstantiated")
        _track(conn, 2, "unsubstantiated")
        conn.execute("DELETE FROM track_l1_external_ids")

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert plan["edge_status_counts"]["pending"] == 0
        assert plan["unsubstantiated_zero_evidence_pair_count"] == 1
        report = apply_l2_track_merge_plan(conn, plan, commit=True)
        assert report["status"] == "applied"
        candidate = conn.execute(
            "SELECT status, evidence_json FROM track_group_candidates"
        ).fetchone()
        assert candidate["status"] == "accepted"
        assert "zero_play_zero_external_evidence" in candidate["evidence_json"]
    finally:
        conn.close()


def test_apply_can_defer_revision_bump_to_outer_governance_transaction() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Same")
        _track(conn, 2, "same")
        before_revision = conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()[0]

        report = apply_l2_track_merge_plan(conn, commit=True, bump_revision=False)

        assert report["status"] == "applied"
        assert report["revision_bumped"] is False
        assert report["track_identity_revision"] == before_revision
        assert (
            conn.execute(
                "SELECT current_revision FROM track_identity_state WHERE state_id=1"
            ).fetchone()[0]
            == before_revision
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM track_groups WHERE group_status='active'"
            ).fetchone()[0]
            == 1
        )
    finally:
        conn.close()


def test_noncanonical_alias_node_cannot_form_automatic_group() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Alias Song")
        _track(conn, 2, "alias song")
        conn.execute(
            """INSERT INTO spotify_track_owners(
                   spotify_track_id, track_id, evidence_type
               ) VALUES ('spotify-1', 2, 'catalog_projection')"""
        )

        plan = build_l2_track_merge_plan(conn)

        assert plan["groups"] == []
        assert plan["noncanonical_identity_node_count"] == 1
        assert plan["noncanonical_candidate_rejection_count"] == 1
        assert any(
            edge["reason"] == "noncanonical_identity_requires_owner_repair"
            and edge["status"] == "rejected"
            for edge in plan["blocked_edges"]
        )
        apply_l2_track_merge_plan(conn, plan, commit=True)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM track_groups WHERE group_status='active'"
            ).fetchone()[0]
            == 0
        )
        assert (
            validate_track_identity_invariants(conn).pending_candidate_noncanonical_reference_count
            == 0
        )
    finally:
        conn.close()


def test_old_pending_candidate_for_superseded_alias_is_rejected() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Alias Song")
        _track(conn, 2, "alias song")
        conn.execute(
            """INSERT INTO spotify_track_owners(
                   spotify_track_id, track_id, evidence_type
               ) VALUES ('spotify-1', 2, 'catalog_projection')"""
        )
        conn.execute("UPDATE track_l1_identities SET identity_status='superseded' WHERE l1_id=1")
        conn.execute(
            """INSERT INTO track_group_candidates(
                   scope, original_l1_id, candidate_l1_id,
                   confidence, evidence_json, status
               ) VALUES ('recording', 2, 1, 0.5, '{"legacy":true}', 'pending')"""
        )

        before = validate_track_identity_invariants(conn)
        assert before.pending_candidate_noncanonical_reference_count == 1
        plan = build_l2_track_merge_plan(conn)
        assert plan["changed"] is False
        assert plan["noncanonical_identity_node_count"] == 0
        assert plan["noncanonical_candidate_rejection_count"] == 1

        report = apply_l2_track_merge_plan(conn, plan, commit=True)

        assert report["status"] == "unchanged"
        candidate = conn.execute(
            """SELECT status, evidence_json FROM track_group_candidates
                WHERE scope='recording'
                  AND MIN(original_l1_id, candidate_l1_id)=1
                  AND MAX(original_l1_id, candidate_l1_id)=2"""
        ).fetchone()
        assert candidate["status"] == "rejected"
        assert "noncanonical_identity_requires_owner_repair" in candidate["evidence_json"]
        assert (
            validate_track_identity_invariants(conn).pending_candidate_noncanonical_reference_count
            == 0
        )
    finally:
        conn.close()


def test_alias_source_link_marks_node_noncanonical_without_raw_owner() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Projection Alias")
        _track(conn, 2, "projection alias")
        conn.execute(
            """INSERT INTO track_l1_source_links(
                   l1_id, track_id, evidence_type, observed_plays
               ) VALUES (2, 1, 'track_projection', 0)"""
        )

        plan = build_l2_track_merge_plan(conn)

        assert plan["groups"] == []
        assert plan["noncanonical_identity_node_count"] == 1
        assert any(
            edge["reason"] == "noncanonical_identity_requires_owner_repair"
            for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


def test_pure_sister_packaging_merges_and_manual_palm_rose_group_survives() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "纯妹妹", plays=3, isrc="TWU712403525", duration_ms=191_918)
        _track(conn, 2, "純妹妹", plays=2, isrc="TWU712403525", duration_ms=191_918)
        _track(conn, 3, "純妹妹 - 2025版", plays=1, isrc="HKD012720776", duration_ms=191_918)
        _track(conn, 4, "手心的薔薇", plays=2, isrc="TWA531480006", duration_ms=280_053)
        _track(
            conn,
            5,
            "手心的薔薇 (ft. 鄧紫棋)",
            plays=1,
            isrc="TWA531480006",
            duration_ms=280_053,
        )
        cursor = conn.execute(
            """INSERT INTO track_groups(
                   canonical_name, primary_track_id, primary_l1_id,
                   scope, is_manual, group_status
               ) VALUES ('手心的薔薇', 4, 4, 'recording', 1, 'active')"""
        )
        group_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (?, ?)",
            [(group_id, 4), (group_id, 5)],
        )

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2, 3], [4, 5]]
        palm_group = plan["groups"][1]
        assert palm_group["target_group_id"] == group_id
        assert palm_group["target_is_manual"] is True
        assert palm_group["evidence_types"] == ["existing_manual_group"]
    finally:
        conn.close()
