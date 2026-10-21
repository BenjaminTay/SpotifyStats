"""Project anchors use installed edition evidence, never a namesake's date."""

import sqlite3

import pytest

from backend.services.release_cycle_resolution import resolve_release_targets

pytestmark = pytest.mark.unit


@pytest.fixture
def source():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE artists(artist_id INTEGER,artist_name TEXT,spotify_artist_id TEXT);
        CREATE TABLE albums(album_id INTEGER,album_name TEXT,artist_id INTEGER);
        CREATE TABLE album_projects(project_id INTEGER,canonical_name TEXT,artist_id INTEGER,
          primary_album_id INTEGER,scope TEXT,release_date TEXT,release_date_precision TEXT,is_manual INTEGER);
        CREATE TABLE album_project_albums(project_id INTEGER,album_id INTEGER);
        CREATE TABLE spotify_album_meta(spotify_album_id TEXT,album_name TEXT,release_date TEXT,release_date_precision TEXT);
        CREATE TABLE album_spotify_links(album_id INTEGER,spotify_album_id TEXT,confidence REAL);
        CREATE TABLE spotify_album_credit_sets(spotify_album_id TEXT);
        CREATE TABLE spotify_album_artist_credits(spotify_album_id TEXT,spotify_artist_id TEXT,credited_name TEXT,credit_order INTEGER);
        INSERT INTO artists VALUES(1,'Main','main');
        INSERT INTO albums VALUES(10,'Album',1),(11,'Album Deluxe',1);
        INSERT INTO album_projects VALUES(100,'Album',1,10,'release','2026-01-02',NULL,0),
          (101,'Album',1,10,'composition','2026-01-02',NULL,0);
        INSERT INTO album_project_albums VALUES(100,10),(100,11),(101,10),(101,11);
        INSERT INTO spotify_album_meta VALUES('original','Album','2026-01-02','day'),
          ('deluxe','Album Deluxe','2026-02-06','day');
        INSERT INTO album_spotify_links VALUES(10,'original',1),(10,'deluxe',1),(11,'deluxe',1);
        INSERT INTO spotify_album_artist_credits VALUES('original','main','Main',0),('deluxe','main','Main',0);
    """)
    yield conn
    conn.close()


def resolve(conn, name="Album", level=2):
    return resolve_release_targets(conn, [{"artist_name": "Main", "album_name": name}], level)[0]


def test_primary_anchor_does_not_use_track_container_or_other_edition(source):
    target = resolve(source)
    assert target.reason is None
    assert (target.identity.project_id, target.release_date, target.source_album_id) == (
        100,
        "2026-01-02",
        "original",
    )
    assert resolve(source, level=3).identity.project_id == 101
    edition = resolve(source, "Album Deluxe")
    assert (edition.identity.project_id, edition.release_date, edition.source_album_id) == (
        100,
        "2026-02-06",
        "deluxe",
    )


@pytest.mark.parametrize(
    "raw,precision,reason",
    [
        ("2026-01-02", None, "release_day_unconfirmed"),
        ("2026", "year", "release_date_coarse"),
        ("2026-01", "month", "release_date_coarse"),
        ("2026-02-30", "day", "release_date_invalid"),
        ("2026", "day", "release_date_invalid"),
    ],
)
def test_precision_and_calendar_are_explicit(source, raw, precision, reason):
    source.execute(
        "UPDATE spotify_album_meta SET release_date=?,release_date_precision=? WHERE spotify_album_id='original'",
        (raw, precision),
    )
    assert resolve(source).reason == reason


def test_date_only_maintenance_does_not_bypass_artist_evidence(source):
    source.execute("DELETE FROM spotify_album_artist_credits WHERE spotify_album_id='original'")
    assert resolve(source).reason == "artist_identity_unconfirmed"


def test_conflicting_same_edition_sources_are_not_chosen_by_order(source):
    source.execute("INSERT INTO spotify_album_meta VALUES('regional','Album','2026-01-01','day')")
    source.execute("INSERT INTO album_spotify_links VALUES(10,'regional',1)")
    source.execute("INSERT INTO spotify_album_artist_credits VALUES('regional','main','Main',0)")
    assert resolve(source).reason == "release_date_conflict"


def test_confirmed_or_manual_project_anchor_is_not_silently_changed(source):
    source.execute(
        "UPDATE album_projects SET release_date='2026-01-01',release_date_precision='day'"
    )
    assert resolve(source).reason == "release_date_conflict"
    source.execute("UPDATE album_projects SET release_date_precision=NULL,is_manual=1")
    assert resolve(source).reason == "release_date_conflict"


def test_unknown_entity_is_not_reported_as_a_date_failure(source):
    assert resolve(source, "Unknown").reason == "entity_not_found"


def test_ambiguous_member_alias_is_not_reported_as_missing_entity(source):
    source.execute(
        "INSERT INTO album_projects VALUES(102,'Different Project',1,11,'release',NULL,NULL,0)"
    )
    source.execute("INSERT INTO album_project_albums VALUES(102,11)")
    assert resolve(source, "Album Deluxe").reason == "release_ambiguous"


def test_existing_project_source_proof_supports_ensemble_without_artist_fanout(source):
    source.execute("UPDATE artists SET spotify_artist_id=NULL")
    assert resolve(source).reason == "artist_identity_unconfirmed"
    source.executescript("""
        CREATE TABLE album_project_external_ids(provider TEXT, external_album_id TEXT,
          project_id INTEGER,evidence_type TEXT,confidence REAL,is_primary INTEGER);
        INSERT INTO album_project_external_ids VALUES('spotify','original',100,'soundtrack_catalog',1,1);
    """)
    target = resolve(source)
    assert target.reason is None and target.source_album_id == "original"
    assert source.execute("SELECT spotify_artist_id FROM artists").fetchone()[0] is None
    source.execute("DELETE FROM spotify_album_artist_credits WHERE spotify_album_id='original'")
    assert resolve(source).reason == "artist_identity_unconfirmed"
