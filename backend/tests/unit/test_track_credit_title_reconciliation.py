from __future__ import annotations

import sqlite3

import pytest

from backend.domains.metadata.track_credits import get_effective_track_credits


@pytest.fixture
def conn():
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.executescript("""
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY, artist_name TEXT);
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, track_name TEXT, artist_id INTEGER);
        CREATE TABLE track_artists(track_id INTEGER, artist_id INTEGER, role TEXT);
        CREATE TABLE spotify_auto_track_credits(track_id INTEGER, artist_id INTEGER,
          spotify_track_id TEXT, spotify_artist_id TEXT, credited_name TEXT, credit_order INTEGER);
        CREATE TABLE artist_identity_aliases(alias_artist_id INTEGER, canonical_artist_id INTEGER);
        INSERT INTO artists VALUES (1, 'Main'), (2, 'Joy Williams'), (3, 'John Paul White'),
          (4, 'Joy Williams and John Paul White'), (5, 'Earth, Wind & Fire'),
          (6, 'Earth'), (7, 'Wind'), (8, 'Fire'), (9, 'Joy Alias'), (10, 'Unlisted');
        INSERT INTO artist_identity_aliases VALUES (9,2);
        INSERT INTO tracks VALUES (1,'Song (feat. Joy Williams and John Paul White)',1),
          (2,'Song (feat. Earth, Wind & Fire)',1), (3,'Song (with Unlisted)',1);
        INSERT INTO track_artists VALUES (1,1,'primary'),(1,4,'featured'),
          (2,1,'primary'),(2,6,'featured'),(2,7,'featured'),(2,8,'featured'),
          (3,1,'primary'),(3,10,'featured');
        INSERT INTO spotify_auto_track_credits VALUES
          (1,1,'t1','a1','Main',0),(1,2,'t1','a2','Joy Williams',1),
          (1,3,'t1','a3','John Paul White',2),
          (2,1,'t2','a1','Main',0),(2,5,'t2','a5','Earth, Wind & Fire',1),
          (3,1,'t3','a1','Main',0);
    """)
    yield database
    database.close()


def ids(conn, track=1, proposed=None):
    return [
        row["artist_id"] for row in get_effective_track_credits(conn, [track], proposed=proposed)
    ]


def test_complete_multiple_names_replace_legacy_composite_without_raw_write(conn):
    before = list(conn.execute("SELECT * FROM track_artists"))
    assert ids(conn) == [1, 2, 3]
    assert list(conn.execute("SELECT * FROM track_artists")) == before


def test_complete_band_replaces_wrong_fragments_even_with_existing_entities(conn):
    assert ids(conn, 2) == [1, 5]


def test_unlisted_collaborator_and_unknown_partial_remain(conn):
    assert ids(conn, 3) == [1, 10]
    conn.execute(
        "UPDATE tracks SET track_name='Song (feat. Joy Williams and Unknown)' WHERE track_id=1"
    )
    assert ids(conn) == [1, 2, 3, 4]


def test_approved_complete_name_vs_multiple_names_is_ambiguous(conn):
    conn.execute(
        "INSERT INTO spotify_auto_track_credits VALUES(1,4,'t1','a4','Joy Williams and John Paul White',3)"
    )
    assert ids(conn) == [1, 2, 3, 4]


def test_no_title_provenance_no_removal_and_primary_is_protected(conn):
    conn.execute("UPDATE tracks SET track_name='Song' WHERE track_id=1")
    assert ids(conn) == [1, 2, 3, 4]
    conn.execute(
        "UPDATE tracks SET track_name='Song (feat. Joy Williams and John Paul White)' WHERE track_id=1"
    )
    conn.execute("UPDATE track_artists SET role='primary' WHERE artist_id=4")
    assert ids(conn) == [1, 4, 2, 3]


def test_manual_readd_restore_composite_and_role_edit(conn):
    assert ids(
        conn, proposed={"track_id": 1, "artist_id": 4, "action": "add", "role": "featured"}
    ) == [1, 2, 3, 4]
    rows = get_effective_track_credits(
        conn, [1], proposed={"track_id": 1, "artist_id": 2, "action": "set_role", "role": "primary"}
    )
    assert [(r["artist_id"], r["role"]) for r in rows] == [
        (1, "primary"),
        (2, "primary"),
        (3, "featured"),
    ]


def test_manual_remove_canonical_identity_cannot_revive_through_alias(conn):
    conn.execute("INSERT INTO track_artists VALUES(1,9,'featured')")
    assert ids(conn) == [1, 2, 3]
    assert ids(
        conn, proposed={"track_id": 1, "artist_id": 2, "action": "remove", "role": None}
    ) == [1, 3]
    assert ids(
        conn, proposed={"track_id": 1, "artist_id": 9, "action": "remove", "role": None}
    ) == [1, 3]


def test_other_recording_does_not_inherit_suppression(conn):
    conn.execute("INSERT INTO tracks VALUES(4,'Song (feat. Joy Williams and John Paul White)',1)")
    conn.execute("INSERT INTO track_artists VALUES(4,1,'primary'),(4,4,'featured')")
    assert ids(conn, 4) == [1, 4]


def test_old_schema_without_automatic_table_still_reads_primary(conn):
    conn.execute("DROP TABLE spotify_auto_track_credits")
    assert ids(conn) == [1, 4]


def test_plain_affiliation_is_description_without_creating_band_identity(conn):
    conn.execute(
        "UPDATE tracks SET track_name='Song (feat. Joy Williams of Unknown Band)' WHERE track_id=1"
    )
    conn.execute("UPDATE artists SET artist_name='Joy Williams of Unknown Band' WHERE artist_id=4")
    assert ids(conn) == [1, 2, 3]
    conn.execute(
        "UPDATE tracks SET track_name='Song (feat. Joy Williams of Unknown Band and Unlisted)' WHERE track_id=1"
    )
    conn.execute(
        "UPDATE artists SET artist_name='Joy Williams of Unknown Band and Unlisted' WHERE artist_id=4"
    )
    assert ids(conn) == [1, 2, 3, 4]
