"""Contract tests for version-merge confirmation workflows."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

import pytest

pytestmark = pytest.mark.contract


@pytest.fixture(scope="function")
def isolated_seed_db(use_seed_db):
    """Copy seed.db so mutation tests do not alter the shared fixture."""
    import backend.core.db as db_mod

    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy2(db_mod.DB_PATH, tmp_path)

    original = db_mod.DB_PATH
    db_mod.DB_PATH = tmp_path

    yield tmp_path

    db_mod.DB_PATH = original
    os.unlink(tmp_path)
    db_mod._load_plays_cached.cache_clear()
    db_mod._load_plays_for_artists_cached.cache_clear()


def test_confirm_track_candidate_creates_l3_group_and_rebuilds(isolated_seed_db):
    """Confirmed candidates become L3 composition groups, not L2 groups."""
    from backend.core.db import get_db
    from backend.core.version_merge import confirm_track_group_candidate
    from backend.domains.playback.track_groups import load_track_group_keys

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM track_group_l1_members WHERE group_id IN (920, 921)")
        conn.execute("DELETE FROM track_group_members WHERE group_id IN (920, 921)")
        conn.execute("DELETE FROM track_groups WHERE group_id IN (920, 921)")
        conn.commit()
    finally:
        conn.close()

    result = confirm_track_group_candidate(920, 926, scope="composition")
    assert result["status"] == "ok"
    assert result["scope"] == "composition"
    assert result["album_projects_rebuilt"] is True

    conn = get_db(readonly=True)
    try:
        l2_keys = load_track_group_keys(conn, merge_level=2)
        assert 926 not in set(l2_keys["track_id"])
        l3_keys = load_track_group_keys(conn, merge_level=3)
        l3_map = l3_keys.set_index("track_id")
        assert int(l3_map.loc[920, "track_agg_id"]) == int(l3_map.loc[926, "track_agg_id"])
        assert l3_map.loc[926, "track_group_scope"] == "composition"
    finally:
        conn.close()


def test_confirm_track_candidate_unifies_existing_same_scope_groups(isolated_seed_db):
    """Manual pair selection must not leave a track in two groups at one scope."""
    from backend.core.db import get_db
    from backend.core.version_merge import confirm_track_group_candidate

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM track_group_l1_members WHERE group_id IN (920, 921, 9920, 9921)")
        conn.execute("DELETE FROM track_group_members WHERE group_id IN (920, 921, 9920, 9921)")
        conn.execute("DELETE FROM track_groups WHERE group_id IN (920, 921, 9920, 9921)")
        conn.execute(
            "INSERT INTO track_groups (group_id, canonical_name, primary_track_id, primary_l1_id, scope, is_manual) VALUES (9920, 'Original group', 920, 920, 'composition', 1)"
        )
        conn.execute(
            "INSERT INTO track_groups (group_id, canonical_name, primary_track_id, primary_l1_id, scope, is_manual) VALUES (9921, 'Candidate group', 926, 926, 'composition', 1)"
        )
        conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (9920, 920)")
        conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (9921, 925)")
        conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (9921, 926)")
        conn.execute("INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (9920, 920)")
        conn.execute("INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (9921, 925)")
        conn.execute("INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (9921, 926)")
        conn.commit()
    finally:
        conn.close()

    result = confirm_track_group_candidate(920, 926, scope="composition")
    assert result["status"] == "ok"
    assert result["group_id"] == 9920
    assert result["member_count"] == 3

    conn = get_db(readonly=True)
    try:
        rows = conn.execute(
            """SELECT groups.group_id, groups.primary_l1_id, members.l1_id
                 FROM track_groups groups
                 JOIN track_group_l1_members members
                   ON members.group_id=groups.group_id
                WHERE groups.scope='composition'
                  AND groups.group_status='active'
                  AND members.l1_id IN (920, 925, 926)
                ORDER BY members.l1_id"""
        ).fetchall()
        assert [(row["group_id"], row["l1_id"]) for row in rows] == [
            (9920, 920),
            (9920, 925),
            (9920, 926),
        ]
        assert all(row["primary_l1_id"] == 920 for row in rows)
        assert (
            conn.execute("SELECT group_status FROM track_groups WHERE group_id=9921").fetchone()[0]
            == "archived"
        )
    finally:
        conn.close()


def test_saved_track_group_management_uses_stable_track_ids(isolated_seed_db):
    """The shared saved-groups UI can list and maintain track groups by stable IDs."""
    from backend.core.db import get_db
    from backend.core.version_merge import (
        delete_track_group,
        get_all_track_groups,
        get_track_group_members,
        set_primary_track,
        update_track_group_members,
    )

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM track_group_l1_members WHERE group_id = 921")
        conn.execute("DELETE FROM track_group_members WHERE group_id = 921")
        conn.execute("DELETE FROM track_groups WHERE group_id = 921")
        conn.execute("DELETE FROM track_group_l1_members WHERE group_id = 9930")
        conn.execute("DELETE FROM track_group_members WHERE group_id = 9930")
        conn.execute("DELETE FROM track_groups WHERE group_id = 9930")
        conn.execute(
            "INSERT INTO track_groups (group_id, canonical_name, primary_track_id, primary_l1_id, scope, is_manual) VALUES (9930, 'UI CRUD group', 920, 920, 'composition', 0)"
        )
        conn.executemany(
            "INSERT INTO track_group_members(group_id, track_id) VALUES (9930, ?)", [(920,), (926,)]
        )
        conn.executemany(
            "INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (9930, ?)",
            [(920,), (926,)],
        )
        conn.commit()
    finally:
        conn.close()

    # Reproduce a pre-enforcement orphan through an explicitly legacy
    # connection. Normal application writes must now reject this update.
    legacy = sqlite3.connect(isolated_seed_db)
    try:
        assert legacy.execute("PRAGMA foreign_keys").fetchone()[0] == 0
        legacy.execute("UPDATE tracks SET artist_id = 999999 WHERE track_id = 920")
        legacy.commit()
    finally:
        legacy.close()

    groups = get_all_track_groups().set_index("group_id")
    assert int(groups.loc[9930, "member_count"]) == 2
    assert groups.loc[9930, "scope"] == "composition"
    assert int(groups.loc[9930, "primary_album_id"]) == 920
    assert groups.loc[9930, "artist_name"] == "Fixture Artist Alpha"
    members = get_track_group_members(9930).set_index("track_id")
    assert int(members.loc[920, "is_primary"]) == 1
    assert int(members.loc[920, "album_id"]) == 920
    assert members.loc[920, "artist_name"] == "Fixture Artist Alpha"
    assert set(members.index) == {920, 926}
    assert set_primary_track(9930, 926) is True
    assert update_track_group_members(9930, add_ids=[925], remove_ids=[920]) is True
    members = get_track_group_members(9930).set_index("track_id")
    assert set(members.index) == {925, 926}
    assert int(members.loc[926, "is_primary"]) == 1
    assert int(get_all_track_groups().set_index("group_id").loc[9930, "is_manual"]) == 1
    assert delete_track_group(9930) is True
    assert 9930 not in set(get_all_track_groups()["group_id"])


def test_manual_candidate_search_and_confirmation_use_one_spotify_owner(isolated_seed_db):
    from backend.core.db import get_db
    from backend.core.version_merge import (
        confirm_track_group_candidate,
        search_track_l1_candidates,
    )

    spotify_id = "5DpQ7EYvM9aCG90luO9PQW"
    conn = get_db(readonly=False)
    try:
        conn.executemany(
            """INSERT INTO tracks(
                   track_id, track_name, artist_id, album_id, spotify_track_id
               ) VALUES (?, ?, ?, 920, ?)""",
            [
                (12001, "假如我们还爱着", 901, spotify_id),
                (12002, "假如我們還愛著", 902, spotify_id),
                (12003, "假如我们还爱着", 1, spotify_id),
            ],
        )
        conn.executemany(
            """INSERT INTO track_l1_identities(
                   l1_id, provider, fallback_track_id,
                   identity_status, representative_track_id
               ) VALUES (?, 'local', ?, 'active', ?)""",
            ((track_id, track_id, track_id) for track_id in (12001, 12002, 12003)),
        )
        conn.execute(
            """INSERT INTO spotify_track_owners(
                   spotify_track_id, track_id, evidence_type
               ) VALUES (?, 12002, 'play_majority')""",
            (spotify_id,),
        )
        conn.execute(
            """INSERT INTO track_l1_external_ids(
                   provider, external_track_id, l1_id, evidence_type, is_primary
               ) VALUES ('spotify', ?, 12002, 'migration', 1)""",
            (spotify_id,),
        )
        conn.executemany(
            """INSERT INTO track_l1_source_links(
                   l1_id, track_id, evidence_type, observed_plays
               ) VALUES (12002, ?, 'track_projection', 0)""",
            ((track_id,) for track_id in (12001, 12002, 12003)),
        )
        conn.commit()
    finally:
        conn.close()

    rows = search_track_l1_candidates("假如我们还爱着")
    assert [int(row["l1_id"]) for row in rows] == [12002]
    assert search_track_l1_candidates("12001")[0]["l1_id"] == 12002
    assert search_track_l1_candidates(spotify_id)[0]["l1_id"] == 12002

    result = confirm_track_group_candidate(
        12001,
        12003,
        scope="recording",
        references_are_l1=True,
    )
    assert result == {
        "status": "error",
        "error_code": "same_spotify_identity",
        "message": "它们已经是同一个 Spotify 曲目，不需要归并",
    }


def test_composition_release_group_is_l3_only_and_rebuilds_projects(isolated_seed_db):
    """Composition release groups power L3 album projects but do not merge at L2."""
    from backend.core.db import get_db, load_plays
    from backend.core.version_merge import create_group
    from backend.domains.playback.album_projects import (
        compute_album_project_plays,
        rebuild_album_projects,
    )

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM release_group_members WHERE group_id = 921")
        conn.execute("DELETE FROM release_groups WHERE group_id = 921")
        rebuild_album_projects(conn)
    finally:
        conn.close()

    group_id = create_group(
        canonical_name="Fixture Future LP",
        artist_id=901,
        primary_album_id=921,
        member_ids=[921, 922, 925],
        scope="composition",
    )

    assert group_id is not None

    conn = get_db(readonly=True)
    try:
        group = conn.execute(
            "SELECT scope FROM release_groups WHERE group_id = ?", (group_id,)
        ).fetchone()
        assert group["scope"] == "composition"

        project_track = conn.execute(
            """SELECT apt.min_merge_level
               FROM album_project_tracks apt
               JOIN album_projects ap ON ap.project_id = apt.project_id
               WHERE ap.canonical_name = 'Fixture Future LP'
                 AND ap.scope = 'composition'
                 AND apt.track_id = 927"""
        ).fetchone()
        assert project_track is not None
        assert int(project_track["min_merge_level"]) == 3

        valid = load_plays(conn, min_ms=30000, music_only=True, merge_enabled=True)
        l2 = compute_album_project_plays(valid, conn, merge_level=2, include_compilations=True)
        l3 = compute_album_project_plays(valid, conn, merge_level=3, include_compilations=True)
        l2_future = l2[l2["album_project_name"] == "Fixture Future LP"].iloc[0]
        l3_future = l3[l3["album_project_name"] == "Fixture Future LP"].iloc[0]

        assert int(l2_future["play_count"]) == 9
        assert int(l3_future["play_count"]) == 12
    finally:
        conn.close()


def test_track_group_confirm_api_returns_rebuild_status(isolated_seed_db):
    from fastapi.testclient import TestClient

    from backend.core.db import get_db
    from backend.main import app

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM track_group_l1_members WHERE group_id IN (920, 921)")
        conn.execute("DELETE FROM track_group_members WHERE group_id IN (920, 921)")
        conn.execute("DELETE FROM track_groups WHERE group_id IN (920, 921)")
        conn.commit()
    finally:
        conn.close()

    with TestClient(app) as client:
        response = client.post(
            "/api/version-merge/track-groups/confirm",
            json={
                "original_track_id": 920,
                "candidate_track_id": 926,
                "scope": "composition",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["scope"] == "composition"
    assert payload["album_projects_rebuilt"] is True


def test_artist_release_groups_api_matches_response_model(isolated_seed_db):
    """Artist-filtered groups must include all ReleaseGroupResponse fields."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        response = client.get("/api/version-merge/groups/artist/Fixture%20Artist%20Alpha")

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert {"artist_name", "created_at"} <= set(payload[0])


def test_release_group_create_api_accepts_composition_scope(isolated_seed_db):
    from fastapi.testclient import TestClient

    from backend.core.db import get_db
    from backend.domains.playback.album_projects import rebuild_album_projects
    from backend.main import app

    with TestClient(app) as client:
        conn = get_db(readonly=False)
        try:
            conn.execute("DELETE FROM release_group_members WHERE group_id = 921")
            conn.execute("DELETE FROM release_groups WHERE group_id = 921")
            rebuild_album_projects(conn)
        finally:
            conn.close()
        response = client.post(
            "/api/version-merge/groups",
            json={
                "canonical_name": "Fixture Future LP",
                "artist_id": 0,
                "primary_album_id": 921,
                "member_ids": [921, 922, 925],
                "scope": "composition",
            },
        )
        assert response.status_code == 200
        group_id = response.json()["group_id"]
        groups_response = client.get("/api/version-merge/groups")

    assert groups_response.status_code == 200
    group = next(row for row in groups_response.json() if row["group_id"] == group_id)
    assert group["scope"] == "composition"
    assert group["artist_name"]

    conn = get_db(readonly=True)
    try:
        stored = conn.execute(
            "SELECT artist_id FROM release_groups WHERE group_id = ?",
            (group_id,),
        ).fetchone()
        assert int(stored["artist_id"]) == 901
    finally:
        conn.close()


def test_album_relation_bundle_confirms_album_and_matching_track_versions(isolated_seed_db):
    """Confirming a composition album relation also creates matching song relations."""
    from backend.core.db import get_db, load_plays
    from backend.core.version_merge import confirm_album_relation_bundle
    from backend.domains.playback.album_projects import (
        compute_album_project_plays,
        rebuild_album_projects,
    )
    from backend.domains.playback.track_groups import load_track_group_keys

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM release_group_members WHERE group_id = 921")
        conn.execute("DELETE FROM release_groups WHERE group_id = 921")
        conn.execute("DELETE FROM track_group_l1_members WHERE group_id = 921")
        conn.execute("DELETE FROM track_group_members WHERE group_id = 921")
        conn.execute("DELETE FROM track_groups WHERE group_id = 921")
        rebuild_album_projects(conn)
    finally:
        conn.close()

    result = confirm_album_relation_bundle(
        canonical_name="Fixture Future LP",
        primary_album_id=921,
        member_album_ids=[925],
        scope="composition",
        relation_type="rerecord",
        confirm_track_pairs=True,
    )

    assert result["status"] == "ok"
    assert result["scope"] == "composition"
    assert result["album_projects_rebuilt"] is True
    assert result["release_group_id"] is not None
    assert result["confirmed_track_pair_count"] == 1
    assert result["candidate_track_pair_count"] == 1
    assert result["exclusive_track_count"] == 1
    assert result["track_pairs"][0]["original_track_id"] == 920
    assert result["track_pairs"][0]["candidate_track_id"] == 925
    assert result["exclusive_tracks"][0]["track_id"] == 927

    conn = get_db(readonly=True)
    try:
        group = conn.execute(
            "SELECT scope FROM release_groups WHERE group_id = ?",
            (result["release_group_id"],),
        ).fetchone()
        assert group["scope"] == "composition"

        l3_keys = load_track_group_keys(conn, merge_level=3)
        l3_map = l3_keys.set_index("track_id")
        assert int(l3_map.loc[920, "track_agg_id"]) == int(l3_map.loc[925, "track_agg_id"])

        valid = load_plays(conn, min_ms=30000, music_only=True, merge_enabled=True)
        l2 = compute_album_project_plays(valid, conn, merge_level=2, include_compilations=True)
        l3 = compute_album_project_plays(valid, conn, merge_level=3, include_compilations=True)
        l2_future = l2[l2["album_project_name"] == "Fixture Future LP"].iloc[0]
        l3_future = l3[l3["album_project_name"] == "Fixture Future LP"].iloc[0]
        assert int(l2_future["play_count"]) == 9
        assert int(l3_future["play_count"]) == 11
    finally:
        conn.close()


def test_album_relation_bundle_api_returns_derived_track_pairs(isolated_seed_db):
    from fastapi.testclient import TestClient

    from backend.core.db import get_db
    from backend.domains.playback.album_projects import rebuild_album_projects
    from backend.main import app

    with TestClient(app) as client:
        conn = get_db(readonly=False)
        try:
            conn.execute("DELETE FROM release_group_members WHERE group_id = 921")
            conn.execute("DELETE FROM release_groups WHERE group_id = 921")
            conn.execute("DELETE FROM track_group_l1_members WHERE group_id = 921")
            conn.execute("DELETE FROM track_group_members WHERE group_id = 921")
            conn.execute("DELETE FROM track_groups WHERE group_id = 921")
            rebuild_album_projects(conn)
        finally:
            conn.close()
        response = client.post(
            "/api/version-merge/album-relations/confirm",
            json={
                "canonical_name": "Fixture Future LP",
                "primary_album_id": 921,
                "member_album_ids": [925],
                "scope": "composition",
                "relation_type": "rerecord",
                "confirm_track_pairs": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["confirmed_track_pair_count"] == 1
    assert payload["exclusive_track_count"] == 1
    assert payload["track_pairs"][0]["original_track_id"] == 920
    assert payload["track_pairs"][0]["candidate_track_id"] == 925

    with TestClient(app) as client:
        response = client.post(
            "/api/version-merge/groups",
            json={
                "canonical_name": "Fixture Future LP",
                "artist_id": 0,
                "primary_album_id": 921,
                "member_ids": [921, 922, 925],
                "scope": "composition",
            },
        )
        assert response.status_code == 200
        group_id = response.json()["group_id"]
        groups_response = client.get("/api/version-merge/groups")

    assert groups_response.status_code == 200
    group = next(row for row in groups_response.json() if row["group_id"] == group_id)
    assert group["scope"] == "composition"
    assert group["artist_name"]

    conn = get_db(readonly=True)
    try:
        stored = conn.execute(
            "SELECT artist_id FROM release_groups WHERE group_id = ?",
            (group_id,),
        ).fetchone()
        assert int(stored["artist_id"]) == 901
    finally:
        conn.close()
