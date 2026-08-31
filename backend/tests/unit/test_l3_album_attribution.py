from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.core.db import SCHEMA
from backend.domains.billboard.details import _build_l3_source_project_explanation
from backend.domains.playback.album_projects import (
    compute_album_project_plays,
    load_album_project_membership,
)
from backend.domains.playback.l3_album_attribution import (
    apply_l3_album_attribution_plan,
    get_l3_album_attribution_state,
    load_l3_song_album_attributions,
    plan_l3_album_attributions,
)

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Artist')")
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (2, 'Other Artist')")
    return conn


def _project(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    album_id: int,
    name: str,
    source_bucket: str,
    scope: str = "release",
    artist_id: int = 1,
    release_date: str = "2020-01-01",
) -> None:
    conn.execute(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
        (album_id, name, artist_id),
    )
    conn.execute(
        """INSERT INTO album_projects(
               project_id, canonical_name, artist_id, primary_album_id,
               release_date, scope, project_type, include_in_charts
           ) VALUES (?, ?, ?, ?, ?, ?, 'album', 1)""",
        (project_id, name, artist_id, album_id, release_date, scope),
    )
    conn.execute(
        """INSERT INTO album_project_albums(
               project_id, album_id, role, source_bucket
           ) VALUES (?, ?, 'member', ?)""",
        (project_id, album_id, source_bucket),
    )


def _track(
    conn: sqlite3.Connection,
    *,
    track_id: int,
    album_id: int,
    project_id: int,
    name: str,
    role: str = "standard",
    artist_id: int = 1,
) -> None:
    conn.execute(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id)
           VALUES (?, ?, ?, ?)""",
        (track_id, name, artist_id, album_id),
    )
    conn.execute(
        """INSERT INTO track_l1_identities(
               l1_id, fallback_track_id, representative_track_id, identity_status
           ) VALUES (?, ?, ?, 'active')""",
        (track_id, track_id, track_id),
    )
    conn.execute(
        """INSERT INTO album_project_tracks(
               project_id, track_id, membership_role, min_merge_level,
               source_album_id
           ) VALUES (?, ?, ?, 2, ?)""",
        (project_id, track_id, role, album_id),
    )


def _composition(conn: sqlite3.Connection, *track_ids: int, name: str) -> int:
    cursor = conn.execute(
        """INSERT INTO track_groups(
               canonical_name, primary_track_id, primary_l1_id,
               scope, is_manual, group_status
           ) VALUES (?, ?, ?, 'composition', 1, 'active')""",
        (name, track_ids[0], track_ids[0]),
    )
    group_id = int(cursor.lastrowid)
    conn.executemany(
        "INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (?, ?)",
        ((group_id, track_id) for track_id in track_ids),
    )
    return group_id


def test_live_version_returns_to_studio_and_cover_remains_live_residual() -> None:
    conn = _connection()
    try:
        _project(
            conn,
            project_id=10,
            album_id=100,
            name="Fearless",
            source_bucket="original_album",
        )
        _project(
            conn,
            project_id=20,
            album_id=200,
            name="Fearless: Live From Wembley",
            source_bucket="original_album",  # deliberately misleading legacy bucket
        )
        _track(conn, track_id=1, album_id=100, project_id=10, name="Love Story")
        _track(conn, track_id=2, album_id=200, project_id=20, name="Love Story (Live)")
        _track(
            conn,
            track_id=3,
            album_id=200,
            project_id=20,
            name="A Case of You (Live Cover)",
        )
        _composition(conn, 1, 2, name="Love Story")

        plan = plan_l3_album_attributions(conn)

        assert plan.scanned_song_count == 2
        assert plan.conflict_song_keys == ()
        by_name = {item.canonical_song_name: item for item in plan.decisions}
        love_story = by_name["Love Story"]
        assert love_story.target_project_id == 10
        assert love_story.origin_release_project_id == 10
        assert love_story.attribution_kind == "studio_album"
        cover = next(item for item in plan.decisions if item.representative_track_id == 3)
        assert cover.target_project_id == 20
        assert cover.attribution_kind == "live_residual"

        report = apply_l3_album_attribution_plan(conn, plan)
        assert report.changed is True
        assert report.rows_inserted == 2
        state = get_l3_album_attribution_state(conn)
        assert state["status"] == "ready"
        assert state["attributed_count"] == 2
        assert apply_l3_album_attribution_plan(conn).changed is False

        events = pd.DataFrame(
            [
                {"track_id": 1, "source_album_id": 100, "ms_played": 180_000},
                {"track_id": 1, "source_album_id": 100, "ms_played": 180_000},
                {"track_id": 2, "source_album_id": 200, "ms_played": 180_000},
                {"track_id": 2, "source_album_id": 200, "ms_played": 180_000},
                {"track_id": 2, "source_album_id": 200, "ms_played": 180_000},
                {"track_id": 3, "source_album_id": 200, "ms_played": 180_000},
            ]
        )
        membership = load_album_project_membership(conn, merge_level=3, include_compilations=True)
        assert not membership.duplicated("canonical_song_key").any()
        totals = compute_album_project_plays(
            events,
            conn,
            merge_level=3,
            include_compilations=True,
        ).set_index("album_project_name")
        assert int(totals.loc["Fearless", "play_count"]) == 5
        assert int(totals.loc["Fearless: Live From Wembley", "play_count"]) == 1
        assert int(totals["play_count"].sum()) == len(events)
    finally:
        conn.close()


def test_vault_track_uses_rerecord_origin_and_album_composition_parent() -> None:
    conn = _connection()
    try:
        _project(
            conn,
            project_id=10,
            album_id=100,
            name="1989",
            source_bucket="original_album",
        )
        _project(
            conn,
            project_id=20,
            album_id=200,
            name="1989 (Taylor's Version)",
            source_bucket="rerecord",
        )
        conn.execute(
            """INSERT INTO album_projects(
                   project_id, canonical_name, artist_id, primary_album_id,
                   release_date, scope, project_type, include_in_charts
               ) VALUES (30, '1989', 1, 100, '2014-01-01',
                         'composition', 'album', 1)"""
        )
        conn.executemany(
            """INSERT INTO album_project_albums(
                   project_id, album_id, role, source_bucket
               ) VALUES (30, ?, 'member', ?)""",
            ((100, "original_album"), (200, "rerecord")),
        )
        _track(
            conn,
            track_id=5,
            album_id=200,
            project_id=20,
            name="Say Don't Go (Taylor's Version)",
            role="rerecord",
        )

        plan = plan_l3_album_attributions(conn)

        assert len(plan.decisions) == 1
        decision = plan.decisions[0]
        assert decision.origin_release_project_id == 20
        assert decision.target_project_id == 30
        assert decision.attribution_kind == "rerecord_union"
    finally:
        conn.close()


def test_same_artist_song_uses_earliest_studio_album_without_manual_review() -> None:
    conn = _connection()
    try:
        _project(
            conn,
            project_id=10,
            album_id=100,
            name="Album A",
            source_bucket="original_album",
            release_date="2018-01-01",
        )
        _project(
            conn,
            project_id=20,
            album_id=200,
            name="Album B",
            source_bucket="original_album",
            release_date="2020-01-01",
        )
        _track(conn, track_id=1, album_id=100, project_id=10, name="Shared Song")
        _track(conn, track_id=2, album_id=200, project_id=20, name="Shared Song")
        _composition(conn, 1, 2, name="Shared Song")

        plan = plan_l3_album_attributions(conn)

        assert plan.conflict_song_keys == ()
        assert len(plan.decisions) == 1
        assert plan.decisions[0].target_project_id == 10
        report = apply_l3_album_attribution_plan(conn, plan)
        assert report.conflict_count == 0
        assert (
            conn.execute("SELECT COUNT(*) FROM l3_song_album_attribution_issues").fetchone()[0] == 0
        )
    finally:
        conn.close()


def test_approved_cross_artist_composition_still_uses_unique_album_owner() -> None:
    conn = _connection()
    try:
        _project(
            conn,
            project_id=10,
            album_id=100,
            name="Artist Album",
            source_bucket="original_album",
        )
        _project(
            conn,
            project_id=20,
            album_id=200,
            name="Other Album",
            source_bucket="original_album",
            artist_id=2,
        )
        _track(conn, track_id=1, album_id=100, project_id=10, name="Shared Song")
        _track(
            conn,
            track_id=2,
            album_id=200,
            project_id=20,
            name="Shared Song",
            artist_id=2,
        )
        _composition(conn, 1, 2, name="Shared Song")

        plan = plan_l3_album_attributions(conn)

        assert plan.conflict_song_keys == ()
        assert len(plan.decisions) == 1
        assert plan.decisions[0].target_project_id == 10
        report = apply_l3_album_attribution_plan(conn, plan)
        assert report.conflict_count == 0
    finally:
        conn.close()


def test_published_projection_rejects_stale_album_project_revision() -> None:
    conn = _connection()
    try:
        _project(
            conn,
            project_id=10,
            album_id=100,
            name="Album",
            source_bucket="original_album",
        )
        _track(conn, track_id=1, album_id=100, project_id=10, name="Song")
        apply_l3_album_attribution_plan(conn)

        assert len(load_l3_song_album_attributions(conn)) == 1
        conn.executescript(
            """CREATE TABLE album_project_revision_state(
                   state_id INTEGER PRIMARY KEY,
                   current_revision INTEGER NOT NULL,
                   updated_at TEXT
               );
               INSERT INTO album_project_revision_state VALUES (1, 1, NULL);"""
        )
        with pytest.raises(RuntimeError, match="missing or stale"):
            load_l3_song_album_attributions(conn)
    finally:
        conn.close()


def test_work_without_album_membership_is_persisted_as_uncovered() -> None:
    conn = _connection()
    try:
        conn.execute(
            "INSERT INTO albums(album_id, album_name, artist_id) VALUES (100, 'Missing Album', 1)"
        )
        conn.execute(
            """INSERT INTO tracks(track_id, track_name, artist_id, album_id)
               VALUES (1, 'Missing Song', 1, 100)"""
        )
        conn.execute(
            """INSERT INTO track_l1_identities(
                   l1_id, fallback_track_id, representative_track_id, identity_status
               ) VALUES (1, 1, 1, 'active')"""
        )

        plan = plan_l3_album_attributions(conn)

        assert plan.scanned_song_count == 1
        assert plan.decisions == ()
        assert plan.uncovered_song_keys == ("l1:1",)
        assert plan.exclusions == ()
        report = apply_l3_album_attribution_plan(conn, plan)
        assert report.scanned_count == 1
        assert report.uncovered_count == 1
        state = get_l3_album_attribution_state(conn)
        assert state["scanned_count"] == 1
        assert state["attributed_count"] == 0
        assert state["uncovered_count"] == 1
        assert (
            conn.execute("SELECT COUNT(*) FROM l3_song_album_attribution_issues").fetchone()[0] == 1
        )
        assert plan_l3_album_attributions(conn).changed is False
    finally:
        conn.close()


def test_live_source_explanation_separates_residual_transferred_and_raw_versions() -> None:
    conn = _connection()
    try:
        _project(conn, project_id=10, album_id=100, name="Fearless", source_bucket="original_album")
        _project(
            conn, project_id=20, album_id=200, name="Tour Live", source_bucket="original_album"
        )
        _track(conn, track_id=1, album_id=100, project_id=10, name="Love Story")
        _track(conn, track_id=2, album_id=200, project_id=20, name="Love Story (Live)")
        _track(conn, track_id=3, album_id=200, project_id=20, name="Live Exclusive")
        _composition(conn, 1, 2, name="Love Story")
        apply_l3_album_attribution_plan(conn)

        events = pd.DataFrame(
            [
                {
                    "track_id": 2,
                    "track_name": "Love Story (Live)",
                    "source_album_id": 200,
                    "ms_played": 120_000,
                },
                {
                    "track_id": 2,
                    "track_name": "Love Story (Live)",
                    "source_album_id": 200,
                    "ms_played": 180_000,
                },
                {
                    "track_id": 3,
                    "track_name": "Live Exclusive",
                    "source_album_id": 200,
                    "ms_played": 160_000,
                },
            ]
        )

        explanation = _build_l3_source_project_explanation(conn, events, 20)

        assert explanation["source_play_count"] == 3
        assert len(explanation["source_tracks"]) == 2
        assert [
            (row["canonical_song_name"], row["play_count"])
            for row in explanation["transferred_tracks"]
        ] == [("Love Story", 2)]
        assert [
            (row["canonical_song_name"], row["play_count"])
            for row in explanation["residual_tracks"]
        ] == [("Live Exclusive", 1)]
        assert explanation["transferred_tracks"][0]["target_project_name"] == "Fearless"
    finally:
        conn.close()


def test_l3_attribution_read_api_exposes_health_decision_evidence_and_search() -> None:
    from backend.api.version_merge import (
        l3_album_attribution_health,
        list_l3_album_attributions,
    )

    conn = _connection()
    try:
        _project(conn, project_id=10, album_id=100, name="Fearless", source_bucket="original_album")
        _track(conn, track_id=1, album_id=100, project_id=10, name="Love Story")
        apply_l3_album_attribution_plan(conn)

        health = l3_album_attribution_health(conn)
        assert health["healthy"] is True
        assert health["published_count"] == 1
        assert health["scanned_count"] == 1
        assert health["published_exclusion_count"] == 0
        assert health["coverage_reconciled"] is True
        assert health["unresolved_raw_play_count"] == 0
        assert health["issue_count"] == 0

        response = list_l3_album_attributions(q="Love", limit=20, offset=0, conn=conn)
        assert response["total"] == 1
        assert response["items"][0]["canonical_song_name"] == "Love Story"
        assert response["items"][0]["target_project_name"] == "Fearless"
        assert "evidence_codes" in response["items"][0]["evidence"]
        assert list_l3_album_attributions(q="missing", limit=20, offset=0, conn=conn)["total"] == 0
    finally:
        conn.close()


def test_l1_risk_health_reads_latest_persisted_governance_classification() -> None:
    from backend.api.version_merge import l1_identity_risk_health

    conn = _connection()
    try:
        conn.execute(
            """INSERT INTO version_governance_runs(
                   run_id, scope, policy_version, status, dry_run, summary_json
               ) VALUES ('risk-run', 'l1+l2+l3', 'policy-v2', 'applied', 0, ?)""",
            ('{"l1_audit":{"keep_l1_count":55,"split_l1_count":2,"review_l1_count":5}}',),
        )
        conn.commit()

        health = l1_identity_risk_health(conn)
        assert health["status"] == "applied"
        assert health["run_id"] == "risk-run"
        assert health["summary"] == {
            "keep_l1_count": 55,
            "split_l1_count": 2,
            "review_l1_count": 5,
        }
    finally:
        conn.close()
