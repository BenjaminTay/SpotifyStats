"""Combined write contracts and actual read consumers for Album evidence."""

from __future__ import annotations

import sqlite3

import pytest

from backend.domains.metadata.album_tracklist import release_position_evidence
from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver
from backend.domains.metadata.spotify_refresh import upsert_album_batch
from backend.tests.unit import test_spotify_album_credit_evidence as credit_tests
from backend.tests.unit.test_album_track_pagination import Provider
from backend.tests.unit.test_spotify_album_credit_evidence import (
    artists,
    connect,
    snapshot,
)

database = credit_tests.database

pytestmark = pytest.mark.unit


def observation(provider, name="Earth, Wind & Fire", sid="id-a"):
    obj = provider.album()
    obj["artists"] = [{"id": sid, "name": name}, {"id": "id-b", "name": "Other"}]
    return obj


def facts(conn):
    return (
        tuple(
            tuple(r)
            for r in conn.execute(
                "SELECT spotify_artist_id,credited_name,credit_order FROM spotify_album_artist_credits WHERE spotify_album_id='album' ORDER BY credit_order"
            )
        ),
        tuple(
            conn.execute(
                "SELECT track_list,total_tracks FROM spotify_album_meta WHERE spotify_album_id='album'"
            ).fetchone()
        ),
        conn.execute(
            "SELECT tracks_json,validated_total FROM spotify_album_tracklist_evidence WHERE spotify_album_id='album'"
        ).fetchone(),
    )


def test_independent_provider_evidence_and_atomic_database_failure(database):
    c = connect(database)
    artists(c)
    protected = snapshot(c)
    p = Provider(106)
    upsert_album_batch(
        c, [observation(p)], provider=p, access_token="token", source_run_id="joint-1"
    )
    assert release_position_evidence(c, "album").status == "complete"
    assert AlbumArtistResolver(c).match("album", 10000) == "verified_id"
    assert (
        c.execute(
            "SELECT source_run_id FROM spotify_album_credit_sets WHERE spotify_album_id='album'"
        ).fetchone()[0]
        == "joint-1"
    )
    initial = facts(c)

    # Artist conflict retains IDs/names while a valid new directory can publish.
    q = Provider(107)
    upsert_album_batch(c, [observation(q, sid="id-c")], provider=q, access_token="token")
    assert facts(c)[0] == initial[0]
    assert (
        c.execute(
            "SELECT total_tracks FROM spotify_album_meta WHERE spotify_album_id='album'"
        ).fetchone()[0]
        == 107
    )
    assert release_position_evidence(c, "album").status == "complete"
    assert (
        c.execute(
            "SELECT event_type FROM spotify_album_credit_events ORDER BY event_id DESC LIMIT 1"
        ).fetchone()[0]
        == "rejected"
    )

    # Page failure retains list/positions, but same-ID renamed artist is reliable.
    failed = Provider(108, mutate=lambda page, _: None)
    outcomes = []
    previous_directory = tuple(facts(c)[1:])
    upsert_album_batch(
        c,
        [observation(failed, name="Renamed, Artist")],
        provider=failed,
        access_token="token",
        outcomes=outcomes,
    )
    assert outcomes[0][1] == "incomplete"
    assert tuple(facts(c)[1:]) == previous_directory
    assert AlbumArtistResolver(c).read("album")[0]["credited_name"] == "Renamed, Artist"
    assert release_position_evidence(c, "album").status == "complete"

    # An actual SQL error rolls back both classes of evidence and the audit.
    c.execute(
        "CREATE TRIGGER reject_release_write BEFORE UPDATE ON spotify_album_tracklist_evidence BEGIN SELECT RAISE(ABORT,'test database failure'); END"
    )
    c.commit()
    before = facts(c)
    events = c.execute("SELECT count(*) FROM spotify_album_credit_events").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        upsert_album_batch(c, [observation(p, name="Next Name")], provider=p, access_token="token")
    assert facts(c) == before
    assert c.execute("SELECT count(*) FROM spotify_album_credit_events").fetchone()[0] == events
    assert snapshot(c) == protected
    c.close()


def test_comparison_uses_track_credits_and_release_positions_readonly(database, monkeypatch):
    from backend.core import version_merge

    c = connect(database)
    artists(c)
    p = Provider(61)
    obj = observation(p)
    upsert_album_batch(c, [obj], provider=p, access_token="token")
    c.execute("INSERT INTO albums(album_id,album_name,artist_id) VALUES(10000,'Album',10000)")
    c.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(10000,'album','play',1)"
    )
    c.execute(
        "INSERT INTO spotify_track_credit_sets(spotify_track_id,artist_count,credit_signature,fetched_at) VALUES('t0',1,'fixture','2026-10-03')"
    )
    c.execute(
        "INSERT INTO spotify_track_artist_credits(spotify_track_id,spotify_artist_id,credited_name,credit_order,observed_at) VALUES('t0','track-only','Track Artist',0,'2026-10-03')"
    )
    c.execute(
        "UPDATE spotify_track_meta SET disc_number=9,track_number=99 WHERE spotify_track_id='t0'"
    )
    c.commit()
    monkeypatch.setattr(version_merge, "get_db", lambda **_: connect(database))
    monkeypatch.setattr(
        version_merge, "_fetch_album_tracks_from_api", lambda _: pytest.fail("GET must not fetch")
    )
    lookup = version_merge._lookup_track_names(c, {"t0", "t60"})
    assert lookup["t0"] == ("Track 0", "Track Artist")
    result = version_merge.get_album_track_comparison(10000, 10000)
    assert result["shared"][0] == ("Track 0", "Track Artist", 1, 1)
    assert result["shared"][-1] == ("Track 60", "", 2, 1)
    assert result["position_incomplete_album_ids"] == []
    c.execute("DELETE FROM spotify_album_tracklist_evidence WHERE spotify_album_id='album'")
    c.commit()
    result = version_merge.get_album_track_comparison(10000, 10000)
    assert len(result["shared"]) == 61
    assert result["position_incomplete_album_ids"] == [10000]
    assert all(row[2:] == (None, None) for row in result["shared"])
    c.close()
