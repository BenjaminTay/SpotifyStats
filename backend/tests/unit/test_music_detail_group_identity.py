"""Detail links to any version must select the chart's canonical identity."""

import sqlite3

import pytest

from backend.domains.billboard.detail_summary import _active_document
from backend.domains.playback.track_groups import resolve_track_group_metadata

pytestmark = pytest.mark.unit


@pytest.fixture
def conn():
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.executescript("""
        CREATE TABLE track_groups(group_id INTEGER, parent_group_id INTEGER,
            primary_l1_id INTEGER, canonical_name TEXT, scope TEXT, group_status TEXT);
        CREATE TABLE track_group_l1_members(group_id INTEGER, l1_id INTEGER);
        CREATE TABLE music_search_index_state(active_generation_id INTEGER);
        CREATE TABLE music_search_documents(generation_id INTEGER, kind TEXT,
            merge_level INTEGER, track_id INTEGER, entity_key TEXT);
        INSERT INTO track_groups VALUES
            (10,NULL,1,'Composition','composition','active'),
            (20,10,2,'Recording','recording','active'),
            (30,NULL,8,'Inactive','recording','inactive');
        INSERT INTO track_group_l1_members VALUES (10,1),(10,2),(20,2),(20,3),(30,9);
        INSERT INTO music_search_index_state VALUES(1);
        INSERT INTO music_search_documents VALUES
            (1,'track',2,2,'track:2'),(1,'track',3,1,'track:1');
    """)
    yield database
    database.close()


@pytest.mark.parametrize("level,primary,scope", [(2, 2, "recording"), (3, 1, "composition")])
def test_nonprimary_link_uses_level_specific_document(conn, level, primary, scope):
    group = resolve_track_group_metadata(conn, 3, level)
    assert group["primary_l1_id"] == primary
    assert group["scope"] == scope
    document = _active_document(conn, kind="track", merge_level=level, track_id=3)
    assert document["track_id"] == primary


def test_inactive_and_unknown_members_remain_unresolved(conn):
    assert resolve_track_group_metadata(conn, 9, 3) is None
    assert _active_document(conn, kind="track", merge_level=3, track_id=999) is None


def test_metadata_read_never_accesses_playback_tables(conn):
    statements = []
    conn.set_trace_callback(statements.append)
    resolve_track_group_metadata(conn, 3, 3)
    assert all("plays" not in statement.lower() for statement in statements)
