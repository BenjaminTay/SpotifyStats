"""Contract tests for version-merge confirmation workflows."""

from __future__ import annotations

import os
import shutil
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
        conn.execute("DELETE FROM track_group_members WHERE group_id IN (920, 921)")
        conn.execute("DELETE FROM track_groups WHERE group_id IN (920, 921)")
        conn.commit()
    finally:
        conn.close()

    result = confirm_track_group_candidate(
        original_track_id=920,
        candidate_track_id=926,
        scope="composition",
    )

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

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM release_group_members WHERE group_id = 921")
        conn.execute("DELETE FROM release_groups WHERE group_id = 921")
        rebuild_album_projects(conn)
    finally:
        conn.close()

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

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM release_group_members WHERE group_id = 921")
        conn.execute("DELETE FROM release_groups WHERE group_id = 921")
        conn.execute("DELETE FROM track_group_members WHERE group_id = 921")
        conn.execute("DELETE FROM track_groups WHERE group_id = 921")
        rebuild_album_projects(conn)
    finally:
        conn.close()

    with TestClient(app) as client:
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
