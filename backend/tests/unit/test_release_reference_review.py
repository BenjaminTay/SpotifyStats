"""Review scopes preserve raw facts, complete members and published song owners."""

import pytest

from backend.core.migrations import migrate_096
from backend.domains.metadata import album_release_date_evidence as dates
from backend.domains.metadata.album_release_references import (
    record_reference,
    reference_sources,
    review_reference,
)
from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver
from backend.services.release_cycle_resolution import resolve_release_targets
from backend.services.release_evidence_review import review_release_evidence
from backend.tests.unit.test_project_release_correction import conn, sources  # noqa: F401

pytestmark = pytest.mark.unit


@pytest.fixture
def c(conn):  # noqa: F811 - reuse the shared synthetic database fixture
    migrate_096(conn)
    if not conn.in_transaction:
        conn.execute("BEGIN")
    return conn


def reference():
    return {
        "project_id": 20,
        "spotify_album_id": "new",
        "relation": "album_artist",
        "date_kind": "original_release",
        "territory": "XW",
        "medium": "digital",
        "scope_note": "Only the existing project song; no ownership transfer",
        "sources": sources(),
        "tracks": [{"track_id": 1, "spotify_track_id": "new-track"}],
    }


def date_item(pid=20, day="2020-11-01"):
    return {
        "project_id": pid,
        "spotify_album_id": "new" if pid == 20 else "old",
        "release_date": day,
        "date_kind": "original_release",
        "territory": "DE",
        "medium": "original album",
        "scope_note": "Original project date, not later edition",
        "sources": sources(),
    }


def target(c):
    return resolve_release_targets(
        c, [{"project_id": 20, "album_name": "Album B", "artist_name": "Artist"}]
    )[0]


def approve(c, **kwargs):
    return review_release_evidence(
        c, actor="reviewer", reason="Explicit synthetic review", run_id="test", **kwargs
    )


def test_target_presence_does_not_relax_complete_credit_identity(c):
    c.execute("INSERT INTO spotify_album_artist_credits VALUES('new','missing','Other',1)")
    r = AlbumArtistResolver(c)
    assert r.match("new", 1) == "unresolved"
    assert r.canonical_key("new", "Artist,Other") is None
    assert r.target_presence("new", 1) == "verified_id"
    assert target(c).reason is None
    assert r.target_presence("new", 999) == "unresolved_target"


def test_ambiguous_target_id_still_rejected(c):
    c.execute(
        "INSERT INTO artists(artist_id,artist_name,spotify_artist_id) VALUES(99999,'Other','artist')"
    )
    assert AlbumArtistResolver(c).target_presence("new", 1) == "ambiguous"
    assert target(c).reason == "artist_identity_unconfirmed"


def test_shared_reference_keeps_unique_source_binding_and_members(c):
    c.execute(
        "INSERT INTO album_project_external_ids(provider,external_album_id,project_id,evidence_type,confidence,is_primary) VALUES('spotify','new',10,'fixture',1,0)"
    )
    old_members = c.execute("SELECT * FROM album_project_tracks").fetchall()
    rid = record_reference(c, reference(), actor="r", reason="Explicit bounded reference")
    assert reference_sources(c, 20, 200) is None
    assert approve(c, references=[(rid, "approve")])["owner_changes"] == 0
    assert target(c).reason is None
    assert target(c).source_album_id == "new"
    assert (
        c.execute(
            "SELECT project_id FROM album_project_external_ids WHERE external_album_id='new'"
        ).fetchone()[0]
        == 10
    )
    assert c.execute("SELECT * FROM album_project_tracks").fetchall() == old_members
    assert approve(c, references=[(rid, "approve")])["changed"] == 0
    assert approve(c, references=[(rid, "revoke")])["changed"] == 1
    assert reference_sources(c, 20, 200) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("tracks", []),
        ("tracks", [{"track_id": 99, "spotify_track_id": "new-track"}]),
        ("tracks", [{"track_id": 1, "spotify_track_id": "old-track"}]),
        ("relation", "title_match"),
        ("date_kind", "edition_release"),
    ],
)
def test_reference_rejects_unproven_scope(c, field, value):
    item = reference()
    item[field] = value
    with pytest.raises(ValueError):
        record_reference(c, item, actor="r", reason="test")


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE spotify_album_meta SET total_tracks=2 WHERE spotify_album_id='new'",
        "UPDATE album_project_tracks SET membership_role='bonus' WHERE project_id=20",
        "UPDATE spotify_track_owners SET track_id=999 WHERE spotify_track_id='new-track'",
        "UPDATE artists SET spotify_artist_id=NULL WHERE artist_id=1",
        "UPDATE l3_song_album_attributions SET origin_release_project_id=10",
    ],
)
def test_reference_drift_invalidates_pending_and_active_reviews(c, sql):
    rid = record_reference(c, reference(), actor="r", reason="test")
    c.execute("SAVEPOINT drift")
    c.execute(sql)
    with pytest.raises(ValueError):
        review_reference(c, rid, "approve", actor="r", reason="test")
    c.execute("ROLLBACK TO drift")
    c.execute("RELEASE drift")
    approve(c, references=[(rid, "approve")])
    c.execute(sql)
    assert reference_sources(c, 20, 200)[0]["reference_verified"] is False
    assert target(c).reason == "release_source_unconfirmed"
    # Stale observations can always be withdrawn.
    assert review_reference(c, rid, "revoke", actor="r", reason="stale")


def test_ordinary_date_conflict_rejected_explicit_review_overlays_without_raw_write(c):
    aid = dates.record_assertion(c, date_item(), actor="r", run_id="test")
    with pytest.raises(ValueError, match="conflicts_with_source"):
        dates.review_assertion(c, aid, "approve", actor="r", reason="test", run_id="test")
    proposal = dates.prepare_date_conflict(c, aid)
    raw = tuple(
        c.execute(
            "SELECT release_date,release_date_precision FROM spotify_album_meta WHERE spotify_album_id='new'"
        ).fetchone()
    )
    assert approve(c, date_conflicts=[proposal])["changed"] == 1
    assert (target(c).reason, target(c).release_date) == (None, "2020-11-01")
    assert (
        tuple(
            c.execute(
                "SELECT release_date,release_date_precision FROM spotify_album_meta WHERE spotify_album_id='new'"
            ).fetchone()
        )
        == raw
    )
    assert approve(c, date_conflicts=[proposal])["changed"] == 0
    # Explicit member edition retains its provider date.
    from backend.domains.metadata.release_dates import release_anchor_sources

    assert (
        release_anchor_sources(c, 200, project_id=20, explicit_edition=True)[0]["release_date"]
        == raw[0]
    )
    dates.review_assertion(c, aid, "revoke", actor="r", reason="withdraw", run_id="test")
    assert target(c).release_date == raw[0]


def test_stale_conflict_proposal_and_active_catalog_change_fail_closed(c):
    aid = dates.record_assertion(c, date_item(), actor="r", run_id="test")
    proposal = dates.prepare_date_conflict(c, aid)
    c.execute(
        "UPDATE spotify_album_meta SET track_list='[\"changed\"]' WHERE spotify_album_id='new'"
    )
    with pytest.raises(ValueError, match="stale_date_conflict"):
        approve(c, date_conflicts=[proposal])
    assert c.execute("SELECT count(*) FROM album_release_date_conflict_reviews").fetchone()[0] == 0
    c.execute(
        "UPDATE spotify_album_meta SET track_list='[\"new-track\"]' WHERE spotify_album_id='new'"
    )
    approve(c, date_conflicts=[proposal])
    c.execute(
        "UPDATE spotify_album_meta SET release_date='2020-12-01' WHERE spotify_album_id='new'"
    )
    assert target(c).reason == "release_date_conflict"


def test_batch_rollback_when_date_would_move_owner(c):
    rid = record_reference(c, reference(), actor="r", reason="test")
    aid = dates.record_assertion(c, date_item(10, "2015-01-09"), actor="r", run_id="test")
    proposal = dates.prepare_date_conflict(c, aid)
    before = [tuple(r) for r in c.execute("SELECT * FROM album_projects ORDER BY project_id")]
    with pytest.raises(ValueError, match="unapproved_attribution_change"):
        approve(c, references=[(rid, "approve")], date_conflicts=[proposal])
    assert [
        tuple(r) for r in c.execute("SELECT * FROM album_projects ORDER BY project_id")
    ] == before
    assert (
        c.execute(
            "SELECT status FROM album_release_references WHERE reference_id=?", (rid,)
        ).fetchone()[0]
        == "pending"
    )
    assert c.execute("SELECT count(*) FROM album_release_date_conflict_reviews").fetchone()[0] == 0


def test_migration_idempotent(c):
    migrate_096(c)
    assert c.execute("SELECT count(*) FROM album_release_references").fetchone()[0] == 0


def test_reviewed_track_artist_reference_supports_date_review_without_artist_merge(c):
    c.execute(
        "UPDATE spotify_album_artist_credits SET spotify_artist_id='ensemble' WHERE spotify_album_id='new'"
    )
    item = reference()
    item["relation"] = "track_artist"
    rid = record_reference(c, item, actor="r", reason="Explicit existing track participation")
    approve(c, references=[(rid, "approve")])
    assert AlbumArtistResolver(c).target_presence("new", 1) != "verified_id"
    assert target(c).reason is None
    aid = dates.record_assertion(c, date_item(), actor="r", run_id="test")
    approve(c, date_conflicts=[dates.prepare_date_conflict(c, aid)])
    assert target(c).release_date == "2020-11-01"


def test_source_correction_cannot_publish_a_date_its_reader_would_reject(c):
    from backend.services.project_release_correction import prepare_release_correction
    from backend.tests.unit.test_project_release_correction import request

    item = request()
    item["release_date"] = "2016-01-09"
    with pytest.raises(ValueError, match="source_date_conflict_requires_explicit_date_review"):
        prepare_release_correction(c, item)
