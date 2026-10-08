from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from backend.domains.playback.album_project_identity import (
    normalize_album_project_lookup,
    resolve_album_project_identity,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.executescript(
        """
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE albums(
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE album_projects(
            project_id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            artist_id INTEGER,
            primary_album_id INTEGER,
            scope TEXT NOT NULL
        );
        CREATE TABLE album_project_albums(project_id INTEGER, album_id INTEGER);
        INSERT INTO artists VALUES (1, 'Beyoncé'), (2, 'Other Artist');
        INSERT INTO albums VALUES
            (10, 'A/B', 1),
            (11, 'Ａ／Ｂ Deluxe', 1),
            (20, 'A/B', 2);
        INSERT INTO album_projects VALUES
            (100, 'A/B', 1, 10, 'release'),
            (101, 'A/B', 1, 10, 'composition'),
            (200, 'A/B', 2, 20, 'release');
        INSERT INTO album_project_albums VALUES
            (100, 10), (100, 11),
            (101, 10), (101, 11),
            (200, 20);
        """
    )
    try:
        yield database
    finally:
        database.close()


def test_normalization_is_nfkc_casefolded_and_space_stable() -> None:
    assert normalize_album_project_lookup("  Ａ／Ｂ   DELUXE ") == "a/b deluxe"


def test_resolver_accepts_member_alias_and_prefers_level_scope(
    conn: sqlite3.Connection,
) -> None:
    l2 = resolve_album_project_identity(
        conn,
        album_name="ａ／ｂ deluxe",
        artist_name="BEYONCÉ",
        merge_level=2,
    )
    l3 = resolve_album_project_identity(
        conn,
        album_name="Ａ／Ｂ DELUXE",
        artist_name="Beyoncé",
        merge_level=3,
    )

    assert l2 is not None
    assert (l2.project_id, l2.canonical_name, l2.matched_by) == (
        100,
        "A/B",
        "member_album_name",
    )
    assert l2.matched_album_id == 11
    assert l3 is not None and l3.project_id == 101


def test_resolver_fails_closed_for_cross_artist_ambiguity(conn: sqlite3.Connection) -> None:
    assert resolve_album_project_identity(conn, album_name="a/b", merge_level=2) is None


def test_stable_project_id_does_not_depend_on_path_name(conn: sqlite3.Connection) -> None:
    identity = resolve_album_project_identity(conn, project_id=100, merge_level=2)

    assert identity is not None
    assert identity.canonical_name == "A/B"
    assert identity.matched_by == "project_id"
    assert identity.requested_project_id == 100


@pytest.mark.parametrize("level", [2, 3])
def test_batch_shares_rows_and_normalization_with_single_lookup_rules(conn, monkeypatch, level):
    from backend.domains.playback import album_project_identity as identity

    items = [
        dict(album_name="Ａ／Ｂ DELUXE", artist_name="BEYONCÉ"),
        dict(album_name="a/b", artist_name="Other Artist"),
        dict(album_name="a/b", artist_name=""),
        dict(album_name="Missing", artist_name="Beyoncé"),
    ]
    expected = [
        identity.resolve_album_project_identity(conn, **item, merge_level=level) for item in items
    ]
    project_reads, normalized = [], []
    original_rows = identity._project_rows
    original_normalize = identity.normalize_album_project_lookup

    def rows(*args, **kwargs):
        project_reads.append(1)
        return original_rows(*args, **kwargs)

    def normalize(value):
        normalized.append(value)
        return original_normalize(value)

    monkeypatch.setattr(identity, "_project_rows", rows)
    monkeypatch.setattr(identity, "normalize_album_project_lookup", normalize)
    actual = identity.resolve_album_project_identities(conn, items, merge_level=level)
    assert actual == expected
    assert project_reads == [1]
    assert len(normalized) == len(set(normalized))
    assert actual[0].project_id == (100 if level == 2 else 101)
    assert actual[1].project_id == 200
    assert actual[2] is None if level == 2 else actual[2].project_id == 101
    assert actual[3] is None


def test_batch_prefers_canonical_over_member_match_and_preserves_first_member(conn):
    from backend.domains.playback.album_project_identity import resolve_album_project_identities

    conn.execute("INSERT INTO albums VALUES(9,'A/B',1)")
    conn.execute("INSERT INTO album_project_albums VALUES(100,9)")
    canonical, member = resolve_album_project_identities(
        conn,
        [
            dict(album_name="A/B", artist_name="Beyoncé"),
            dict(album_name="Ａ／Ｂ Deluxe", artist_name="Beyoncé"),
        ],
    )
    assert canonical.matched_by == "canonical_name"
    assert canonical.matched_album_id is None
    assert member.matched_album_id == 11
