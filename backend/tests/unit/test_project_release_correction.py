"""Edition evidence and owner-preserving maintenance; synthetic music facts."""

import copy
import json

import pytest

from backend.core.migrations import migrate_094, migrate_095
from backend.domains.metadata.album_track_release_evidence import record_assertion, review_assertion
from backend.domains.playback.l3_album_attribution import (
    apply_l3_album_attribution_plan,
    l3_album_attribution_dependencies_ready,
    plan_l3_album_attributions,
)
from backend.services.project_release_correction import (
    apply_release_correction,
    prepare_release_correction,
)
from backend.tests.unit.test_l3_album_attribution import _connection, _project, _track

pytestmark = pytest.mark.unit


@pytest.fixture
def conn():
    c = _connection()
    migrate_094(c)
    migrate_095(c)
    c.execute("ALTER TABLE artists ADD COLUMN spotify_artist_id TEXT")
    c.execute(
        "CREATE TABLE album_project_revision_state(state_id INTEGER PRIMARY KEY,current_revision INTEGER,updated_at TEXT)"
    )
    c.execute('INSERT INTO album_project_revision_state VALUES(1,0,"now")')
    c.execute("UPDATE artists SET spotify_artist_id='artist' WHERE artist_id=1")
    _project(
        c,
        project_id=10,
        album_id=100,
        name="Album A",
        source_bucket="original_album",
        release_date="2025-03-28",
    )
    _project(
        c,
        project_id=20,
        album_id=200,
        name="Album B",
        source_bucket="original_album",
        release_date="2020-10-30",
    )
    _track(c, track_id=1, album_id=100, project_id=10, name="Shared Song")
    c.execute(
        "INSERT INTO album_project_tracks(project_id,track_id,membership_role,min_merge_level,source_album_id) VALUES(20,1,'standard',2,200)"
    )
    for sid, name, day, tid, album in (
        ("old", "Album A", "2015-01-09", "old-track", 100),
        ("new", "Album B", "2020-10-30", "new-track", 200),
    ):
        c.execute(
            "INSERT INTO spotify_album_meta(spotify_album_id,album_name,album_type,release_date,release_date_precision,total_tracks,track_list) VALUES(?,?,'album',?,'day',1,?)",
            (sid, name, day, json.dumps([tid])),
        )
        c.execute(
            "INSERT INTO spotify_track_owners(spotify_track_id,track_id,evidence_type) VALUES(?,1,'import_match')",
            (tid,),
        )
        c.execute(
            "INSERT INTO spotify_album_credit_sets(spotify_album_id,artist_count,credit_signature,fetched_at,source) VALUES(?,1,'fixture','now','fixture')",
            (sid,),
        )
        c.execute(
            "INSERT INTO spotify_album_artist_credits(spotify_album_id,spotify_artist_id,credited_name,credit_order) VALUES(?,'artist','Artist',0)",
            (sid,),
        )
        c.execute(
            "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(?,?,'fixture',1)",
            (album, sid),
        )
    apply_l3_album_attribution_plan(c)
    yield c
    c.close()


def sources():
    return [
        {
            "url": "https://label.example/catalog",
            "title": "Synthetic release",
            "source_kind": "label_catalog",
            "claim": "Explicit edition/track evidence",
            "observed_at": "2026-10-23",
        }
    ]


def request():
    return {
        "request_id": "synthetic-correction",
        "project_id": 10,
        "source_id": "old",
        "release_date": "2015-01-09",
        "date_kind": "original_release",
        "territory": "XW",
        "medium": "digital",
        "scope_note": "Synthetic original date; no claim about later bonus tracks",
        "sources": sources(),
        "preserve_track_ids": [1],
        "assertion_ids": [],
    }


def bind(c, pid, sid):
    c.execute(
        "INSERT INTO album_project_external_ids(provider,external_album_id,project_id,evidence_type,confidence,is_primary) VALUES('spotify',?,?,'fixture',1,1)",
        (sid, pid),
    )


def fact(c, pid, kind, day):
    sid = "old" if pid == 10 else "new"
    aid = record_assertion(
        c,
        {
            "project_id": pid,
            "anchor_track_id": 1,
            "spotify_album_id": sid,
            "spotify_track_id": sid + "-track",
            "membership_kind": kind,
            "included_on": day,
            "date_kind": "edition_release",
            "territory": "XW",
            "medium": "digital",
            "sources": sources(),
        },
        actor="reviewer",
        reason="explicit synthetic evidence",
    )
    review_assertion(c, aid, "approve", actor="reviewer", reason="approve synthetic evidence")
    return aid


def owner(c):
    return c.execute(
        "SELECT target_project_id FROM l3_song_album_attributions WHERE canonical_song_key='l1:1'"
    ).fetchone()[0]


def test_date_correction_preserves_owner_and_is_idempotent(conn):
    original_members = conn.execute("SELECT * FROM album_project_tracks").fetchall()
    original_provider = conn.execute("SELECT * FROM spotify_album_meta").fetchall()
    proposal = prepare_release_correction(conn, request())
    with conn:
        conn.execute("BEGIN")
        result = apply_release_correction(
            conn, proposal, actor="reviewer", reason="retain published home"
        )
    assert result["owner_changes"] == 0 and owner(conn) == 20
    assert (
        conn.execute("SELECT decision_source FROM l3_song_album_attributions").fetchone()[0]
        == "manual"
    )
    assert tuple(
        conn.execute(
            "SELECT release_date,release_date_precision FROM album_projects WHERE project_id=10"
        ).fetchone()
    ) == ("2015-01-09", "day")
    assert conn.execute("SELECT * FROM album_project_tracks").fetchall() == original_members
    assert conn.execute("SELECT * FROM spotify_album_meta").fetchall() == original_provider
    assert l3_album_attribution_dependencies_ready(conn)
    revision = conn.execute("SELECT current_revision FROM album_project_revision_state").fetchone()[
        0
    ]
    with conn:
        conn.execute("BEGIN")
        assert apply_release_correction(conn, proposal, actor="reviewer", reason="repeat")[
            "idempotent"
        ]
    assert (
        conn.execute("SELECT current_revision FROM album_project_revision_state").fetchone()[0]
        == revision
    )
    apply_l3_album_attribution_plan(conn)
    assert owner(conn) == 20  # A subsequent full maintenance keeps the explicit decision.


def test_missing_owner_preservation_rolls_back_source_date_and_projection(conn):
    req = request()
    req["preserve_track_ids"] = []
    proposal = prepare_release_correction(conn, req)
    with conn:
        conn.execute("BEGIN")
        with pytest.raises(ValueError, match="unapproved_attribution_change"):
            apply_release_correction(
                conn, proposal, actor="reviewer", reason="no migration approved"
            )
        assert (
            conn.execute("SELECT release_date FROM album_projects WHERE project_id=10").fetchone()[
                0
            ]
            == "2025-03-28"
        )
        assert not conn.execute("SELECT 1 FROM album_project_external_ids").fetchone()
        assert not conn.execute("SELECT 1 FROM album_release_corrections").fetchone()
        assert owner(conn) == 20 and l3_album_attribution_dependencies_ready(conn)


@pytest.mark.parametrize("change", ["date", "catalog", "member"])
def test_proposal_refuses_baseline_drift(conn, change):
    proposal = prepare_release_correction(conn, request())
    if change == "date":
        conn.execute("UPDATE album_projects SET release_date='2024-01-01' WHERE project_id=10")
    elif change == "catalog":
        conn.execute(
            "UPDATE spotify_album_meta SET track_list='[\"different\"]' WHERE spotify_album_id='old'"
        )
    else:
        conn.execute("UPDATE album_project_tracks SET inferred=1 WHERE project_id=10")
    with pytest.raises(ValueError):
        apply_release_correction(conn, proposal, actor="reviewer", reason="stale input")
    assert not conn.execute("SELECT 1 FROM album_release_corrections").fetchone()


def test_scoped_publication_does_not_adopt_unrelated_planner_drift(conn):
    for pid, aid, day in ((30, 300, "2018-01-01"), (40, 400, "2020-01-01")):
        _project(
            conn,
            project_id=pid,
            album_id=aid,
            name="Unrelated " + str(pid),
            source_bucket="original_album",
            release_date=day,
        )
    _track(conn, track_id=2, album_id=300, project_id=30, name="Other Song")
    conn.execute(
        "INSERT INTO album_project_tracks(project_id,track_id,membership_role,min_merge_level,source_album_id) VALUES(40,2,'standard',2,400)"
    )
    apply_l3_album_attribution_plan(conn)
    # A pre-existing drift, deliberately outside the requested correction.
    conn.execute("UPDATE album_projects SET release_date='2010-01-01' WHERE project_id=40")
    conn.commit()
    prior = dict(
        conn.execute(
            "SELECT * FROM l3_song_album_attributions WHERE canonical_song_key='l1:2'"
        ).fetchone()
    )
    proposal = prepare_release_correction(conn, request())
    with conn:
        conn.execute("BEGIN")
        apply_release_correction(
            conn, proposal, actor="reviewer", reason="preserve every published owner"
        )
    after = dict(
        conn.execute(
            "SELECT * FROM l3_song_album_attributions WHERE canonical_song_key='l1:2'"
        ).fetchone()
    )
    assert {k: v for k, v in prior.items() if k != "album_project_revision"} == {
        k: v for k, v in after.items() if k != "album_project_revision"
    }
    assert owner(conn) == 20 and l3_album_attribution_dependencies_ready(conn)


def test_reviewed_bonus_does_not_inherit_early_project_date(conn):
    conn.execute("BEGIN")
    bind(conn, 10, "old")
    bind(conn, 20, "new")
    fact(conn, 10, "bonus", None)
    fact(conn, 20, "original", "2020-10-30")
    conn.execute("UPDATE album_projects SET release_date='1900-01-01' WHERE project_id=10")
    plan = plan_l3_album_attributions(conn)
    assert not plan.issues and plan.decisions[0].target_project_id == 20
    assert "reviewed_source_membership" in plan.decisions[0].evidence_codes
    assert (
        conn.execute(
            "SELECT membership_role FROM album_project_tracks WHERE project_id=10"
        ).fetchone()[0]
        == "standard"
    )


def test_equivalent_reviewed_sources_use_actual_inclusion_day(conn):
    conn.execute("BEGIN")
    bind(conn, 10, "old")
    bind(conn, 20, "new")
    fact(conn, 10, "original", "2015-01-09")
    fact(conn, 20, "original", "2020-10-30")
    assert plan_l3_album_attributions(conn).decisions[0].target_project_id == 10


@pytest.mark.parametrize(
    "case", ["unknown_day", "unreviewed_peer", "different_territory", "stale_source"]
)
def test_noncomparable_memberships_require_review(conn, case):
    conn.execute("BEGIN")
    bind(conn, 10, "old")
    bind(conn, 20, "new")
    fact(conn, 10, "original", None if case == "unknown_day" else "2015-01-09")
    if case != "unreviewed_peer":
        aid = fact(conn, 20, "original", "2020-10-30")
        if case == "different_territory":
            conn.execute(
                "UPDATE album_track_release_assertions SET territory='JP' WHERE assertion_id=?",
                (aid,),
            )
    if case == "stale_source":
        conn.execute(
            "UPDATE spotify_album_meta SET track_list='[\"replaced\"]' WHERE spotify_album_id='old'"
        )
    plan = plan_l3_album_attributions(conn)
    assert not plan.decisions and plan.conflict_song_keys == ("l1:1",)
    assert plan.issues[0].evidence_codes == ("source_membership_not_comparable",)


def test_source_ownership_and_existing_manual_decision_are_not_overwritten(conn):
    proposal = prepare_release_correction(conn, request())
    bind(conn, 20, "old")
    conn.commit()
    proposal = prepare_release_correction(conn, request())
    with conn:
        conn.execute("BEGIN")
        with pytest.raises(ValueError, match="source_owned_by_another_project"):
            apply_release_correction(conn, proposal, actor="reviewer", reason="cannot steal source")
    assert conn.execute("SELECT project_id FROM album_project_external_ids").fetchone()[0] == 20


def test_reusing_request_id_with_different_proposal_is_rejected(conn):
    proposal = prepare_release_correction(conn, request())
    with conn:
        conn.execute("BEGIN")
        apply_release_correction(conn, proposal, actor="reviewer", reason="preserve owner")
    changed = copy.deepcopy(proposal)
    changed["request"]["release_date"] = "2015-01-13"
    with conn, pytest.raises(ValueError, match="request_id_reused"):
        conn.execute("BEGIN")
        apply_release_correction(conn, changed, actor="reviewer", reason="different request")


def test_cli_preview_does_not_change_source_and_apply_refuses_its_alias(
    conn, tmp_path, monkeypatch
):
    import sqlite3

    from backend.core import db
    from scripts.correct_project_release import main

    path = tmp_path / "configured.db"
    writer = sqlite3.connect(path)
    conn.backup(writer)
    writer.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    manifest = tmp_path / "request.json"
    manifest.write_text(json.dumps(request()))
    output = tmp_path / "preview.json"
    main(
        [
            "--db-path",
            str(path),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
            "--actor",
            "reviewer",
            "--reason",
            "preview only",
        ]
    )
    evidence = json.loads(output.read_text())
    assert evidence["status"] == "preview_passed" and evidence["result"]["owner_changes"] == 0
    source = sqlite3.connect(path)
    assert (
        source.execute("SELECT release_date FROM album_projects WHERE project_id=10").fetchone()[0]
        == "2025-03-28"
    )
    assert not source.execute("SELECT 1 FROM album_release_corrections").fetchone()
    source.close()
    alias = tmp_path / "alias.db"
    alias.symlink_to(path)
    with pytest.raises(SystemExit):
        main(
            [
                "--db-path",
                str(alias),
                "--mode",
                "apply",
                "--manifest",
                str(output),
                "--output",
                str(tmp_path / "apply.json"),
                "--actor",
                "reviewer",
                "--reason",
                "forbidden source",
            ]
        )


def test_date_anchor_never_selects_anniversary_by_catalog_size(conn):
    from backend.domains.playback.album_projects import _best_spotify_album_for_local_album

    conn.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,album_name,album_type,release_date,release_date_precision,total_tracks) VALUES('anniversary','Album A (10th Anniversary Edition)','album','2025-03-28','day',28)"
    )
    conn.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(100,'anniversary','fixture',1)"
    )
    assert _best_spotify_album_for_local_album(conn, 100)["spotify_album_id"] == "anniversary"
    assert (
        _best_spotify_album_for_local_album(conn, 100, for_release_date=True)["spotify_album_id"]
        == "old"
    )


def test_existing_manual_decision_is_not_replaced(conn):
    conn.execute(
        "INSERT INTO l3_song_album_attribution_overrides(anchor_track_id,target_project_id,action,reason) VALUES(1,10,'force_target','prior explicit decision')"
    )
    conn.commit()
    proposal = prepare_release_correction(conn, request())
    with conn:
        conn.execute("BEGIN")
        with pytest.raises(ValueError, match="existing_manual_owner_conflicts"):
            apply_release_correction(
                conn, proposal, actor="reviewer", reason="must preserve old decision"
            )
    assert (
        conn.execute(
            "SELECT target_project_id FROM l3_song_album_attribution_overrides WHERE active=1"
        ).fetchone()[0]
        == 10
    )


def test_release_date_fallback_uses_reviewed_day_without_rewriting_provider(conn, monkeypatch):
    from backend.domains.metadata import release_dates
    from backend.domains.playback.album_projects import _best_spotify_album_for_local_album

    monkeypatch.setattr(
        release_dates,
        "release_anchor_sources",
        lambda *args, **kwargs: [
            {
                "spotify_album_id": "old",
                "release_date": "2015-01-13",
                "release_date_precision": "day",
            }
        ],
    )
    selected = _best_spotify_album_for_local_album(conn, 100, for_release_date=True)
    assert selected["release_date"] == "2015-01-13"
    assert (
        conn.execute(
            "SELECT release_date FROM spotify_album_meta WHERE spotify_album_id='old'"
        ).fetchone()[0]
        == "2015-01-09"
    )


@pytest.mark.parametrize(
    "bucket,kind,relation",
    [
        ("original_album", "compilation", None),
        ("rerecord", "album", None),
        ("live_acoustic_remix", "album", "live"),
        ("single", "single", None),
    ],
)
def test_original_membership_does_not_promote_non_native_release(bucket, kind, relation):
    import pandas as pd

    from backend.domains.playback.l3_album_attribution import (
        _ProjectCandidate,
        _qualify_source_candidate,
    )

    candidate = _ProjectCandidate(
        project_id=10,
        canonical_name="Synthetic",
        canonical_artist_id=1,
        release_date="2020-01-01",
        project_type=kind,
        is_manual=False,
        relation_tag=relation,
        source_buckets=(bucket,),
        membership_roles=("standard",),
        track_relation_tags=(),
        has_original_recording=True,
        target_project_id=10,
        target_project_name="Synthetic",
    )
    evidence = {
        "assertion_id": 1,
        "spotify_album_id": "old",
        "spotify_track_id": "old-track",
        "membership_kind": "original",
        "included_on": "2015-01-09",
        "date_kind": "edition_release",
        "territory": "XW",
        "medium": "digital",
        "valid": True,
    }
    result = _qualify_source_candidate(
        candidate, pd.DataFrame({"track_id": [1]}), {(10, 1): [evidence]}
    )
    assert result.source_buckets == (bucket,)


def test_stale_evidence_is_not_hidden_by_manual_preservation(conn):
    conn.execute("BEGIN")
    bind(conn, 10, "old")
    fact(conn, 10, "bonus", None)
    conn.execute(
        "INSERT INTO l3_song_album_attribution_overrides(anchor_track_id,target_project_id,action,reason) VALUES(1,20,'force_target','preserve')"
    )
    conn.execute(
        "UPDATE spotify_album_meta SET track_list='[\"replaced\"]' WHERE spotify_album_id='old'"
    )
    plan = plan_l3_album_attributions(conn)
    assert not plan.decisions and plan.conflict_song_keys == ("l1:1",)


def test_correction_does_not_silently_replace_an_approved_original_date(conn):
    from backend.domains.metadata import album_release_date_evidence as dates

    conn.execute("BEGIN")
    bind(conn, 10, "old")
    conn.execute(
        "UPDATE spotify_album_meta SET release_date='2025-03-28' WHERE spotify_album_id='old'"
    )
    aid = dates.record_assertion(
        conn,
        {
            "project_id": 10,
            "spotify_album_id": "old",
            "release_date": "2025-03-28",
            "date_kind": "original_release",
            "territory": "XW",
            "medium": "digital",
            "scope_note": "Existing independently approved date",
            "sources": sources(),
        },
        actor="reviewer",
        run_id="existing-date",
    )
    dates.review_assertion(
        conn, aid, "approve", actor="reviewer", reason="existing approval", run_id="existing-date"
    )
    apply_l3_album_attribution_plan(conn)
    conn.commit()
    with pytest.raises(ValueError, match="approved_original_date_requires_separate_review"):
        prepare_release_correction(conn, request())
    assert (
        conn.execute(
            "SELECT status FROM album_release_date_assertions WHERE assertion_id=?", (aid,)
        ).fetchone()[0]
        == "approved"
    )
