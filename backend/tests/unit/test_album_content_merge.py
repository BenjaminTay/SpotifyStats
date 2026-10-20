"""Content evidence, existing-group expansion and shared workflow regressions."""

from dataclasses import replace

import pytest

from backend.domains.playback.album_project_auto_merge import (
    apply_album_project_auto_merge_plan,
    plan_album_project_auto_merges,
)
from backend.domains.playback.album_project_identity import resolve_album_project_identity
from backend.domains.playback.album_projects import rebuild_album_projects
from backend.tests.unit.test_album_project_auto_merge import (
    _add_local_album,
    _add_release_track_metadata,
    _add_spotify_release,
    _connection,
    _prepare_standalone_projects,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def conn():
    c = _connection()
    yield c
    c.close()


def add(c, aid, name, recordings, *, artist_id=1, artist="Artist", date="2021-01-01"):
    sid = f"album-{aid}"
    ids = [f"{aid}-track-{i}" for i in range(len(recordings))]
    _add_spotify_release(
        c,
        spotify_album_id=sid,
        album_name=name,
        album_artists=artist,
        release_date=date,
        track_ids=ids,
    )
    _add_local_album(
        c,
        album_id=aid,
        album_name=name,
        artist_id=artist_id,
        artist_name=artist,
        spotify_album_id=sid,
        spotify_track_id=ids[0],
    )
    _add_release_track_metadata(
        c,
        spotify_album_id=sid,
        tracks=[(tid, f"Track {rid}", f"ISRC-{rid}") for tid, rid in zip(ids, recordings)],
    )


@pytest.mark.parametrize(
    "name,order",
    [
        ("An Entirely Different Title", [1, 2, 3, 4, 5, 6, 7]),
        ("The First Chapter: The Encore", [7, 5, 3, 1, 6, 2, 4]),
        ("A Giant Expansion", list(range(1, 31))),
    ],
)
def test_title_and_order_do_not_block_complete_recording_superset(conn, name, order):
    add(conn, 10, "The First Chapter", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, name, order)
    _prepare_standalone_projects(conn)
    plan = plan_album_project_auto_merges(conn)
    assert len(plan.candidates) == 1
    item = plan.candidates[0]
    assert item.relation_types == ("content_superset",)
    assert len(item.track_matches) == 5
    assert {m["evidence"] for m in item.track_matches} == {"isrc"}
    assert item.primary_album_id == 10


def test_expand_existing_group_preserves_id_members_external_ids_and_old_links(conn):
    add(conn, 10, "Base", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "Base + Acoustic Collection", [1, 2, 3, 4, 5, 90])
    add(conn, 12, "A New World", [1, 2, 3, 4, 5, 6, 7])
    conn.execute(
        "INSERT INTO release_groups(group_id,canonical_name,artist_id,primary_album_id,scope,is_manual) VALUES(100,'Base',1,10,'release',0)"
    )
    conn.executemany("INSERT INTO release_group_members VALUES(100,?)", [(10,), (11,)])
    _prepare_standalone_projects(conn)
    target = conn.execute(
        "SELECT project_id FROM album_projects WHERE primary_album_id=10"
    ).fetchone()[0]
    retired = conn.execute(
        "SELECT project_id FROM album_projects WHERE primary_album_id=12"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO album_project_external_ids(provider,external_album_id,project_id,evidence_type,confidence,is_primary) VALUES('spotify','album-12',?,'catalog_exact',1,1)",
        (retired,),
    )
    conn.commit()
    plan = plan_album_project_auto_merges(conn)
    assert plan.candidates[0].album_ids == (10, 11, 12)
    before = [tuple(r) for r in conn.execute("SELECT * FROM plays ORDER BY play_id")]
    apply_album_project_auto_merge_plan(conn, plan)
    assert (
        conn.execute(
            "SELECT count(*) FROM album_projects WHERE project_id=?", (target,)
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT project_id FROM album_project_external_ids WHERE external_album_id=?",
            ("album-12",),
        ).fetchone()[0]
        == target
    )
    assert resolve_album_project_identity(conn, project_id=retired).project_id == target
    assert resolve_album_project_identity(conn, project_id=retired).requested_project_id == retired
    assert (
        conn.execute("SELECT source_bucket FROM album_project_albums WHERE album_id=12").fetchone()[
            0
        ]
        == "deluxe"
    )
    rebuild_album_projects(conn)
    assert (
        conn.execute("SELECT source_bucket FROM album_project_albums WHERE album_id=12").fetchone()[
            0
        ]
        == "deluxe"
    )
    assert [tuple(r) for r in conn.execute("SELECT * FROM plays ORDER BY play_id")] == before
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    events = conn.execute("SELECT count(*) FROM album_release_merge_events").fetchone()[0]
    again = plan_album_project_auto_merges(conn)
    assert not again.candidates
    apply_album_project_auto_merge_plan(conn, again)
    assert conn.execute("SELECT count(*) FROM album_release_merge_events").fetchone()[0] == events


def test_partial_overlap_and_same_titles_with_conflicting_isrc_remain_pending(conn):
    add(conn, 10, "Base", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "Beyond", [1, 2, 3, 4, 9, 10])
    _prepare_standalone_projects(conn)
    plan = plan_album_project_auto_merges(conn)
    assert not plan.candidates
    assert plan.pending[0]["coverage"] == 0.8
    conn.execute(
        "UPDATE spotify_track_meta SET track_name='Track 5' WHERE spotify_track_id='11-track-4'"
    )
    assert not plan_album_project_auto_merges(conn).candidates


def test_bridge_cannot_merge_two_independent_bases_via_a_bundle(conn):
    add(conn, 10, "One", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "Two", [11, 12, 13, 14, 15], date="2020-02-01")
    add(conn, 12, "Both Albums In One", [1, 2, 3, 4, 5, 11, 12, 13, 14, 15])
    _prepare_standalone_projects(conn)
    plan = plan_album_project_auto_merges(conn)
    assert not plan.candidates
    assert dict(plan.skipped_reason_counts)["ambiguous_content_base"] == 1


def test_incomplete_catalog_different_artist_and_duplicate_position_are_not_accepted(conn):
    add(conn, 10, "One", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New Name", [1, 2, 3, 4, 5, 6], artist_id=2, artist="Other")
    _prepare_standalone_projects(conn)
    assert not plan_album_project_auto_merges(conn).candidates
    conn.execute(
        "UPDATE spotify_album_meta SET album_artists='Artist' WHERE spotify_album_id='album-11'"
    )
    conn.execute("UPDATE spotify_album_meta SET total_tracks=7 WHERE spotify_album_id='album-11'")
    assert not plan_album_project_auto_merges(conn).candidates
    conn.execute("UPDATE spotify_album_meta SET total_tracks=6 WHERE spotify_album_id='album-11'")
    conn.execute("UPDATE spotify_track_meta SET isrc='ISRC-1' WHERE spotify_track_id='10-track-1'")
    assert not plan_album_project_auto_merges(conn).candidates


def test_shared_detection_and_apply_revalidate_instead_of_trusting_payload(conn, monkeypatch):
    from backend.core import version_merge

    add(conn, 10, "Old", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New", [1, 2, 3, 4, 5, 6])
    _prepare_standalone_projects(conn)

    class Borrowed:
        def __getattr__(self, name):
            return getattr(conn, name)

        def close(self):
            pass

    monkeypatch.setattr(version_merge, "get_db", lambda **kw: Borrowed())
    monkeypatch.setattr(version_merge, "_detect_groups_for_type", lambda *a: [])
    monkeypatch.setattr(version_merge, "_refresh_version_merge_dependents", lambda *a, **kw: None)
    monkeypatch.setattr(version_merge, "_notify_version_merge_dependents", lambda: None)
    rows = version_merge.detect_release_groups()
    assert set(rows.iloc[0]["members"][i]["album_id"] for i in range(2)) == {10, 11}
    assert version_merge.apply_detected_groups(rows) == 1
    assert not plan_album_project_auto_merges(conn).candidates


def test_album_manual_separation_and_stale_plan_are_enforced(conn):
    from backend.domains.playback.album_release_governance import preserve_separation

    add(conn, 10, "Old", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New", [1, 2, 3, 4, 5, 6])
    _prepare_standalone_projects(conn)
    old = plan_album_project_auto_merges(conn)
    preserve_separation(conn, [10], [11], reason="manual_member_removal")
    conn.commit()
    assert not plan_album_project_auto_merges(conn).candidates
    with pytest.raises(RuntimeError, match="stale"):
        apply_album_project_auto_merge_plan(conn, old)
    assert not conn.execute("SELECT * FROM album_release_merge_events").fetchall()


def test_selected_plan_applies_only_the_selected_relation(conn):
    for aid, name, tracks in [
        (10, "A", [1, 2, 3, 4, 5]),
        (11, "B", [1, 2, 3, 4, 5, 6]),
        (12, "C", [11, 12, 13, 14, 15]),
        (13, "D", [11, 12, 13, 14, 15, 16]),
    ]:
        add(conn, aid, name, tracks, date="2020-01-01")
    _prepare_standalone_projects(conn)
    plan = plan_album_project_auto_merges(conn)
    assert len(plan.candidates) == 2
    apply_album_project_auto_merge_plan(conn, replace(plan, candidates=(plan.candidates[0],)))
    assert len(plan_album_project_auto_merges(conn).candidates) == 1


def test_canonical_and_legacy_artist_evidence_share_one_complete_identity(conn):
    from backend.domains.metadata.spotify_album_credits import save_album_credit_evidence

    add(conn, 10, "Old", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New", [1, 2, 3, 4, 5, 6])
    conn.execute("ALTER TABLE artists ADD COLUMN spotify_artist_id TEXT")
    conn.execute("UPDATE artists SET spotify_artist_id='provider-artist' WHERE artist_id=1")
    save_album_credit_evidence(
        conn, {"id": "album-11", "artists": [{"id": "provider-artist", "name": "Artist"}]}
    )
    _prepare_standalone_projects(conn)
    assert len(plan_album_project_auto_merges(conn).candidates) == 1
    conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES(2,'ARTIST')")
    assert not plan_album_project_auto_merges(conn).candidates


def test_manual_member_removal_and_group_deletion_persist_album_exclusions(conn, monkeypatch):
    from backend.core import version_merge
    from backend.domains.playback.album_release_governance import separated_pairs

    add(conn, 10, "Old", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New", [1, 2, 3, 4, 5, 6])
    _prepare_standalone_projects(conn)
    apply_album_project_auto_merge_plan(conn, plan_album_project_auto_merges(conn))
    gid = conn.execute("SELECT group_id FROM release_groups").fetchone()[0]

    class Borrowed:
        def __getattr__(self, name):
            return getattr(conn, name)

        def close(self):
            pass

    monkeypatch.setattr(version_merge, "get_db", lambda **kw: Borrowed())
    monkeypatch.setattr(version_merge, "_refresh_version_merge_dependents", lambda *a, **k: None)
    assert version_merge.update_group_members(gid, remove_ids=[11])
    assert (10, 11) in separated_pairs(conn)
    assert (
        conn.execute("SELECT is_manual FROM release_groups WHERE group_id=?", (gid,)).fetchone()[0]
        == 1
    )
    conn.execute("INSERT INTO release_group_members VALUES(?,11)", (gid,))
    conn.commit()
    conn.execute("DELETE FROM album_release_separations")
    conn.commit()
    assert version_merge.delete_group(gid)
    assert (10, 11) in separated_pairs(conn)


def test_apply_rolls_back_catalog_redirects_and_audit_when_rebuild_fails(conn, monkeypatch):
    from backend.domains.playback import album_project_auto_merge as service

    add(conn, 10, "Old", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New", [1, 2, 3, 4, 5, 6])
    _prepare_standalone_projects(conn)
    plan = plan_album_project_auto_merges(conn)

    def fail(*args, **kwargs):
        raise RuntimeError("injected rebuild failure")

    monkeypatch.setattr(service, "rebuild_album_projects", fail)
    with pytest.raises(RuntimeError, match="injected"):
        apply_album_project_auto_merge_plan(conn, plan)
    for table in ("album_release_merge_events", "album_project_redirects", "release_groups"):
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_same_named_recordings_with_distinct_isrc_do_not_auto_merge(conn):
    add(conn, 10, "Old", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New", [1, 2, 3, 4, 5, 6])
    conn.execute(
        "UPDATE spotify_track_meta SET isrc='different-' || isrc WHERE spotify_album_id='album-11'"
    )
    _prepare_standalone_projects(conn)
    assert not plan_album_project_auto_merges(conn).candidates


def test_spotify_relinks_with_same_owner_match_without_isrc(conn):
    add(conn, 10, "Old", [1, 2, 3, 4, 5], date="2020-01-01")
    add(conn, 11, "New", [1, 2, 3, 4, 5, 6])
    conn.execute("UPDATE spotify_track_meta SET isrc=NULL")
    for i in range(5):
        # Owner rows are independent facts; the planner only reads them.
        owner = 1000 + i
        conn.execute(
            "INSERT INTO tracks(track_id,track_name,artist_id,album_id) VALUES(?, ?, 1,10)",
            (owner, f"Owner {i}"),
        )
        for aid in (10, 11):
            conn.execute(
                "INSERT INTO spotify_track_owners(spotify_track_id,track_id,evidence_type) VALUES(?,?,'import_match')",
                (f"{aid}-track-{i}", owner),
            )
    _prepare_standalone_projects(conn)
    plan = plan_album_project_auto_merges(conn)
    assert len(plan.candidates) == 1
    assert {m["evidence"] for m in plan.candidates[0].track_matches} == {"recording_owner"}
