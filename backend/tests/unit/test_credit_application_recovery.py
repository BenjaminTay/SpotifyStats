from __future__ import annotations

import pytest

from backend.domains.metadata.l2_track_auto_merge import build_l2_track_merge_plan
from backend.domains.metadata.spotify_refresh import refresh_missing_spotify_metadata
from backend.domains.metadata.spotify_track_credits import sync_automatic_spotify_credits
from backend.domains.metadata.track_credits import get_effective_track_credits
from backend.providers.base import ProviderNetworkError
from backend.tests.unit.test_l2_track_auto_merge import _connection
from backend.tests.unit.test_l2_track_auto_merge import _track as _l2_track
from backend.tests.unit.test_spotify_track_credit_evidence import _conn, _seed_track, _track

pytestmark = pytest.mark.unit


def test_cached_credits_are_applied_on_retry_after_album_network_failure():
    conn = _conn()
    conn.execute("ALTER TABLE artists ADD COLUMN spotify_artist_id TEXT")
    conn.execute("ALTER TABLE artists ADD COLUMN image_url TEXT")
    conn.execute("ALTER TABLE albums ADD COLUMN spotify_album_id TEXT")
    conn.execute("ALTER TABLE albums ADD COLUMN image_url TEXT")
    _seed_track(conn)
    conn.execute("INSERT INTO track_artists(track_id,artist_id,role) VALUES (1,1,'primary')")
    conn.execute("DELETE FROM spotify_track_meta")
    conn.commit()

    class Provider:
        fail = True
        requests = 0

        def get_tracks(self, ids, token):
            self.requests += len(ids)
            return {"tracks": [_track()]}

        def get_albums(self, ids, token):
            if self.fail:
                raise ProviderNetworkError("http", "fixture album failure")
            return {"albums": []}

        def get_artists_by_ids(self, ids, token):
            return {"artists": []}

    provider = Provider()
    with pytest.raises(ProviderNetworkError):
        refresh_missing_spotify_metadata(conn, provider, "fixture-token")
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_sets").fetchone()[0] == 1
    provider.fail = False
    result = refresh_missing_spotify_metadata(conn, provider, "fixture-token")
    assert provider.requests == 1
    assert not result.errors
    assert {r["artist_id"] for r in get_effective_track_credits(conn, [1])} == {1, 2}
    revision = conn.execute("SELECT current_revision FROM track_credit_state").fetchone()[0]
    refresh_missing_spotify_metadata(conn, provider, "fixture-token")
    assert conn.execute("SELECT current_revision FROM track_credit_state").fetchone()[0] == revision
    conn.close()


def test_l2_does_not_merge_bare_title_solo_and_effective_featured_recording():
    conn = _connection()
    _l2_track(conn, 1, "Song")
    _l2_track(conn, 2, "Song")
    conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES (2,'Guest')")
    conn.execute("INSERT INTO track_artists(track_id,artist_id,role) VALUES (2,2,'featured')")
    plan = build_l2_track_merge_plan(conn)
    assert not plan["accepted_edges"]
    assert any(e["reason"] == "participant_conflict" for e in plan["blocked_edges"])
    conn.close()


def test_l2_blocks_participant_conflict_through_a_third_recording():
    conn = _connection()
    for track_id in (1, 2, 3):
        _l2_track(conn, track_id, "Song")
    conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES (2,'Guest')")
    conn.execute("INSERT INTO track_artists(track_id,artist_id,role) VALUES (2,2,'featured')")
    plan = build_l2_track_merge_plan(conn)
    assert all(not ({1, 2} <= set(g["member_l1_ids"])) for g in plan["groups"])
    assert all(not ({2, 3} <= set(g["member_l1_ids"])) for g in plan["groups"])
    conn.close()


def test_applied_evidence_is_rechecked_after_projection_loss_and_is_idempotent():
    from backend.domains.metadata.spotify_track_credits import (
        credit_application_coverage,
        save_track_credit_evidence,
    )

    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    assert credit_application_coverage(conn)["pending"] == 1
    sync_automatic_spotify_credits(conn)
    assert credit_application_coverage(conn)["pending"] == 0
    revision = conn.execute("SELECT current_revision FROM track_credit_state").fetchone()[0]
    sync_automatic_spotify_credits(conn)
    assert conn.execute("SELECT current_revision FROM track_credit_state").fetchone()[0] == revision
    conn.execute("DELETE FROM spotify_auto_track_credits WHERE artist_id=2")
    assert credit_application_coverage(conn)["pending"] == 1
    sync_automatic_spotify_credits(conn)
    assert credit_application_coverage(conn)["pending"] == 0
    conn.close()


def test_ambiguous_application_is_visible_and_retried_after_evidence_change():
    from backend.domains.metadata.spotify_track_credits import (
        credit_application_coverage,
        save_track_credit_evidence,
    )

    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track([{"id": "wrong", "name": "Other"}]))
    assert sync_automatic_spotify_credits(conn)["skipped"] == 1
    assert credit_application_coverage(conn)["blocked"] == 1
    save_track_credit_evidence(conn, _track())
    assert credit_application_coverage(conn)["pending"] == 1
    sync_automatic_spotify_credits(conn)
    assert credit_application_coverage(conn)["blocked"] == 0
    conn.close()


def test_application_state_and_revision_rollback_together():
    import sqlite3

    from backend.domains.metadata.spotify_track_credits import save_track_credit_evidence

    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    conn.execute(
        "CREATE TRIGGER reject_application BEFORE INSERT ON spotify_credit_application_state BEGIN SELECT RAISE(ABORT,'fixture'); END"
    )
    revision = conn.execute("SELECT current_revision FROM track_credit_state").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        sync_automatic_spotify_credits(conn)
    assert conn.execute("SELECT COUNT(*) FROM spotify_auto_track_credits").fetchone()[0] == 0
    assert conn.execute("SELECT current_revision FROM track_credit_state").fetchone()[0] == revision
    conn.close()


def test_l2_split_does_not_prevent_l3_bare_title_collaboration():
    from backend.domains.metadata.l3_track_auto_merge import build_l3_track_merge_plan

    conn = _connection()
    for track_id in (1, 2):
        _l2_track(conn, track_id, "Song")
    conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES (2,'Guest')")
    conn.execute("INSERT INTO track_artists(track_id,artist_id,role) VALUES (2,2,'featured')")
    assert not build_l2_track_merge_plan(conn)["accepted_edges"]
    plan = build_l3_track_merge_plan(conn)
    assert any({1, 2} <= set(group["member_l1_ids"]) for group in plan["groups"])
    conn.close()


def test_l2_waits_for_cached_but_unapplied_participant_evidence():
    from backend.domains.metadata.spotify_track_credits import save_track_credit_evidence

    conn = _connection()
    for track_id in (1, 2):
        _l2_track(conn, track_id, "Song")
        conn.execute(
            "INSERT INTO spotify_track_owners(spotify_track_id,track_id) VALUES (?,?)",
            (f"spotify-{track_id}", track_id),
        )
    save_track_credit_evidence(conn, {**_track(), "id": "spotify-2"})
    plan = build_l2_track_merge_plan(conn)
    assert not plan["accepted_edges"]
    assert any(edge["reason"] == "participant_evidence_unapplied" for edge in plan["blocked_edges"])
    conn.close()


def test_manual_recording_exception_keeps_priority_over_participants():
    conn = _connection()
    for track_id in (1, 2):
        _l2_track(conn, track_id, "Song")
    conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES (2,'Guest')")
    conn.execute("INSERT INTO track_artists(track_id,artist_id,role) VALUES (2,2,'featured')")
    conn.execute(
        "INSERT INTO track_merge_overrides(scope,left_l1_id,right_l1_id,action,reason) VALUES ('recording',1,2,'force_merge','fixture')"
    )
    assert any(
        e["evidence_type"] == "force_merge"
        for e in build_l2_track_merge_plan(conn)["accepted_edges"]
    )
    conn.execute("UPDATE track_merge_overrides SET action='force_separate'")
    assert not build_l2_track_merge_plan(conn)["accepted_edges"]
    conn.close()


def test_application_migration_is_idempotent_without_backfilling_success():
    from backend.core.migrations import migrate_093

    conn = _conn()
    conn.execute("DROP TABLE spotify_credit_application_state")
    migrate_093(conn)
    migrate_093(conn)
    assert conn.execute("SELECT COUNT(*) FROM spotify_credit_application_state").fetchone()[0] == 0
    conn.close()


@pytest.mark.parametrize("same_credits", [True, False])
def test_multiple_owned_provider_ids_require_identical_credit_evidence(same_credits):
    from backend.domains.metadata.spotify_track_credits import save_track_credit_evidence

    conn = _conn()
    _seed_track(conn)
    conn.execute("UPDATE tracks SET spotify_track_id='legacy-unowned' WHERE track_id=1")
    conn.execute(
        "INSERT INTO spotify_track_owners(spotify_track_id,track_id) VALUES ('spotify-track-2',1)"
    )
    conn.execute(
        "INSERT INTO spotify_track_meta(spotify_track_id,track_name) VALUES ('spotify-track-2','合作歌曲')"
    )
    save_track_credit_evidence(conn, _track())
    second = _track() if same_credits else _track([{"id": "spotify-artist-1", "name": "主艺人"}])
    second["id"] = "spotify-track-2"
    save_track_credit_evidence(conn, second)
    report = sync_automatic_spotify_credits(conn)
    assert report["changed"] == int(same_credits)
    assert report["skipped"] == int(not same_credits)
    # Neither provider ownership nor raw track identity may be rewritten.
    assert (
        conn.execute("SELECT spotify_track_id FROM tracks WHERE track_id=1").fetchone()[0]
        == "legacy-unowned"
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM spotify_track_owners WHERE track_id=1").fetchone()[0]
        == 2
    )
    if same_credits:
        assert {r["artist_id"] for r in get_effective_track_credits(conn, [1])} == {1, 2}
        assert sync_automatic_spotify_credits(conn)["changed"] == 0
    conn.close()


@pytest.mark.parametrize("complete", [True, False])
def test_reviewed_track_primary_is_an_anchor_only_for_complete_provider_members(complete):
    from backend.domains.metadata.spotify_track_credits import (
        credit_application_coverage,
        save_track_credit_evidence,
    )
    from backend.domains.metadata.track_credits import (
        apply_track_credit_override,
        get_track_credit_revision,
    )

    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track([{"id": "spotify-artist-2", "name": "合作艺人"}]))
    assert sync_automatic_spotify_credits(conn)["skipped"] == 1

    def edit(artist, action, role):
        apply_track_credit_override(
            conn,
            track_id=1,
            artist_id=artist,
            action=action,
            role=role,
            evidence_type="spotify_track_review",
            evidence_source="spotify-track-1",
            reason="user reviewed this specific release",
            expected_revision=get_track_credit_revision(conn),
            idempotency_key=f"review-{artist}-{action}",
        )

    edit(2, "add", "primary")
    if complete:
        edit(1, "remove", None)
    assert credit_application_coverage(conn)["pending"] == 1
    result = sync_automatic_spotify_credits(conn)
    assert result["skipped"] == int(not complete)
    assert credit_application_coverage(conn)["blocked"] == int(not complete)
    assert conn.execute("SELECT artist_id FROM tracks WHERE track_id=1").fetchone()[0] == 1
    if complete:
        assert [(r["artist_id"], r["role"]) for r in get_effective_track_credits(conn, [1])] == [
            (2, "primary")
        ]
        assert sync_automatic_spotify_credits(conn)["changed"] == 0
        conn.execute("UPDATE track_credit_overrides SET active=0 WHERE action='remove'")
        assert credit_application_coverage(conn)["pending"] == 1
        assert sync_automatic_spotify_credits(conn)["skipped"] == 1
    conn.close()


def test_track_metadata_retains_provider_release_names_separately_from_statistics():
    from backend.domains.billboard.detail_summary import _track_meta
    from backend.domains.metadata.spotify_track_credits import save_track_credit_evidence

    conn = _conn()
    _seed_track(conn)
    conn.execute(
        "INSERT INTO track_l1_identities(l1_id,provider,fallback_track_id,representative_track_id) VALUES (1,'local',1,1)"
    )
    save_track_credit_evidence(conn, _track())
    meta = _track_meta(conn, 1)
    assert meta["release_artist_names"] == ["主艺人", "合作艺人"]
    conn.close()


@pytest.mark.parametrize("change", ["add", "remove", "unresolved"])
def test_reviewed_complete_credits_are_not_expanded_or_replaced_on_provider_change(change):
    from backend.domains.metadata.spotify_track_credits import (
        credit_application_coverage,
        save_track_credit_evidence,
    )
    from backend.domains.metadata.track_credits import apply_track_credit_override

    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    sync_automatic_spotify_credits(conn)
    # The original primary is retained, but the complete release was reviewed.
    apply_track_credit_override(
        conn,
        track_id=1,
        artist_id=2,
        action="set_role",
        role="primary",
        evidence_type="spotify_track_review",
        evidence_source="spotify-track-1",
        reason="reviewed complete release",
        expected_revision=1,
        idempotency_key="review-complete",
    )
    sync_automatic_spotify_credits(conn)
    before = [(r["artist_id"], r["role"]) for r in get_effective_track_credits(conn, [1])]
    automatic = [tuple(r) for r in conn.execute("SELECT * FROM spotify_auto_track_credits")]
    conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES (3,'Other')")
    artists = _track()["artists"]
    if change == "remove":
        artists = artists[:1]
    else:
        artists = [
            *artists,
            {"id": "spotify-artist-3", "name": "Other" if change == "add" else "New Unknown"},
        ]
    save_track_credit_evidence(conn, _track(artists))
    result = sync_automatic_spotify_credits(conn)
    assert result["skipped"] == 1
    assert result["changed"] == 0 and result["created_artists"] == 0
    assert credit_application_coverage(conn)["blocked"] == 1
    assert [tuple(r) for r in conn.execute("SELECT * FROM spotify_auto_track_credits")] == automatic
    assert [(r["artist_id"], r["role"]) for r in get_effective_track_credits(conn, [1])] == before
    conn.close()
