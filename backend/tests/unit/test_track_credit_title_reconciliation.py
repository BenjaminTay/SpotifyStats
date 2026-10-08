from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from backend.domains.metadata import track_credits as credits
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


# Frozen pre-index suppression is an independent oracle for the returned rows.
def _legacy_suppress_covered_title_products(
    conn: sqlite3.Connection,
    credit_map: dict[tuple[int, int], dict[str, Any]],
    automatic: list[dict[str, Any]],
) -> None:
    """Discard only legacy title products explained by approved track credits.

    A missing Spotify artist is not evidence that a raw collaborator is wrong.
    Require a unique interpretation of the entire original title block, then
    match the historical parser's exact products. Manual decisions run later.
    No source rows or global artist identities are changed.
    """
    if not automatic:
        return
    identity = credits.get_artist_identity_map(conn)
    artists = {
        int(row[0]): str(row[1])
        for row in conn.execute("SELECT artist_id, artist_name FROM artists")
    }

    def canonical(artist_id: int) -> int:
        resolved = identity.get(artist_id)
        return resolved.canonical_artist_id if resolved else artist_id

    by_track: dict[int, list[dict[str, Any]]] = {}
    for credit in automatic:
        by_track.setdefault(int(credit["track_id"]), []).append(credit)
    where, params = credits._where_track_ids(by_track, "t")
    titles = {
        int(row[0]): str(row[1] or "")
        for row in conn.execute(f"SELECT t.track_id, t.track_name FROM tracks t {where}", params)
    }
    raw_by_track: dict[int, list[tuple[int, int]]] = {}
    for key, row in credit_map.items():
        if row["role"] != "primary" and key[0] in by_track:
            raw_by_track.setdefault(key[0], []).append(key)
    # Affiliation text may name a band not credited on this track. Existing
    # primary entities establish its name, never participation or fan-out.
    affiliations = (
        {
            int(row[0])
            for row in conn.execute(
                "SELECT DISTINCT artist_id FROM track_artists WHERE role='primary'"
            )
        }
        if credits._table_exists(conn, "track_artists")
        else set()
    )
    for track_id, raw_keys in raw_by_track.items():
        title = titles.get(track_id, "")
        blocks = credits.extract_title_credit_blocks(title)
        if not blocks:
            continue
        approved = {canonical(int(row["artist_id"])) for row in by_track[track_id]}
        names: dict[str, set[int]] = {}

        def add_name(name: str, artist_id: int) -> None:
            if name:
                names.setdefault(name, set()).add(artist_id)

        for row in by_track[track_id]:
            add_name(str(row["credited_name"] or ""), canonical(int(row["artist_id"])))
        for artist_id, name in artists.items():
            resolved_id = canonical(artist_id)
            if resolved_id in approved:
                add_name(name, resolved_id)
                if artist_id in identity:
                    add_name(identity[artist_id].display_name, resolved_id)
            elif artist_id in affiliations and " of " in title.casefold():
                add_name(name, resolved_id)
        for block in blocks:
            resolved = credits.resolve_block_entities(block, names, supported_artist_ids=approved)
            if not resolved or not set(resolved).issubset(approved):
                continue
            products = {
                credits.normalize_credit_name(name)
                for name in credits.legacy_names_for_block(block, title)
            }
            for key in raw_keys:
                if (
                    canonical(key[1]) not in approved
                    and credits.normalize_credit_name(artists.get(key[1], "")) in products
                ):
                    credit_map.pop(key, None)


@pytest.mark.parametrize(
    "scenario",
    (
        "raw_spotify",
        "manual_add",
        "manual_remove",
        "manual_role",
        "alias",
        "canonical_display",
        "ambiguous_complete",
        "same_name_collision",
        "raw_primary_affiliation",
        "uncredited_alias_affiliation",
        "uncredited_display_affiliation",
        "no_automatic_table",
    ),
)
def test_indexed_credits_equal_complete_legacy_rows(conn, monkeypatch, scenario):
    proposed = None
    if scenario.startswith("manual_"):
        conn.executescript("""
            CREATE TABLE track_credit_overrides(
              override_id INTEGER, track_id INTEGER, artist_id INTEGER, action TEXT,
              role TEXT, evidence_type TEXT, evidence_source TEXT, reason TEXT,
              actor TEXT, revision INTEGER, created_at TEXT, active INTEGER);
            INSERT INTO track_credit_overrides VALUES
              (1,1,4,'add','featured','user_confirmed',NULL,'restore composite',
               'fixture',1,'2026-01-01',1);
        """)
        action = {"manual_add": "add", "manual_remove": "remove", "manual_role": "set_role"}[
            scenario
        ]
        proposed = {"track_id": 1, "artist_id": 2, "action": action, "role": "primary"}
    elif scenario == "alias":
        conn.execute(
            "UPDATE tracks SET track_name='Song (feat. Joy Alias and John Paul White)' WHERE track_id=1"
        )
        conn.execute(
            "UPDATE artists SET artist_name='Joy Alias and John Paul White' WHERE artist_id=4"
        )
        conn.execute("INSERT INTO track_artists VALUES(1,9,'featured')")
    elif scenario == "ambiguous_complete":
        conn.execute(
            "INSERT INTO spotify_auto_track_credits VALUES(1,4,'t1','a4','Joy Williams and John Paul White',3)"
        )
    elif scenario == "canonical_display":
        conn.executescript("""
            CREATE TABLE artist_identity_groups(identity_id INTEGER,
              canonical_artist_id INTEGER,display_artist_id INTEGER,
              display_name TEXT,status TEXT);
            CREATE TABLE artist_identity_members(membership_id INTEGER,
              identity_id INTEGER,artist_id INTEGER,active INTEGER);
            INSERT INTO artist_identity_groups VALUES(1,2,9,'Approved Joy','active');
            INSERT INTO artist_identity_members VALUES(1,1,2,1),(2,1,9,1);
            UPDATE tracks SET track_name='Song (feat. Approved Joy and John Paul White)' WHERE track_id=1;
            UPDATE artists SET artist_name='Approved Joy and John Paul White' WHERE artist_id=4;
        """)
    elif scenario == "same_name_collision":
        conn.execute("UPDATE artists SET artist_name='Joy Williams' WHERE artist_id=3")
        conn.execute(
            "UPDATE spotify_auto_track_credits SET credited_name='Joy Williams' WHERE artist_id=3"
        )
    elif scenario.endswith("affiliation"):
        conn.execute("INSERT INTO tracks VALUES(99,'Band recording',5)")
        conn.execute("INSERT INTO track_artists VALUES(99,5,'primary')")
        band = "Earth, Wind & Fire"
        if scenario == "uncredited_alias_affiliation":
            band = "Alias Band, Inc."
            conn.execute("INSERT INTO artists VALUES(11,?)", (band,))
            conn.execute("INSERT INTO artist_identity_aliases VALUES(11,5)")
        elif scenario == "uncredited_display_affiliation":
            band = "Display Band, Inc."
            conn.executescript("""
                CREATE TABLE artist_identity_groups(identity_id INTEGER,
                  canonical_artist_id INTEGER,display_artist_id INTEGER,
                  display_name TEXT,status TEXT);
                CREATE TABLE artist_identity_members(membership_id INTEGER,
                  identity_id INTEGER,artist_id INTEGER,active INTEGER);
                INSERT INTO artist_identity_groups VALUES(1,5,5,'Display Band, Inc.','active');
                INSERT INTO artist_identity_members VALUES(1,1,5,1);
            """)
        conn.execute(
            "UPDATE tracks SET track_name=? WHERE track_id=1",
            (f"Song (feat. Joy Williams of {band} and John Paul White)",),
        )
        conn.execute(
            "UPDATE artists SET artist_name=? WHERE artist_id=4",
            (f"Joy Williams of {band.split(',')[0]}",),
        )
    elif scenario == "no_automatic_table":
        conn.execute("DROP TABLE spotify_auto_track_credits")

    protected_tables = ("artists", "tracks", "track_artists")
    before = {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
        for table in protected_tables
    }
    actual = get_effective_track_credits(conn, proposed=proposed)
    with monkeypatch.context() as patch:
        patch.setattr(
            credits,
            "_suppress_covered_title_products",
            lambda database, raw, automatic, **kwargs: _legacy_suppress_covered_title_products(
                database, raw, automatic
            ),
        )
        expected = get_effective_track_credits(conn, proposed=proposed)
    assert actual == expected
    after = {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
        for table in protected_tables
    }
    assert before == after
    if scenario == "raw_primary_affiliation":
        assert [row["artist_id"] for row in actual if row["track_id"] == 1] == [1, 2, 3]
    elif scenario in ("uncredited_alias_affiliation", "uncredited_display_affiliation"):
        assert 4 in [row["artist_id"] for row in actual if row["track_id"] == 1]


@pytest.mark.parametrize("automatic", (True, False))
def test_effective_call_shares_one_identity_mapping_and_raw_name_read(conn, monkeypatch, automatic):
    if not automatic:
        conn.execute("DROP TABLE spotify_auto_track_credits")
    original = credits.get_artist_identity_map
    calls = []

    def identity(database):
        calls.append(database)
        return original(database)

    monkeypatch.setattr(credits, "get_artist_identity_map", identity)
    statements = []
    conn.set_trace_callback(statements.append)
    try:
        assert get_effective_track_credits(conn)
    finally:
        conn.set_trace_callback(None)
    assert calls == [conn]
    # One read inside the identity resolver and one raw-name read for this call.
    assert statements.count("SELECT artist_id, artist_name FROM artists") == 2


def test_title_index_scans_artists_once_for_many_automatic_tracks(conn):
    for track_id in range(20, 40):
        conn.execute(
            "INSERT INTO tracks VALUES(?,'Song (feat. Joy Williams and John Paul White)',1)",
            (track_id,),
        )
        conn.executemany("INSERT INTO track_artists VALUES(?,?,'featured')", ((track_id, 4),))
        conn.executemany(
            "INSERT INTO spotify_auto_track_credits VALUES(?,?,'t','a',?,?)",
            ((track_id, 2, "Joy Williams", 1), (track_id, 3, "John Paul White", 2)),
        )
    identity = credits.get_artist_identity_map(conn)

    class CountedArtists(dict):
        scans = 0

        def items(self):
            self.scans += 1
            return super().items()

    artists = CountedArtists(
        (int(row[0]), str(row[1]))
        for row in conn.execute("SELECT artist_id,artist_name FROM artists")
    )
    raw = credits._raw_credit_map(conn)
    credits._suppress_covered_title_products(
        conn, raw, credits._automatic_spotify_credits(conn), identity=identity, artists=artists
    )
    assert artists.scans == 1
    assert all((track_id, 4) not in raw for track_id in range(20, 40))


def test_private_raw_map_retains_default_identity_adapter(conn):
    assert credits._effective_raw_map(conn, [1]) == credits._effective_raw_map(
        conn,
        [1],
        identity=credits.get_artist_identity_map(conn),
        artists={
            int(row[0]): str(row[1])
            for row in conn.execute("SELECT artist_id,artist_name FROM artists")
        },
    )
