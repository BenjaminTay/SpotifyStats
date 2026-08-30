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
